"""Compare released 0.2 and 0.3 on the same bytes and check each restoration."""
import argparse
import json
import platform
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "step_v2_study"))
from replay import PINS, cli, digest, fetch, materialize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=["transfer", "prior", "all"], default="transfer")
    parser.add_argument("--input-dir", type=Path, help="use already downloaded files by pinned name")
    parser.add_argument("--v2", type=Path, help="use a local copy of the published 0.2 program")
    parser.add_argument("--v3", type=Path, default=HERE.parent / "cn-preview.pyz")
    parser.add_argument("--with-brotli", action="store_true", help="also compare optional modes")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("choose a fresh output file")
    if args.with_brotli and not shutil.which("brotli"):
        parser.error("install the Brotli command-line tool first")
    spec = json.loads((HERE / "manifest.json").read_text())
    reader_digest = digest(args.v3.read_bytes())
    if reader_digest != spec["v3_sha256"]:
        parser.error("the 0.3 program differs from the pinned release")
    files = []
    if args.group in ("prior", "all"):
        files.extend(PINS["files"])
    if args.group in ("transfer", "all"):
        files.extend(spec["files"])
    result = {"python": platform.python_version(), "platform": platform.system() + "-" + platform.machine(),
              "v3_sha256": reader_digest, "v2_sha256": spec["v2"]["sha256"], "files": []}
    with tempfile.TemporaryDirectory() as folder:
        local = Path(folder)
        older = args.v2 or HERE.parent / "cn-preview-v2.pyz"
        if not args.v2 and not older.exists():
            older = local / "v2.pyz"
            older.write_bytes(fetch(spec["v2"]))
        if digest(older.read_bytes()) != spec["v2"]["sha256"]:
            raise ValueError("The 0.2 program differs from the pinned release")
        directory = args.input_dir or local
        if not args.input_dir:
            materialize(directory, files)
        for row in files:
            path = directory / row["file"]
            raw = path.read_bytes()
            if len(raw) != row["input_bytes"] or digest(raw) != row["sha256"]:
                raise ValueError("Input differs from pinned source: " + path.name)
            entry = {key: row[key] for key in ("file", "group", "input_bytes", "sha256")}
            for profile, flags in [("portable", [])] + ([("optional", ["--with-brotli"])] if args.with_brotli else []):
                old = cli(older, path, flags)
                new = cli(args.v3, path, flags)
                earlier, current = old["candidate_bytes"], new["candidate_bytes"]
                if flags and "SXD2-split-brotli" not in earlier:
                    raise ValueError("The 0.2 Brotli profile did not run: " + path.name)
                if not all(current.get(key) == size for key, size in earlier.items()):
                    raise ValueError("Historical candidate sizes changed: " + path.name)
                added = {"SXD3-dictionary-xz"}
                if flags:
                    added.update({"SXD3-dual-floats-brotli", "SXD3-dictionary-brotli"})
                if not added.issubset(current):
                    raise ValueError("An expected STEP profile did not run: " + path.name)
                if new["bytes"] > old["bytes"] or new["bytes"] != min(new["candidate_bytes"].values()):
                    raise ValueError("Size selection failed: " + path.name)
                entry[profile] = {"v2": old, "v3": new, "saved_bytes": old["bytes"] - new["bytes"]}
            result["files"].append(entry)
            print(path.name, flush=True)
    with args.out.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
