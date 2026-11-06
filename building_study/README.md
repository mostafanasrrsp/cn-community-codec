# Six building openings under a Chicago weather year

Six rectangular windows and glazed doors from EnergyPlus's distributed five-zone example produced **11,993 front-facing sun queries**. On an Apple M3, skipping certified zero contributions avoided **475 integrations (3.96%)**. The median paired CPU speed ratio was **1.041×**. The corresponding Metal dispatch-and-wait ratio was **0.967×**, a slowdown. The earlier research-panel skip rate was about 31.5%. The same geometric rule can be useful in one workload and cost time in another.

## What went into the measurement

The building file supplies the four vertices, rotations and wall construction for each opening. For this experiment the *entire* wall stack (0.134599997 m) is treated as a straight, black recess. Real reveal depths, glazing, frame overlap, scene occlusion and diffuse sky are outside this model. Transmission here is the idealized geometric component. The building is a published example model, and the weather is a typical meteorological year. An annual energy prediction or a physical measurement would require additional data. [Building source](https://github.com/NatLabRockies/EnergyPlus/blob/cf7368216c73c43181e057fa33b479c4e0c86df0/testfiles/5ZoneAirCooled.idf) · [Weather source](https://github.com/NatLabRockies/EnergyPlus/blob/cf7368216c73c43181e057fa33b479c4e0c86df0/weather/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw)

We evaluated the solar position at each hour's midpoint in local standard time. Of 8,760 hours, 4,009 had positive valid direct-normal irradiance and a solar disk fully above the horizon. Across the six openings, 11,993 window–hour pairs had their entire disk in front of the opening. The sun is a uniform disk of angular radius 0.266°. Each eligible pair uses the same eight radial by 32 azimuth quadrature nodes. The test counts each eligible query once, without irradiance weighting. [Solar position approximation](https://gml.noaa.gov/grad/solcalc/solareqns.PDF)

For each skipped query, a plane strictly separates the whole cone from the aperture's nonzero support in both exact-source and decoded geometry. The native CPU decision matches a rational-arithmetic check on the supplied numerical inputs. The finite-precision Metal version cross-checks its flags against these decisions. Each native implementation also checks its skipped results against its own unculled integrator at the same numerical precision. The ungated CPU returned 476 zeros, one more than the conservative culler skipped. Both paths skipped 475. The largest difference between uncompressed and decoded CPU transmission over this replay was 0.002954 (rounded upward). A separate certificate bounds ideal response error across all represented directions.

## Sizes and timing boundaries

The six extracted geometry records occupy 299 bytes as CSV, 49 bytes as general GX01, or 33 bytes as a specialized two-coefficient binary16 profile, including its nine-byte header. Both binary profiles pass the 0.010 tolerance. Both rely on the same external ordering, placement and local frames. Room geometry, original CAD semantics and weather are separate. The IDF and EPW originals remain 166,199 and 1,639,985 bytes respectively.

| M3 measurement | Without culling | With culling | Median paired ratio |
| --- | ---: | ---: | ---: |
| CPU panel | 3.937 ms | 3.813 ms | 1.041× |
| Metal kernel | 0.648 ms | 0.682 ms | 0.951× |
| Metal dispatch through completion | 0.900 ms | 0.929 ms | 0.967× |

These are warm, paired runs with the same inputs. CPU uses 11 pairs, reorders the queries between pairs, alternates the order of the arms, and averages three traversals per sample. Metal uses 21 pairs. Raw trials, readbacks, timing quartiles, precision differences and per-opening counts are in [results.json](results/results.json). On this machine, input parsing plus geometry encoding took 0.038 s and constructing the query arrays, exact decision oracle and input files took 0.840 s. Compilation, host preparation and device readback are outside the kernel timer. The study times a direct-beam query workload; running the EnergyPlus program itself, GPU cache counters and industrial energy use are separate experiments.

## Reproduce

Use Python 3.9+ and a C++17 compiler (Clang or GCC). For the optional Mac GPU replay, install the Xcode Metal tools. In this study directory, download the two files below. The run checks their SHA-256 against the pinned upstream revision. The included sibling community_codec directory supplies the Python codec. Keep the extracted kit directories together.

    curl -fL https://raw.githubusercontent.com/NatLabRockies/EnergyPlus/cf7368216c73c43181e057fa33b479c4e0c86df0/testfiles/5ZoneAirCooled.idf -o building.idf
    curl -fL https://raw.githubusercontent.com/NatLabRockies/EnergyPlus/cf7368216c73c43181e057fa33b479c4e0c86df0/weather/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw -o chicago.epw
    python3 run.py --idf building.idf --epw chicago.epw --out my-results --cpu-only

Omit --cpu-only to run both CPU and Metal on macOS. Run Python without its optimization flag so that all validation checks execute. Fixed geometry, hashes, counts and error bounds can be compared across machines; timings depend on hardware and system load.
