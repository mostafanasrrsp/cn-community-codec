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
