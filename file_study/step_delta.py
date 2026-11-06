"""SXD1 research profile: exact lexical reference separation for STEP Part 21.

The file's literal text and predicted entity IDs are separate streams inside one XZ
member. Only canonical decimal identities up to nine digits are transformed.
Transforming a comment or a quoted reference is also exactly reversible.
"""
import hashlib
import lzma
import re
import struct

HEADER = struct.Struct('<4sI32s')
LIMIT = 8 << 20
REF, DECL = 30, 31
TOKEN = re.compile(rb'#(0|[1-9][0-9]{0,8})(?![0-9])([ \t]*(?==))?')


def append_number(buf, number):
    while number >= 128:
        buf.append((number & 127) | 128)
        number >>= 7
    buf.append(number)


def pack(raw):
    if len(raw)>LIMIT or not raw.lstrip().startswith(b'ISO-10303-21;') or b'\x1e' in raw or b'\x1f' in raw:
        raise ValueError('Requires STEP text <=8 MiB without the two reserved control bytes')
    literals, numbers = bytearray(), bytearray()
    previous = end = 0
    for match in TOKEN.finditer(raw):
        literals.extend(raw[end:match.start()])
        value = int(match[1])
        delta = value-previous
        append_number(numbers, 2*delta if delta>=0 else -2*delta-1)
        if match[2] is not None:
            literals.append(DECL)
            previous = value
        else:
            literals.append(REF)
        end = match.end(1)
    literals.extend(raw[end:])
    joined = struct.pack('<I',len(literals)) + literals + numbers
    return HEADER.pack(b'SXD1',len(raw),hashlib.sha256(raw).digest()) + lzma.compress(joined,preset=6)


def unpack(wire):
    if len(wire)<HEADER.size or len(wire)>3*LIMIT+65536:
        raise ValueError('Unknown or oversized frame')
    magic,size,expected = HEADER.unpack_from(wire)
    if magic!=b'SXD1' or size>LIMIT:
        raise ValueError('Unsupported frame')
    xz = lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=64<<20)
    # A two-character identity can become a marker and five varint bytes.
    max_payload = 3 * size + 4
    payload = xz.decompress(wire[HEADER.size:], max_length=max_payload + 1)
    if not xz.eof or xz.unused_data or not 4 <= len(payload) <= max_payload:
        raise ValueError('Invalid XZ member or length')
    count = struct.unpack_from('<I',payload)[0]
    if count>len(payload)-4:
        raise ValueError('Invalid literal length')
    literals, numbers = payload[4:4+count], memoryview(payload)[4+count:]
    output = bytearray()
    pos = previous = end = 0
    for match in re.finditer(b'[\x1e\x1f]',literals):
        output.extend(literals[end:match.start()])
        value = 0
        for shift in range(0,35,7):
            if pos >= len(numbers):
                raise ValueError('Truncated identity')
            byte = numbers[pos]
            pos += 1
            value |= (byte & 127)<<shift
            if not (byte & 128):
                break
        else:
            raise ValueError('Oversized identity')
        identity = previous + ((value>>1) ^ -(value&1))
        if not 0<=identity<1_000_000_000:
            raise ValueError('Out-of-range identity')
        output.extend(b'#'+str(identity).encode())
        if len(output)>size:
            raise ValueError('Output exceeds declared length')
        if match[0]==bytes([DECL]):
            previous=identity
        end=match.end()
    output.extend(literals[end:])
    if pos!=len(numbers) or len(output)!=size or hashlib.sha256(output).digest()!=expected:
        raise ValueError('Invalid reconstruction')
    return bytes(output)


def main(argv=None):
    """The caller chooses both paths. Publish one new regular output atomically."""
    import argparse
    import os
    import sys
    import tempfile
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('pack', 'unpack'))
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    limit = LIMIT if args.operation == 'pack' else 3 * LIMIT + 65536
    try:
        if not args.input.is_file():
            raise ValueError('Input must be a regular file')
        if os.path.lexists(args.output):
            raise FileExistsError('Choose an unused output filename')
        with args.input.open('rb') as source:
            data = source.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Input exceeds this preview’s size limit')
        result = pack(data) if args.operation == 'pack' else unpack(data)
        # A hard link publishes only a complete frame and never replaces a target.
        staged = tempfile.NamedTemporaryFile(dir=args.output.parent, delete=False)
        temporary = Path(staged.name)
        try:
            with staged:
                staged.write(result)
            os.link(temporary, args.output)
        finally:
            temporary.unlink()
    except (ValueError, OSError, lzma.LZMAError) as exc:
        print(f'SXD1: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
