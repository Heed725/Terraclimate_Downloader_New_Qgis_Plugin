# -*- coding: utf-8 -*-
import os

from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsApplication, QgsProcessingProvider

from .terraclimate_algorithm import TerraClimateDownloadAlgorithm

QAction = getattr(QtGui, "QAction", None)
if QAction is None:
    QAction = getattr(QtWidgets, "QAction")


class TerraClimateProvider(QgsProcessingProvider):
    def id(self):
        return "terraclimate_downloader"

    def name(self):
        return "TerraClimate Downloader"

    def longName(self):
        return self.name()

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))

    def loadAlgorithms(self):
        self.addAlgorithm(TerraClimateDownloadAlgorithm())


class TerraClimateDownloaderPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None

    def initGui(self):
        self.provider = TerraClimateProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
        self.action = QAction(icon, "TerraClimate Downloader", self.iface.mainWindow())
        self.action.setToolTip("Open the TerraClimate Downloader processing algorithm")
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&TerraClimate Downloader", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu("&TerraClimate Downloader", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None

    def run(self):
        import processing
        processing.execAlgorithmDialog("terraclimate_downloader:download_terraclimate")
