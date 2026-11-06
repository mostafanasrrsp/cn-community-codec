# Corridor Numerics experimental codec 0.1.0

Two commands answer different research questions. **pack** preserves every byte of one existing file. It tries three established compressors and stores the smallest payload, including the original as a candidate. **geometry-pack** builds a compact queryable representation of a collection of ideal apertures. It verifies a maximum absolute transmission error of 0.010 for every aperture before it writes the stream.

## Try an ordinary file

Use the portable Python app on a machine with Python 3.9 or later and the standard zlib, bzip2 and lzma modules. It runs locally with no downloads, service, credentials or GPU. In a terminal in the folder containing the app:

    python3 cncodec-0.1.0.pyz pack myfile.pdf myfile.cnf
    python3 cncodec-0.1.0.pyz inspect myfile.cnf
    python3 cncodec-0.1.0.pyz unpack myfile.cnf recovered.pdf
    cmp myfile.pdf recovered.pdf

A successful cmp exits silently. Inspect reports the selected method, original and complete packed size, and verified SHA-256. Each package includes 45 bytes for framing and verification. JPEGs, media and archives can grow by up to those 45 bytes. The reference implementation tries candidates in sequence and holds one file in memory. It suits experiments in size; it also spends CPU time to find the smallest candidate. The input limit is 64 MiB per file. The output restores file contents; keep filesystem permissions, extended attributes and directories separately. Always name a fresh output, or use the explicit --force flag to replace an earlier output after verification.

## Try an aperture

Create a UTF-8 CSV named apertures.csv with this example, or use examples/apertures.csv from the source archive.

    id,B00,B01,B10,B11,d,bx,by
    open,1,0,0,1,0,0,0
    square,2,0,0,2,1,0,0
    offset,4,0.25,0,1,1,0.125,-0.25

Run:

    python3 cncodec-0.1.0.pyz geometry-pack apertures.csv apertures.gx01
    python3 cncodec-0.1.0.pyz geometry-verify apertures.csv apertures.gx01
    python3 cncodec-0.1.0.pyz geometry-query apertures.gx01 1 0.5 0

The last command returns transmission **0.75** for the second row. The four B fields are the two physical in-plane edge vectors as the **columns** of a matrix, expressed in one orthonormal plane frame. d is the depth in the same length units. bx and by are dimensionless affine biases in the aperture basis. Query coordinates are directional slopes in that plane frame. Geometry must have positive determinant, nonnegative depth, and zero bias for a flat/open aperture. Decimal and hexadecimal binary64 literals work. The limits are 50,000 rows and 16 MiB of CSV.

This is a derived response sidecar. Row number (starting at zero) gives the link to the source; retain your source file, identifiers, coordinate frames, units, provenance, and any material or construction data. A CAD scene, image or measured light field needs its own extraction and validation. The certificate compares two mathematical response maps on all slopes for each supplied binary64 record. Manufacturing tolerances, physical transmission and importer error require distinct measurements. The stored target ID declares the requested error budget; supply the corresponding source geometry to verify that claim. For file integrity without the source CSV, wrap the GX01 file with the lossless pack command.

## Install, inspect and repeat

The release folder contains a standalone .pyz, a universal Python wheel, a source archive and SHA256SUMS. Verify the supplied local release digests using shasum -a 256 -c SHA256SUMS. If you prefer an installed command:

    python3 -m venv .codec-venv
    .codec-venv/bin/python -m pip install --no-index --no-deps cn_aperture_codec-0.1.0-py3-none-any.whl
    .codec-venv/bin/cncodec --help

The same commands work from the extracted source folder as python3 -m cncodec. Run the included checks with python3 -m unittest discover -s tests -v. FORMAT.md describes the two wire formats and source provenance. The package includes a synthetic three-aperture example. Original research files, project data and third-party test corpora retain their original licenses and are distributed separately. This local candidate uses the MIT license, matching the Revision 9 numerical routines. See LICENSE.

[Revision 9 and public scientific supplement](https://doi.org/10.5281/zenodo.23985228)
