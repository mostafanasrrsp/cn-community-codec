"""Run the packaged default and optional profiles on the source-hash-pinned lab corpora."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
APP = HERE / "cn-preview.pyz"
if not APP.exists():
    APP = LAB / "cn-preview.pyz"
sys.path.insert(0, str(LAB / "file_study"))
from benchmark_files import SOURCES


def fetch(location, expected, local):
    if isinstance(location, Path):
        data = location.read_bytes()
    else:
        with urllib.request.urlopen(location, timeout=45) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("source differs from hash in experiment manifest")
    local.write_bytes(data)


def qualify(ident, source, frame, restored, method, digest):
    command = [sys.executable, "-I", str(APP)]
    options = ["--with-brotli"] if method == "optional-brotli" else []
    result = json.loads(subprocess.check_output(command + ["pack", str(source), str(frame), "--force"] + options))
    subprocess.run(command + ["unpack", str(frame), str(restored), "--force"], check=True,
                   stdout=subprocess.DEVNULL)
    if hashlib.sha256(restored.read_bytes()).hexdigest() != digest or result["sha256"] != digest:
        raise ValueError("failed disk-to-disk integrity for " + ident)
    result["id"] = ident
    result["configuration"] = method
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solar-cache", type=Path, help="folder of NOAA files matching recorded hashes")
    parser.add_argument("--public-only", action="store_true", help="skip the private mixed-corpus files")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mixed_path = LAB / "file_study" / "file-results.json"
    if mixed_path.is_file():
        mixed = json.loads(mixed_path.read_text())
        original = {s["id"]: s for s in mixed["sources"]}
        controls = {
            ident: min(s["wire_bytes"] for s in mixed["observations"]
                       if s["id"] == ident and s["method"] != "cn")
            for ident in original
        }
    else:
        # The public kit includes only sanitized per-file measurements.
        reference = json.loads((HERE / "preview-results.json").read_text())
        original = {s["id"]: s for s in reference["rows"] if s["cohort"] == "mixed"}
        controls = {ident: s["smallest_measured_stock_frame"] for ident, s in original.items()}

    solar = json.loads((LAB / "solar_study" / "results.json").read_text())
    rows = []
    with tempfile.TemporaryDirectory() as temp:
        source, frame, restored = (Path(temp) / name for name in ("source", "wire", "restored"))
        for ident, category, where in SOURCES:
            if args.public_only and isinstance(where, Path):
                continue
            digest = original[ident]["sha256"]
            fetch(where, digest, source)
            row = qualify(ident, source, frame, restored, "portable", digest)
            row.update(category=category, cohort="mixed", smallest_measured_stock_frame=controls[ident])
            rows.append(row)
            print(ident, row["format"], row["wire_bytes"], flush=True)
        for item in solar["files"]:
            if item["split"] == "development":
                continue
            ident = item["file"]
            path = args.solar_cache / ident if args.solar_cache else None
            fetch(path if path and path.exists() else item["url"], item["sha256"], source)
            configs = ["portable", "optional-brotli"] if shutil.which("brotli") else ["portable"]
            for config in configs:
                row = qualify(ident, source, frame, restored, config, item["sha256"])
                row.update(cohort="solar-heldout", smallest_measured_stock_frame=min(
                    s["stock"] for s in item["sizes"].values()))
                rows.append(row)
                print(ident, config, row["format"], row["wire_bytes"], flush=True)
    args.output.write_text(json.dumps(dict(artifact_sha256=hashlib.sha256(APP.read_bytes()).hexdigest(),
                                           rows=rows), indent=2) + "\n")


if __name__ == "__main__":
    main()
