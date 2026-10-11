#!/usr/bin/env python3
"""
Diagnose PCT_NAT_PFT problems in an ELM land-use timeseries (or surface) file.

Mimics the ELM check in dynVarMod/read_variable_3d -> check_sums_equal_1_3d:
    abs(sum(PCT_NAT_PFT/100 over natpft) - 1) > 1e-14  -> endrun
which aborts with "sum of PCT_NAT_PFT not 1.0".

For every time slice it classifies bad gridcells as
    nan   : any NaN in the natpft column
    zero  : sum == 0 (typical "no data" fill at PFTDATA_MASK == 0 points)
    neg   : any negative value
    off   : sum differs from 100 by more than --tol
and breaks the counts down by PFTDATA_MASK (and by the ELM domain land mask
if --domain is given, since that mask decides which cells ELM actually reads).

The file is read one time slice at a time, so 0.25-deg x 166-year files are fine.

Usage:
    python check_pct_nat_pft.py landuse.nc
    python check_pct_nat_pft.py landuse.nc --surf surfdata.nc --domain domain.lnd.nc \
        --csv bad_cells.csv
"""
import argparse
import sys

import numpy as np
from netCDF4 import Dataset

CATS = ('nan', 'zero', 'neg', 'off')


def get_var(nc, names):
    for n in names:
        if n in nc.variables:
            v = nc.variables[n]
            v.set_auto_mask(False)
            return v
    return None


def column_stats(arr, ax_pft, tol):
    """arr: PCT_NAT_PFT with natpft at axis ax_pft and spatial dims last.
    Returns (sum, category-code) on the spatial grid; any extra dims (e.g. topounit)
    are collapsed with "worst" semantics. Category code: 0 ok, 1..4 = CATS."""
    has_nan = np.isnan(arr).any(axis=ax_pft)
    has_neg = (arr < 0).any(axis=ax_pft)
    s = np.nansum(arr, axis=ax_pft)
    code = np.zeros(s.shape, dtype=np.int8)
    code[np.abs(s - 100.0) > tol] = 4
    code[(s == 0) & ~has_nan] = 2
    code[has_neg] = 3
    code[has_nan] = 1
    # collapse any extra leading dims (topounit): keep the first non-zero code
    while code.ndim > 2:
        bad = code != 0
        idx = np.argmax(bad, axis=0)
        code = np.take_along_axis(code, idx[None], axis=0)[0]
        s = np.take_along_axis(s, idx[None], axis=0)[0]
    return s, code


def load_domain_mask(path, shape, lat):
    with Dataset(path) as nc:
        mvar = get_var(nc, ['mask', 'MASK'])
        if mvar is None:
            print(f'WARNING: no mask variable in {path}; ignoring --domain')
            return None
        m = np.asarray(mvar[:]).squeeze()
        if m.shape != shape:
            print(f'WARNING: domain mask shape {m.shape} != data grid {shape}; ignoring --domain')
            return None
        yc = get_var(nc, ['yc', 'lat'])
        if yc is not None and lat is not None:
            ycol = np.asarray(yc[:]).squeeze()
            ycol = ycol[:, 0] if ycol.ndim == 2 else ycol
            if np.allclose(ycol[::-1], lat, atol=1e-3) and not np.allclose(ycol, lat, atol=1e-3):
                print('NOTE: domain latitude is reversed relative to data file; flipping mask')
                m = m[::-1, :]
    return m > 0


