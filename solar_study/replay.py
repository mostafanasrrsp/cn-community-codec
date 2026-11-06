"""Download and replay the immutable-by-hash SURFRAD study. Python 3.9+, Brotli, zstd."""
import argparse
import bz2
import gzip
import hashlib
import json
import lzma
import platform
import struct
import subprocess
import tempfile
import urllib.request
import zlib
from pathlib import Path

HEADER = struct.Struct(">4sBHHI")
TRIALS = ["bon20115"] + [f"{site}20{day}" for site in ("fpk", "dra") for day in ("032", "183", "310")]
MODES = ["gzip-6", "bzip2-9", "xz-6", "zstd-3", "zstd-19", "brotli-11"]
HERE = Path(__file__).resolve().parent


def run(command, data):
    return subprocess.run(command, input=data, stdout=subprocess.PIPE, check=True).stdout


def compress(data, mode):
    if mode == "gzip-6":
        return gzip.compress(data, compresslevel=6, mtime=0)
    if mode == "bzip2-9":
        return bz2.compress(data, compresslevel=9)
    if mode == "xz-6":
        return lzma.compress(data, preset=6)
    if mode == "brotli-11":
        return run(["brotli", "-q", "11", "-c"], data)
    return run(["zstd", "-q", "--single-thread", "-c", "-" + mode.split("-")[1]], data)


def decompress(data, mode):
    if mode == "gzip-6":
        return gzip.decompress(data)
    if mode == "bzip2-9":
        return bz2.decompress(data)
    if mode == "xz-6":
        return lzma.decompress(data)
    if mode == "brotli-11":
        return run(["brotli", "-d", "-c"], data)
    return run(["zstd", "-q", "-dc"], data)


def layout(data):
    rows = data.splitlines(keepends=True)
    prefix = b"".join(rows[:2])
    rows = rows[2:]
    if not rows or len(prefix) > 65535:
        return None
    width = len(rows[0])
    if width > 65535 or not width or len(rows) >= 2**32 or any(len(r) != width for r in rows):
        return None
    body = data[len(prefix):]
    return prefix + b"".join(body[i::width] for i in range(width)), len(prefix), width, len(rows)


def restore(frame):
    magic, mode_id, prefix_size, width, height = HEADER.unpack_from(frame)
    assert magic == b"SRT1" and 0 < mode_id <= len(MODES)
    decoded = decompress(frame[HEADER.size:], MODES[mode_id - 1])
    assert len(decoded) == prefix_size + width * height
    body = decoded[prefix_size:]
    original = bytearray(len(body))
    for i in range(width):
        original[i::width] = body[i * height:(i + 1) * height]
    return decoded[:prefix_size] + original


def check_file(key, directory, expected_digest):
    filename = key + ".dat"
    url = f"https://gml.noaa.gov/aftp/data/radiation/surfrad/{key[:3]}/2020/{filename}"
    path = directory / filename
    if not path.is_file():
        with urllib.request.urlopen(url, timeout=40) as response:
            data = response.read()
        path.write_bytes(data)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_digest and digest != expected_digest:
        raise ValueError(f"Source content changed for {filename}")
    transform = layout(data)
    sizes = {}
    for i, mode in enumerate(MODES, 1):
        stock = compress(data, mode)
        if decompress(stock, mode) != data:
            raise ValueError(f"Stock {mode} failed for {filename}")
        if transform is None:
            sizes[mode] = {"stock": len(stock), "transposed": None}
            continue
        payload, prefix_size, width, height = transform
        frame = HEADER.pack(b"SRT1", i, prefix_size, width, height) + compress(payload, mode)
        restored = restore(frame)
        if restored != data or hashlib.sha256(restored).hexdigest() != digest:
            raise ValueError(f"SRT1 {mode} failed for {filename}")
        sizes[mode] = {"stock": len(stock), "transposed": len(frame)}
    return {"file": filename, "split": "development" if key.startswith("bon") else "holdout",
            "url": url, "sha256": digest, "source": len(data), "row_shape": transform[1:] if transform else None,
            "sizes": sizes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path, default=Path("solar-replay-results.json"))
    args = parser.parse_args()
    expected = {}
    reference = HERE / "results.json"
    if reference.is_file():
        expected = {r["file"]: r["sha256"] for r in json.loads(reference.read_text())["files"]}
    with tempfile.TemporaryDirectory() as tmp:
        directory = args.cache or Path(tmp)
        directory.mkdir(parents=True, exist_ok=True)
        files = [check_file(k, directory, expected.get(k + ".dat")) for k in TRIALS]
    environment = {"platform": platform.platform(), "machine": platform.machine(),
                   "python": platform.python_version(), "zlib": zlib.ZLIB_RUNTIME_VERSION,
                   "zstd": run(["zstd", "--version"], b"").decode().strip(),
                   "brotli": run(["brotli", "--version"], b"").decode().strip()}
    result = {"environment": environment, "transform_frame_header_bytes": HEADER.size, "files": files}
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
