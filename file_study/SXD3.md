# SXD3 STEP frames

The preview preserves the exact bytes of STEP Part 21 text, including decimal signs, trailing zeros, exponent spelling, whitespace, comments and quoted text. Inputs up to 8 MiB with the `ISO-10303-21;` prefix after optional whitespace qualify. Four byte values, 0x1c through 0x1f, are reserved for lexical markers. The archive selector can use a generic method for other files.

## Envelope

A 41-byte header precedes one compressed payload. At offsets 0, 4, 8 and 40 are respectively ASCII `SXD3`, the original unsigned 32-bit little-endian byte count, the original SHA-256 (32 raw bytes), and the one-byte method ID.

| ID | Profile | Payload | Compression |
| --- | --- | --- | --- |
| 1 | dictionary-xz | Exact decimal dictionary | XZ, one member |
| 2 | dual-floats-brotli | SXD2 dual lexical streams | Standard Brotli |
| 3 | dictionary-brotli | Exact decimal dictionary | Standard Brotli |

Method 2 uses the complete uncompressed payload layout of SXD2 method 2. Methods 1 and 3 share a layout. Pack can choose method 1 by default and offers methods 2 and 3 with `--with-brotli`. An SXD3-capable reader handles these new frames. The current reader also accepts earlier formats. [SXD2 specification](SXD2.md)

## Dictionary payload

Five consecutive little-endian unsigned 32-bit lengths identify the text, declaration, reference, dictionary and index streams, in that order. Those five streams appear next; the remainder is the literal-decimal stream. Text, declarations and references use the SXD2 dual rules. Every 0x1c marker in text consumes one dictionary index, in order. Other text, including NUL outside transformed decimals, retains its original spelling.

A dictionary entry is a unique ASCII decimal spelling of at most 128 bytes followed by one NUL. Valid spellings match `[+-]?[0-9]+\.[0-9]+(?:E[+-]?[0-9]+)?` in full. The first entry has index 1. Values 0 through 127 take one byte. Values 128 through 16383 take two bytes: the first stores the low seven bits with bit 7 set, and the second stores the remaining seven bits in the range 1 through 127. Index zero consumes a complete NUL-terminated spelling from the literal-decimal stream. It must be a valid decimal absent from the dictionary. Literal lengths are bounded by the original file length. Every dictionary entry must be used at least twice.

The reference encoder counts the first 65,536 distinct eligible spellings, continuing to count their repeats. It selects up to 16,383 repeated spellings, ordered by descending occurrence count and then lexical byte order. The order is an encoder choice. The frame carries the entire dictionary. Equal numeric values with different spellings can take separate entries.

## Restore and validation

A decoder bounds each stream before parsing, rejects duplicate entries, malformed indexes, invalid spellings, unknown methods and unconsumed data, and enforces the original byte count throughout reconstruction. Dual-mode declaration and reference validation follows SXD2. Restore checks the STEP eligibility and the original SHA-256 before returning any bytes.

For an original size of *n*, the decompressed dictionary payload limit is 6*n* + 20 bytes and the dual lexical payload limit is 3*n* + 12 bytes. Frames are bounded to 6 × 8 MiB + 65,536 bytes. XZ decoding uses a 64 MiB decoder memory limit. The optional Brotli path bounds its output and disallows the large-window extension. SHA-256 checks content integrity; verification of authorship requires a trusted external signature or digest. [Reference implementation](step_delta_v3.py) · [Brotli stream specification](https://www.rfc-editor.org/rfc/rfc7932.html#section-9.1)
