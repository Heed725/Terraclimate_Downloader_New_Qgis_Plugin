# Changelog

## 1.0.0 — 2026-08-18

- Rebuilt the TerraClimate downloader for QGIS 3.22+.
- Removed runtime requirements for NumPy, xarray, rioxarray, netCDF4, dask, and requests.
- Uses Python standard library networking and QGIS-bundled GDAL.
- Added THREDDS NCSS server-side subsetting.
- Added AOI polygon clipping, month/year range selection, retry handling, and spatial stride controls.
- Added chronological multiband GeoTIFF output with band descriptions.
- Added automated GitHub Actions packaging and v1.0.0 release ZIP.
