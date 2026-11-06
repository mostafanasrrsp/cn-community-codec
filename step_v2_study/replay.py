"""Replay the two released encoder configurations, v1 and eight conventional controls."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from controls import methods

HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fetch(record):
    request = urllib.request.Request(record["url"], headers={"User-Agent": "CN-STEP-replay/0.2"})
    with urllib.request.urlopen(request, timeout=180) as response:
        data = response.read()
    if digest(data) != record["sha256"]:
        raise ValueError("Upstream hash differs for " + record["url"])
    return data


def materialize(directory, selected):
    selected_by_archive = {}
    for row in selected:
        if "archive" in row:
            selected_by_archive.setdefault(row["archive"], []).append(row)
        else:
            (directory / row["file"]).write_bytes(fetch(row))
    for key, members in selected_by_archive.items():
        with zipfile.ZipFile(io.BytesIO(fetch(PINS["archives"][key]))) as archive:
            for row in members:
                (directory / row["file"]).write_bytes(archive.read(row["member"]))


def cli(app, raw_path, flags):
    with tempfile.TemporaryDirectory() as directory:
        wire = Path(directory) / "trial.cn"
        output = Path(directory) / "restored.step"
        command = [sys.executable, "-I", str(app)]
        meta = json.loads(subprocess.check_output([*command, "pack", str(raw_path), str(wire), *flags]))
        metadata = json.loads(subprocess.check_output([*command, "inspect", str(wire)]))
        subprocess.check_output([*command, "unpack", str(wire), str(output)])
        if output.read_bytes() != raw_path.read_bytes() or meta["sha256"] != metadata["sha256"]:
            raise ValueError("Restored bytes differ: " + raw_path.name)
        return dict(bytes=wire.stat().st_size, format=meta["format"], method=meta["method"],
                    wire_sha256=digest(wire.read_bytes()), exact=True, candidate_bytes=meta["candidate_bytes"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, help="use already-downloaded files by their pinned names")
    parser.add_argument("--v1", type=Path, help="path to the pinned published v1 reader")
    parser.add_argument("--v2", type=Path, help="path to the pinned published v2 reader")
    parser.add_argument("--group", choices=("F1", "AP242", "fresh"), help="replay only this cohort")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("choose a fresh output path")
    if not shutil.which("brotli") or not shutil.which("zstd"):
        parser.error("install the Brotli and Zstandard command-line tools for the full comparison")
    selected = [r for r in PINS["files"] if args.group in (None, r["group"])]
    result = {"python": platform.python_version(), "platform": platform.platform(),
              "v2_sha256": PINS["v2"]["sha256"], "files": []}
    with tempfile.TemporaryDirectory() as folder:
        directory = args.input_dir or Path(folder)
        if not args.input_dir:
            materialize(directory, selected)
        v2 = args.v2
        if v2 is None:
            for candidate in (HERE.parent / "cn-preview-v2.pyz", HERE.parent / "cn-preview.pyz"):
                if candidate.is_file() and digest(candidate.read_bytes()) == PINS["v2"]["sha256"]:
                    v2 = candidate
                    break
            else:
                v2 = Path(folder) / "v2.pyz"
                v2.write_bytes(fetch(PINS["v2"]))
        if digest(v2.read_bytes()) != PINS["v2"]["sha256"]:
            raise ValueError("v2 program differs from published reference")
        v1 = args.v1 or HERE.parent / "cn-preview-v1.pyz"
        if not args.v1 and not v1.exists():
            v1 = Path(folder) / "v1.pyz"
            v1.write_bytes(fetch(PINS["v1"]))
        if digest(v1.read_bytes()) != PINS["v1"]["sha256"]:
            raise ValueError("v1 program differs from published reference")
        for row in selected:
            path = directory / row["file"]
            data = path.read_bytes()
            if digest(data) != row["sha256"] or len(data) != row["input_bytes"]:
                raise ValueError("Changed fixture: " + row["file"])
            print(row["file"], flush=True)
            entry = {k: row[k] for k in ("file", "group", "input_bytes", "sha256")}
            controls = {}
            for name, (encode, decode) in methods(path.name).items():
                frame = encode(data)
                if decode(frame) != data:
                    raise ValueError("Control failed: " + name)
                controls[name] = len(frame)
            entry.update(controls=controls, v1=cli(v1, path, []), default=cli(v2, path, []),
                         compact=cli(v2, path, ["--with-brotli"]))
            result["files"].append(entry)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
