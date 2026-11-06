"""Command line for the CN research codec. All output paths are explicit."""
import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

from . import __version__, transport


def read_limited(path, limit):
    if not path.is_file():
        raise ValueError("input must be a regular file")
    with path.open("rb") as source:
        data = source.read(limit + 1)
    if len(data) > limit:
        raise ValueError("input exceeds this format's file limit")
    return data


def write_output(output, data, *, source, force):
    if output.resolve() == source.resolve() or (output.exists() and output.samefile(source)):
        raise ValueError("input and output must be different files")
    temp = tempfile.NamedTemporaryFile(dir=output.parent, delete=False)
    staging = Path(temp.name)
    try:
        with temp:
            temp.write(data)
        if force:
            os.replace(staging, output)
        else:
            os.link(staging, output)
    finally:
        staging.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("pack", "unpack", "inspect", "geometry-pack", "geometry-verify", "geometry-query"):
        cmd = commands.add_parser(name)
        cmd.add_argument("input", type=Path)
        if name in ("pack", "unpack", "geometry-pack"):
            cmd.add_argument("output", type=Path)
            cmd.add_argument("--force", action="store_true")
        if name == "geometry-verify":
            cmd.add_argument("wire", type=Path)
        if name == "geometry-query":
            cmd.add_argument("index", type=int)
            cmd.add_argument("px")
            cmd.add_argument("py")
    args = parser.parse_args(argv)
    try:
        if args.command in ("pack", "unpack", "inspect"):
            limit = transport.LIMIT + (0 if args.command == "pack" else transport.HEADER.size)
            raw = read_limited(args.input, limit)
            if args.command == "pack":
                out = transport.pack_bytes(raw)
            elif args.command == "unpack":
                out = transport.unpack_bytes(raw)
            else:
                info = transport.metadata(raw)
                transport.unpack_bytes(raw)
                print(json.dumps(dict(info, verified=True)))
                return 0
            write_output(args.output, out, source=args.input, force=args.force)
        else:
            from . import geometry
            geometry.command(args, read_limited, write_output)
    except (ValueError, OSError, OverflowError, csv.Error) as exc:
        print("cncodec: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
