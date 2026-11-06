"""Bit-packed QR charts for the R9 ideal normalized aperture response.

encode accepts (B00, B01, B10, B11, depth, bx, by).
decode returns the exact rational affine map (W00,W01,W10,W11,bx,by).
Length excludes the enclosing layout/method tag.
"""
import math
import struct
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from functools import lru_cache

ANGLE_BITS = {"intrinsic16": 16, "intrinsic24": 24, "intrinsic32": 32, "ratio32": 32}
PI = Decimal("3.141592653589793238462643383279502884197169399375105820974944592307816406286")
FRAC_BITS = 10
MINI_BITS = 19  # sign, biased 8-bit exponent, 10 stored fraction bits
ROT_SCALE = 1 << 62


def mini_encode(value):
    """Finite normal with 11 significant bits; ties to even. One zero code."""
    if not value:
        return 0
    sign = value < 0
    fraction, exp = math.frexp(abs(value))
    integer = round(math.ldexp(fraction, FRAC_BITS + 1))
    if integer == 1 << (FRAC_BITS + 1):
        integer //= 2
        exp += 1
    biased = exp - 1 + 127
    if not 1 <= biased <= 254:
        raise OverflowError("magnitude outside mini-float range")
    return (int(sign) << 18) | (biased << 10) | (integer - (1 << FRAC_BITS))


def mini_decode(bits):
    if bits == 0:
        return Fraction(0)
    biased = (bits >> FRAC_BITS) & 255
    if biased in (0, 255):
        raise ValueError("invalid mini-float exponent")
    sign = -1 if bits >> 18 else 1
    mantissa = (1 << FRAC_BITS) + (bits & 1023)
    return sign * mantissa * Fraction(2) ** (biased - 127 - FRAC_BITS)


@lru_cache(maxsize=16384)
def rotation(angle_word, bits):
    """Define the decoder's finite rotation independently of platform libm."""
    quarter = 1 << (bits - 2)
    quadrant, remainder = divmod(angle_word, quarter)
    with localcontext() as ctx:
        ctx.prec = 72
        ctx.rounding = ROUND_HALF_EVEN
        x = (PI * remainder) / (2 * quarter)
        minus_x2 = -x * x
        sine_term, cosine_term = x, Decimal(1)
        sine, cosine = sine_term, cosine_term
        for n in range(1, 31):
            sine_term = sine_term * minus_x2 / ((2*n) * (2*n+1))
            cosine_term = cosine_term * minus_x2 / ((2*n-1) * (2*n))
            sine += sine_term
            cosine += cosine_term
        s = Fraction(int((sine * ROT_SCALE).to_integral_value()), ROT_SCALE)
        c = Fraction(int((cosine * ROT_SCALE).to_integral_value()), ROT_SCALE)
    return ((c,s),(-s,c),(-c,-s),(s,-c))[quadrant]


def field_widths(method, offset):
    sizes = [ANGLE_BITS[method], 19, 19, 32] if method == "ratio32" else [ANGLE_BITS[method], 19, 19, 19, 19]
    return sizes + ([16, 16] if offset else [])


def length(method, offset):
    return (sum(field_widths(method, offset)) + 7) // 8


def ieee_word(value, code):
    return int.from_bytes(struct.pack(">" + code, value), "big")


def ieee_value(word, code):
    n = struct.calcsize(">" + code)
    return Fraction(struct.unpack(">" + code, word.to_bytes(n, "big"))[0])


def encode(method, raw, offset):
    a, b, c, g, depth, bx, by = raw
    ar, br, cr, gr = map(Fraction, raw[:4])
    det = ar * gr - br * cr
    if det <= 0 or depth < 0 or (depth == 0 and (bx or by)):
        raise ValueError("source requires positive orientation and a valid depth")
    if not offset and (bx or by):
        raise ValueError("offset needs two transmitted words")
    width = math.hypot(a, c)
    dot = ar * br + cr * gr
    height = float(det / Fraction(width))
    skew = float(dot / Fraction(width))
    n = 1 << ANGLE_BITS[method]
    angle = round(math.atan2(c, a) * (n / math.tau)) % n
    if method == "ratio32":
        if depth == 0:
            # A reserved zero/zero pair denotes the centered flat slope.
            words = [angle, 0, 0, 0]
        else:
            words = [angle, mini_encode(width/depth), mini_encode(height/depth), ieee_word(float(dot/det), "f")]
    else:
        words = [angle] + [mini_encode(v) for v in (width, skew, height, depth)]
    if offset:
        words += [ieee_word(v, "e") for v in (bx, by)]
    packed = 0
    for word, size in zip(words, field_widths(method, offset)):
        if not 0 <= word < 1 << size:
            raise ValueError("field exceeds width")
        packed = (packed << size) | word
    return packed.to_bytes(length(method, offset), "big")


def decode(method, payload, offset):
    if len(payload) != length(method, offset):
        raise ValueError("wrong payload length")
    packed = int.from_bytes(payload, "big")
    words = []
    for size in reversed(field_widths(method, offset)):
        words.append(packed & ((1 << size)-1))
        packed >>= size
    if packed:
        raise ValueError("nonzero high padding")
    words.reverse()
    c, s = rotation(words[0], ANGLE_BITS[method])
    bx, by = [ieee_value(x, "e") for x in words[-2:]] if offset else (Fraction(0), Fraction(0))
    if method == "ratio32":
        width, height = mini_decode(words[1]), mini_decode(words[2])
        shear = ieee_value(words[3], "f")
        if width == height == shear == bx == by == 0:
            return (Fraction(0),) * 6
        skew, depth = shear * height, Fraction(1)
    else:
        width, skew, height, depth = map(mini_decode, words[1:5])
    if width <= 0 or height <= 0 or depth < 0 or (depth == 0 and (bx or by)):
        raise ValueError("invalid reconstructed geometry")
    # R is a finite Q62 rotation, so use its true determinant, not an assumed 1.
    scale = depth / (width * height * (c*c + s*s))
    return (scale*(s*skew + c*height), scale*(s*height - c*skew),
            -scale*s*width, scale*c*width, bx, by)
