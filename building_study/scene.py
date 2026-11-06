"""Adapt the pinned EnergyPlus file and Chicago weather to an ideal absorbing-reveal study."""
import csv
import datetime
import hashlib
import math
import re
from pathlib import Path

COMMIT = 'cf7368216c73c43181e057fa33b479c4e0c86df0'
FILES = {
    'idf': ('testfiles/5ZoneAirCooled.idf', '1b39b63b097b4df17c7dead9883ef6963b6863894640e62dbb562398b6f39614'),
    'epw': ('weather/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw', '3cc3dc0c7bcc93e7203e8d9aab657d384315f5a0c86cdede23f792d437a0309f')
}


def checked(path, kind):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != FILES[kind][1]:
        raise ValueError(f'Unexpected {kind} file. Use the pinned version.')
    return data.decode('latin1')


def sub(v, u):
    return tuple(a-b for a, b in zip(v, u))


def dot(v, u):
    return sum(a*b for a, b in zip(v, u))


def cross(v, u):
    return (v[1]*u[2]-v[2]*u[1], v[2]*u[0]-v[0]*u[2], v[0]*u[1]-v[1]*u[0])


def unit(v):
    norm = math.sqrt(dot(v, v))
    return tuple(a/norm for a in v)


def clockwise(v, angle):
    c, s = math.cos(angle), math.sin(angle)
    return (v[0]*c+v[1]*s, -v[0]*s+v[1]*c, v[2])


def windows(path):
    text = re.sub(r'!.*', '', checked(path, 'idf'))
    objects = {}
    for record in text.split(';'):
        fields = [s.strip() for s in record.split(',')]
        if len(fields) > 1:
            objects.setdefault(fields[0].lower(), {})[fields[1]] = fields[2:]
    assert next(iter(objects['globalgeometryrules'].values()))[:2] == ['CounterClockWise', 'Relative']
    rotation = float(next(iter(objects['building'].values()))[0])
    shapes = []
    for name, a in objects['fenestrationsurface:detailed'].items():
        parent = objects['buildingsurface:detailed'][a[2]]
        assert parent[0].upper() == 'WALL' and parent[4].upper() == 'OUTDOORS'
        assert a[0] in ('WINDOW', 'GLASSDOOR') and a[5] == '' and a[6:8] == ['1','4']
        layers = objects['construction'][parent[1]]
        # Test assumption: the ideal black, full-depth reveal spans the host wall stack.
        depth = sum(float(objects['material'][layer][1]) for layer in layers)
        north = rotation + float(objects['zone'][parent[2]][0])
        xyz = list(map(float, a[8:]))
        p = [tuple(xyz[i:i+3]) for i in range(0,12,3)]
        right, up = sub(p[2], p[1]), sub(p[0], p[1])
        assert math.dist(right, sub(p[3], p[0])) < 1e-9 and abs(dot(right,up)) < 1e-9
        u, v = (clockwise(unit(edge), math.radians(north)) for edge in (right, up))
        shapes.append(dict(name=name, width=math.dist(p[2],p[1]), height=math.dist(p[0],p[1]),
                           depth=depth, basis=[u,v,cross(u,v)], layers=layers))
    return shapes


def direction(day, hour, lat, lon, zone):
    # NOAA fractional-year approximation at the midpoint of each local-standard-time EPW hour.
    gamma = 2 * math.pi / 365 * (day - 1 + (hour-12)/24)
    c, s = math.cos, math.sin
    eqt = 229.18*(.000075+.001868*c(gamma)-.032077*s(gamma)-.014615*c(2*gamma)-.040849*s(2*gamma))
    dec = (.006918-.399912*c(gamma)+.070257*s(gamma)-.006758*c(2*gamma)
           +.000907*s(2*gamma)-.002697*c(3*gamma)+.00148*s(3*gamma))
    ha = math.radians((hour*60+eqt+4*lon-60*zone)/4-180)
    lat = math.radians(lat)
    return (-c(dec)*s(ha), c(lat)*s(dec)-s(lat)*c(dec)*c(ha), s(lat)*s(dec)+c(lat)*c(dec)*c(ha))


def active_hours(path):
    rows = list(csv.reader(checked(path,'epw').splitlines()))
    lat, lon, zone = map(float, rows[0][6:9])
    data = rows[8:]
    assert len(data) == 8760
    for row in data:
        month, day, hour = map(int, row[1:4])
        dni = float(row[14])
        if 0 < dni < 9999:
            doy = datetime.date(2001,month,day).timetuple().tm_yday
            sun = direction(doy, hour-.5, lat, lon, zone)
            if sun[2] > math.sin(math.radians(.266)):
                yield (month, day, hour, dni, sun)


def geometry_csv(shapes):
    columns = ('B00','B01','B10','B11','d','bx','by')
    rows = [(s['width'],0,0,s['height'],s['depth'],0,0) for s in shapes]
    return ','.join(columns)+'\n'+''.join(','.join(map(str,r))+'\n' for r in rows)
