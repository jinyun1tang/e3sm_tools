import contextlib
import io
from pathlib import Path
import tempfile
import unittest

import netCDF4 as nc
import numpy as np
import yaml

from extract_point import run, locate


class PointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        with nc.Dataset(self.root/'domain.nc', 'w') as ds:
            ds.createDimension('nj', 1)
            ds.createDimension('ni', 3)
            for name, vals in [('xc', [350, 351, 352]), ('yc', [45, 45, 45]), ('mask', [1, 1, 0])]:
                ds.createVariable(name, 'f8', ('nj', 'ni'))[:] = [vals]
        with nc.Dataset(self.root/'restart.nc', 'w') as ds:
            ds.surface_dataset = '/original/global_surface.nc'
            for dim, size in [('gridcell', 2), ('topounit', 3), ('landunit', 3), ('column', 4), ('pft', 5), ('lev', 2)]:
                ds.createDimension(dim, size)
            def var(name, dims, values, dtype='i4'):
                ds.createVariable(name, dtype, dims)[:] = values
            # Restart ordering differs from domain; second grid cell is selected.
            var('grid1d_lon', ('gridcell',), [350, 351], 'f8')
            var('grid1d_lat', ('gridcell',), [45, 45], 'f8')
            for prefix, dim, parents in [('topo1d', 'topounit', [1, 2, 2]),
                                         ('land1d', 'landunit', [1, 2, 2]),
                                         ('cols1d', 'column', [1, 2, 2, 2]),
                                         ('pfts1d', 'pft', [1, 2, 2, 2, 2])]:
                var(prefix+'_gridcell_index', (dim,), parents)
                var(prefix+'_ixy', (dim,), [7]*len(parents))
            var('land1d_topounit_index', ('landunit',), [1, 2, 3])
            var('cols1d_topounit_index', ('column',), [1, 2, 2, 3])
            var('cols1d_landunit_index', ('column',), [1, 2, 2, 3])
            var('pfts1d_column_index', ('pft',), [1, 2, 3, 4, 4])
            var('grainc', ('pft',), [1, 2, 3, 4, 5], 'f8')
            var('cropseedc_deficit', ('pft',), [-1, -2, -3, -4, -5], 'f8')
            v = ds.createVariable('packed', 'i2', ('lev', 'pft'), fill_value=-999)
            v.scale_factor = 0.1
            v.set_auto_maskandscale(False)
            v[:] = [[1, 2, -999, 4, 5], [6, 7, 8, 9, 10]]
        self.cfg = {'point': {'londeg': -9, 'latdeg': 45}, 'files': [
            {'kind': 'domain', 'input': 'domain.nc', 'output': 'out/domain.nc', 'lon': 'xc', 'lat': 'yc', 'mask': 'mask'},
            {'kind': 'surface', 'input': 'domain.nc', 'output': 'out/surface.nc', 'lon': 'xc', 'lat': 'yc'},
            {'kind': 'restart', 'input': 'restart.nc', 'output': 'out/restart.nc', 'lon': 'grid1d_lon', 'lat': 'grid1d_lat'}]}

    def execute(self, dry=False):
        path = self.root/'config.yaml'
        path.write_text(yaml.safe_dump(self.cfg))
        with contextlib.redirect_stdout(io.StringIO()):
            return run(path, dry)

    def test_restart_and_raw_values(self):
        report = self.execute()
        self.assertEqual(report['selected']['londeg'], 351)
        with nc.Dataset(self.root/'out/restart.nc') as ds:
            self.assertEqual(ds.surface_dataset, str((self.root/'out/surface.nc').resolve()))
            np.testing.assert_array_equal(ds['pfts1d_column_index'][:], [1, 2, 3, 3])
            np.testing.assert_array_equal(ds['cols1d_topounit_index'][:], [1, 1, 2])
            np.testing.assert_array_equal(ds['cropseedc_deficit'][:], [-2, -3, -4, -5])
            np.testing.assert_array_equal(ds['pfts1d_ixy'][:], [1]*4)
            ds.set_auto_maskandscale(False)
            np.testing.assert_array_equal(ds['packed'][:], [[2, -999, 4, 5], [7, 8, 9, 10]])
        with self.assertRaisesRegex(ValueError, 'Refusing'):
            self.execute()

    def test_dry_run_and_mismatch(self):
        self.execute(True)
        self.assertFalse((self.root/'out').exists())
        with nc.Dataset(self.root/'restart.nc', 'a') as ds:
            ds['grid1d_lon'][:] = [0, 1]
        with self.assertRaisesRegex(ValueError, 'coordinate distance'):
            self.execute()
        self.assertFalse((self.root/'out').exists())

    def test_bad_parent_rejected_before_publication(self):
        with nc.Dataset(self.root/'restart.nc', 'a') as ds:
            ds['pfts1d_column_index'][1] = 1
        with self.assertRaisesRegex(ValueError, 'unselected parent'):
            self.execute()
        self.assertFalse((self.root/'out/domain.nc').exists())

    def test_surface_metadata_preflight(self):
        report = self.execute(True)
        self.assertEqual(report['files'][-1]['surface_dataset'], str((self.root/'out/surface.nc').resolve()))
        with nc.Dataset(self.root/'restart.nc') as ds:
            self.assertEqual(ds.surface_dataset, '/original/global_surface.nc')
        self.cfg['files'] = [s for s in self.cfg['files'] if s['kind'] != 'surface']
        with self.assertRaisesRegex(ValueError, 'exactly one surface'):
            self.execute(True)

    def test_ambiguous_surface_rejected(self):
        self.cfg['files'].append(dict(self.cfg['files'][1], output='out/other_surface.nc'))
        with self.assertRaisesRegex(ValueError, 'exactly one surface'):
            self.execute(True)

    def test_rectilinear(self):
        with nc.Dataset(self.root/'regular.nc', 'w') as ds:
            ds.createDimension('lon', 3)
            ds.createDimension('lat', 2)
            ds.createVariable('lon', 'f8', ('lon',))[:] = [350, 351, 352]
            ds.createVariable('lat', 'f8', ('lat',))[:] = [44, 45]
            sel, _, _, distance = locate(ds, {'lon': 'lon', 'lat': 'lat'}, -9, 45)
            self.assertEqual(sel['lon'].tolist(), [1])
            self.assertEqual(sel['lat'].tolist(), [1])
            self.assertEqual(distance, 0)

    def test_landuse_preserves_time_and_crop_axis(self):
        with nc.Dataset(self.root/'landuse.nc', 'w') as ds:
            for dim, size in [('time', None), ('crop', 3), ('gridcell', 2)]:
                ds.createDimension(dim, size)
            ds.createVariable('LONGXY', 'f8', ('gridcell',))[:] = [351, 350]
            ds.createVariable('LATIXY', 'f8', ('gridcell',))[:] = [45, 45]
            ds.createVariable('time', 'i4', ('time',))[:] = [1850, 1851]
            ds.createVariable('PCT_CFT', 'f8', ('time', 'crop', 'gridcell'))[:] = np.arange(12).reshape(2, 3, 2)
        self.cfg['files'].append({'kind': 'landuse', 'input': 'landuse.nc', 'output': 'out/landuse.nc', 'lon': 'LONGXY', 'lat': 'LATIXY'})
        self.execute()
        with nc.Dataset(self.root/'out/landuse.nc') as ds:
            self.assertTrue(ds.dimensions['time'].isunlimited())
            self.assertEqual(ds['PCT_CFT'].shape, (2, 3, 1))
            np.testing.assert_array_equal(ds['PCT_CFT'][:], np.arange(12).reshape(2, 3, 2)[:, :, :1])


if __name__ == '__main__':
    unittest.main()
