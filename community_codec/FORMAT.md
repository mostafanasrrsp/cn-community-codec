# Codec profiles, version 0.1.0

Values below describe complete wire files. Unknown magic, target IDs, unsupported method codes, malformed lengths and trailing data are errors. Both formats require the caller to name their output. Neither executes embedded programs, extracts embedded paths nor fetches external dictionaries.

## CNF1 single-file lossless transport

The 45-byte prefix is the ASCII magic CNF1, uint8 method, uint64 little-endian original length, and 32 raw SHA-256 bytes of the original contents. The rest of the file is exactly one payload. Method codes in ascending order are 0 (original contents), 1 (zlib-wrapped DEFLATE), 2 (bzip2 stream), and 3 (XZ stream). The encoder retains the first candidate of the smallest byte length and never emits a payload longer than the source. Reference encoder settings are zlib default, bzip2 level 9 and XZ preset 3. Other encoders can generate distinct legitimate bytes. Digest validation covers decoded contents and detects accidental corruption; authenticity requires trusted distribution or signatures.

The implementation caps inputs at 64 MiB and reads at most the declared length plus one byte of decoded output to detect overflow. Length and digest must match, the compressed stream must have terminated, and appended or concatenated streams are rejected. Decoded files are committed only after successful validation. No filesystem or ownership metadata is embedded.

## GX01 global profile with target ID 2

Bytes 0–3 are ASCII GX01. Byte 4 is 2 (tolerance 1/100). Bytes 5–8 are the unsigned little-endian record count. A table of five-bit tags follows, least-significant bit first across bytes. Unused final bits must be zero. Concatenated payloads follow the table in the same order as the input rows. Tag 0 is the flat, unit-response case with no payload. For each family in the following registry the first listed tag describes a centered case, and the next includes a stored two-component bias:

| Tags | Family |
| --- | --- |
| 1, 2 | fixed10 slope |
| 3, 4 | fixed12 slope |
| 5, 6 | binary16 slope |
| 7, 8 | binary32 slope |
| 9, 10 | exact binary64 primitive fallback |
| 11, 12 | binary16 primitives |
| 13, 14 | binary32 primitives |
| 15, 16 | BFP-10 |
| 17, 18 | BFP-12 |
| 19, 20 | 24-bit angle, intrinsic |
| 21, 22 | 32-bit angle, intrinsic |
| 23, 24 | 32-bit angle, ratio |
| 25, 26 | 40-bit angle, ratio |
| 27, 28 | 24-bit angle, short ratio |

Tags 29–31 are reserved. The payload lengths and word layouts are given by standard_charts.py, intrinsic.py and angle_charts.py; test_codec.py includes centered golden vectors for the complete registry and exercises offset decoding. The source primitive is seven binary64 numbers. The decoder reconstructs W = d B⁻¹ and β, or the corresponding approximation, for the normalized tent-product response F(Wp + β). The zero-depth, zero-bias case has F = 1. The certificate bounds the l1 norm of the affine displacement on the corners of both exact and decoded supports using rational arithmetic; the tent product is 1-Lipschitz in that norm. For supported inputs the exact primitive fallback ensures representability. Decoded coefficient values and transmission may differ from the source. A comparison against the source requires its matching row order. Scalar IDs, world-space pose, physical units and original CAD text remain in the host representation.

A GX01 stream can also represent other research targets outside this implementation. This implementation accepts only target 2 and never authorizes a footprint-conditioned or passive-sensor tolerance. Structural validation is possible on stream bytes; checking the certificate requires the corresponding input geometry.

## Provenance

The original Revision 9 study/geometry/run_geometry.py (MIT, Mostafa Nasr) in aperture_revision_9_scientific_supplement.zip supplies the affine mapping, support-corner certificate, and base word layouts. Its SHA-256 is 2668475a4d348dfd487692fc21a8693a1db722be3749e920e0956d33cf4329c8. The middle-path research program supplies the GX01 portfolio, block exponent, intrinsic and gauge-ratio charts. Source snapshots are identified below.

| Original source | SHA-256 |
| --- | --- |
| codec/replay.py | ebe136bcbaadbd6eb681aa6daa173253ecec2001a40003122928e37c7b421df0 |
| intrinsic/intrinsic.py | 14f6073464d15b2332ecf4523838180a92bc97069526240d71d824a3bddb0577 |
| intrinsic/angle_probe.py | fc38d36ee0b06e536756fe6c9f77158a9e92993f22c9058c1f2b0c8caeb78259 |

The release adds independent framing, bounded input checks, verification, a CLI and packaging, and retains the original MIT copyright notice. Dataset and benchmark materials are separate. The standard compressors run through Python's installed libraries. The package ships no compressor binary or trained dictionary.

[Revision 9 DOI and supplement](https://doi.org/10.5281/zenodo.23985228)

## Reference replay on this build

The packaged encoder reproduced the archived full GX01 target-2 streams byte-for-byte for the three 2,000-row research panels. Each encoded record was independently decoded and checked against its original source row using the certificate routine. These panels share the R9 fixture generator and measure compatibility; they do not measure wall-clock performance on deployed CAD scenes.

| Panel | Full stream bytes | SHA-256 |
| --- | ---: | --- |
| Revision 9, released | 20,508 | d09763831bfa29efd425388401205534b44e87f2f71519e8a5785e89e813511e |
| First held-out seed | 20,520 | cdc2a38e78336f84c5c2d2d7e4b979d53e80d10061ac5bdf62ced7c8ad26bd72 |
| Second held-out seed, 986994865 | 20,378 | 4b60c1a61f19805f62e98cf484fc7a3e78223c4dfbce961f4d0312a7f19b380b |
