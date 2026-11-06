# SRT2 · exact fixed-width solar trace experiment

Six held-out daily observation files from NOAA SURFRAD contained **2,073,882 original bytes**. SRT2 with byte-column transpose and Brotli quality 11 stored them in **126,787 bytes** and restored every source byte. An established scientific stack using the same kind of shuffle and Brotli, in six complete Zarr archives, used **129,892 bytes**. SRT2’s margin was **3,105 bytes (2.39%)**. Against eight conventional whole-file compressor levels the margin was **36.91%**. The scientific-container control explains why those results are so different.

The transform groups, for example, the tens digit of the same measurement at successive times, followed by its units digit at all those times. Runs of spaces, signs, decimal points, unchanged digits and quality flags become contiguous. This exploits the existing *file layout*. The method consumes no aperture geometry, irradiance model or field calibration. NOAA's two held-out stations use the same fixed-width format. This result supports a community experiment for that file family. General sensor logs, binary arrays, images and irregular CSV require separate tests. Byte-transposition is an established prefilter, including in the HDF5 shuffle filter; the application and numbers here are the research contribution. [HDF5 compression and shuffle](https://support.hdfgroup.org/documentation/hdf5-docs/hdf5_topics/UsingCompressionInHDF5.html)

## Try a single file

Python 3.9+ can run the XZ profile directly. The smaller default uses the Brotli command-line tool on PATH. Each source must have two prefix lines followed by one or more equal-width records including terminators. The file limit is 8 MiB. The codec preserves line endings, missing-value sentinels, the exact representation of every number and every byte in the prefix. Existing destinations are protected. Supply a new destination path for each output. The code and instructions are provided for local experimentation. A cardholder, sensor, network service or training budget is unnecessary.

```sh
curl -fLsS https://gml.noaa.gov/aftp/data/radiation/surfrad/fpk/2020/fpk20032.dat -o fpk20032.dat
python3 solar_codec.py encode --method xz fpk20032.dat fpk20032.srt
python3 solar_codec.py test fpk20032.srt
python3 solar_codec.py decode fpk20032.srt restored.dat
cmp fpk20032.dat restored.dat
```

Using `--method brotli` on this example produces a 19,616-byte complete frame with the reported versions. The frame starts with SRT2, a one-byte backend code, a big-endian uint16 prefix length, uint16 row width, uint32 row count, and 32 bytes of original SHA-256. These 45 bytes precede one compressed stream. The transpose includes each row's line ending. The decoder bounds both input and output and verifies the digest before installing output. XZ decoding also caps codec memory at 96 MiB. A digest detects corruption; use a separate signed manifest for distribution authenticity. Seekable blocks, interoperability with other implementations and adversarial security review remain release work. Avoid passing private traces to any remote service.

## Whole-file results

The layout was frozen using one development day from Bondville, Illinois. The three dates and two unseen stations expose some variation in irradiance, but all files are daily 2020 observations from one agency. The candidate backend that gave the smallest transposed development file was Brotli-11. Applying that single choice to all held-out files permits comparison with an oracle that may choose the smallest stock output per file. Stock XZ happened to win every held-out file. Original upstream filenames identify year and day-of-year. The first and second station results respectively saved **37.24%** and **36.72%** over the strongest stock choices.

| Station / file | Original bytes | Strongest stock bytes | SRT2 Brotli bytes | Savings vs strongest stock |
| --- | ---: | ---: | ---: | ---: |
| Fort Peck / fpk20032 | 345,645 | 31,544 | 19,616 | 37.81% |
| Fort Peck / fpk20183 | 345,645 | 35,404 | 22,798 | 35.61% |
| Fort Peck / fpk20310 | 345,645 | 31,452 | 19,346 | 38.49% |
| Desert Rock / dra20032 | 345,649 | 33,664 | 21,021 | 37.56% |
| Desert Rock / dra20183 | 345,649 | 34,848 | 22,380 | 35.78% |
| Desert Rock / dra20310 | 345,649 | 34,252 | 21,626 | 36.86% |
| **Total** | **2,073,882** | **201,164** | **126,787** | **36.97%** |

Stock totals across the same files were gzip-6 411,730 bytes, bzip2-9 298,884, XZ-6 201,164, zstd-3 421,332, zstd-19 254,337, and Brotli-11 229,938. SRT2 saved **44.86% over stock Brotli-11**. These are file sizes. Selection time, streaming throughput and battery life require separate measurements. XZ-6 and single-thread zstd-19 offer different speed/size trade-offs.

## Reproduce and inspect

The size sweep requires Python, the Brotli CLI and the zstd CLI on PATH. Run the following from this directory. It fetches seven selected upstream files into a scratch directory, verifies the reference digest when results.json is present and compares restored bytes. No third-party observations or codec binaries are included here.

