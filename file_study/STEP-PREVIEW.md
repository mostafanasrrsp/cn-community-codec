# A reversible STEP experiment

SXD1 is an experimental single-file encoding for plain-text ISO 10303-21 CAD exchange files. It separates entity numbers such as `#135` from the surrounding text, predicts each number relative to the last declaration, and compresses the two streams together with XZ. Decoding restores the exact original bytes, including geometry, whitespace, comments and line endings. CAD applications open the restored STEP file. Use standard STEP or ZIP-based STPZ for exchange with existing tools. [CAx Implementor Forum compression practice](https://www.mbx-if.org/home/wp-content/uploads/2024/05/rec_prac_file_compression_v12.pdf)

## Try your own file

In a local folder on a filesystem that supports hard links, run the following with Python 3.9+ and the standard `lzma` module. Choose fresh output names. Retain your original.

```sh
python3 step_delta.py pack original.step trial.sxd1
python3 step_delta.py unpack trial.sxd1 restored.step
cmp original.step restored.step
```

A silent `cmp` means the files match. The tool has no dependency on a CAD program. It accepts one regular STEP file up to 8 MiB, with its Part 21 header and without ASCII control bytes 30 or 31. It stores one file’s bytes, omits filename/permissions/timestamps, writes the one destination you name and refuses to overwrite an existing path. A newly compressed file can grow. For source files larger than the cap use your usual compressor.

Use trusted local files and an output folder you control. A 64 MiB XZ decoder-memory limit and explicit length checks bound the decoder. The embedded SHA-256 detects corruption. Anyone able to change the frame can also replace its hash. Security review and independent fuzz testing are still open.

## Reproduce the transfer test

With `step_delta.py`, `reproduce_step.py` and `step-transfer-results.json` in the same directory, run:

```sh
python3 reproduce_step.py --sxd1-only
python3 reproduce_step.py
```

The first command verifies the STEP profile using the Python standard library. The second also needs `zstd` and `brotli` on PATH. Both retrieve the six original public files and check source hashes before testing. The evidence JSON records each upstream URL and measured wire size. Incidental backend-version differences are reported. No CAD files accompany this kit.

We fixed the subset as the first six entries in the STEP Tools AP203 example index, in publisher order, after developing the method on five other files. Together the six files occupied 772,043 bytes. The measured SXD1 frames totaled 45,568 bytes and all six restored exactly. For each file we chose the smallest complete frame from ZIP-Deflate9, gzip9, bzip2-9, zstd19, Brotli11, XZ6 and XZ9; that deliberately strong comparison totaled 89,574 bytes. SXD1 used 49.13% fewer bytes. Standard one-entry ZIP-Deflate9 totaled 150,122 bytes. One of the five development inputs did better with plain Brotli11. The six files came from a second distributor. The AP203 AS1 assembly shares plate, L-bracket, bolt, nut and rod identities with the AP214 AS1 development model. Treat them as related designs despite different exporters and distinct source hashes. Excluding the related transfer file leaves five files, 693,377 original bytes, 40,324 SXD1 bytes and 81,826 bytes for the best conventional frame per file (50.72% fewer bytes). The effect survives this check. A second exporter population and independent lab are still needed. [STEP Tools sample index](https://steptools.com/docs/stpfiles/ap203/index.html)

On the six transfer files the Python implementation took 68.7 ms to encode and 46.3 ms to decode in memory, summing per-file medians of five warm trials on an Apple M3. Direct XZ6 took 113.6 ms and 5.0 ms respectively. Measure both size and opening time for your own workload.
