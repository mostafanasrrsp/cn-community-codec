"""MIT-licensed numerical routines from Mostafa Nasr’s Revision 9 study/geometry/run_geometry.py."""
import math
import struct
from fractions import Fraction as F

CORNERS = ((-1,-1),(-1,1),(1,-1),(1,1))


def det(m):
    return m[0]*m[3] - m[1]*m[2]


def model(raw):
    a, b, c, d, depth, bx, by = map(F, raw)
    determinant = a*d-b*c
    if determinant <= 0 or depth < 0 or (not depth and (bx or by)):
        raise ValueError("Invalid physical geometry")
    return tuple(depth*x/determinant for x in (d,-b,-c,a)) + (bx,by)


def slope(m, q):
    a,b,c,d,x,y = m
    u,v = q[0]-x,q[1]-y
    dt = det(m)
    return (d*u-b*v)/dt, (a*v-c*u)/dt


def apply(m,p):
    a,b,c,d,x,y=m
    return a*p[0]+b*p[1]+x, c*p[0]+d*p[1]+y


def response(m,p):
    x,y = apply(m,p)
    return max(0,1-abs(x)) * max(0,1-abs(y))


def certificate(m,h):
    if m == h:
        return F(0)
    if not det(m) or not det(h):
        raise ValueError("Nonflat certificates require full rank")
    error_map = tuple(x-y for x,y in zip(m,h))
    # The l1 norm of an affine map is convex, so bounding both supporting
    # parallelograms requires only their corners. Elsewhere both masks are zero.
    largest = F(0)
    for supported in (m,h):
        for q in CORNERS:
            ex, ey = apply(error_map,slope(supported,q))
            largest = max(largest,abs(ex)+abs(ey))
    return min(F(1),largest)


def fixed_pack(words,bits):
    mask = (1 << bits)-1
    if any(not -(1 << (bits-1)) <= w < (1 << (bits-1)) for w in words):
        raise OverflowError("Outside common signed grid")
    integer = 0
    for word in words:
        integer = (integer << bits) | (word & mask)
    return integer.to_bytes((len(words)*bits+7)//8, "big")


def fixed_unpack(payload,n,bits):
    value = int.from_bytes(payload,"big")
    if value >> (n*bits):
        raise ValueError("Unused fixed-point padding bits nonzero")
    mask = (1 << bits)-1
    words = [(value >> (bits*i)) & mask for i in reversed(range(n))]
    return tuple(F(w-(1 << bits) if w >= (1 << (bits-1)) else w,1 << (bits-2)) for w in words)


def length(method,offset):
    n = 6 if offset else 4
    if method.startswith("fixed"):
        return (n*int(method[5:])+7)//8
    if method == "exact":
        return 8*(n+1)
    return n*(2 if method == "binary16" else 4)


def encode(method,raw,m,offset):
    n=6 if offset else 4
    if method.startswith("fixed"):
        bits = int(method[5:])
        scale = 1 << (bits-2)
        return fixed_pack(tuple(round(x*scale) for x in m[:n]),bits)
    if method == "exact":
        fields = raw if offset else raw[:5]
        return struct.pack("<"+str(len(fields))+"d",*fields)
    code = "e" if method=="binary16" else "f"
    record = struct.pack("<"+str(n)+code,*map(float,m[:n]))
    if any(not math.isfinite(x) for x in struct.unpack("<"+str(n)+code,record)):
        raise OverflowError("Non-finite floating-point coefficient")
    return record


def decode(method,payload,offset):
    n = 6 if offset else 4
    if method.startswith("fixed"):
        coeff = fixed_unpack(payload,n,int(method[5:]))
    elif method=="exact":
        raw = struct.unpack("<"+str(n+1)+"d",payload)
        return model(raw if offset else raw+(0.,0.))
    else:
        code = "e" if method=="binary16" else "f"
        coeff = tuple(map(F,struct.unpack("<"+str(n)+code,payload)))
    return coeff if offset else coeff+(F(0),F(0))