```sh
python3 replay.py --cache ./solar-inputs --output ./local-sweep.json
python3 check_profile.py ./solar-inputs --output ./local-profile.json
```

[Protocol](Protocol.md) · [Original sizes, source URLs, digests, and six-backend sweep](results.json) · [Validated SRT2 frame sizes and hashes](profile-results.json) · [NOAA dataset metadata](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc%3AC00540) · [NOAA SURFRAD data archive](https://gml.noaa.gov/aftp/data/radiation/surfrad/)

The development sweep used a 13-byte experimental SRT1 header across all transformed arms. The SRT2 user tool adds a 32-byte source digest and offers the two best development backends. Every SRT2 number above includes that additional cost. The profile verification also exercised wrong magic, unknown mode, oversized declared output, truncated data, trailing data, bad digests, unequal row lengths, embedded binary bytes, and CRLF. Each of the seven original files round-tripped with both shipping backends. Research use of these public observations carries no implication of NOAA endorsement.

## Sensitivity to stronger whole-file settings

After freezing the six-backend sweep, we tested single-thread XZ-9e and zstd-22 on the exact same six held-out sources and verified all twelve restorations. The eight-setting oracle improved the conventional total from **201,164 to 200,972 bytes**, selecting XZ-9e on two Fort Peck days and XZ-6 on the other four days. SRT2-Brotli's **126,787 bytes** give a **36.91%** saving against this stronger comparator. Fixed XZ-9e totaled 201,260 bytes; fixed zstd-22 totaled 254,237 bytes. No parameters of SRT2 changed. To repeat after obtaining the inputs, run `python3 sensitivity.py ./solar-inputs --output ./local-sensitivity.json`. [Per-file results and versions](sensitivity-results.json)

## What existing scientific containers can already do

We ran this sensitivity check after fixing the SRT2 codec. All three containers store each entire 240-byte record as one element. Their own filter implementation can therefore group the same byte position from successive observations. Each archive includes both prefix lines, source SHA-256, shape, filter settings and format overhead. Every restoration started from the serialized container and matched the original bytes. No third-party compression implementation was modified.

| Complete representation on the same six station-days | Total bytes | SRT2 reduction vs control |
| --- | ---: | ---: |
| XZ-9e with its native delta filter at stride 240, directly on the original file | 187,748 | 32.47% |
| HDF5 opaque record + byte shuffle + gzip-9, one day per chunk | 157,271 | 19.38% |
| Blosc2 CFrame + byte shuffle + Zstd level 9, one day per chunk | 132,981 | 4.66% |
| Zarr v2 ZipStore + byte shuffle + Brotli-11, outer ZIP DEFLATE | **129,892** | **2.39%** |
| SRT2 + Brotli-11 | **126,787** | — |

The best Zarr setting won every day among 36 container configurations. Across HDF5 and Blosc2 the sweep varied chunk sizes, with ordinary, byte-shuffled or bit-shuffled records as applicable. Zarr comparisons included XZ, Zstd and Brotli, optional byte delta after shuffling, and stored or DEFLATE-compressed ZIP entries. The script additionally inflated each first HDF5 chunk and each Zarr body to verify the actual transposed byte order. **216 complete container round trips** and **six native-XZ delta round trips** passed.

The six Zarr body chunks used **126,077 bytes** after all filters and compression. Metadata and ZIP framing used **3,815 bytes**, including source prefixes. SRT2 compressed its prefixes together with the transposed bodies into **126,517 bytes** and added **270 bytes** of headers. The smaller complete SRT2 files reflect where and how the two formats store metadata. Zarr’s established filters already capture most of the reduction; the compressed body chunks are slightly smaller than the SRT2 streams, whose content also includes the prefixes. Chunk access, metadata discovery and interoperability are separate considerations. This study measured complete single-day sizes and exact recovery for this cohort. An independent instrument format and direct timing are the next checks.

To repeat the post-hoc comparison, use the source cache from the reproduction instructions above and a separate Python 3.12 environment. Only this optional research comparison needs these packages. The native delta arm uses the XZ CLI.

```sh
python3.12 -m venv comparator-env
comparator-env/bin/python -m pip install h5py==3.16.0 blosc2==4.14.1 numpy==2.5.4 zarr==3.4.2 numcodecs==0.17.1 imagecodecs==2026.10.10
comparator-env/bin/python container_controls.py ./solar-inputs --output ./local-container-controls.json
```

[Per-file sizes, configuration and library versions](container-results.json) · [h5py shuffle filter](https://docs.h5py.org/en/stable/high/dataset.html#shuffle-filter) · [Blosc2 compression parameters](https://blosc.org/python-blosc2/reference/storage.html) · [Zarr v2 format](https://zarr-specs.readthedocs.io/en/latest/v2/v2.0.html) · [Imagecodecs project](https://github.com/cgohlke/imagecodecs)
