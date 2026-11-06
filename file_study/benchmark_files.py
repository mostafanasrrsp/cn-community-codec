"""Compare complete, stand-alone lossless frames. No input content is written to results."""
import argparse
import hashlib
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMIT = '8f492390ddc7a2ae221a1369ef560589cf8c70fb'
PUBLIC = f'https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/{COMMIT}/Models'
STEPDATA = 'https://raw.githubusercontent.com/stepcode/stepcode/24783b448511b8f6bce2829286a3f00015430236/data'
PUBLIC_SOURCES = [
    ('external-ap209', 'public analysis STEP', f'{STEPDATA}/ap209/ATS1Mod0-outresult.stp'),
    ('external-ap214', 'public assembly STEP', f'{STEPDATA}/ap214e3/as1-oc-214.stp'),
    ('box', 'public GLB', f'{PUBLIC}/Box/glTF-Binary/Box.glb'),
    ('lantern', 'public GLB', f'{PUBLIC}/Lantern/glTF-Binary/Lantern.glb'),
]
try:
    from private_files import PRIVATE_SOURCES
except ImportError:
    PRIVATE_SOURCES = []
SOURCES = PRIVATE_SOURCES + PUBLIC_SOURCES
ENV = dict(os.environ, PYTHONPATH=str(HERE.parent / 'community_codec'), PYTHONDONTWRITEBYTECODE='1')
CN = ([sys.executable, str(Path(os.environ['CN_CODEC_PYZ']).resolve())]
      if os.environ.get('CN_CODEC_PYZ') else [sys.executable, '-m', 'cncodec'])
# Pair of argv with stdout-to-file flags; regular files and process startup for all.
CONFIGS = {
    'gzip6': (['gzip', '-nc', '-6', 'source'], True, ['gzip', '-dc', 'wire'], True),
    'zstd3': (['zstd', '-q', '--single-thread', '-3', '--check', '-c', 'source'], True, ['zstd', '-qdc', 'wire'], True),
    'xz6': (['xz', '-T1', '-6', '-c', 'source'], True, ['xz', '-dc', 'wire'], True),
    'bzip2-9': (['bzip2', '-9c', 'source'], True, ['bzip2', '-dc', 'wire'], True),
    'brotli5': (['brotli', '-q', '5', '-c', 'source'], True, ['brotli', '-dc', 'wire'], True),
    'zip6': (['zip', '-qX', '-6', 'wire.zip', 'source'], False, ['unzip', '-p', 'wire.zip', 'source'], True),
    'cn': (CN + ['pack', 'source', 'wire'], False, CN + ['unpack', 'wire', 'restored'], False),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(args, folder, stdout_path=None):
    started = time.perf_counter_ns()
    if stdout_path:
        with stdout_path.open('wb') as dst:
            subprocess.run(args, cwd=folder, stdout=dst, check=True, env=ENV)
    else:
        subprocess.run(args, cwd=folder, stdout=subprocess.DEVNULL, check=True, env=ENV)
    return round((time.perf_counter_ns() - started) / 1e6, 4)


def run():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--public-only', action='store_true', help='Download only the four public reference assets')
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    if args.repeats < 1:
        ap.error('at least one repeat required')
    manifest, rows = [], []
    with tempfile.TemporaryDirectory(prefix='cn-full-file-') as root:
        folder = Path(root)
        local = folder/'source'
        for ident, category, origin in SOURCES:
            if args.public_only and not isinstance(origin, str):
                continue
            if isinstance(origin, str):
                request = urllib.request.Request(origin, headers={'User-Agent':'CN-file-study/0.1'})
                with urllib.request.urlopen(request, timeout=45) as src, local.open('wb') as dest:
                    shutil.copyfileobj(src, dest)
                magic = b'glTF' if origin.endswith('.glb') else b'ISO-10303-21;'
                if not local.read_bytes().lstrip().startswith(magic):
                    raise ValueError('unexpected source format for '+ident)
                provenance = origin
            else:
                shutil.copyfile(origin, local)
                provenance = str(origin.relative_to(Path.home())) if origin.is_relative_to(Path.home()) else origin.name
            digest = sha(local)
            manifest.append(dict(id=ident, category=category, bytes=local.stat().st_size, sha256=digest, source=provenance))
            order = list(CONFIGS)
            for rep in range(args.repeats):
                random.Random(1073 + rep).shuffle(order)
                for method in order:
                    encode, stdout_enc, decode, stdout_dec = CONFIGS[method]
                    wire = folder/('wire.zip' if method == 'zip6' else 'wire')
                    restored = folder/'restored'
                    et = execute(encode, folder, wire if stdout_enc else None)
                    dt = execute(decode, folder, restored if stdout_dec else None)
                    if sha(restored) != digest:
                        raise ValueError(f'{method} did not restore {ident}')
                    selected = ''
                    if method == 'cn':
                        header = json.loads(subprocess.check_output(CN+['inspect', str(wire)], env=ENV))
                        selected = header['method']
                    rows.append(dict(id=ident, method=method, repeat=rep+1, wire_bytes=wire.stat().st_size,
                                     encode_ms=et, decode_ms=dt, verified=True, selected=selected))
                    restored.unlink()
                    wire.unlink()
            print(ident, local.stat().st_size, flush=True)
    versions = {}
    for tool, opts in [('gzip',['--version']),('zstd',['--version']),('xz',['--version']),
                       ('bzip2',['--help']),('brotli',['-V']),('zip',['-v']),('unzip',['-v'])]:
        proc = subprocess.run([tool]+opts, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        versions[tool] = proc.stdout.splitlines()[:3]
    hw = subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip() if sys.platform == 'darwin' else platform.processor()
    out = dict(schema=1, host=dict(cpu=hw, os=platform.platform(), python=platform.python_version(), versions=versions),
               repeats=args.repeats, sources=manifest, observations=rows)
    output = args.output or HERE/('file-public-results.json' if args.public_only else 'file-results.json')
    output.write_text(json.dumps(out, indent=2)+'\n')


if __name__ == '__main__':
    run()
