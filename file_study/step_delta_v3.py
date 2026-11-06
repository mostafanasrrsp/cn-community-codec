"""Lossless SXD3 STEP profiles. Decimal spelling is preserved exactly."""
import hashlib
import lzma
import struct

import solar_codec
import step_delta_v2 as v2

MAGIC = b"SXD3"
HEADER = struct.Struct("<4sI32sB")
DUAL_WIDTHS = struct.Struct("<III")
DICT_WIDTHS = struct.Struct("<IIIII")
METHODS = {"dictionary-xz": 1, "dual-floats-brotli": 2, "dictionary-brotli": 3}
NAMES = {value: name for name, value in METHODS.items()}
MAX_ENTRIES = 16383
MAX_OBSERVED = 65536
MAX_ENTRY_BYTES = 128
FRAME_LIMIT = 6 * v2.LIMIT + 65536


def tokens(buf):
    """Yield NUL-terminated lexemes without splitting the whole input into objects."""
    start = 0
    while start < len(buf):
        end = buf.find(b"\0", start)
        if end < 0:
            raise ValueError("unterminated decimal text")
        yield buf[start:end]
        start = end + 1


def dictionary_payload(dual):
    text_len, decl_len, ref_len = DUAL_WIDTHS.unpack_from(dual)
    split = DUAL_WIDTHS.size + text_len + decl_len + ref_len
    decimals = dual[split:]
    counts = {}
    for token in tokens(decimals):
        if len(token) <= MAX_ENTRY_BYTES and (token in counts or len(counts) < MAX_OBSERVED):
            counts[token] = counts.get(token, 0) + 1
    ranked = sorted((token for token, count in counts.items() if count > 1),
                    key=lambda token: (-counts[token], token))[:MAX_ENTRIES]
    numbers = {token: number for number, token in enumerate(ranked, 1)}
    dictionary = b"".join(token + b"\0" for token in ranked)
    codes = bytearray()
    literals = bytearray()
    for token in tokens(decimals):
        index = numbers.get(token, 0)
        if index < 128:
            codes.append(index)
        else:
            codes.extend(((index & 127) + 128, index >> 7))
        if not index:
            literals.extend(token)
            literals.append(0)
    widths = DICT_WIDTHS.pack(text_len, decl_len, ref_len, len(dictionary), len(codes))
    return b"".join((widths, dual[DUAL_WIDTHS.size:split], dictionary, codes, literals))


def restore_dictionary(payload, size):
    if len(payload) < DICT_WIDTHS.size:
        raise ValueError("truncated dictionary header")
    text_len, decl_len, ref_len, dictionary_len, codes_len = DICT_WIDTHS.unpack_from(payload)
    number_start = DICT_WIDTHS.size
    dictionary_start = number_start + text_len + decl_len + ref_len
    codes_start = dictionary_start + dictionary_len
    literals_start = codes_start + codes_len
    if (text_len > size or literals_start > len(payload)
            or dictionary_len > min(MAX_ENTRIES * (MAX_ENTRY_BYTES + 1), size)):
        raise ValueError("out-of-bounds dictionary stream length")
    entries = []
    found = set()
    for value in tokens(payload[dictionary_start:codes_start]):
        if (len(entries) == MAX_ENTRIES or len(value) > MAX_ENTRY_BYTES
                or not v2.FLOAT.fullmatch(value) or value in found):
            raise ValueError("invalid or duplicate dictionary entry")
        found.add(value)
        entries.append(value)
    occurrences = payload.count(bytes([v2.DECIMAL]), number_start, number_start + text_len)
    if not occurrences <= codes_len <= occurrences * 2 or occurrences * 3 > size:
        raise ValueError("invalid index count")
    pos = codes_start
    literal_pos = literals_start
    spelling_bytes = 0
    restored = bytearray()
    uses = [0] * len(entries)
    for _ in range(occurrences):
        if pos >= literals_start:
            raise ValueError("truncated dictionary index")
        index = payload[pos]
        pos += 1
        if index & 128:
            if pos >= literals_start or not 1 <= payload[pos] < 128:
                raise ValueError("noncanonical dictionary index")
            index = (index & 127) + (payload[pos] << 7)
            pos += 1
        if index:
            if index > len(entries):
                raise ValueError("unknown dictionary index")
            value = entries[index - 1]
            uses[index - 1] += 1
        else:
            end = payload.find(b"\0", literal_pos)
            if end < 0 or end - literal_pos > size - spelling_bytes:
                raise ValueError("unterminated or oversized literal spelling")
            value = payload[literal_pos:end]
            if not v2.FLOAT.fullmatch(value) or value in found:
                raise ValueError("invalid dictionary literal")
            literal_pos = end + 1
        spelling_bytes += len(value)
        if spelling_bytes > size:
            raise ValueError("dictionary output exceeds original size")
        restored.extend(value)
        restored.append(0)
    if pos != literals_start or literal_pos != len(payload) or any(n < 2 for n in uses):
        raise ValueError("unused dictionary data")
    if DUAL_WIDTHS.size + text_len + decl_len + ref_len + len(restored) > 3 * size + DUAL_WIDTHS.size:
        raise ValueError("expanded lexical payload exceeds size limit")
    return b"".join((DUAL_WIDTHS.pack(text_len, decl_len, ref_len), payload[number_start:dictionary_start], restored))


