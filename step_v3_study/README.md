# Comparing STEP file sizes in Community Codec 0.3

Can a dictionary of repeated decimal spellings save bytes on CAD files while recovering every character of the original STEP text? We compared the released 0.2 and 0.3 programs on the same inputs. Both tried their portable methods first. In a second run both could also try Brotli. Each file gets the smallest complete frame among the eligible methods in that run.

| Drawings | Mode | v0.2 bytes | v0.3 bytes | Reduction |
| --- | --- | ---: | ---: | ---: |
| Fifteen public files used in development | Portable | 3,050,071 | 3,042,023 | 8,048 (0.26%) |
| Same fifteen | Optional Brotli | 3,047,965 | 3,033,999 | 13,966 (0.46%) |
| Three additional public NIST drawings | Portable | 444,035 | 444,035 | 0 |
| Same three | Optional Brotli | 444,035 | 437,354 | 6,681 (1.50%) |
| One additional private drawing | Portable | 7,973 | 7,681 | 292 |
| Same private drawing | Optional Brotli | 7,973 | 7,551 | 422 |
| All four additional drawings | Portable | 452,008 | 451,716 | 292 (0.065%) |
| All four additional drawings | Optional Brotli | 452,008 | 444,905 | 7,103 (1.57%) |

The percentage is the difference in total stored bytes divided by the corresponding 0.2 total. It includes the frame headers. Sending the reader for the first time costs 24,700 bytes for 0.3 versus 21,950 for 0.2. All restored bytes matched. The extra searches require encoding work, and this experiment measures size. The public replay covers 18 drawings. Only aggregate sizes are available for the private drawing.

## Individual public drawings

All sizes are bytes. The control column reports the smallest of the eight conventional results for each input. The first three rows are the additional public NIST drawings. The other fifteen were used in development. The four-file total above also includes one private drawing.

| Drawing | Original | .stpZ (DEFLATE-9) | Smallest control | 0.3 default | 0.3 with Brotli |
| --- | ---: | ---: | ---: | ---: | ---: |
| `nist_ctc_04_asme1_ap242-e1.stp` | 1,287,291 | 259,723 | 158,195 (brotli11) | 89,633 | 89,374 |
| `nist_ftc_07_asme1_ap242-e2.stp` | 1,478,375 | 333,724 | 215,730 (brotli11) | 157,465 | 153,997 |
| `nist_stc_07_asme1_ap242-e3.stp` | 1,945,387 | 376,378 | 248,428 (brotli11) | 196,937 | 193,983 |
| `A1_RECT_cassette.step` | 142,986 | 25,222 | 14,298 (brotli11) | 3,357 | 2,974 |
| `A1_SQ_cassette.step` | 142,870 | 25,213 | 14,329 (brotli11) | 3,381 | 3,108 |
| `A2_DARK_reference.step` | 113,091 | 20,250 | 12,441 (brotli11) | 4,601 | 4,237 |
| `A2_RECT_reference.step` | 128,572 | 22,698 | 13,920 (brotli11) | 5,037 | 4,642 |
| `A2_SQ_reference.step` | 128,567 | 22,694 | 13,914 (brotli11) | 5,029 | 4,646 |
| `A3_installed_fixture.step` | 297,618 | 50,763 | 30,031 (brotli11) | 6,889 | 6,472 |
| `nist_ctc_01_asme1_ap242-e1.stp` | 396,445 | 86,880 | 58,300 (xz6) | 51,341 | 51,341 |
| `nist_ctc_02_asme1_ap242-e2.stp` | 1,981,342 | 435,887 | 264,552 (xz6) | 227,877 | 227,877 |
| `nist_ftc_08_asme1_ap242-e1-tg.stp` | 2,120,356 | 497,936 | 343,100 (xz6) | 290,333 | 290,333 |
| `nist_ftc_08_asme1_ap242-e2.stp` | 4,722,264 | 1,467,600 | 1,016,780 (xz6) | 955,061 | 955,061 |
| `nist_stc_06_asme1_ap242-e3.stp` | 1,006,401 | 228,663 | 155,173 (brotli11) | 112,489 | 112,489 |
| `MBDTest01_1.step` | 65,732 | 12,260 | 8,190 (brotli11) | 2,837 | 2,563 |
| `nist_ctc_03_asme1_ap242-e2.stp` | 673,846 | 140,404 | 93,816 (xz6) | 84,109 | 84,109 |
| `nist_ftc_06_asme1_ap242-e2.stp` | 1,971,192 | 428,042 | 288,492 (xz6) | 269,097 | 269,097 |
| `nist_stc_10_asme1_ap242-e2.stp` | 4,875,056 | 1,524,876 | 1,074,692 (xz6) | 1,020,585 | 1,015,050 |

[Additional control measurements](transfer-controls.json) · [Development control measurements](../step_v2_study/control-sizes.json) · [Control settings](../step_v2_study/controls.py)

## Repeat the comparison

Extract the [replication kit](https://github.com/mostafanasrrsp/cn-community-codec/releases/download/v0.3.0-preview/STEP-v3-replication.zip). Use Python 3.9 or later. For the optional mode install the Brotli command-line tool and put it on PATH. From the kit directory run

```sh
python3 step_v3_study/compare.py --group transfer --with-brotli --out my-transfer.json
```

This fetches three public NIST inputs, verifies the archive and input hashes, and runs pack, inspect and unpack for each program in both modes. It compares each restored file with its source and records the file size, selected method and frame digest. To try the portable profile alone, omit `--with-brotli`. Choose `--group prior` for the earlier 15 public files or `--group all` for all 18. Use a fresh output filename each time. The replication ZIP contains both readers. The full source checkout downloads the pinned 0.2 reader if needed. Compression library versions can affect frame sizes.

* [Three public transfer inputs and reader pin](manifest.json) and [earlier input and archive pins](../step_v2_study/manifest.json)
* [Transfer results](transfer-results.json) and [development set results](prior-results.json), including competing frame sizes and exact-restore checks
* [Cross-platform compatibility results](compatibility.json)
* [Wire format](../file_study/SXD3.md) and [older conventional-control comparisons](../step_v2_study/README.md)
