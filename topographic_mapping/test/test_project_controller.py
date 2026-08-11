import os
import tempfile
import unittest

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsValueMapFieldFormatter,
    QgsField,
    QgsFields,
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter,
    QgsCoordinateTransformContext,
    QgsVectorLayer,
)

from topographic_mapping.core import ProjectController, EditMode
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

    def test_clean_layer_name(self):
        """Tests cleaning product view layer name suffixes."""
        self.assertEqual(
            ProjectController.clean_layer_name("water_point_product_view"),
            "water_point",
        )
        self.assertEqual(
            ProjectController.clean_layer_name("water_point"), "water_point"
        )

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

    def test_map_sheet_layer_and_signals(self):
        """
        Tests map sheet layer retrieval and signal emissions on add/remove.
        """
        project = QgsProject()
        controller = ProjectController(project, None)

        loaded_signal_emitted = False
        unloaded_signal_emitted = False

        def on_loaded():
            nonlocal loaded_signal_emitted
            loaded_signal_emitted = True

        def on_unloaded():
            nonlocal unloaded_signal_emitted
            unloaded_signal_emitted = True

        controller.map_sheet_layer_loaded.connect(on_loaded)
        controller.map_sheet_layer_unloaded.connect(on_unloaded)

        self.assertIsNone(controller.map_sheet_layer())

        fields = QgsFields()
        fields.append(QgsField("type", QVariant.String))
        map_sheet_layer = self.create_dummy_layer(
            ProjectController.MAP_SHEET_LAYER_NAME, fields
        )
        project.addMapLayer(map_sheet_layer)

        self.assertTrue(loaded_signal_emitted)
        self.assertEqual(controller.map_sheet_layer(), map_sheet_layer)

        project.removeMapLayer(map_sheet_layer.id())
        self.assertTrue(unloaded_signal_emitted)
        self.assertIsNone(controller.map_sheet_layer())

    def test_editable_vector_layers_iterator(self):
        """
        Test direct iteration over editable vector layers
        """
        project = QgsProject()
        fields = QgsFields()

        layer1 = self.create_dummy_layer("water_point", fields)
        layer2 = self.create_dummy_layer("airport", fields)
        layer3 = self.create_dummy_layer("coastline", fields)
        layer3.setReadOnly(True)

        project.addMapLayer(layer1)
        project.addMapLayer(layer2)
        project.addMapLayer(layer3)

        controller = ProjectController(project, None)

        iterator = controller.editable_vector_layers()
        got_layers = []
        got_layers.append(next(iterator))
        got_layers.append(next(iterator))
        with self.assertRaises(StopIteration):
            next(iterator)
        self.assertCountEqual(got_layers, [layer1, layer2])

    def test_editable_vector_layers_in_gpkg_iterator(self):
        """
        Test direct iteration over editable vector layers in a specific gpkg
        """
        project = QgsProject()
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.Int))
        fields.append(QgsField("type", QVariant.String))

        layer1 = self.create_dummy_layer("water_point", fields)
        layer2 = self.create_dummy_layer("airport", fields)
        layer2.setReadOnly(True)

        project.addMapLayer(layer1)
        project.addMapLayer(layer2)

        controller = ProjectController(project, None)
        gpkg_path = controller.working_geopackage_path()
        self.assertTrue(gpkg_path)

        iterator = controller.editable_vector_layers_in_gpkg(gpkg_path)
        self.assertEqual(next(iterator), layer1)
        with self.assertRaises(StopIteration):
            next(iterator)

        empty_iterator = controller.editable_vector_layers_in_gpkg(
            "/nonexistent/path.gpkg"
        )
        with self.assertRaises(StopIteration):
            next(empty_iterator)

    def test_working_geopackage_path_and_editable_layers(self):
        """
        Tests determining working GeoPackage path and fetching editable layers in GPKG.
        """
        project = QgsProject()
        controller = ProjectController(project, None)

        gpkg_path = controller.working_geopackage_path()
        self.assertIsNone(gpkg_path)

        fields = QgsFields()
        fields.append(QgsField("id", QVariant.Int))
        fields.append(QgsField("type", QVariant.String))

        layer1 = self.create_dummy_layer("NOT_A_FEATURE_TYPE", fields)
        project.addMapLayer(layer1)

        gpkg_path = controller.working_geopackage_path()
        self.assertIsNone(gpkg_path)
        project.removeMapLayer(layer1.id())

        layer2 = self.create_dummy_layer("water_point", fields)
        project.addMapLayer(layer2)

        gpkg_path = controller.working_geopackage_path()
        self.assertIsNotNone(gpkg_path)
        self.assertTrue(gpkg_path.endswith(".gpkg"))

        layers_in_gpkg = list(controller.editable_vector_layers_in_gpkg(gpkg_path))
        self.assertEqual(len(layers_in_gpkg), 1)
        self.assertEqual(layers_in_gpkg[0], layer2)

    def test_geometry_and_attribute_changed_slots(self):
        """
        Tests automatic tracking of version and change_type on feature edits.
        """
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.Int))
        fields.append(QgsField("name", QVariant.String))
        fields.append(QgsField("change_type", QVariant.String))
        fields.append(QgsField("version", QVariant.Int))

        layer = self.create_dummy_layer("water_point", fields)
        project = QgsProject()
        project.addMapLayer(layer)
        _ = ProjectController(project, None)

        layer.startEditing()
        feat = QgsFeature(layer.fields())
        feat["id"] = 1
        feat["name"] = "test"
        feat["change_type"] = "new"
        feat["version"] = 1
        feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
        layer.addFeature(feat)
        layer.commitChanges()

        fid = next(layer.getFeatures()).id()

        # trigger attribute change on edited feature
        layer.startEditing()
        name_idx = layer.fields().lookupField("name")
        layer.changeAttributeValue(fid, name_idx, "updated_name")

        updated_feat = layer.getFeature(fid)
        self.assertTrue(updated_feat.isValid())
        self.assertEqual(updated_feat["change_type"], "modified attributes")
        self.assertEqual(updated_feat["version"], 2)

        # trigger geometry change on edited feature
        layer.changeGeometry(fid, QgsGeometry.fromPointXY(QgsPointXY(1, 1)))

        updated_feat = layer.getFeature(fid)
        self.assertEqual(updated_feat["change_type"], "modified geometry and att")
        self.assertEqual(updated_feat["version"], 2)
        layer.commitChanges()

        layer.startEditing()
        layer.changeGeometry(fid, QgsGeometry.fromPointXY(QgsPointXY(1, 3)))

        updated_feat = layer.getFeature(fid)
        self.assertEqual(updated_feat["change_type"], "modified geometry and att")
        self.assertEqual(updated_feat["version"], 3)
        layer.commitChanges()

    def test_set_edit_mode(self):
        """
        Tests switching layer edit modes between RealWorld and ProductData.
        """
        project = QgsProject()
        fields = QgsFields()
        fields.append(QgsField("type", QVariant.String))

        layer = self.create_dummy_layer("water_point", fields)
        project.addMapLayer(layer)

        controller = ProjectController(project, None)
        gpkg_path = controller.working_geopackage_path()

        controller.set_edit_mode(gpkg_path, EditMode.ProductData)
        self.assertIn("water_point_product_view", layer.source())

        controller.set_edit_mode(gpkg_path, EditMode.RealWorld)
        self.assertNotIn("water_point_product_view", layer.source())


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestProjectController)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
