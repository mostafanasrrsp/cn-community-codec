"""Bounded, byte-exact STEP Part 21 lexical profiles for the CN preview.

SXD2 separates literal, declaration and reference bytes. Its second profile also
predicts references from previous references and separates original decimal text.
The length and checksum in the envelope always refer to the complete source file.
"""
import hashlib
import lzma
import re
import struct

import solar_codec
import step_delta

MAGIC = b"SXD2"
HEADER = struct.Struct("<4sI32sB")
LIMIT = step_delta.LIMIT
FRAME_LIMIT = 3 * LIMIT + 65536
PROFILES = {"split-tuned": 1, "dual-floats-tuned": 2, "split-brotli": 3}
NAMES = {number: name for name, number in PROFILES.items()}
PREFIX = b"ISO-10303-21;"
DECIMAL, LAST_REFERENCE, REFERENCE, DECLARATION = range(28, 32)
MARKER = re.compile(rb"[\x1c-\x1f]")
# An unsigned search can start only at the beginning of a run of digits. This
# avoids rescanning every suffix of a long integer that has no decimal point.
FLOAT = re.compile(rb"(?:[+-][0-9]+|(?<![0-9])[0-9]+)\.[0-9]+(?:E[+-]?[0-9]+)?")
TUNED_XZ = [{"id": lzma.FILTER_LZMA2, "preset": 6, "lc": 2, "lp": 0,
             "pb": 0, "nice_len": 273}]


def eligible(raw):
    return len(raw) <= LIMIT and raw.lstrip().startswith(PREFIX) and not MARKER.search(raw)


def _append_delta(numbers, delta):
    step_delta.append_number(numbers, delta * 2 if delta >= 0 else -delta * 2 - 1)


def _split(raw, dual):
    literals, declarations, references = bytearray(), bytearray(), bytearray()
    previous_declaration = previous_reference = end = 0
    for match in step_delta.TOKEN.finditer(raw):
        literals.extend(raw[end:match.start()])
        identity = int(match[1])
        delta = identity - previous_declaration
        if match[2] is not None:
            literals.append(DECLARATION)
            _append_delta(declarations, delta)
            previous_declaration = identity
        else:
            reference_delta = identity - previous_reference
            if dual and abs(reference_delta) < abs(delta):
                literals.append(LAST_REFERENCE)
                delta = reference_delta
            else:
                literals.append(REFERENCE)
            _append_delta(references, delta)
            previous_reference = identity
        # Keep the original whitespace between a declaration and '='.
        end = match.end(1)
    literals.extend(raw[end:])
    if not dual:
        widths = struct.pack("<II", len(literals), len(declarations))
        return b"".join((widths, literals, declarations, references))

    text, decimals = bytearray(), bytearray()
    end = 0
    for match in FLOAT.finditer(literals):
        text.extend(literals[end:match.start()])
        text.append(DECIMAL)
        decimals.extend(match[0])
        decimals.append(0)
        end = match.end()
    text.extend(literals[end:])
    widths = struct.pack("<III", len(text), len(declarations), len(references))
    return b"".join((widths, text, declarations, references, decimals))


def pack(raw, profile="split-tuned"):
    if profile not in PROFILES or not eligible(raw):
        raise ValueError("SXD2 requires a supported profile and STEP text up to 8 MiB without reserved bytes 0x1c–0x1f")
    payload = _split(raw, profile == "dual-floats-tuned")
    if profile == "split-brotli":
        compressed = solar_codec.brotli(payload, True, FRAME_LIMIT - HEADER.size)
    else:
        compressed = lzma.compress(payload, format=lzma.FORMAT_XZ, filters=TUNED_XZ)
    return HEADER.pack(MAGIC, len(raw), hashlib.sha256(raw).digest(), PROFILES[profile]) + compressed


def _header(wire):
    if not HEADER.size < len(wire) <= FRAME_LIMIT:
        raise ValueError("invalid SXD2 frame length")
    magic, size, digest, method = HEADER.unpack_from(wire)
    if magic != MAGIC or method not in NAMES or not len(PREFIX) <= size <= LIMIT:
        raise ValueError("unknown or oversized SXD2 frame")
    return size, digest, NAMES[method]


