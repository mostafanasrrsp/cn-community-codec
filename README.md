# Corridor Numerics Community Codec

An experimental, offline Python tool for packing one file and restoring its original bytes. Try it on a copy of your own file, see which method won, and share a result that someone else can reproduce.

**[Download the preview kit and studies](https://github.com/mostafanasrrsp/cn-community-codec/releases/tag/v0.2.0-preview)** · **[Report a result or problem](https://github.com/mostafanasrrsp/cn-community-codec/issues)** · **[Codec research](https://corridornumerics.com/codec.html)**

## Try it in two minutes

Extract the preview kit or clone this repository. In its top-level folder, run the following commands with Python 3.9 or newer. On Windows, use the Python launcher in place of `python3`.

```sh
python3 cn-preview.pyz pack community_codec/examples/apertures.csv trial.cn
python3 cn-preview.pyz inspect trial.cn
python3 cn-preview.pyz unpack trial.cn restored.csv
```

The output shows the complete stored size and the original content digest. On macOS or Linux, run `cmp community_codec/examples/apertures.csv restored.csv` to check the two files byte for byte. Then try a file of your own using fresh output names.

## What the preview handles

* **Single-file transport** covers inputs up to 64 MiB. It compares raw storage, zlib, bzip2 and XZ. Eligible plain-text STEP and fixed-width NOAA SURFRAD files up to 8 MiB get an additional structure-aware comparison. The encoder decodes and checks the winning frame before writing it. An incompressible file can grow by the 45-byte ordinary frame header. The archive carries file contents only.
* **Queryable aperture geometry** is a separate operation. Its GX01 representation bounds transmission error at 0.010 for supported ideal straight-prism geometries. To create and check one, follow the [geometry example](KIT-GUIDE.md#query-an-aperture) and [format description](community_codec/FORMAT.md).

## What has been measured

Version 0.2 adds lossless STEP profiles. In a trial on 15 public engineering files, the default configuration used fewer bytes than version 0.1 in each of three groups. Every restored file matched the original byte for byte.

| STEP sample | v0.1 bytes | v0.2 default bytes | v0.2 with Brotli bytes |
| --- | ---: | ---: | ---: |
| Six F1 bench components | 32,416 | 28,382 | 26,550 |
| Six AP242 examples | 1,743,508 | 1,647,898 | 1,647,624 |
| Three additional NIST examples | 1,428,936 | 1,373,791 | 1,373,791 |

The portable default needs only Python. To try the additional Brotli candidate, install the Brotli command-line tool and add `--with-brotli` when packing. A Brotli frame also needs that tool to restore. Include the 21,950-byte reader once when estimating a first transfer to someone with Python. For the inputs above, the full study compares eight conventional tools/settings, records complete frame sizes and verifies macOS to Linux compatibility. [Study, per-file results and replay instructions](step_v2_study/README.md) · [Download the replication kit](https://github.com/mostafanasrrsp/cn-community-codec/releases/download/v0.2.0-preview/STEP-v2-replication.zip)

In an earlier mixed 18-file study the saving over the best of six conventional methods or the original was 0.17%. The [kit guide](KIT-GUIDE.md) includes the STEP and solar results, reader-distribution costs and negative results. The [M3 query benchmark](https://github.com/mostafanasrrsp/cn-community-codec/releases/download/v0.1.0-preview/M3-crossover.zip) measures a separate geometry workload.

## Improve it

[Contribute a benchmark, report a bug or propose code](CONTRIBUTING.md). Results where another tool wins are welcome. The preview source is [MIT licensed](LICENSE). Upstream test files retain their own terms. The mathematical background and scientific supplement are in [Aperture Revision 9](https://doi.org/10.5281/zenodo.23985228).
