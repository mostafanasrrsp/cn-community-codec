"""Slope, primitive and block-floating charts from the CN middle-path replay."""
import math
import struct
from fractions import Fraction as F
from . import affine

SLOPE = ("fixed10", "fixed12", "binary16", "binary32", "exact")
PRIMITIVE = ("parameter16", "parameter32")
BLOCK = ("bfp10", "bfp12")


def power_two(e):
    return F(2) ** e

def ceil_log2(x):
    if x <= 0:
        raise ValueError('positive input required')
    guess = x.numerator.bit_length() - x.denominator.bit_length()
    return guess + (x > power_two(guess))

def length(method, offset):
    if method in SLOPE:
        return affine.length(method, offset)
    if method in PRIMITIVE:
        return (7 if offset else 5) * (2 if method == 'parameter16' else 4)
    bits = int(method[3:])
    n = 6 if offset else 4
    return 1 + (n*bits+7)//8

def encode(method, raw, geom, offset):
    if method in SLOPE:
        return affine.encode(method, raw, geom, offset)
    if method in PRIMITIVE:
        code = 'e' if method == 'parameter16' else 'f'
        fields = raw if offset else raw[:5]
        return struct.pack('<'+str(len(fields))+code, *fields)
    bits = int(method[3:])
    scale = 1 << (bits-1)
    peak = max(map(abs, geom[:4]))
    exponent = ceil_log2(peak) if peak else 0
    unit = power_two(exponent)/scale
    words = [round(v/unit) for v in geom[:4]]
    # +1 does not fit signed two's complement. Renormalize instead of wrap or clipping.
    if max(words) >= scale:
        exponent += 1
        unit *= 2
        words = [round(v/unit) for v in geom[:4]]
    if not -128 <= exponent <= 127:
        raise OverflowError('exponent overflow')
    if offset:
        # Explicit offset grid: +-4 covers all immutable Panel G offsets.
        words.extend(round(v*scale/4) for v in geom[-2:])
    return struct.pack('b', exponent) + affine.fixed_pack(words,bits)

def decode(method, payload, offset):
    if len(payload) != length(method, offset):
        raise ValueError('record length mismatch')
    if method in SLOPE:
        return affine.decode(method,payload,offset)
    if method in PRIMITIVE:
        code = 'e' if method == 'parameter16' else 'f'
        fields = struct.unpack('<'+str(7 if offset else 5)+code, payload)
        if not all(map(math.isfinite,fields)):
            raise OverflowError('nonfinite primitive')
        det = affine.det(tuple(map(F,fields[:4])))
        if det == 0:
            raise ValueError('rank_lost')
        if det < 0:
            raise ValueError('orientation_reversed')
        return affine.model(fields if offset else fields+(0.,0.))
    bits = int(method[3:])
    exponent, = struct.unpack('b',payload[:1])
    # Published unpack returns signed integer / 2^(bits-2); normalized mantissa is half that.
    vals = affine.fixed_unpack(payload[1:],6 if offset else 4,bits)
    block = tuple(v*power_two(exponent)/2 for v in vals[:4])
    return block + (tuple(v*2 for v in vals[4:]) if offset else (F(0),F(0)))
