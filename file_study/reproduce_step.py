"""Rebuild and verify the six-file SXD1 transfer study from the original public URLs."""
import argparse
import bz2
import gzip
import hashlib
import io
import json
import lzma
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import step_delta


def run_tool(args, data):
    return subprocess.run(args, input=data, stdout=subprocess.PIPE, check=True).stdout


def zip_single(raw):
    out = io.BytesIO()
    entry = zipfile.ZipInfo('part.stp', (2000, 1, 1, 0, 0, 0))
    with zipfile.ZipFile(out, 'w') as archive:
        archive.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return out.getvalue()


def unzip_single(frame):
    with zipfile.ZipFile(io.BytesIO(frame)) as archive:
        return archive.read('part.stp')


def methods(sxd1_only):
    if sxd1_only:
        return {'sxd1-xz6': (step_delta.pack, step_delta.unpack)}
    return {
        'zip-deflate9': (zip_single, unzip_single),
        'gzip9': (lambda d: gzip.compress(d, compresslevel=9, mtime=0), gzip.decompress),
        'bzip2-9': (bz2.compress, bz2.decompress),
        'zstd19': (lambda d: run_tool(['zstd', '-q', '--single-thread', '-19', '-c'], d),
                   lambda d: run_tool(['zstd', '-dq', '-c'], d)),
        'brotli11': (lambda d: run_tool(['brotli', '-q', '11', '-c'], d),
                     lambda d: run_tool(['brotli', '-dc'], d)),
        'xz9': (lambda d: lzma.compress(d, preset=9), lzma.decompress),
        'xz6': (lambda d: lzma.compress(d, preset=6), lzma.decompress),
        'sxd1-xz6': (step_delta.pack, step_delta.unpack),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sxd1-only', action='store_true', help='Use only the Python standard library')
    args = parser.parse_args()
    manifest = Path(__file__).with_name('step-transfer-results.json')
    totals = {}
    total_input = 0
    for entry in json.loads(manifest.read_text()):
        with urllib.request.urlopen(entry['source'], timeout=45) as src:
            raw = src.read(step_delta.LIMIT + 1)
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Upstream source size/hash changed for ' + entry['id'])
        total_input += len(raw)
        print(f"{entry['id']} ({len(raw):,} input bytes)")
        for name, (encode, decode) in methods(args.sxd1_only).items():
            wire = encode(raw)
            if decode(wire) != raw:
                raise ValueError(f"Restored bytes differ: {entry['id']} / {name}")
            totals[name] = totals.get(name, 0) + len(wire)
            reference = entry['sizes'][name]
            difference = f' (reference {reference:,})' if len(wire) != reference else ''
            print(f'  {name}: {len(wire):,}{difference}')
    print(f'Input total: {total_input:,}')
    for name, size in totals.items():
        print(f'{name}: {size:,}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, lzma.LZMAError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