def breakdown(label, codes, groups):
    """Print counts of each bad category for each group (name -> boolean mask)."""
    print(f'  {label}')
    hdr = '    {:<28s}' + '{:>10s}' * (len(CATS) + 2)
    print(hdr.format('group', 'cells', *CATS, 'total_bad'))
    for name, g in groups.items():
        c = codes[g]
        counts = [int((c == k + 1).sum()) for k in range(len(CATS))]
        print(('    {:<28s}' + '{:>10d}' * (len(CATS) + 2)).format(
            name, int(g.sum()), *counts, int((c != 0).sum())))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('file', help='land-use timeseries (or surface) file with PCT_NAT_PFT')
    p.add_argument('--surf', help='surface dataset (fsurdat) to compare PFTDATA_MASK and PCT_NAT_PFT')
    p.add_argument('--domain', help='ELM land domain file; its mask defines the cells ELM reads')
    p.add_argument('--tol', type=float, default=1e-12,
                   help='tolerance on |sum-100| in percent (ELM uses 1e-14 on fractions = 1e-12 %%)')
    p.add_argument('--csv', help='write per-cell list of bad cells to this CSV file')
    p.add_argument('--verbose-years', action='store_true', help='print a line for every time slice')
    a = p.parse_args()

    nc = Dataset(a.file)
    var = get_var(nc, ['PCT_NAT_PFT'])
    if var is None:
        sys.exit('ERROR: PCT_NAT_PFT not found')
    dims = var.dimensions
    print(f'File: {a.file}')
    print(f'PCT_NAT_PFT{dims} shape={var.shape}')
    if dims[-2:] != ('lsmlat', 'lsmlon'):
        print(f'WARNING: expected spatial dims (lsmlat, lsmlon) last, got {dims[-2:]}')
    has_time = 'time' in dims
    if has_time and dims.index('time') != 0:
        sys.exit('ERROR: time must be the first dimension')
    ax_pft = dims.index('natpft') - (1 if has_time else 0)
    nlat, nlon = var.shape[-2:]
    nt = var.shape[0] if has_time else 1

    tvar = get_var(nc, ['time'])
    tvals = np.asarray(tvar[:]) if (has_time and tvar is not None) else np.arange(nt)
    lat_v = get_var(nc, ['lsmlat', 'LATIXY'])
    lon_v = get_var(nc, ['lsmlon', 'LONGXY'])
    lat = np.asarray(lat_v[:]) if lat_v is not None else None
    lon = np.asarray(lon_v[:]) if lon_v is not None else None
    if lat is not None and lat.ndim == 2:
        lat = lat[:, 0]
    if lon is not None and lon.ndim == 2:
        lon = lon[0, :]

    mvar = get_var(nc, ['PFTDATA_MASK'])
    pmask = np.asarray(mvar[:]) if mvar is not None else None

    groups = {'all cells': np.ones((nlat, nlon), bool)}
    if pmask is not None:
        for v in np.unique(pmask):
            groups[f'PFTDATA_MASK=={v}'] = pmask == v
    dmask = load_domain_mask(a.domain, (nlat, nlon), lat) if a.domain else None
    if dmask is not None:
        groups['domain land (ELM reads)'] = dmask
        if pmask is not None:
            groups['domain land & PFTMASK==0'] = dmask & (pmask == 0)
            groups['domain land & PFTMASK==1'] = dmask & (pmask == 1)

    # per-cell accumulators over time
    nbad = np.zeros((nlat, nlon), np.int32)
    first_t = np.full((nlat, nlon), -1, np.int32)
    first_sum = np.full((nlat, nlon), np.nan)
    first_code = np.zeros((nlat, nlon), np.int8)
    first_code_all = None

    print(f'\nScanning {nt} time slice(s) ...')
    years_bad = []
    for it in range(nt):
        arr = np.asarray(var[it] if has_time else var[:], dtype=np.float64)
        s, code = column_stats(arr, ax_pft, a.tol)
        bad = code != 0
        new = bad & (first_t < 0)
        first_t[new] = it
        first_sum[new] = s[new]
        first_code[new] = code[new]
        nbad += bad
        if it == 0:
            first_code_all = code.copy()
        nb_relevant = int((bad & dmask).sum()) if dmask is not None else int(bad.sum())
        if nb_relevant:
            years_bad.append(tvals[it])
        if a.verbose_years or it in (0, nt - 1):
            print(f'  t={it:4d} time={tvals[it]}: bad={int(bad.sum())}'
                  + (f'  (on domain land: {nb_relevant})' if dmask is not None else ''))
    nc.close()

    print('\n=== Breakdown at first time slice ===')
    breakdown(f'time={tvals[0]}', first_code_all, groups)

    ever = nbad > 0
    print('\n=== Cells bad in at least one time slice (category at first bad slice) ===')
    breakdown('any time', np.where(ever, first_code, 0), groups)
    if has_time:
        print(f'\nTime slices with bad cells{" on domain land" if dmask is not None else ""}: '
              f'{len(years_bad)} of {nt}'
              + (f'  (first {years_bad[0]}, last {years_bad[-1]})' if years_bad else ''))
        if ever.any():
            print(f'Of the ever-bad cells: {int((nbad == nt).sum())} bad in every slice, '
                  f'{int(((nbad > 0) & (nbad < nt)).sum())} bad in only some slices')

    # comparison with surface dataset
    if a.surf:
        print(f'\n=== Comparison with surface dataset {a.surf} ===')
        with Dataset(a.surf) as sf:
            smask_v = get_var(sf, ['PFTDATA_MASK'])
            if smask_v is not None and pmask is not None:
                smask = np.asarray(smask_v[:])
                if smask.shape == pmask.shape:
                    diff = smask != pmask
                    print(f'  PFTDATA_MASK differs at {int(diff.sum())} cells')
                    print(f'  ever-bad cells by surf PFTDATA_MASK: '
                          + ', '.join(f'{v}:{int((ever & (smask == v)).sum())}' for v in np.unique(smask)))
                else:
                    print(f'  PFTDATA_MASK shape mismatch: surf {smask.shape} vs file {pmask.shape}')
            sv = get_var(sf, ['PCT_NAT_PFT'])
            if sv is not None and sv.shape[-2:] == (nlat, nlon):
                sdims = sv.dimensions
                ss, scode = column_stats(np.asarray(sv[:], dtype=np.float64), sdims.index('natpft'), a.tol)
                print(f'  surf PCT_NAT_PFT bad cells: {int((scode != 0).sum())}')
                both = ever & (scode == 0)
                print(f'  cells OK in surf but bad in this file: {int(both.sum())}  '
                      '(file inconsistent with fsurdat)')
            elif sv is not None:
                print(f'  surf PCT_NAT_PFT grid {sv.shape[-2:]} != file grid {(nlat, nlon)}; skipped')

    # list a few examples
    idx = np.argwhere(ever)
    if len(idx):
        print('\n=== Example bad cells (up to 20) ===')
        print(f'  {"j":>5s} {"i":>5s} {"lat":>9s} {"lon":>9s} {"PFTMASK":>7s} '
              f'{"dom":>4s} {"first_t":>8s} {"cat":>5s} {"sum":>12s} {"nbad":>5s}')
        for j, i in idx[:20]:
            print(f'  {j:5d} {i:5d} '
                  f'{(lat[j] if lat is not None else np.nan):9.3f} {(lon[i] if lon is not None else np.nan):9.3f} '
                  f'{(pmask[j, i] if pmask is not None else -9):7d} '
                  f'{(int(dmask[j, i]) if dmask is not None else -9):4d} '
                  f'{str(tvals[first_t[j, i]]):>8s} {CATS[first_code[j, i] - 1]:>5s} '
                  f'{first_sum[j, i]:12.6g} {nbad[j, i]:5d}')

    if a.csv and len(idx):
        with open(a.csv, 'w') as f:
            f.write('j,i,lat,lon,pftdata_mask,domain_land,first_bad_time,category,sum_at_first_bad,n_bad_slices\n')
            for j, i in idx:
                f.write(f'{j},{i},'
                        f'{lat[j] if lat is not None else ""},{lon[i] if lon is not None else ""},'
                        f'{pmask[j, i] if pmask is not None else ""},'
                        f'{int(dmask[j, i]) if dmask is not None else ""},'
                        f'{tvals[first_t[j, i]]},{CATS[first_code[j, i] - 1]},'
                        f'{first_sum[j, i]:.10g},{nbad[j, i]}\n')
        print(f'\nWrote {len(idx)} bad cells to {a.csv}')

    # verdict
    print('\n=== Interpretation ===')
    if not ever.any():
        print('  No bad PCT_NAT_PFT columns found.')
        return
    relevant = ever & dmask if dmask is not None else ever
    if dmask is not None and not relevant.any():
        print('  All bad cells are outside the domain land mask -> ELM never reads them; '
              'the abort must come from elsewhere (check grid/topounit alignment).')
        return
    if pmask is not None:
        n0 = int((relevant & (pmask == 0)).sum())
        n1 = int((relevant & (pmask == 1)).sum())
        print(f'  Bad cells{" on domain land" if dmask is not None else ""}: '
              f'{n0} with PFTDATA_MASK==0, {n1} with PFTDATA_MASK==1')
        if n0 and not n1:
            print('  -> "no data" fill at fake-land points. mksurfdata writes 100% bare ground '
                  '(natpft index 0) there; set PCT_NAT_PFT[:,0,...]=100 at these cells.')
        elif n1:
            print('  -> bad values at real PFT points: the file was likely regridded/edited '
                  'inconsistently with fsurdat. Regenerate it or renormalize those columns.')
    zero_ct = int((relevant & (first_code == 2)).sum())
    nan_ct = int((relevant & (first_code == 1)).sum())
    if nan_ct:
        print(f'  {nan_ct} cells contain NaN (_FillValue=NaN); ELM will propagate NaN or skip the check '
              'depending on natpft 0 -> replace with bare-ground fill.')
    if zero_ct:
        print(f'  {zero_ct} cells sum to exactly 0 -> matches "sum is: 0.0" in the ELM error.')


if __name__ == '__main__':
    main()
