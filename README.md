# Corridor Numerics Community Codec

An experimental, offline Python tool for packing one file and restoring its original bytes. Try it on a copy of your own file, see which method won, and share a result that someone else can reproduce.

**[Download the preview kit and studies](https://github.com/mostafanasrrsp/cn-community-codec/releases/tag/v0.3.0-preview)** · **[Report a result or problem](https://github.com/mostafanasrrsp/cn-community-codec/issues)** · **[Codec research](https://corridornumerics.com/codec.html)**

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

Version 0.3 adds a dictionary for repeated decimal spellings in STEP drawings. For example, identical coordinate strings can share one entry while `1.0` and `1.00` retain their different bytes. The encoder compares the new methods with the earlier ones. It checks the winning frame by restoring the original file.

| STEP files | Mode for both versions | v0.2 bytes | v0.3 bytes | Bytes saved |
| --- | --- | ---: | ---: | ---: |
| Four additional drawings (three public, one private) | Default | 452,008 | 451,716 | 292 (0.065%) |
| Same four drawings | With Brotli | 452,008 | 444,905 | 7,103 (1.57%) |
| Fifteen previously studied drawings | Default | 3,050,071 | 3,042,023 | 8,048 (0.26%) |
| Same fifteen drawings | With Brotli | 3,047,965 | 3,033,999 | 13,966 (0.46%) |

On the **three public additional drawings**, both defaults produced 444,035 bytes in total. With Brotli, 0.3 used 437,354 bytes. These are complete file sizes before distributing the reader. The default needs only Python. To try the optional profiles, install the Brotli command-line tool and add `--with-brotli` when packing. A winning Brotli frame also needs that tool to restore. Trying more methods adds encoding work. [Per-file data and replay instructions](step_v3_study/README.md) · [Download the two-version replication kit](https://github.com/mostafanasrrsp/cn-community-codec/releases/download/v0.3.0-preview/STEP-v3-replication.zip) · [Earlier eight-control comparison](step_v2_study/README.md)

In an earlier mixed 18-file study the saving over the best of six conventional methods or the original was 0.17%. The [kit guide](KIT-GUIDE.md) includes the STEP and solar results, reader-distribution costs and negative results. The [M3 query benchmark](https://github.com/mostafanasrrsp/cn-community-codec/releases/download/v0.1.0-preview/M3-crossover.zip) measures a separate geometry workload.

## Improve it

[Contribute a benchmark, report a bug or propose code](CONTRIBUTING.md). Results where another tool wins are welcome. The preview source is [MIT licensed](LICENSE). Upstream test files retain their own terms. The mathematical background and scientific supplement are in [Aperture Revision 9](https://doi.org/10.5281/zenodo.23985228).

Watch *Oblique*, our 24-second Blender film of three v4 device design studies, on the [Corridor Numerics community page](https://corridornumerics.com/community.html#film).
