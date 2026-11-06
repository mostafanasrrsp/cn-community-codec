# Corridor Numerics Community Codec

An experimental, offline Python tool for packing one file and restoring its original bytes. Try it on a copy of your own file, see which method won, and share a result that someone else can reproduce.

**[Download the preview kit and studies](https://github.com/mostafanasrrsp/cn-community-codec/releases/tag/v0.1.0-preview)** · **[Report a result or problem](https://github.com/mostafanasrrsp/cn-community-codec/issues)** · **[Codec research](https://corridornumerics.com/codec.html)**

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

Six public STEP AP242 files totaled 10,292,540 original bytes. The preview stored 1,743,508 bytes. Choosing the smallest of eight conventional outputs for each file took 1,846,095 bytes. That is 5.56% fewer bytes on these six files. The specialized method spends more time packing and restoring than a simple ZIP operation. The [AP242 replication kit](https://github.com/mostafanasrrsp/cn-community-codec/releases/download/v0.1.0-preview/AP242-replication.zip) supplies the source-file links, expected digests, per-file results, controls and scripts.

In an earlier mixed 18-file study the saving over the best of six conventional methods or the original was 0.17%. The [kit guide](KIT-GUIDE.md) includes the STEP and solar results, reader-distribution costs and negative results. The [M3 query benchmark](https://github.com/mostafanasrrsp/cn-community-codec/releases/download/v0.1.0-preview/M3-crossover.zip) measures a separate geometry workload.

## Improve it

[Contribute a benchmark, report a bug or propose code](CONTRIBUTING.md). Results where another tool wins are welcome. The preview source is [MIT licensed](LICENSE). Upstream test files retain their own terms. The mathematical background and scientific supplement are in [Aperture Revision 9](https://doi.org/10.5281/zenodo.23985228).
