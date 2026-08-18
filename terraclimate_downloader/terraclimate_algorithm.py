# -*- coding: utf-8 -*-
"""Dependency-safe TerraClimate downloader for QGIS.

Uses Python's standard library for HTTP and QGIS-bundled GDAL for NetCDF/GeoTIFF.
No xarray, rioxarray, netCDF4, dask, requests, or pip installation is required.
"""
import calendar
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from osgeo import gdal

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterVectorLayer,
    QgsProject,
    QgsVectorFileWriter,
)


gdal.UseExceptions()


class TerraClimateDownloadAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    VARIABLE = "VARIABLE"
    START_YEAR = "START_YEAR"
    END_YEAR = "END_YEAR"
    MONTH = "MONTH"
    STRIDE = "STRIDE"
    BUFFER = "BUFFER"
    RETRIES = "RETRIES"
    OUTPUT = "OUTPUT"

    VARIABLES = [
        "aet", "def", "pdsi", "pet", "ppt", "q", "soil", "srad",
        "swe", "tmax", "tmin", "vap", "vpd", "ws"
    ]
    VARIABLE_LABELS = [
        "Actual evapotranspiration (aet) — mm",
        "Climate water deficit (def) — mm",
        "Palmer drought severity index (pdsi)",
        "Potential evapotranspiration (pet) — mm",
        "Precipitation (ppt) — mm",
        "Runoff (q) — mm",
        "Soil moisture (soil) — mm",
        "Shortwave radiation (srad) — W/m²",
        "Snow water equivalent (swe) — mm",
        "Maximum temperature (tmax) — °C",
        "Minimum temperature (tmin) — °C",
        "Vapor pressure (vap) — kPa",
        "Vapor pressure deficit (vpd) — kPa",
        "Wind speed (ws) — m/s",
    ]
    MONTH_LABELS = ["All months"] + [calendar.month_name[i] for i in range(1, 13)]
    STRIDE_LABELS = ["Native (~4 km)", "2 (~8 km)", "4 (~16 km)", "8 (~32 km)", "16 (~64 km)"]
    STRIDES = [1, 2, 4, 8, 16]
    MIN_YEAR = 1958
    MAX_YEAR = 2025

    NCSS_BASES = [
        "https://thredds.northwestknowledge.net/thredds/ncss/TERRACLIMATE_ALL/data",
        "http://thredds.northwestknowledge.net:8080/thredds/ncss/TERRACLIMATE_ALL/data",
    ]
    FILESERVER_BASES = [
        "https://thredds.northwestknowledge.net/thredds/fileServer/TERRACLIMATE_ALL/data",
        "http://thredds.northwestknowledge.net:8080/thredds/fileServer/TERRACLIMATE_ALL/data",
    ]

    def tr(self, text):
        return QCoreApplication.translate("TerraClimateDownloadAlgorithm", text)

    def createInstance(self):
        return TerraClimateDownloadAlgorithm()

    def name(self):
        return "download_terraclimate"

    def displayName(self):
        return self.tr("Download TerraClimate data (dependency-safe)")

    def group(self):
        return ""

    def groupId(self):
        return ""

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))

    def shortHelpString(self):
        return self.tr(
            "Downloads TerraClimate monthly data through THREDDS, clips it to the selected polygon, "
            "and writes GeoTIFF. NCSS is attempted first; if the subset service is unavailable or "
            "returns a server error, the plugin falls back to the yearly NetCDF fileServer download. "
            "This build deliberately avoids xarray/rioxarray/netCDF4/dask and uses the GDAL library "
            "already bundled with QGIS. For a single year with All months, the output has 12 bands."
        )

    def initAlgorithm(self, config=None):
        try:
            polygon_type = QgsProcessing.SourceType.TypeVectorPolygon
        except AttributeError:
            polygon_type = QgsProcessing.TypeVectorPolygon

        try:
            integer_type = QgsProcessingParameterNumber.Type.Integer
            double_type = QgsProcessingParameterNumber.Type.Double
        except AttributeError:
            integer_type = QgsProcessingParameterNumber.Integer
            double_type = QgsProcessingParameterNumber.Double

        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT, self.tr("Area of interest (polygon)"), [polygon_type]
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.VARIABLE, self.tr("TerraClimate variable"), self.VARIABLE_LABELS,
            defaultValue=self.VARIABLES.index("ppt")
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.START_YEAR, self.tr("Start year"), integer_type, 2024,
            minValue=self.MIN_YEAR, maxValue=self.MAX_YEAR
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.END_YEAR, self.tr("End year"), integer_type, 2024,
            minValue=self.MIN_YEAR, maxValue=self.MAX_YEAR
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.MONTH, self.tr("Month"), self.MONTH_LABELS, defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.STRIDE, self.tr("Spatial downsampling"), self.STRIDE_LABELS, defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.BUFFER, self.tr("Bounding-box buffer (degrees)"), double_type, 0.1,
            minValue=0.0, maxValue=5.0
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.RETRIES, self.tr("Network retries"), integer_type, 3,
            minValue=1, maxValue=10
        ))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, self.tr("Output GeoTIFF"), defaultValue=None
        ))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if not layer or not layer.isValid():
            raise QgsProcessingException("A valid polygon layer is required.")

        variable = self.VARIABLES[self.parameterAsEnum(parameters, self.VARIABLE, context)]
        start_year = self.parameterAsInt(parameters, self.START_YEAR, context)
        end_year = self.parameterAsInt(parameters, self.END_YEAR, context)
        month_index = self.parameterAsEnum(parameters, self.MONTH, context)
        stride = self.STRIDES[self.parameterAsEnum(parameters, self.STRIDE, context)]
        buffer_deg = self.parameterAsDouble(parameters, self.BUFFER, context)
        retries = self.parameterAsInt(parameters, self.RETRIES, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        if end_year < start_year:
            raise QgsProcessingException("End year must be greater than or equal to start year.")

        years = list(range(start_year, end_year + 1))
        month = None if month_index == 0 else month_index
        bbox = self._layer_bbox_wgs84(layer, buffer_deg)
        workdir = tempfile.mkdtemp(prefix="terraclimate_qgis_")
        band_files = []

        try:
            cutline = os.path.join(workdir, "aoi.gpkg")
            self._write_cutline(layer, cutline, context)

            total_years = len(years)
            for yi, year in enumerate(years):
                if feedback.isCanceled():
                    raise QgsProcessingException("Operation canceled.")

                feedback.pushInfo("Downloading TerraClimate %s for %s…" % (variable, year))
                nc_path = os.path.join(workdir, "%s_%s.nc" % (variable, year))
                source_kind = self._download_year(
                    variable, year, bbox, stride, nc_path, retries, feedback
                )

                dataset = self._open_netcdf_variable(nc_path, variable)
                if dataset is None:
                    raise QgsProcessingException(
                        "GDAL could not open variable '%s' in %s" % (variable, nc_path)
                    )

                band_count = dataset.RasterCount
                if band_count < 1:
                    raise QgsProcessingException("The downloaded NetCDF contains no raster bands.")

                if month is not None:
                    if month > band_count:
                        raise QgsProcessingException(
                            "Requested month %d but downloaded dataset has only %d band(s)."
                            % (month, band_count)
                        )
                    band_numbers = [month]
                else:
                    band_numbers = list(range(1, band_count + 1))

                feedback.pushInfo(
                    "Using %s source; processing %d band(s)." % (source_kind, len(band_numbers))
                )

                for band_no in band_numbers:
                    if feedback.isCanceled():
                        raise QgsProcessingException("Operation canceled.")
                    raw_tif = os.path.join(
                        workdir, "%s_%s_b%02d_raw.tif" % (variable, year, band_no)
                    )
                    clip_tif = os.path.join(
                        workdir, "%s_%s_b%02d.tif" % (variable, year, band_no)
                    )
                    gdal.Translate(
                        raw_tif,
                        dataset,
                        bandList=[band_no],
                        creationOptions=["COMPRESS=DEFLATE", "TILED=YES"],
                    )
                    self._warp_clip(raw_tif, cutline, clip_tif)
                    band_files.append(clip_tif)

                dataset = None
                feedback.setProgress(int(((yi + 1) / max(1, total_years)) * 85))

            if not band_files:
                raise QgsProcessingException("No output bands were produced.")

            feedback.pushInfo("Building final GeoTIFF with %d band(s)…" % len(band_files))
            vrt_path = os.path.join(workdir, "stack.vrt")
            vrt = gdal.BuildVRT(vrt_path, band_files, separate=True)
            if vrt is None:
                raise QgsProcessingException("Could not build the output band stack.")
            vrt = None

            final = gdal.Translate(
                output,
                vrt_path,
                format="GTiff",
                creationOptions=["COMPRESS=DEFLATE", "TILED=YES", "BIGTIFF=IF_SAFER"],
            )
            if final is None:
                raise QgsProcessingException("Could not create the final GeoTIFF.")
            final = None

            self._set_band_descriptions(output, variable, years, month)
            feedback.setProgress(100)
            feedback.pushInfo("Saved: %s" % output)
            return {self.OUTPUT: output}
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def _layer_bbox_wgs84(self, layer, buffer_deg):
        extent = layer.extent()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if layer.crs() != wgs84:
            transform = QgsCoordinateTransform(layer.crs(), wgs84, QgsProject.instance())
            extent = transform.transformBoundingBox(extent)
        west = max(-180.0, extent.xMinimum() - buffer_deg)
        east = min(180.0, extent.xMaximum() + buffer_deg)
        south = max(-90.0, extent.yMinimum() - buffer_deg)
        north = min(90.0, extent.yMaximum() + buffer_deg)
        if east <= west or north <= south:
            raise QgsProcessingException("Invalid area-of-interest extent.")
        return west, south, east, north

    def _write_cutline(self, layer, path, context):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.fileEncoding = "UTF-8"
        options.layerName = "aoi"
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, path, context.transformContext(), options
        )
        error_code = result[0] if isinstance(result, tuple) else result
        if error_code != QgsVectorFileWriter.NoError:
            raise QgsProcessingException(
                "Could not create temporary AOI cutline: %s" % (result,)
            )

    def _ncss_url(self, base, variable, year, bbox, stride):
        """Build a conservative NCSS request for an individual yearly file.

        TerraClimate yearly files already contain exactly one year, so requesting
        time=all is both simpler and more robust than a synthetic date range.
        """
        west, south, east, north = bbox
        filename = "TerraClimate_%s_%s.nc" % (variable, year)
        query = urllib.parse.urlencode({
            "var": variable,
            "north": "%.8f" % north,
            "south": "%.8f" % south,
            "east": "%.8f" % east,
            "west": "%.8f" % west,
            "horizStride": str(stride),
            "time": "all",
            "timeStride": "1",
            "accept": "netcdf",
        })
        return "%s/%s?%s" % (base.rstrip("/"), filename, query)

    def _fileserver_url(self, base, variable, year):
        filename = "TerraClimate_%s_%s.nc" % (variable, year)
        return "%s/%s" % (base.rstrip("/"), filename)

    def _download_year(self, variable, year, bbox, stride, destination, retries, feedback):
        """Try NCSS first, then fall back to the complete yearly NetCDF file."""
        last_error = None
        user_agent = (
            "TerraClimate-QGIS-Plugin/1.0.1 "
            "(+https://github.com/Heed725/Terraclimate_Downloader_New_Qgis_Plugin)"
        )

        for base in self.NCSS_BASES:
            url = self._ncss_url(base, variable, year, bbox, stride)
            for attempt in range(1, retries + 1):
                try:
                    feedback.pushInfo("NCSS request: %s" % url.split("?")[0])
                    self._download_url(url, destination, user_agent, feedback)
                    return "NCSS subset"
                except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as exc:
                    last_error = exc
                    feedback.pushInfo(
                        "NCSS attempt %d/%d failed: %s" % (attempt, retries, exc)
                    )
                    if attempt < retries:
                        time.sleep(min(2 ** (attempt - 1), 8))

        feedback.pushInfo(
            "NCSS was unavailable. Falling back to the complete yearly TerraClimate NetCDF file."
        )
        for base in self.FILESERVER_BASES:
            url = self._fileserver_url(base, variable, year)
            for attempt in range(1, retries + 1):
                try:
                    feedback.pushInfo("Direct file request: %s" % url)
                    self._download_url(url, destination, user_agent, feedback)
                    return "yearly fileServer NetCDF"
                except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as exc:
                    last_error = exc
                    feedback.pushInfo(
                        "Direct-file attempt %d/%d failed: %s" % (attempt, retries, exc)
                    )
                    if attempt < retries:
                        time.sleep(min(2 ** (attempt - 1), 8))

        raise QgsProcessingException(
            "TerraClimate download failed after NCSS and direct-file retries: %s" % last_error
        )

    def _download_url(self, url, destination, user_agent, feedback):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/x-netcdf, application/octet-stream, */*",
            },
        )
        with urllib.request.urlopen(request, timeout=240) as response, open(
            destination, "wb"
        ) as handle:
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" in content_type:
                preview = response.read(500).decode("utf-8", "replace")
                raise IOError("Server returned HTML instead of NetCDF: %s" % preview[:160])

            downloaded = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if downloaded and downloaded % (25 * 1024 * 1024) < 1024 * 1024:
                    feedback.pushInfo("Downloaded %.1f MB…" % (downloaded / 1048576.0))

        if not os.path.exists(destination) or os.path.getsize(destination) < 512:
            raise IOError("Server returned an unexpectedly small response.")
        feedback.pushInfo(
            "Downloaded %.2f MB" % (os.path.getsize(destination) / 1048576.0)
        )

    def _open_netcdf_variable(self, nc_path, variable):
        direct_name = 'NETCDF:"%s":%s' % (nc_path, variable)
        ds = gdal.Open(direct_name, gdal.GA_ReadOnly)
        if ds is not None and ds.RasterCount > 0:
            return ds

        container = gdal.Open(nc_path, gdal.GA_ReadOnly)
        if container is None:
            return None
        for name, description in container.GetSubDatasets():
            lowered = name.lower()
            if lowered.endswith(":" + variable.lower()) or (":" + variable.lower()) in lowered:
                return gdal.Open(name, gdal.GA_ReadOnly)
        if container.RasterCount > 0:
            return container
        return None

    def _warp_clip(self, source, cutline, destination):
        options = gdal.WarpOptions(
            format="GTiff",
            cutlineDSName=cutline,
            cutlineLayer="aoi",
            cropToCutline=True,
            dstNodata=-9999,
            multithread=True,
            creationOptions=["COMPRESS=DEFLATE", "TILED=YES"],
        )
        result = gdal.Warp(destination, source, options=options)
        if result is None:
            raise QgsProcessingException(
                "GDAL failed while clipping the downloaded raster."
            )
        result = None

    def _set_band_descriptions(self, path, variable, years, month):
        ds = gdal.Open(path, gdal.GA_Update)
        if ds is None:
            return
        labels = []
        for year in years:
            months = [month] if month is not None else range(1, 13)
            for m in months:
                labels.append("%s %04d-%02d" % (variable, year, m))
        for index in range(1, min(ds.RasterCount, len(labels)) + 1):
            ds.GetRasterBand(index).SetDescription(labels[index - 1])
        ds.FlushCache()
        ds = None
