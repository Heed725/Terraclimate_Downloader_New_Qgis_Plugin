# TerraClimate Downloader New — QGIS Plugin

A dependency-safe QGIS plugin for downloading and clipping monthly TerraClimate data directly from the official THREDDS services.

## Why this new version exists

The older plugin depended on a scientific Python stack installed into the QGIS Python environment:

- NumPy
- xarray
- rioxarray
- netCDF4
- dask

Those packages can conflict with QGIS's bundled GDAL/NumPy/Python libraries, especially on Windows. This new plugin removes that dependency chain completely.

## Dependency model

**No `pip install` is required.**

The plugin uses only:

- QGIS Python API
- PyQt shipped with QGIS
- `osgeo.gdal` shipped with QGIS
- Python standard library (`urllib`, `tempfile`, `calendar`, etc.)

Do **not** install or upgrade NumPy, GDAL, netCDF4, xarray, rioxarray, or dask inside QGIS just for this plugin.

## Features

- Download TerraClimate through THREDDS NCSS server-side subsetting.
- Select an AOI polygon layer.
- Climate variables: `aet`, `def`, `pdsi`, `pet`, `ppt`, `q`, `soil`, `srad`, `swe`, `tmax`, `tmin`, `vap`, `vpd`, `ws`.
- Select one year or a year range.
- Select one month or all 12 months.
- Server-side spatial downsampling for very large AOIs.
- Configurable AOI buffer and retry count.
- Exact polygon clipping with QGIS-bundled GDAL.
- Multiband GeoTIFF output in chronological order.
- Band descriptions such as `ppt 2024-01`, `ppt 2024-02`, etc.
- No binary Python wheels bundled in the plugin.

## Installation

### Recommended — GitHub Release ZIP

1. Open **Releases** in this repository.
2. Download `terraclimate_downloader_new-qgis-v1.0.0.zip`.
3. Open QGIS.
4. Go to **Plugins → Manage and Install Plugins… → Install from ZIP**.
5. Select the ZIP and install it.
6. Enable **TerraClimate Downloader New**.

## Usage

1. Load a polygon boundary for the area you need.
2. Click the **TerraClimate Downloader** toolbar button, or open the Processing Toolbox and search for **Download TerraClimate data (dependency-free)**.
3. Select the polygon layer.
4. Choose the climate variable.
5. Select start/end year.
6. Choose **All months** or a specific month.
7. For a small AOI, keep **Native (~4 km)**. For a continent or very large area, use stride 2, 4, 8, or 16.
8. Select an output `.tif` file.
9. Run the algorithm.

## Output behavior

- One year + one month → 1-band GeoTIFF.
- One year + all months → normally 12 bands.
- Multiple years + one month → one band per year.
- Multiple years + all months → bands are stacked chronologically.

## Dependency troubleshooting

If the old TerraClimate plugin previously asked you to run commands such as:

```text
pip install numpy xarray rioxarray netCDF4 dask
```

that is no longer required for this repository.

If your QGIS Python environment was already modified and QGIS now has NumPy/GDAL import errors, repairing or reinstalling the affected QGIS installation/profile may still be necessary; this plugin itself does not modify Python packages.

## TerraClimate data source

TerraClimate is maintained by the Climatology Lab and provides monthly climate and climatic water-balance data at about 1/24° (~4 km). The lab recommends direct NetCDF downloads or THREDDS services such as OPeNDAP/NCSS for programmatic subsets.

## Compatibility

- QGIS 3.22+
- Windows, Linux, macOS
- No external Python environment required

## License

GPL-3.0-or-later.
