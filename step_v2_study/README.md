# STEP transfer trial for preview 0.2

This trial asks how many bytes the shipped preview needs to move a STEP file and restore the exact original. It measures a single complete frame per file, including the header. It preserves text formatting, STEP entities, precision and file contents. CAD geometry, optical performance and query speed require separate experiments.

| Cohort | Files | Original | Best conventional | Preview 0.1 | Preview 0.2 default | Preview 0.2 with Brotli |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| F1 mechanical components | 6 | 953,704 | 98,933 | 32,416 | 28,382 | 26,550 |
| AP242 examples | 6 | 10,292,540 | 1,846,095 | 1,743,508 | 1,647,898 | 1,647,624 |
| Additional NIST edition 2 examples | 3 | 7,520,094 | 1,457,000 | 1,428,936 | 1,373,791 | 1,373,791 |

The default preview reduced total bytes versus its predecessor by 12.44%, 5.48% and 3.86%, respectively. The extra Brotli search improved all six F1 files, one of the six AP242 examples, and none of the three additional examples. These cohorts contain related mechanical files and recurring exporter conventions. Testing different exporters and larger drawings would establish where the advantage carries over. Complete stored sizes are separate from the time and memory spent trying all candidates.

**Comparison.** For each file the conventional column uses the smallest complete result from STPZ (single-entry ZIP DEFLATE at levels 6 and 9), gzip-9, bzip2-9, XZ-6, XZ-9, Zstandard-19 and Brotli-11. Each output was restored and checked. All three codec configurations ran pack, inspect and unpack on every input, with an independent byte comparison. The 45 macOS-authored frames also restored in an Alpine arm64 Linux guest running Python 3.13.13. A further three guest-authored frames covered the two XZ profiles and the Brotli profile and restored on macOS.

**Reader cost.** The v0.2 reader occupies 21,950 bytes and can be supplied once per recipient. On the F1 group, adding a first reader delivery to the default frames yields 50,332 bytes. Include Python and the optional Brotli runtime if your receiver needs those too. The reference reader accepts CNF1, SXD1, SRT2, SXD2 and separate GX01 geometry operations. A new SXD2 frame requires the new reader.

## Reproduce

Use Python 3.9 or newer, its standard compression libraries, and the Brotli and Zstandard command-line tools on PATH. The external tools supply comparison controls. Only optional Brotli frames require an external decoder during ordinary use.

From the repository or replication kit root, run:

    python3 step_v2_study/replay.py --group F1 --out f1-replay.json

Omit the group argument to run all 15. The other group identifiers are AP242 and fresh. The script downloads the pinned public archives, verifies source hashes, and runs each released reader with fresh paths. Use --input-dir to reuse source files by their exact manifest names, and --v1 to supply the original v0.1 reader. The dedicated release kit includes both readers. The full comparison can take several minutes and reserves an XZ-9 dictionary for its conventional benchmark. Repeated encodes can vary in cost and compressor revisions can change the encoded bytes. Every restored source must match exactly.

* [Input sources and content hashes](manifest.json)
* [Per-file selection, frame hashes and sizes](results.json)
* [Per-file conventional control sizes](control-sizes.json)
* [Cross-platform restore evidence](linux-cross-read.json)
* [Replay](replay.py) and [complete control settings](controls.py)

This kit redistributes the scripts and measurements. Each source drawing stays with its originating publisher under its own terms.
