"""Pack one local file or build a certified aperture sidecar."""
import argparse
import hashlib
import json
import lzma
import re
import shutil
import sys
from pathlib import Path

from cncodec import transport
from cncodec.__main__ import main as geometry_cli, read_limited, write_output
import solar_codec
import step_delta

VERSION = "0.1.0"
GEOMETRY = ("geometry-pack", "geometry-verify", "geometry-query")
STATIONS = {b"Bondville", b"Fort Peck", b"Desert Rock"}
LOCATION = re.compile(rb"[ \t]*[+-]?\d{1,2}\.\d+[ \t]+[+-]?\d{1,3}\.\d+[ \t]+-?\d+[ \t]+m[ \t]+version 1[ \t]*")
NUMBER = rb"[+-]?\d+(?:\.\d+)?"
# Date/time integers, decimal hour, zenith, then 20 value/quality pairs.
OBSERVATION = re.compile(rb"[ \t]*\d{4}(?:[ \t]+\d{1,3}){5}(?:[ \t]+" + NUMBER
                         + rb"){2}(?:[ \t]+" + NUMBER + rb"[ \t]+\d){20}[ \t]*")


def is_solar(raw):
    if len(raw) > solar_codec.CAP:
        return False
    first, _, rest = raw[:512].partition(b"\n")
    location, sep, _ = rest.partition(b"\n")
    if first.strip() not in STATIONS or not sep or not LOCATION.fullmatch(location.rstrip(b"\r")):
        return False
    lines = raw.splitlines(keepends=True)[2:]
    if not lines:
        return False
    eol = b"\r\n" if lines[0].endswith(b"\r\n") else b"\n"
    return all(len(row) == 239 + len(eol) and row.endswith(eol)
               and OBSERVATION.fullmatch(row[:-len(eol)]) for row in lines)


def restore(frame):
    tag = frame[:4]
    if tag == b"CNF1":
        return transport.unpack_bytes(frame)
    if tag == b"SXD1":
        return step_delta.unpack(frame)
    if tag == solar_codec.MAGIC:
        return solar_codec.decode(frame)
    if tag == b"GX01":
        raise ValueError("this is an aperture sidecar; use geometry-verify or geometry-query")
    raise ValueError("unrecognized file signature")


def describe(frame, original):
    tag = frame[:4]
    if tag == b"CNF1":
        method = transport.metadata(frame)["method"]
    elif tag == b"SXD1":
        method = "step-delta+xz6"
    else:
        method_id = solar_codec.HEADER.unpack_from(frame)[1]
        method = next(k for k, v in solar_codec.METHODS.items() if v == method_id)
    return dict(format=tag.decode("ascii"), method=method, original_bytes=len(original),
                wire_bytes=len(frame), sha256=hashlib.sha256(original).hexdigest(), verified=True)


def select(raw, with_brotli):
    best = transport.pack_bytes(raw)
    sizes = {"CNF1": len(best)}
    notes = []
    def consider(key, candidate):
        nonlocal best
        sizes[key] = len(candidate)
        if len(candidate) < len(best):
            if restore(candidate) != raw:
                raise ValueError(f"{key} failed trial reconstruction")
            best = candidate

    if len(raw) <= step_delta.LIMIT and raw.lstrip().startswith(b"ISO-10303-21;"):
        if b"\x1e" not in raw and b"\x1f" not in raw:
            consider("SXD1", step_delta.pack(raw))
    elif is_solar(raw):
        consider("SRT2-xz", solar_codec.encode(raw, "xz"))
        if with_brotli:
            if shutil.which("brotli"):
                try:
                    candidate = solar_codec.encode(raw, "brotli")
                    consider("SRT2-brotli", candidate)
                except (ValueError, OSError) as exc:
                    notes.append(f"Skipped optional Brotli trial: {exc}")
            else:
                notes.append("Brotli CLI unavailable; compared portable profiles.")
    if restore(best) != raw:
        raise ValueError("selected frame failed source verification")
    return best, sizes, notes


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in GEOMETRY:
        return geometry_cli(argv)
    parser = argparse.ArgumentParser(prog="cn-preview", description=__doc__,
            epilog="Aperture sidecars: geometry-pack INPUT.csv OUT.gx01; geometry-verify INPUT.csv OUT.gx01; geometry-query OUT.gx01 INDEX PX PY.")
    parser.add_argument("--version", action="version", version=VERSION)
    cmds = parser.add_subparsers(dest="command", required=True)
    pack = cmds.add_parser("pack", help="try eligible lossless profiles, keep the smallest verified file")
    unpack = cmds.add_parser("unpack", help="restore a lossless file after checking its digest")
    inspect = cmds.add_parser("inspect", help="identify a lossless file and verify its original content digest")
    for sub in (pack, unpack, inspect):
        sub.add_argument("input", type=Path)
    for sub in (pack, unpack):
        sub.add_argument("output", type=Path)
        sub.add_argument("--force", action="store_true", help="replace an existing output after verification")
    pack.add_argument("--with-brotli", action="store_true",
                      help="include the optional Brotli solar profile; readers need the Brotli CLI for that profile")
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            original = read_limited(args.input, transport.LIMIT)
            frame, sizes, notes = select(original, args.with_brotli)
            result = describe(frame, original)
            result["candidate_bytes"] = sizes
            if notes:
                result["notes"] = notes
            write_output(args.output, frame, source=args.input, force=args.force)
        else:
            frame = read_limited(args.input, transport.LIMIT + transport.HEADER.size)
            original = restore(frame)
            result = describe(frame, original)
            if args.command == "unpack":
                write_output(args.output, original, source=args.input, force=args.force)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, OverflowError, lzma.LZMAError) as exc:
        print(f"cn-preview: {exc}", file=sys.stderr)
        return 1
