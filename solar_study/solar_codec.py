#!/usr/bin/env python3
"""Exact fixed-row trace profile. Python 3.9+. Optional Brotli command-line tool."""
import argparse
import hashlib
import lzma
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

HEADER = struct.Struct(">4sBHHI32s")
MAGIC = b"SRT2"
CAP = 8 << 20
# Some lossless compressors add framing or overhead to incompressible bytes.
FRAME_CAP = CAP + (1 << 20)
METHODS = {"xz": 3, "brotli": 6}


def limited_read(path, limit):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("file exceeds the experimental size limit")
    return data


def brotli(data, encode, limit):
    exe = shutil.which("brotli")
    if exe is None:
        raise ValueError("this method requires the Brotli CLI")
    flags = ["-q", "11", "-c"] if encode else ["-d", "-c"]
    # A file for stdin avoids deadlock if the child starts emitting output early.
    with tempfile.TemporaryFile() as stdin:
        stdin.write(data)
        stdin.seek(0)
        with subprocess.Popen([exe, *flags], stdin=stdin, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL) as proc:
            try:
                result = proc.stdout.read(limit + 1)
                if len(result) > limit:
                    raise ValueError("Brotli output exceeds the declared length")
                if proc.wait() != 0:
                    raise ValueError("invalid Brotli stream or compressor failure")
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.stdout.close()
    return result


def encode(original, method):
    if len(original) > CAP:
        raise ValueError("source exceeds 8 MiB")
    # The protocol preserves both prefix lines and the exact terminators.
    lines = original.splitlines(keepends=True)
    if len(lines) < 3:
        raise ValueError("expected two header lines and fixed-width records")
    prefix = b"".join(lines[:2])
    rows = lines[2:]
    width, height = len(rows[0]), len(rows)
    if len(prefix) > 65535 or not 0 < width <= 65535 or any(len(r) != width for r in rows):
        raise ValueError("unsupported fixed-row layout; use the general exact-file codec")
    body = original[len(prefix):]
    transposed = prefix + b"".join(body[i::width] for i in range(width))
    if method == "xz":
        compressed = lzma.compress(transposed, preset=6)
    else:
        compressed = brotli(transposed, True, FRAME_CAP - HEADER.size)
    header = HEADER.pack(MAGIC, METHODS[method], len(prefix), width, height,
                         hashlib.sha256(original).digest())
    return header + compressed


def decode(frame):
    if not HEADER.size <= len(frame) <= FRAME_CAP:
        raise ValueError("invalid frame length")
    magic, mode, prefix, width, height, digest = HEADER.unpack_from(frame)
    size = prefix + width * height
    if magic != MAGIC or mode not in METHODS.values() or not width or not height or size > CAP:
        raise ValueError("unsupported or oversized trace header")
    compressed = frame[HEADER.size:]
    if mode == METHODS["xz"]:
        inflater = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=96 << 20)
        content = inflater.decompress(compressed, max_length=size + 1)
        if not inflater.eof or inflater.unused_data:
            raise ValueError("truncated, oversize or trailing XZ data")
    else:
        content = brotli(compressed, False, size)
    if len(content) != size:
        raise ValueError("decoded length differs from the header")
    body = content[prefix:]
    original_rows = bytearray(len(body))
    for i in range(width):
        original_rows[i::width] = body[i * height:(i + 1) * height]
    original = content[:prefix] + original_rows
    if hashlib.sha256(original).digest() != digest:
        raise ValueError("restored source digest differs")
    return original


def install_new(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(tmp, path)   # Atomic publication with no overwrite.
        finally:
            tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    enc = commands.add_parser("encode")
    enc.add_argument("source", type=Path)
    enc.add_argument("destination", type=Path)
    enc.add_argument("--method", choices=METHODS, default="brotli")
    dec = commands.add_parser("decode")
    dec.add_argument("source", type=Path)
    dec.add_argument("destination", type=Path)
    chk = commands.add_parser("test")
    chk.add_argument("source", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "encode":
            original = limited_read(args.source, CAP)
            frame = encode(original, args.method)
            # Refuse to output a frame that does not decode to the complete source.
            if decode(frame) != original:
                raise ValueError("round-trip failure")
            install_new(args.destination, frame)
            print(f"{len(original)} source bytes -> {len(frame)} complete frame bytes")
        else:
            original = decode(limited_read(args.source, FRAME_CAP))
            if args.action == "decode":
                install_new(args.destination, original)
            print(f"verified {len(original)} source bytes; SHA-256 {hashlib.sha256(original).hexdigest()}")
    except (OSError, ValueError, lzma.LZMAError) as exc:
        print(f"solar trace: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
