"""Second, post-hoc direct-file control for the six held-out station-days."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
ADD = {
    "xz-9e": ["xz", "--threads=1", "-9e", "-c"],
    "zstd-22": ["zstd", "--ultra", "--single-thread", "-22", "-q", "-c"],
}


def run(command, data):
    return subprocess.run(command, input=data, stdout=subprocess.PIPE, check=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("--output", type=Path, default=Path("local-sensitivity.json"))
    args = parser.parse_args()
    sweep = json.loads((ROOT / "results.json").read_text())["files"]
    profile = {r["file"]: r for r in json.loads((ROOT / "profile-results.json").read_text())["files"]}
    rows = []
    for prior in sweep:
        if prior["split"] != "holdout":
            continue
        filename = prior["file"]
        data = (args.cache / filename).read_bytes()
        if hashlib.sha256(data).hexdigest() != prior["sha256"]:
            raise ValueError(f"source mismatch for {filename}")
        sizes = {m: v["stock"] for m, v in prior["sizes"].items()}
        old = min(sizes.values())
        for mode, command in ADD.items():
            encoded = run(command, data)
            if run([command[0], "-d", "-c"], encoded) != data:
                raise ValueError(f"round-trip mismatch for {filename} using {mode}")
            sizes[mode] = len(encoded)
        best = min(sizes, key=sizes.get)
        rows.append({"file": filename, "sha256": prior["sha256"], "original_best": old,
                     "new_controls": {k: sizes[k] for k in ADD},
                     "eight_arm_best_method": best, "eight_arm_best_bytes": sizes[best],
                     "srt2_brotli": profile[filename]["brotli"]["frame_bytes"]})
    totals = {k: sum(r[k] for r in rows) for k in ("original_best", "eight_arm_best_bytes", "srt2_brotli")}
    controls = {k: sum(r["new_controls"][k] for r in rows) for k in ADD}
    result = {"kind": "post-hoc direct-file sensitivity", "versions": {
        k: run([cmd[0], "--version"], b"").decode().strip() for k, cmd in ADD.items()},
        "files": rows, "totals": totals, "extra_setting_totals": controls,
        "srt2_fraction_below_eight_arm_best": 1 - totals["srt2_brotli"] / totals["eight_arm_best_bytes"]}
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
