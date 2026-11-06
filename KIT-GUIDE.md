# Corridor Numerics Community Codec • Experimental preview 0.2.0

Pack a single file, restore the exact bytes, and see which method won. A second, explicitly selected tool creates queryable aperture geometry for the ideal absorbing straight-prism model in Revision 9. Everything runs locally. The software is free under the MIT license. The public studies below can be reproduced from the linked upstream data.

## First two minutes

Unzip this kit, open a terminal in the extracted directory and run these commands. Python 3.9 or newer with its standard zlib, bz2 and lzma modules is sufficient. On Windows use the Python 3 launcher in place of python3.

    python3 cn-preview.pyz pack community_codec/examples/apertures.csv trial.cn
    python3 cn-preview.pyz inspect trial.cn
    python3 cn-preview.pyz unpack trial.cn restored.csv

The pack and inspect results show the selected method, complete stored size and SHA-256 of the original contents. On macOS or Linux, compare the two files with this command. A successful comparison exits silently.

    cmp community_codec/examples/apertures.csv restored.csv

Try the same three commands on a copy of your own STEP file, image or document. Use fresh output names. Keep the original. The preview restores file contents. Paths, permissions, resource forks and extended attributes need separate handling. Run it on files you trust. If byte savings are the objective, compare the complete trial file against your usual compressor, and record any case where the original is already smaller.

## Which method runs?

* **Ordinary files** up to 64 MiB: CNF1 compares raw storage, zlib, bzip2 and XZ. For incompressible input the complete output may grow by 45 bytes.
* **Plain-text STEP Part 21** up to 8 MiB: the tool also tries SXD1 on matching inputs. It separates references from surrounding text and describes each reference by its difference from the last declaration, then compresses the resulting bytes with XZ. Version 0.2 also tries two SXD2 XZ profiles that separate literal and numeric streams. Optionally try a third with `--with-brotli`. Restore to STEP before opening the model in CAD.
* **Recognized fixed-width NOAA SURFRAD records** up to 8 MiB: the tool also tries grouping matching byte positions across records and then applying XZ. Add `--with-brotli` to the pack command to try Brotli as well. Reading a winning Brotli frame requires the Brotli executable on PATH. Other formats and station layouts use the ordinary path.
* The encoder keeps the smallest eligible complete frame and verifies it by decoding before writing. The optional system utilities for reference benchmarks are listed in the study guides. Compressor search costs time and memory. Single-file limits make this an experiment on modest inputs.

## Query an aperture

    python3 cn-preview.pyz geometry-pack community_codec/examples/apertures.csv example.gx01
    python3 cn-preview.pyz geometry-verify community_codec/examples/apertures.csv example.gx01
    python3 cn-preview.pyz geometry-query example.gx01 1 0.5 0

The last command returns transmission 0.75. Row indices start at zero. GX01 bounds the ideal transmission error at 0.010 over directions for each supplied aperture. Keep the input geometry, stable identifiers and coordinate frames with the application using this sidecar. Recovering an original file calls for the ordinary lossless pack/unpack commands above.

## Version 0.2 STEP study

The default v0.2 preview stored six F1 STEP files in 28,382 bytes, six AP242 examples in 1,647,898 bytes, and three additional NIST examples in 1,373,791 bytes. The corresponding v0.1 sizes were 32,416, 1,743,508 and 1,428,936 bytes. The 21,950-byte v0.2 reader restores all earlier preview formats. See the [15-file study and replay](step_v2_study/README.md) for exact control settings, per-file results and cross-platform restoration.

## Earlier measurements with version 0.1

Three comparisons show where to try the preview first. On six publicly downloadable AP203 STEP files the specialized frames took **45,568 bytes** versus **89,574 bytes** for the smallest of seven conventional frames per file. Decoding in memory took about nine times as long as direct XZ6. On six NOAA station-days our smallest frames took **126,787 bytes** versus **129,892 bytes** for an established Zarr configuration, a **2.39%** advantage attributable to framing. In the full 18-file mixed local test the preview saved **0.17%** beyond the best of six ordinary methods or retaining the original. The release includes the public inputs' URLs, hashes and reproduction scripts. The private input files and their identities are omitted.

A first delivery changes the comparison. If the recipient already has Python and the comparison tools, sending the 19,049-byte preview reader once brings the six STEP files to 64,617 bytes, still 24,957 below the ordinary frames. For the six solar files, the portable XZ profile plus reader totals 147,951 bytes. That is 18,059 bytes more than the Zarr archive. A reader installed for later transfers can be reused.

The aperture calculation is separately timed. In a published six-opening building with a year of weather, 475 of 11,993 direct-sun queries qualified for safe skipping. The initial paired M3 pass measured a 1.041× CPU speed ratio and a 0.967× Metal dispatch-through-completion ratio. Count file import and preparation if your workload opens a building only once. Use the included replay to test your machine.

On an incompressible 64 MiB generated input the packaged command used 342 MiB peak resident memory, took 17.44 seconds to pack, and added 45 bytes on the M3 test machine. That one boundary trial illustrates the cost of trying every eligible method. This prototype is intended for replication and trusted local inputs. The v0.2 study includes a separate Linux reader check. Hostile-input evaluation and streaming support remain future work.

* [STEP measurements](file_study/STEP-PREVIEW.md) and [per-file results](file_study/step-transfer-results.json). Run reproduce_step.py from its directory with --sxd1-only to fetch and hash-check the six examples before testing. time_step.py compares in-memory encode and decode against matched XZ.
* [Solar measurements](solar_study/README.md) and [frozen trial design](solar_study/Protocol.md). The guide covers whole-file controls and the published inputs.
* [M3 CPU and Metal replay](building_study/README.md). The original building and weather data can be downloaded at the pinned source revisions in the guide.
* [Format notes](community_codec/FORMAT.md) explain the general container and GX01. The optional wheel in community_codec/dist installs the core CNF1/GX01 package. The top-level cn-preview.pyz includes the STEP and solar profiles.
* To rebuild the self-contained app from the included source, run python3 preview/build_preview.py. The result in preview/cn-preview.pyz should match the copy at the top level.
* Run python3 preview/test_preview.py to check the packaged commands. Run python3 preview/check_preview.py --public-only --output public-results.json to test the combined command on pinned public files. Run the core suite from community_codec with python3 -m unittest discover -s tests.
* To check this kit after extraction on macOS, run shasum -a 256 -c SHA256SUMS. Hashes detect accidental corruption. Source observations, proprietary CAD and third-party executable binaries are obtained separately.
* Useful test feedback includes file format and exporter, original and packed bytes, comparison method and level, hardware and software versions, encode/decode times, and whether the restored digest matched. A digest and these measurements let you report results without sharing the file.

[Revision 9 scientific record](https://doi.org/10.5281/zenodo.23985228) · [Experiment C companion](https://doi.org/10.5281/zenodo.24001923)
