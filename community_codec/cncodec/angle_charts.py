"""Two fixed wire profiles for the normalized affine-response chart.

r40 uses a 40-bit roll and binary32 shear (13/17 bytes). r24 uses a
24-bit roll and binary16 shear (9/13 bytes). Magnitudes are unsigned
6-exponent/10-fraction normals. Out-of-range input requires fallback.
"""
import math
import struct
from fractions import Fraction

from .intrinsic import encode as ratio_encode
from .intrinsic import ieee_value, rotation

ANGLE = {"ratio40": 40, "ratio24short": 24}


def length(method, offset):
    return ANGLE[method] // 8 + 4 + (4 if method == "ratio40" else 2) + (4 if offset else 0)


def narrow_mag(word):
    biased_exponent = ((word >> 10) & 255) - 127 + 31
    if word >> 18 or not 1 <= biased_exponent <= 62:
        raise OverflowError("positive magnitude outside 6-bit exponent range")
    return (biased_exponent << 10) | (word & 1023)


def mag(word):
    exponent = word >> 10
    if not 1 <= exponent <= 62:
        raise ValueError("non-normal magnitude")
    return (1024 + (word & 1023)) * Fraction(2) ** (exponent - 31 - 10)


def encode(method, raw, offset):
    # Reuse the standard gauge-invariant encoder's exact source checks and
    # scalar quantizer. Its 32-bit angle is replaced by a new direct angle.
    source = ratio_encode("ratio32", raw, offset)
    if raw[4] == 0:
        return bytes(length(method, offset))
    offset_bytes = source[-4:] if offset else b""
    n = int.from_bytes(source[:-4] if offset else source, "big")
    a = narrow_mag((n >> 51) & 0x7ffff)
    h = narrow_mag((n >> 32) & 0x7ffff)
    short = method == "ratio24short"
    if short:
        A, B, C, D = map(Fraction, raw[:4])
        shear_bytes = struct.pack(">e", float((A*B+C*D)/(A*D-B*C)))
    else:
        shear_bytes = (n & 0xffffffff).to_bytes(4, "big")
    bits = ANGLE[method]
    theta = round(math.atan2(raw[2], raw[0]) * ((1 << bits)/math.tau)) % (1 << bits)
    return theta.to_bytes(bits//8, "big") + struct.pack(">HH", a, h) + shear_bytes + offset_bytes


def decode(method, payload, offset):
    if len(payload) != length(method, offset):
        raise ValueError("wrong payload length")
    if not any(payload):
        return (Fraction(0),) * 6
    bits = ANGLE[method]
    i = bits//8
    c,s = rotation(int.from_bytes(payload[:i], "big"), bits)
    width, height = map(mag, struct.unpack(">HH", payload[i:i+4]))
    i += 4
    n = 4 if method == "ratio40" else 2
    shear = ieee_value(int.from_bytes(payload[i:i+n],"big"), "f" if n == 4 else "e")
    bx, by = map(Fraction, struct.unpack(">ee",payload[-4:])) if offset else (Fraction(0),Fraction(0))
    scale = 1 / (c*c+s*s)
    return (scale*(c+shear*s)/width, scale*(s-shear*c)/width, -scale*s/height, scale*c/height, bx,by)
