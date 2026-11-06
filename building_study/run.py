"""Replay a pinned building and weather file using the public CN codec.

Run from the source tree, or install the wheel first. Use --cpu-only outside macOS.
"""
import argparse
import json
import math
import platform
import statistics
import struct
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path

from scene import FILES, COMMIT, windows, active_hours, geometry_csv, unit, dot, cross

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'community_codec'))
from cncodec import affine, geometry

ANGLE = .266  # degrees, fixed uniform solar disk angular radius
TAU = math.sin(math.radians(ANGLE)) + 1e-14
COS = math.cos(math.radians(ANGLE))


def faces(w):
    normals = [(sg*w[i], sg*w[i+1], sg*w[4+i//2]-1)
               for i in (0, 2) for sg in (1, -1)]
    return [tuple(x/max(map(abs, n)) for x in n) for n in normals]


def native_faces(bank):
    flat = []
    for n in bank:
        flat.extend([*n, math.sqrt(dot(n,n))])
    return flat


def excludes(bank, axis):
    # Exact rational comparison on represented input and outward-rounded sine;
    # a strict positive separation by any plane suffices to reject the disk.
    for n in bank:
        proj = dot(n, axis)
        if proj > 0 and proj*proj > dot(n,n)*Fraction(TAU)**2:
            return True
    return False


def f32(x):
    return struct.unpack('<f',struct.pack('<f',x))[0]


def rectangular_control(exact):
    # A consumer-specific candidate: registered RC01 profile, little-endian count, then
    # two binary16 coefficients per centered, axis-aligned window in its own frame.
    if any(any(m[i] for i in (1,2,4,5)) for m in exact):
        raise ValueError('rectangular control requires centered local axes')
    wire = struct.pack('<4sBI', b'RC01', 2, len(exact))
    wire += b''.join(struct.pack('<2e', m[0], m[3]) for m in exact)
    errors = []
    for model, (x,y) in zip(exact,struct.iter_unpack('<2e',wire[9:])):
        errors.append(affine.certificate(model,(Fraction(x),0,0,Fraction(y),0,0)))
    return dict(profile='RC01 study-only, 9-byte header and 4 bytes per opening',
                wire_bytes=len(wire), max_certificate=float(max(errors)),
                passes=all(e<=geometry.LIMIT for e in errors))


def generate(shapes, hours, decoded, exact, tmp):
    arrays = []
    exact_arrays = []
    gpu_shapes = []
    for a,b in zip(exact, decoded):
        banks = [faces(a),faces(b),faces(tuple(Fraction(f32(x)) for x in b))]
        normal_data = [list(map(float, native_faces(bank))) for bank in banks]
        arrays.append([*map(float,b),*normal_data[0],*normal_data[1]])
        exact_arrays.append([*map(float,a),*normal_data[0],*normal_data[0]])
        gpu_shapes.append(struct.pack('<56f',*b,0,0,*sum(normal_data,[])))
    counts = []
    queries = []
    gpu_query = bytearray()
    for idx,s in enumerate(shapes):
        submitted = skipped = 0
        banks = [faces(exact[idx]),faces(decoded[idx])]
        for _,_,_,_,sun in hours:
            axis = unit(tuple(dot(sun,v) for v in s['basis']))
            if axis[2] <= TAU + 2**-44:
                continue
            rational = tuple(map(Fraction,axis))
            proof = [excludes(bank,rational) for bank in banks]
            queries.append((idx, *axis,ANGLE,TAU,int(all(proof)),int(proof[0])))
            ref = (1,0,0) if abs(axis[2])>.8 else (0,0,1)
            e = unit(cross(ref,axis))
            f = cross(axis,e)
            gpu_query.extend(struct.pack('<12f4I',*axis,TAU,*e,COS,*f,axis[2]*(1+COS)/2,idx,0,0,0))
            submitted += 1
            skipped += int(all(proof))
        counts.append(dict(name=s['name'],full_front_cones=submitted,certified_skips=skipped))
    header = [len(shapes),len(queries)]
    for name, records, proof_index in [('decoded',arrays,-2),('exact',exact_arrays,-1)]:
        with (tmp/(name+'.txt')).open('w') as out:
            print(*header,file=out)
            for r in records:
                print(*r,file=out)
            for q in queries:
                print(*q[:-2],q[proof_index],file=out)
    (tmp/'gpu.bin').write_bytes(struct.pack('<2I',*header)+b''.join(gpu_shapes)+gpu_query)
    return counts,queries


def paired(base,gated):
    ratios=[a/b for a,b in zip(base,gated)]
    quartiles=statistics.quantiles(ratios,n=4,method='inclusive')
    return dict(baseline_ms=base, gated_ms=gated, median_baseline_ms=statistics.median(base),
                median_gated_ms=statistics.median(gated), median_paired_speedup=statistics.median(ratios),
                speedup_iqr=[quartiles[0],quartiles[2]], pairs=len(ratios))


def run(args):
    from hashlib import sha256
    out = args.out
    out.mkdir(exist_ok=True,parents=True)
    start=time.perf_counter()
    shapes=windows(args.idf)
    hours=list(active_hours(args.epw))
    csv_bytes=geometry_csv(shapes).encode()
    rows=list(geometry.geometries(csv_bytes))
    wire=geometry.encode(rows)
    cert=geometry.verify(rows,wire)
    decoded=geometry.decode(wire)
    exact=[affine.model(row) for row in rows]
    (out/'windows.csv').write_bytes(csv_bytes)
    (out/'windows.gx01').write_bytes(wire)
    parse_seconds=time.perf_counter()-start
    with tempfile.TemporaryDirectory() as t:
        tmp=Path(t)
        start=time.perf_counter()
        counts,queries=generate(shapes,hours,decoded,exact,tmp)
        prepared=time.perf_counter()-start
        native=HERE/'native'
        cpu=tmp/'cpu'
        subprocess.run(['c++','-O3','-ffp-contract=off','-std=c++17',native/'cpu.cpp','-o',cpu],check=True)
        cpu_run=lambda key,n:json.loads(subprocess.check_output([cpu,tmp/(key+'.txt'),'8',str(n)]))
        ref=cpu_run('exact',0)['outputs']
        result=cpu_run('decoded',11)
        vals=result.pop('outputs')
        max_error=max(abs(a-b) for a,b in zip(ref,vals))
        assert len(ref)==len(vals)==len(queries) and max_error<=0.0100000001
        assert all(math.isfinite(v) and -.00000001<=v<=1.00000001 for v in vals)
        report=dict(commit=COMMIT,inputs=FILES,platform=platform.platform(),total_weather_hours=8760,
                    openings=shapes,active_sun_hours=len(hours),submitted_queries=len(queries),counts=counts,
                    grid='8 Gaussian radial x 32 azimuth, uniform solar disk, fully front-facing only',
                    total_certified_skips=sum(r['certified_skips'] for r in counts),
                    zero_unculled_queries=sum(v==0 for v in vals),
                    cpu=paired(result['baseline_ms'],result['gated_ms']),cpu_traversals_per_sample=result['panels_per_sample'],
                    max_sampled_exact_vs_decoded_error=max_error, certificate=cert,
                    rectangular_fp16_control=rectangular_control(exact),
                    wire_sha256=sha256(wire).hexdigest(), geometry_csv_bytes=len(csv_bytes),
                    parse_and_encode_seconds=parse_seconds,build_query_and_oracle_seconds=prepared)
        if not args.cpu_only:
            sdk=['xcrun','-sdk','macosx']
            air,lib,exe=(tmp/x for x in ('cull.air','cull.metallib','metal-replay'))
            subprocess.run(sdk+['metal','-fno-fast-math','-c',native/'cull.metal','-o',air],check=True)
            subprocess.run(sdk+['metallib',air,'-o',lib],check=True)
            subprocess.run(sdk+['clang++','-O2','-std=c++17','-fobjc-arc',native/'metal_host.mm',
                                '-framework','Metal','-framework','Foundation','-o',exe],check=True)
            gpu=json.loads(subprocess.check_output([exe,lib,tmp/'gpu.bin','8']))
            flags,observed=gpu['skipped'],gpu['values']
            assert len(observed)==len(flags)==len(queries)
            assert all(math.isfinite(v) for v in observed)
            assert all(not flag or (q[-2] and v==0) for flag,q,v in zip(flags,queries,observed))
            report['metal']=dict(device=gpu['device'],skipped=sum(flags),
                                 execution=paired(gpu['base_gpu_ms'],gpu['cull_gpu_ms']),
                                 dispatch_and_wait=paired(gpu['base_wall_ms'],gpu['cull_wall_ms']),
                                 base_readback_us=gpu['base_read_us'],gated_readback_us=gpu['cull_read_us'],
                                 max_deviation_from_cpu=max(abs(a-b) for a,b in zip(vals,observed)))
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print('Openings:',len(shapes),'front-facing cones:',len(queries),'skipped:',report['total_certified_skips'])
        print('GX01 bytes:',len(wire),'CPU paired speedup:',report['cpu']['median_paired_speedup'])
        if 'metal' in report:
            print('Metal dispatch-and-wait paired speedup:',report['metal']['dispatch_and_wait']['median_paired_speedup'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--idf',type=Path,required=True)
    parser.add_argument('--epw',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--cpu-only',action='store_true')
    run(parser.parse_args())
