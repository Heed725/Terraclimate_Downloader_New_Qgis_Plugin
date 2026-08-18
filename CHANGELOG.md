# Changelog

## 1.0.1 — 2026-08-18

- Fixed TerraClimate NCSS HTTP 500 failures by requesting `time=all` for yearly NetCDF files.
- Changed NCSS output request to the documented `accept=netcdf` format.
- Month selection is now performed locally from the returned yearly bands, avoiding fragile synthetic date ranges.
- Added automatic THREDDS `fileServer` fallback when NCSS is unavailable or returns server errors.
- Added clearer network/download logging and response validation.
- Added a valid `.pre-commit-config.yaml` so pre-commit.ci no longer fails at configuration discovery.
- Kept the dependency-safe design: no pip-installed NumPy, xarray, rioxarray, netCDF4, dask, or requests.

## 1.0.0 — 2026-08-18

- Rebuilt the TerraClimate downloader for QGIS 3.22+.
- Removed runtime requirements for NumPy, xarray, rioxarray, netCDF4, dask, and requests.
- Uses Python standard library networking and QGIS-bundled GDAL.
- Added THREDDS NCSS server-side subsetting.
- Added AOI polygon clipping, month/year range selection, retry handling, and spatial stride controls.
- Added chronological multiband GeoTIFF output with band descriptions.
- Added automated GitHub Actions packaging and v1.0.0 release ZIP.
