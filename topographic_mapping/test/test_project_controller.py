import os
import tempfile
import unittest

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsProject,
    QgsValueMapFieldFormatter,
    QgsField,
    QgsFields,
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter,
    QgsCoordinateTransformContext,
    QgsVectorLayer,
)

from topographic_mapping.core import ProjectController
from .test_base import TopographicTestBase
from .utilities import get_qgis_app

QGIS_APP = get_qgis_app()


class TestProjectController(TopographicTestBase):
    """Test suite for ProjectController using real QGIS objects (No Mocks)."""

    def setUp(self):
        super().setUp()

        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()
        super().tearDown()

    def create_dummy_layer(self, layer_name: str, fields: QgsFields) -> QgsVectorLayer:
        """
        Helper method to create a real GeoPackage layer on disk, with a specified layer name
        """
        gpkg_path = os.path.join(self.temp_dir.name, f"{layer_name}.gpkg")
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = layer_name

        # Create the file on disk
        writer = QgsVectorFileWriter.create(
            gpkg_path,
            fields,
            Qgis.WkbType.Point,
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsCoordinateTransformContext(),
            options,
        )
        del writer

        uri = f"{gpkg_path}|layername={layer_name}"
        layer = QgsVectorLayer(uri, layer_name, "ogr")
        self.assertTrue(
            layer.isValid(), f"Dummy layer {layer_name} failed to initialize."
        )

        return layer

    def test_layer_schema_configuration(self):
        """Tests that schemas are loaded from disk and widget setups are applied to fields."""

        # mock a water layer
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.Int))
        fields.append(QgsField("t50_id", QVariant.String))
        fields.append(QgsField("type", QVariant.String))
        fields.append(QgsField("name", QVariant.String))
        fields.append(QgsField("capture_method", QVariant.String))
        fields.append(QgsField("change_type", QVariant.String))
        fields.append(QgsField("version", QVariant.Int))

        layer = self.create_dummy_layer("water_point", fields)
        self.assertTrue(layer.isValid())
        project = QgsProject()
        project.addMapLayer(layer)

        _ = ProjectController(project, None)

        version_idx = layer.fields().lookupField("version")
        version_setup = layer.editorWidgetSetup(version_idx)
        self.assertEqual(version_setup.type(), "Range")
        self.assertEqual(version_setup.config().get("Min"), 1.0)
        self.assertEqual(version_setup.config().get("Max"), 2147483647.0)

        feature_type_idx = layer.fields().lookupField("type")
        feature_type_setup = layer.editorWidgetSetup(feature_type_idx)
        self.assertEqual(feature_type_setup.type(), "ValueMap")

        status_map = feature_type_setup.config().get("map", [])
        self.assertIn({"rock": "rock"}, status_map)
        self.assertIn({"soakhole": "soakhole"}, status_map)
        self.assertIn({"<NULL>": QgsValueMapFieldFormatter.NULL_VALUE}, status_map)

        default_def = layer.defaultValueDefinition(feature_type_idx)
        # Because the field is named "type", it explicitly gets overridden
        # to "@current_feature_type" at the end of _set_layer_schema
        self.assertEqual(default_def.expression(), "@current_feature_type")

    def test_layer_for_parent_feature_type(self):
        """
        Test retrieving layers matching a parent feature type
        """
        project = QgsProject()
        fields = QgsFields()
        layer = self.create_dummy_layer("water_point", fields)
        layer.setName("water point")
        self.assertTrue(layer.isValid())
        project.addMapLayer(layer)
        layer = self.create_dummy_layer("water", fields)
        layer.setName("water features")
        self.assertTrue(layer.isValid())
        project.addMapLayer(layer)
        layer = self.create_dummy_layer("water", fields)
        layer.setName("water read only")
        layer.setReadOnly(True)
        self.assertTrue(layer.isValid())
        project.addMapLayer(layer)
        layer = self.create_dummy_layer("airport", fields)
        layer.setName("airports")
        self.assertTrue(layer.isValid())
        project.addMapLayer(layer)
        layer = self.create_dummy_layer("xxyyzz", fields)
        layer.setName("water_point")
        self.assertTrue(layer.isValid())
        project.addMapLayer(layer)
        layer = self.create_dummy_layer("coastline", fields)
        layer.setReadOnly(True)
        self.assertTrue(layer.isValid())
        project.addMapLayer(layer)

        controller = ProjectController(project, None)

        self.assertIsNone(controller.layer_for_feature_type("x"))
        # read only layers should not be returned
        self.assertIsNone(controller.layer_for_feature_type("coastline"))
        self.assertEqual(
            controller.layer_for_feature_type("water_point").name(), "water point"
        )
        self.assertEqual(
            controller.layer_for_feature_type("water").name(), "water features"
        )
        self.assertEqual(
            controller.layer_for_feature_type("airport").name(), "airports"
        )
        self.assertEqual(
            controller.layer_for_feature_type("water_point").name(), "water point"
        )


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestProjectController)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
