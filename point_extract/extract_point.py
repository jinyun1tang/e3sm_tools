#!/usr/bin/env python3
"""Subset ELM land inputs by coordinates, preserving raw NetCDF values."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile

import netCDF4 as nc
import numpy as np
import yaml


def locate(ds, spec, lon, lat):
    """Support paired, rectilinear and curvilinear coordinate arrays."""
    x, y = ds[spec['lon']], ds[spec['lat']]
    dims = tuple(dict.fromkeys(y.dimensions + x.dimensions))
    def expand(v):
        a = np.ma.filled(np.ma.asarray(v[:], dtype=float), np.nan)
        order = sorted(range(len(v.dimensions)), key=lambda i: dims.index(v.dimensions[i]))
        a = a.transpose(order)
        return a.reshape([len(ds.dimensions[d]) if d in v.dimensions else 1 for d in dims])
    xx, yy = np.broadcast_arrays(expand(x), expand(y))
    dl = np.deg2rad((xx - lon + 180) % 360 - 180)
    dy = np.deg2rad(yy - lat)
    a = np.sin(dy/2)**2 + np.cos(np.deg2rad(lat))*np.cos(np.deg2rad(yy))*np.sin(dl/2)**2
    distance = 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    valid = np.isfinite(distance) & (np.abs(yy) <= 90)
    if spec.get('mask'):
        valid &= np.broadcast_to(expand(ds[spec['mask']]), xx.shape) > 0
    if not valid.any():
        raise ValueError('No valid coordinate cells')
    ij = np.unravel_index(np.argmin(np.where(valid, distance, np.inf)), xx.shape)
    return {d: np.array([i]) for d, i in zip(dims, ij)}, float(xx[ij]), float(yy[ij]), float(distance[ij])


def restart_selection(ds, selection):
    if set(selection) != {'gridcell'}:
        raise ValueError('Restart coordinates must use the gridcell dimension')
    old_grid = int(selection['gridcell'][0]) + 1
    for prefix, dim in [('topo1d', 'topounit'), ('land1d', 'landunit'),
                        ('cols1d', 'column'), ('pfts1d', 'pft')]:
        if dim not in ds.dimensions:
            continue
        name = prefix + '_gridcell_index'
        if name not in ds.variables or ds[name].dimensions != (dim,):
            raise ValueError(f'Missing or invalid restart relationship: {name}')
        selection[dim] = np.flatnonzero(ds[name][:] == old_grid)
        if not selection[dim].size:
            raise ValueError(f'No {dim} entries for selected gridcell')
    return selection


def raw_subset(var, selection):
    # netCDF4 uses orthogonal indexing for integer arrays.
    return var[tuple(selection.get(d, slice(None)) for d in var.dimensions)] if var.dimensions else var[...]


def transform(name, data, selection, restart):
    if not restart:
        return data
    if re.fullmatch(r'(grid|topo|land|cols|pfts)1d_[ij]xy', name):
        return np.ones_like(data)
    match = re.fullmatch(r'(?:topo|land|cols|pfts)1d_(gridcell|topounit|landunit|column)_index', name)
    if match:
        dim = match.group(1)
        mapping = {int(old)+1: new+1 for new, old in enumerate(selection[dim])}
        try:
            return np.array([mapping[int(v)] for v in data.flat], dtype=data.dtype).reshape(data.shape)
        except KeyError as exc:
            raise ValueError(f'{name} references an unselected parent {exc}') from exc
    return data


def extract(source, output, selection, restart):
    with nc.Dataset(source) as src, nc.Dataset(output, 'w', format=src.data_model) as dst:
        if src.groups:
            raise ValueError('Grouped NetCDF files are not supported')
        src.set_auto_maskandscale(False)
        src.set_auto_chartostring(False)
        dst.setncatts(src.__dict__)
        for name, dim in src.dimensions.items():
            dst.createDimension(name, len(selection[name]) if name in selection else
                                (None if dim.isunlimited() else len(dim)))
        for name, var in src.variables.items():
            attrs = dict(var.__dict__)
            fill = attrs.pop('_FillValue', None)
            out = dst.createVariable(name, var.datatype, var.dimensions, fill_value=fill)
            out.setncatts(attrs)
            out.set_auto_maskandscale(False)
            out.set_auto_chartostring(False)
            out[...] = transform(name, raw_subset(var, selection), selection, restart)
    # Reopen and verify every variable, including crop pools and weights.
    with nc.Dataset(source) as src, nc.Dataset(output) as dst:
        for ds in (src, dst):
            ds.set_auto_maskandscale(False)
            ds.set_auto_chartostring(False)
        for name, var in src.variables.items():
            expected = transform(name, raw_subset(var, selection), selection, restart)
            actual = dst[name][...]
            equal = np.array_equal(expected, actual, equal_nan=True) if np.asarray(expected).dtype.kind in 'fc' else np.array_equal(expected, actual)
            if not equal:
                raise ValueError(f'Output verification failed: {name}')


def run(config, dry_run=False):
    config = Path(config).resolve()
    cfg = yaml.safe_load(config.read_text())
    def path(value):
        p = Path(value).expanduser()
        return (config.parent / p).resolve() if not p.is_absolute() else p.resolve()
    if cfg['point'].get('londeg') is None or cfg['point'].get('latdeg') is None:
        raise ValueError('Set point.londeg and point.latdeg in the YAML configuration')
    lon, lat = float(cfg['point']['londeg']), float(cfg['point']['latdeg'])
    if not np.isfinite(lon) or not np.isfinite(lat) or not -90 <= lat <= 90:
        raise ValueError('Invalid point coordinates')
    files = cfg['files']
    if not files or files[0]['kind'] != 'domain':
        raise ValueError('The first file must be the domain')
    report = {'requested': {'londeg': lon, 'latdeg': lat}, 'files': []}
    jobs, destinations = [], set()
    sources = {path(s['input']) for s in files}
    for spec in files:
        source, output = path(spec['input']), path(spec['output'])
        if output in sources or output in destinations or output.exists():
            raise ValueError(f'Refusing existing, duplicate, or input output path: {output}')
        destinations.add(output)
        if spec['kind'] not in ('domain', 'surface', 'landuse', 'restart'):
            raise ValueError(f"Unsupported kind: {spec['kind']}")
        with nc.Dataset(source) as ds:
            selection, x, y, km = locate(ds, spec, lon, lat)
            limit = float(cfg['point'].get('max_distance_km', 25)) if not jobs else float(cfg.get('match_tolerance_km', 0.01))
            if km > limit:
                raise ValueError(f'{source}: coordinate distance {km:.6g} km exceeds {limit} km')
            if not jobs:
                lon, lat = x, y
                report['selected'] = {'londeg': x, 'latdeg': y, 'distance_km': km}
            restart = spec['kind'] == 'restart'
            if restart:
                selection = restart_selection(ds, selection)
            jobs.append((source, output, selection, restart))
            report['files'].append({'input': str(source), 'output': str(output),
                                    'indices_zero_based': {d: v.tolist() for d, v in selection.items()}})
    print(json.dumps(report, indent=2))
    if dry_run:
        return report
    # Stage and verify all files before publishing any of them.
    staged = []
    try:
        for source, output, selection, restart in jobs:
            output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.nc', delete=False) as f:
                temporary = Path(f.name)
            staged.append((temporary, output))
            extract(source, temporary, selection, restart)
        for temporary, output in staged:
            # Hard link refuses to overwrite an output created concurrently.
            os.link(temporary, output)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', help='YAML configuration')
    parser.add_argument('--dry-run', action='store_true', help='Validate inputs and report selection without writing files')
    args = parser.parse_args()
    run(args.config, args.dry_run)
