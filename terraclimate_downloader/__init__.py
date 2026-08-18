# -*- coding: utf-8 -*-
"""TerraClimate Downloader for QGIS."""


def classFactory(iface):
    from .plugin import TerraClimateDownloaderPlugin
    return TerraClimateDownloaderPlugin(iface)
