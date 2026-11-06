"""Verify the SRT2 profile against the pinned public corpus and malformed-input controls."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path

from solar_codec import CAP, HEADER, decode, encode


def must_reject(fn, *args):
    try:
        fn(*args)
    except (ValueError, lzma.LZMAError):
        return
    raise AssertionError("malformed input unexpectedly accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path, help="cache made by replay.py")
    parser.add_argument("--output", type=Path, default=Path("profile-replay.json"))
    args = parser.parse_args()
    prior = json.loads((Path(__file__).resolve().parent / "results.json").read_text())
    sizes = []
    for item in prior["files"]:
        raw = (args.cache / item["file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item["sha256"]
        case = {"file": item["file"], "split": item["split"], "source_bytes": len(raw),
                "strongest_stock": min(v["stock"] for v in item["sizes"].values())}
        for method in ["brotli", "xz"]:
            frame = encode(raw, method)
            restored = decode(frame)
            assert restored == raw
            assert len(frame) == item["sizes"]["brotli-11" if method == "brotli" else "xz-6"]["transposed"] + 32
            case[method] = {"frame_bytes": len(frame), "frame_sha256": hashlib.sha256(frame).hexdigest()}
            bad_header = bytearray(frame)
            bad_header[13] ^= 1
            must_reject(decode, bad_header)
            must_reject(decode, frame[:-1])
            must_reject(decode, frame + b'junk')
        sizes.append(case)
    for method in ["brotli", "xz"]:
        for test in [b"h1\r\nh2\r\n12\r\n34\r\n", b"\0\n\n\0\xff\n", b"a\nb\nx"]:
            assert decode(encode(test, method)) == test
        must_reject(encode, b"h\nh\n1\n22\n", method)
    must_reject(decode, b"x")
    must_reject(decode, HEADER.pack(b"SRT2", 6, 1, 1, CAP, bytes(32)))
    must_reject(decode, HEADER.pack(b"SRT2", 9, 1, 1, 1, bytes(32)))
    must_reject(decode, HEADER.pack(b"XXXX", 6, 1, 1, 1, bytes(32)))
    args.output.write_text(json.dumps({"srt2_header_bytes": HEADER.size, "files": sizes,
                                      "malformed_input_checks": "passed"}, indent=2) + "\n")


if __name__ == "__main__":
    main()
