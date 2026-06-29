from pathlib import Path

from qgis.PyQt.QtCore import QObject, QVariant

from qgis.core import (
    QgsProviderRegistry,
    QgsFields,
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsField,
)

from .stored_object_manager import STORED_OBJECT_MANAGER


class MarkupManager(QObject):
    """
    Manages markup functionality
    """

    MARKUP_DB_FILE = "markup.gpkg"

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        if not self.markup_db_path().exists():
            MarkupManager.create_markup_database()

    @staticmethod
    def markup_db_path() -> Path:
        """
        Returns the path to the markup database
        """
        return STORED_OBJECT_MANAGER.get_plugin_data_path(MarkupManager.MARKUP_DB_FILE)

    @staticmethod
    def markup_layer_fields() -> QgsFields:
        """
        Returns the markup layer field definitions
        """
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.LongLong))
        fields.append(QgsField("notes", QVariant.String))
        fields.append(QgsField("open", QVariant.Bool))
        return fields

    @staticmethod
    def create_markup_database():
        """
        Creates a new empty markup database
        """
        markup_layer_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        polygon_markup_layer_uri = {
            "path": MarkupManager.markup_db_path().as_posix(),
            "layerName": "polygon_markup",
        }
        res = QgsProviderRegistry.instance().createEmptyLayer(
            "ogr",
            QgsProviderRegistry.instance().encodeUri("ogr", polygon_markup_layer_uri),
            MarkupManager.markup_layer_fields(),
            Qgis.WkbType.MultiPolygon,
            markup_layer_crs,
            Qgis.CreateLayerActionOnExisting.CreateOrOverwriteFile,
        )
        assert res.result() == Qgis.VectorExportResult.Success

        point_markup_layer_uri = {
            "path": MarkupManager.markup_db_path().as_posix(),
            "layerName": "point_markup",
        }
        res = QgsProviderRegistry.instance().createEmptyLayer(
            "ogr",
            QgsProviderRegistry.instance().encodeUri("ogr", point_markup_layer_uri),
            MarkupManager.markup_layer_fields(),
            Qgis.WkbType.MultiPoint,
            markup_layer_crs,
            Qgis.CreateLayerActionOnExisting.CreateOrOverwriteLayer,
        )
        assert res.result() == Qgis.VectorExportResult.Success

        line_markup_layer_uri = {
            "path": MarkupManager.markup_db_path().as_posix(),
            "layerName": "line_markup",
        }
        res = QgsProviderRegistry.instance().createEmptyLayer(
            "ogr",
            QgsProviderRegistry.instance().encodeUri("ogr", line_markup_layer_uri),
            MarkupManager.markup_layer_fields(),
            Qgis.WkbType.MultiLineString,
            markup_layer_crs,
            Qgis.CreateLayerActionOnExisting.CreateOrOverwriteLayer,
        )
        assert res.result() == Qgis.VectorExportResult.Success
