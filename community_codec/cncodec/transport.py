"""Single-file, lossless transport with a bounded, verifying decoder."""
import bz2
import hashlib
import lzma
import struct
import zlib

HEADER = struct.Struct("<4sBQ32s")
LIMIT = 64 * 1024 * 1024
NAMES = ("store", "zlib", "bzip2", "xz")


def pack_bytes(data):
    if len(data) > LIMIT:
        raise ValueError("input exceeds the 64 MiB per-file limit")
    best = data
    selected = 0
    for mode, compress in enumerate((zlib.compress, bz2.compress,
                                      lambda raw: lzma.compress(raw, preset=3)), 1):
        candidate = compress(data)
        if len(candidate) < len(best):
            selected, best = mode, candidate
    return HEADER.pack(b"CNF1", selected, len(data), hashlib.sha256(data).digest()) + best


def metadata(wire):
    if not HEADER.size <= len(wire) <= HEADER.size + LIMIT:
        raise ValueError("invalid transport size")
    magic, mode, size, digest = HEADER.unpack_from(wire)
    if magic != b"CNF1" or mode >= len(NAMES):
        raise ValueError("unknown file format or codec")
    payload_size = len(wire) - HEADER.size
    if size > LIMIT or payload_size > size or (mode == 0 and payload_size != size):
        raise ValueError("invalid transport size declaration")
    return dict(format="CNF1", method=NAMES[mode], original_bytes=size,
                wire_bytes=len(wire), header_bytes=HEADER.size, sha256=digest.hex())


def unpack_bytes(wire):
    info = metadata(wire)
    payload = memoryview(wire)[HEADER.size:]
    size = info["original_bytes"]
    method = info["method"]
    if method == "store":
        raw = bytes(payload)
    else:
        if method == "zlib":
            decoder = zlib.decompressobj()
        elif method == "bzip2":
            decoder = bz2.BZ2Decompressor()
        else:
            decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=64 << 20)
        try:
            raw = decoder.decompress(payload, size + 1)
        except (OSError, EOFError, lzma.LZMAError, zlib.error) as exc:
            raise ValueError("invalid compressed payload") from exc
        if not decoder.eof or decoder.unused_data:
            raise ValueError("truncated, oversized, concatenated or trailing payload")
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != info["sha256"]:
        raise ValueError("decoded length or SHA-256 mismatch")
    return raw
