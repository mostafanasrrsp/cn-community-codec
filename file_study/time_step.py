"""Compare in-memory STEP preprocessing+XZ against the same runtime and XZ level."""
import argparse
import hashlib
import json
import lzma
import random
import statistics
import time
import urllib.request
from pathlib import Path
import step_delta

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('local-step-timings.json'))
args = parser.parse_args()
here = Path(__file__).resolve().parent
entries = json.loads((here / 'step-transfer-results.json').read_text())
rows = []
for entry in entries:
    with urllib.request.urlopen(entry['source'], timeout=45) as source:
        raw = source.read(step_delta.LIMIT + 1)
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    methods = ['xz6', 'sxd1']
    for rep in range(6):
        random.Random(271 + rep).shuffle(methods)
        for method in methods:
            start = time.perf_counter_ns()
            packed = step_delta.pack(raw) if method == 'sxd1' else lzma.compress(raw, preset=6)
            middle = time.perf_counter_ns()
            restored = step_delta.unpack(packed) if method == 'sxd1' else lzma.decompress(packed)
            stop = time.perf_counter_ns()
            if restored != raw:
                raise ValueError('reconstruction failure')
            if rep:
                rows.append(dict(id=entry['id'], method=method, repeat=rep, wire_bytes=len(packed),
                                 encode_ms=(middle-start)/1e6, decode_ms=(stop-middle)/1e6))
args.output.write_text(json.dumps(rows, indent=2)+'\n')
for method in ('xz6','sxd1'):
    print(method, {key: sum(statistics.median(r[key] for r in rows if r['id'] == item['id'] and r['method'] == method)
                            for item in entries) for key in ('encode_ms','decode_ms')})