def pack(raw, method):
    """Encode one named profile. The selector may reuse its transformed streams."""
    if method not in METHODS or not v2.eligible(raw):
        raise ValueError("unsupported SXD3 profile or STEP source")
    dual = v2._split(raw, True)
    payload = dual if method == "dual-floats-brotli" else dictionary_payload(dual)
    return pack_payload(payload, len(raw), hashlib.sha256(raw).digest(), method)


def pack_payload(payload, size, digest, method):
    """Frame a prepared payload with the original byte count and SHA-256."""
    if method == "dictionary-xz":
        body = lzma.compress(payload, format=lzma.FORMAT_XZ, filters=v2.TUNED_XZ)
    else:
        body = solar_codec.brotli(payload, True, FRAME_LIMIT - HEADER.size)
    if len(body) + HEADER.size > FRAME_LIMIT:
        raise ValueError("frame exceeds limit")
    return HEADER.pack(MAGIC, size, digest, METHODS[method]) + body


def _header(frame):
    if not HEADER.size < len(frame) <= FRAME_LIMIT:
        raise ValueError("invalid SXD3 frame length")
    magic, size, digest, number = HEADER.unpack_from(frame)
    if magic != MAGIC or number not in NAMES or not len(v2.PREFIX) <= size <= v2.LIMIT:
        raise ValueError("invalid SXD3 header")
    return size, digest, NAMES[number]


def profile_name(frame):
    return _header(frame)[2]


def unpack(frame):
    size, digest, method = _header(frame)
    limit = (3 * size + DUAL_WIDTHS.size if method == "dual-floats-brotli"
             else 6 * size + DICT_WIDTHS.size)
    body = frame[HEADER.size:]
    if method == "dictionary-xz":
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=64 << 20)
        payload = decoder.decompress(body, max_length=limit + 1)
        if not decoder.eof or decoder.unused_data or len(payload) > limit:
            raise ValueError("invalid SXD3 XZ member")
    else:
        # RFC 7932 section 9.1 reserves this WBITS prefix. Some CLI builds
        # accept it as a large-window extension; SXD3 uses standard Brotli.
        if body[0] & 0x7f == 0x11:
            raise ValueError("large-window Brotli is outside the SXD3 profile")
        payload = solar_codec.brotli(body, False, limit)
    if method != "dual-floats-brotli":
        payload = restore_dictionary(payload, size)
    restored = v2._restore_payload(payload, size, True)
    if not v2.eligible(restored) or hashlib.sha256(restored).digest() != digest:
        raise ValueError("invalid reconstructed source or digest")
    return restored
