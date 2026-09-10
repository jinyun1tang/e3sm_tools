# Extract a single ELM land grid cell

This standalone utility subsets existing land files without OLMT's site-data
overrides. It does not create or submit a simulation. Coordinates select the
nearest valid domain-cell center, not a new interpolated land point.

## Run on the machine containing the input files

```bash
python3 -m venv point-env
point-env/bin/pip install -r requirements.txt
# Edit point.yaml: set point.londeg and point.latdeg; check paths/coordinate names.
point-env/bin/python extract_point.py point.yaml --dry-run > selection.json
point-env/bin/python extract_point.py point.yaml > extraction.json
```

Longitude may use -180..180 or 0..360. The maximum selection distance is explicit
in YAML. Each subsequent file is matched to the selected domain center (not
independently to the requested coordinates). `match_tolerance_km` guards against
selecting a different cell. Inspect the JSON report before extraction. Its source
indices are zero-based; ELM restart relationship variables are one-based.

The example uses paths from the supplied lnd_in. Coordinate variable names are
configurable and must be checked with `ncdump -h` on the actual files. Coordinates
can be paired 1-D, rectilinear 1-D, or curvilinear 2-D. Domain `mask > 0` limits
selection to valid cells; optionally specify another mask variable. Spatial
dimensions are inferred from coordinate dimensions and remain length one.
All other dimensions, including time, crop/PFT categories, soil layers, and
topographic categories in surface data, are retained.

## Restart handling

The script selects the gridcell by `grid1d_lon/lat`, then selects *all* associated
topounits, landunits, columns and PFTs via their `*_gridcell_index` relationships.
It renumbers parent references to the new local one-based ordering, and sets
`grid/topo/land/cols/pfts1d_ixy/jxy` to one. No crop pools, weights, or active flags
are reset. It requires standard ELM restart dimensions and relationship fields
from `subgridRestMod.F90`; grouped NetCDF is unsupported. Nonstandard restart
schemas need review before use. The resulting file is for `finidat` in a new
point case, not a complete coupled continuation restart.

Each variable is copied without NetCDF scale/offset conversion, then checked
against the selected source values (with only the stated index changes).
All files are staged and verified before publishing. Existing outputs and input
overwrites are refused. Storage compression/chunk layout is not preserved.
At most one selected variable is processed at a time; long time-series variables
may still need substantial memory. Source global metadata is preserved, so
descriptive global extent attributes may still describe the original grid.

Coordinate agreement does not prove that a new case builds the same subgrid
structure. Use the same surface/land-use settings, crop types, parameter file,
topographic configuration and initial date, and verify initialized pools and
weights against the source before interpreting a carbon balance reproduction.
If source restart metadata differs, use ELM interpinic with a point template
instead of guessing relationships.

## Forcing and case setup

This extracts the four necessary land datasets, not meteorological streams.
Reuse the original five DATM source streams (Solar, Precip, TPQW, aerosol,
topography) and four ELM auxiliary source files (N/P deposition, population,
lightning); change DATM's destination domain to domain_point.nc. Preserve
bilinear mapping, source domains, time interpolation, the weather cycle
1901–1920 aligned to model year 1, and the 1800-second land timestep.

Set fsurdat, finidat and flanduse_timeseries to the generated outputs, and configure
the case's land/atmosphere destination domain consistently. Keep parameter and
snow lookup files unchanged. MOSART files need no extraction with do_rtm=false;
preserve the original inactive-routing and two-way-irrigation behavior.
Compact forcing remapping is intentionally outside this utility: exact source
stream definitions and mapping/filling behavior must be supplied first.

## Tests

```bash
point-env/bin/python -m unittest discover -s . -p 'test_*.py' -v
```
Tests generate temporary synthetic NetCDFs; no ELM case is created.
