# Try the Corridor Numerics file codec

Keep **cn-preview.pyz** and run it with Python 3.9 or newer. The default mode runs offline and uses Python's standard zlib, bzip2 and lzma modules. On a Mac, open Terminal in the folder with the file and try a copy of one of your own files.

```sh
python3 cn-preview.pyz pack drawing.step drawing.cn
python3 cn-preview.pyz inspect drawing.cn
python3 cn-preview.pyz unpack drawing.cn recovered.step
cmp drawing.step recovered.step
```

A silent `cmp` means the file contents match exactly. Replace the names in the example as needed. You can copy the .cn file and the .pyz reader to another computer. The decoder identifies the format from the bytes, so you can choose your own extension. The pack result lists the complete byte counts it compared. Inspect checks the original content digest. Every output needs a fresh filename unless you explicitly use `--force`.

| What you give it | What it tries |
| --- | --- |
| One ordinary file up to 64 MiB | Original bytes, DEFLATE, bzip2 and XZ in an integrity-checked CNF1 frame. |
| STEP Part 21 text up to 8 MiB | Also tries separating entity-reference differences before XZ (SXD1). |
| Matching fixed-row NOAA SURFRAD v1 data up to 8 MiB | Also tries grouping equivalent byte columns before XZ (SRT2). The auto-detector currently recognizes Bondville, Fort Peck and Desert Rock. |
| An already compressed file | Uses the smaller of the eligible complete frames. The raw fallback can grow the original by 45 bytes. |

You can explicitly add `--with-brotli` to the pack command to try one more SRT2 method on eligible solar data. Both sender and receiver need a working Brotli command-line tool for a resulting Brotli frame. With the default options, the recipient only needs Python. Candidate selection entails extra encoding work; the program reads one regular file into memory. Keep permissions, extended attributes and directory structure separately. SHA-256 verifies file contents. To verify the downloaded program against a trusted copy of the included digest, run `shasum -a 256 -c SHA256SUMS`.

## Try the aperture response experiment separately

Here is a complete CSV example to save as **apertures.csv**.

```csv
id,B00,B01,B10,B11,d,bx,by
square,2,0,0,2,1,0,0
```

```sh
python3 cn-preview.pyz geometry-pack apertures.csv square.gx01
python3 cn-preview.pyz geometry-verify apertures.csv square.gx01
python3 cn-preview.pyz geometry-query square.gx01 0 0.5 0
```

The third command returns a transmission of 0.75 for this ideal square. GX01 is a separate, lossy, queryable geometry representation. The encoder verifies a maximum absolute modeled transmission difference of 0.010 against each input geometry. Keep your original geometry, coordinates, units and row identities. A physical prediction also needs suitable geometry, materials, model assumptions and measurements. Ordinary file packing always restores the original bytes.

## Inspect, test and reproduce

The .pyz is a standard ZIP of Python source and the MIT software license. To inspect its contents, use `python3 -m zipfile -l cn-preview.pyz`. The app carries no test corpus, model, external compressor executable or telemetry. The source kit includes the router and its build recipe. From the full lab source tree, `python3 preview/build_preview.py` regenerates the app and `python3 preview/test_preview.py` exercises its packaged commands in a temporary folder. The individual profile directories contain wire details and separate controlled experiments.

To repeat the combined app on freely downloadable inputs from that tree:

```sh
python3 preview/check_preview.py --public-only --output preview-public-results.json
```

The mixed-file results also include 14 local research/product assets. Their contents remain private. The results file records sizes and checksums. The six held-out solar series have their own cohort and stock settings. Keep the cohorts separate when interpreting the results.
