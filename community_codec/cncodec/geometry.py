"""Strict GX01, target 2. Ordered records represent an ideal normalized response."""
import csv
import io
import json
import math
import struct
from fractions import Fraction

from . import affine, angle_charts, intrinsic, standard_charts

HEADER = struct.Struct("<4sBI")
FIELDS = ("B00", "B01", "B10", "B11", "d", "bx", "by")
LIMIT = Fraction(1, 100)
MAX_RECORDS = 50000
MAX_CSV_BYTES = 16 * 1024 * 1024
MAX_WIRE_BYTES = HEADER.size + MAX_RECORDS * 57
METHODS = (standard_charts.SLOPE + standard_charts.PRIMITIVE + standard_charts.BLOCK
           + ("intrinsic24", "intrinsic32", "ratio32", "ratio40", "ratio24short"))
CHARTS = ([standard_charts] * 9 + [intrinsic] * 3 + [angle_charts] * 2)
FLAT = (Fraction(0),) * 6


def binary64(text):
    if text is None or len(text) > 96:
        raise ValueError("missing or overlong numeric field")
    text = text.strip()
    if text.lower().lstrip("+-").startswith("0x"):
        number = float.fromhex(text)
    else:
        number = float(text)
    if not math.isfinite(number):
        raise ValueError("number must be finite")
    return number


def geometries(data):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    header = reader.fieldnames or []
    if len(set(header)) != len(header) or not set(FIELDS).issubset(header):
        raise ValueError("CSV needs distinct column names and " + ",".join(FIELDS))
    for index, row in enumerate(reader):
        if index >= MAX_RECORDS:
            raise ValueError("geometry count exceeds format limit")
        if None in row:
            raise ValueError(f"extra field in geometry row {index + 1}")
        try:
            yield tuple(binary64(row[key]) for key in FIELDS)
        except (OverflowError, ValueError) as exc:
            raise ValueError(f"geometry row {index + 1}: {exc}") from exc


def select_record(raw):
    model = affine.model(raw)
    if not raw[4]:
        return 0, b""
    offset = bool(raw[-2] or raw[-1])
    # Ties use the wire registry's original order. Stop at the first certified size.
    order = sorted(range(len(METHODS)), key=lambda i: CHARTS[i].length(METHODS[i], offset))
    for index in order:
        method, chart = METHODS[index], CHARTS[index]
        try:
            if chart is standard_charts:
                payload = chart.encode(method, raw, model, offset)
            else:
                payload = chart.encode(method, raw, offset)
            decoded = chart.decode(method, payload, offset)
            if affine.det(decoded) and affine.certificate(model, decoded) <= LIMIT:
                return 1 + 2 * index + int(offset), payload
        except (OverflowError, ValueError, struct.error, ZeroDivisionError):
            # Lower precision can overflow, underflow or destroy rank. Try the next layout.
            continue
    raise ValueError("no representable record including exact geometry fallback")


def encode(rows):
    tags = bytearray()
    payloads = bytearray()
    accumulator = occupied = count = 0
    for index, raw in enumerate(rows):
        if index >= MAX_RECORDS:
            raise ValueError("geometry count exceeds format limit")
        try:
            tag, payload = select_record(raw)
        except ValueError as exc:
            raise ValueError(f"geometry row {index + 1}: {exc}") from exc
        payloads.extend(payload)
        accumulator |= tag << occupied
        occupied += 5
        if occupied >= 8:
            tags.append(accumulator & 255)
            accumulator >>= 8
            occupied -= 8
        count += 1
    if occupied:
        tags.append(accumulator)
    return HEADER.pack(b"GX01", 2, count) + tags + payloads


def decode(wire):
    if not HEADER.size <= len(wire) <= MAX_WIRE_BYTES:
        raise ValueError("invalid geometry stream length")
    magic, target, count = HEADER.unpack_from(wire)
    if magic != b"GX01" or target != 2:
        raise ValueError("requires global GX01 with 0.010 target (ID 2)")
    if count > MAX_RECORDS:
        raise ValueError("geometry count exceeds format limit")
    end_tags = HEADER.size + (5 * count + 7) // 8
    if end_tags > len(wire):
        raise ValueError("truncated tag table")
    used = 5 * count % 8
    if used and wire[end_tags - 1] >> used:
        raise ValueError("nonzero tag padding")
    result = []
    pos = end_tags
    for index in range(count):
        byte, shift = divmod(5 * index, 8)
        at = HEADER.size + byte
        word = wire[at]
        if shift > 3:
            word |= wire[at + 1] << 8
        tag = (word >> shift) & 31
        if tag == 0:
            result.append(FLAT)
            continue
        if tag > 2 * len(METHODS):
            raise ValueError(f"unknown strict GX01 tag {tag}")
        family, offset = divmod(tag - 1, 2)
        method, chart = METHODS[family], CHARTS[family]
        end = pos + chart.length(method, bool(offset))
        if end > len(wire):
            raise ValueError("truncated geometry payload")
        try:
            model = chart.decode(method, wire[pos:end], bool(offset))
            if not affine.det(model):
                raise ValueError("nonflat tag reconstructed a singular map")
        except (OverflowError, ValueError, struct.error, ZeroDivisionError) as exc:
            raise ValueError(f"invalid record {index} ({method}): {exc}") from exc
        result.append(model)
        pos = end
    if pos != len(wire):
        raise ValueError("trailing geometry payload")
    return result


def verify(rows, wire):
    decoded = decode(wire)
    count = 0
    maximum = Fraction(0)
    for index, raw in enumerate(rows):
        if index >= len(decoded):
            raise ValueError("source and geometry record counts differ")
        bound = affine.certificate(affine.model(raw), decoded[index])
        if bound > LIMIT:
            raise ValueError(f"geometry row {index + 1} exceeds strict certificate")
        maximum = max(maximum, bound)
        count += 1
    if count != len(decoded):
        raise ValueError("source and geometry record counts differ")
    return dict(format="GX01", target_id=2, records=count, wire_bytes=len(wire),
                absolute_error_budget="1/100", max_certificate_fraction=str(maximum))


def command(args, read_limited, write_output):
    if args.command == "geometry-query":
        decoded = decode(read_limited(args.input, MAX_WIRE_BYTES))
        if not 0 <= args.index < len(decoded):
            raise ValueError("record index out of range (zero-based)")
        point = tuple(Fraction(binary64(s)) for s in (args.px, args.py))
        value = affine.response(decoded[args.index], point)
        print(json.dumps(dict(record=args.index, transmission=float(value),
                              transmission_fraction=str(value))))
        return
    data = read_limited(args.input, MAX_CSV_BYTES)
    if args.command == "geometry-pack":
        wire = encode(geometries(data))
        info = verify(geometries(data), wire)
        write_output(args.output, wire, source=args.input, force=args.force)
    else:
        wire = read_limited(args.wire, MAX_WIRE_BYTES)
        info = verify(geometries(data), wire)
    print(json.dumps(info))
