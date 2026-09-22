from pathlib import Path

from qgis.PyQt.QtCore import QObject, QVariant

from qgis.core import (
    QgsProviderRegistry,
    QgsFields,
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsField,
    QgsProject,
    QgsVectorLayer,
    QgsLayerTreeGroup,
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
        if res.result() != Qgis.VectorExportResult.Success:
            raise AssertionError("Could not create markup database")

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
        if res.result() != Qgis.VectorExportResult.Success:
            raise AssertionError("Could not create markup database")

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
        if res.result() != Qgis.VectorExportResult.Success:
            raise AssertionError("Could not create markup database")

    def project_has_point_markup_layer(self, project: QgsProject) -> bool:
        """
        Returns True if the project contains the point markup layer
        """
        db_path = MarkupManager.markup_db_path().as_posix()
        for _, layer in project.mapLayers().items():
            parts = QgsProviderRegistry.instance().decodeUri(
                layer.providerType(), layer.source()
            )
            if parts["path"] != db_path:
                continue

            elif parts["layerName"] == "point_markup":
                return True

        return False

    def project_has_line_markup_layer(self, project: QgsProject) -> bool:
        """
        Returns True if the project contains the line markup layer
        """
        db_path = MarkupManager.markup_db_path().as_posix()
        for _, layer in project.mapLayers().items():
            parts = QgsProviderRegistry.instance().decodeUri(
                layer.providerType(), layer.source()
            )
            if parts["path"] != db_path:
                continue

            elif parts["layerName"] == "line_markup":
                return True

        return False

    def project_has_polygon_markup_layer(self, project: QgsProject) -> bool:
        """
        Returns True if the project contains the polygon markup layer
        """
        db_path = MarkupManager.markup_db_path().as_posix()
        for _, layer in project.mapLayers().items():
            parts = QgsProviderRegistry.instance().decodeUri(
                layer.providerType(), layer.source()
            )
            if parts["path"] != db_path:
                continue

            elif parts["layerName"] == "polygon_markup":
                return True

        return False

    def project_has_all_markup_layers(self, project: QgsProject) -> bool:
        """
        Returns True if the project contains the markup layers
        """
        return (
            self.project_has_line_markup_layer(project)
            and self.project_has_point_markup_layer(project)
            and self.project_has_polygon_markup_layer(project)
        )

    def load_polygon_markup_layer(self) -> QgsVectorLayer:
        """
        Loads the polygon markup layer
        """
        return QgsVectorLayer(
            self.markup_db_path().as_posix() + "|layername=polygon_markup",
            "Polygon Markup",
            "ogr",
        )

    def load_line_markup_layer(self) -> QgsVectorLayer:
        """
        Loads the line markup layer
        """
        return QgsVectorLayer(
            self.markup_db_path().as_posix() + "|layername=line_markup",
            "Line Markup",
            "ogr",
        )

    def load_point_markup_layer(self) -> QgsVectorLayer:
        """
        Loads the point markup layer
        """
        return QgsVectorLayer(
            self.markup_db_path().as_posix() + "|layername=point_markup",
            "Point Markup",
            "ogr",
        )

    def add_markup_layers_if_not_present(self, project: QgsProject):
        """
        Adds the markup layers to the project if not already present
        """
        if self.project_has_all_markup_layers(project):
            return

        added_layers = []
        if not self.project_has_point_markup_layer(project):
            added_layers.append(self.load_point_markup_layer())
        if not self.project_has_polygon_markup_layer(project):
            added_layers.append(self.load_polygon_markup_layer())
        if not self.project_has_line_markup_layer(project):
            added_layers.append(self.load_line_markup_layer())

        layer_tree = project.layerTreeRoot()
        markup_group = None
        for child in layer_tree.children():
            if isinstance(child, QgsLayerTreeGroup) and child.customProperty(
                "_is_markup_group"
            ):
                markup_group = child
                break

        if markup_group is None:
            markup_group = QgsLayerTreeGroup("Markup", True)
            markup_group.setCustomProperty("_is_markup_group", True)
            layer_tree.insertChildNode(0, markup_group)

        project.addMapLayers(added_layers, False)
        for layer in added_layers:
            markup_group.addLayer(layer)

        project.addMapLayers(added_layers)