def profile_name(wire):
    return _header(wire)[2]


def _read_delta(numbers, pos):
    value = 0
    for shift in range(0, 35, 7):
        if pos == len(numbers):
            raise ValueError("truncated SXD2 identity")
        byte = numbers[pos]
        pos += 1
        value |= (byte & 127) << shift
        if byte < 128:
            if (shift and not byte) or value > 1999999998:
                raise ValueError("invalid SXD2 identity encoding")
            return (value >> 1) ^ -(value & 1), pos
    raise ValueError("oversized SXD2 identity")


def _restore_payload(payload, size, dual):
    header_size = 12 if dual else 8
    if len(payload) < header_size:
        raise ValueError("truncated SXD2 stream lengths")
    literal_length, declaration_length = struct.unpack_from("<II", payload)
    literal_end = header_size + literal_length
    declaration_end = literal_end + declaration_length
    reference_end = declaration_end + struct.unpack_from("<I", payload, 8)[0] if dual else len(payload)
    if literal_length > size or declaration_end > reference_end or reference_end > len(payload):
        raise ValueError("invalid SXD2 stream lengths")
    view = memoryview(payload)
    literals = view[header_size:literal_end]
    declarations = view[literal_end:declaration_end]
    references = view[declaration_end:reference_end]
    decimal_pos = reference_end
    declaration_pos = reference_pos = previous_declaration = previous_reference = tail = 0
    output = bytearray()
    for match in MARKER.finditer(literals):
        literal_size = match.start() - tail
        if len(output) + literal_size >= size:
            raise ValueError("SXD2 output exceeds declared length")
        output.extend(literals[tail:match.start()])
        kind = literals[match.start()]
        if kind == DECIMAL:
            if not dual:
                raise ValueError("unexpected SXD2 decimal marker")
            end = payload.find(b"\0", decimal_pos)
            if end < 0 or end - decimal_pos > size - len(output):
                raise ValueError("invalid SXD2 decimal length")
            token = view[decimal_pos:end]
            if not FLOAT.fullmatch(token):
                raise ValueError("invalid SXD2 decimal text")
            output.extend(token)
            decimal_pos = end + 1
        else:
            if kind == DECLARATION:
                delta, declaration_pos = _read_delta(declarations, declaration_pos)
                identity = previous_declaration + delta
                previous_declaration = identity
            else:
                if kind == LAST_REFERENCE and not dual:
                    raise ValueError("unexpected SXD2 reference predictor")
                delta, reference_pos = _read_delta(references, reference_pos)
                base = previous_reference if kind == LAST_REFERENCE else previous_declaration
                identity = base + delta
                previous_reference = identity
            if not 0 <= identity < 1000000000:
                raise ValueError("invalid SXD2 identity")
            token = b"#" + str(identity).encode("ascii")
            if len(output) + len(token) > size:
                raise ValueError("SXD2 output exceeds declared length")
            output.extend(token)
        tail = match.end()
    if (declaration_pos != len(declarations) or reference_pos != len(references)
            or decimal_pos != len(payload) or len(output) + len(literals) - tail != size):
        raise ValueError("invalid SXD2 reconstruction length")
    output.extend(literals[tail:])
    return bytes(output)


def unpack(wire):
    size, digest, profile = _header(wire)
    body = memoryview(wire)[HEADER.size:]
    # Even a two-byte '#0' can become a marker plus five varint bytes.
    bound = 3 * size + 12
    if profile == "split-brotli":
        payload = solar_codec.brotli(body, False, bound)
    else:
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=64 << 20)
        payload = decoder.decompress(body, max_length=bound + 1)
        if not decoder.eof or decoder.unused_data or len(payload) > bound:
            raise ValueError("invalid SXD2 XZ member or payload length")
    original = _restore_payload(payload, size, profile == "dual-floats-tuned")
    if not original.lstrip().startswith(PREFIX) or hashlib.sha256(original).digest() != digest:
        raise ValueError("invalid SXD2 source or digest")
    return original
