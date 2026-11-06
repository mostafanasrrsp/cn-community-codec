# SXD2 STEP frame, preview 0.2

SXD2 preserves STEP Part 21 text as original bytes. Matching input starts with ISO-10303-21; after optional whitespace, fits within 8 MiB, and contains none of the reserved bytes 0x1c through 0x1f. Other eligible candidates remain available to the archive selector. The encoder verifies the entire winning frame using the same decoder as unpack.

The 41-byte header consists of ASCII SXD2, a little-endian unsigned 32-bit original byte count, the 32-byte SHA-256 digest of the original, and one profile byte. Profile 1, split-tuned, and profile 2, dual-floats-tuned, carry a single XZ member. Profile 3, split-brotli, uses the split-tuned payload layout and an external Brotli encoder and decoder.

Split-tuned uses two little-endian unsigned 32-bit lengths for literal bytes and declaration bytes, followed by those streams and the reference bytes. Markers 31 and 30 stand for declaration and reference respectively. Both identifiers are differences from the last declaration, initially zero, zigzag-encoded using unsigned base-128 variable-length integers. Each identifier reconstructs its original # and decimal digits.

Dual-floats-tuned adds a third 32-bit length for the reference stream. A fourth stream holds the original decimal literals, each followed by a zero byte. Marker 28 refers to the next such token. Marker 29 chooses the previous reference rather than the previous declaration as predictor. Literal text, whitespace, comments and exact decimal spelling survive the round trip. See the reference implementation for lexical matching and validation details.

The decompressed stream bound is three times the original length plus 12 bytes. The reference XZ decoder caps its memory at 64 MiB and accepts exactly one member. Restore checks stream consumption, reconstructed length, marker validity, STEP prefix and original SHA-256. Keep using the v0.2 reader for new frames and compare recovered bytes before discarding an original.

[Reference source](step_delta_v2.py) · [Study](../step_v2_study/README.md)
