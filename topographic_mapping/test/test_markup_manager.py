import os
from pathlib import Path
import tempfile
import unittest

from pip._internal.utils import temp_dir
from qgis.PyQt.QtCore import QVariant
from qgis._core import QgsWkbTypes
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
    QgsVectorLayerSimpleLabeling,
    QgsPalLayerSettings,
)

from topographic_mapping.core import MarkupManager
from .test_base import TopographicTestBase
from .utilities import get_qgis_app

QGIS_APP = get_qgis_app()


class TestMarkupManager(TopographicTestBase):
    """
    Test suite for MarkupManager
    """

    def setUp(self):
        super().setUp()

        self.temp_dir = tempfile.TemporaryDirectory()
        temp_dir = self.temp_dir

        @staticmethod
        def markup_db_path():
            nonlocal temp_dir
            return Path(temp_dir.name) / "markup.gpkg"

        MarkupManager.markup_db_path = markup_db_path

    def tearDown(self):
        self.temp_dir.cleanup()
        super().tearDown()

    def test_db_path(self):
        manager = MarkupManager()
        self.assertTrue(manager.markup_db_path())

    def test_create_markup_db(self):
        manager = MarkupManager()
        manager.create_markup_database()

        db_path = manager.markup_db_path().as_posix()

        vl = QgsVectorLayer(
            db_path + "|layername=polygon_markup", "markup database", "ogr"
        )
        self.assertTrue(vl.isValid())
        self.assertEqual(vl.wkbType(), Qgis.WkbType.MultiPolygon)

        vl = QgsVectorLayer(
            db_path + "|layername=point_markup", "markup database", "ogr"
        )
        self.assertTrue(vl.isValid())
        self.assertEqual(vl.wkbType(), Qgis.WkbType.MultiPoint)

        vl = QgsVectorLayer(
            db_path + "|layername=line_markup", "markup database", "ogr"
        )
        self.assertTrue(vl.isValid())
        self.assertEqual(vl.wkbType(), Qgis.WkbType.MultiLineString)

    def test_layers(self):
        manager = MarkupManager()
        poly = manager.load_polygon_markup_layer()
        self.assertTrue(poly.isValid())
        self.assertEqual(poly.wkbType(), Qgis.WkbType.MultiPolygon)

        line = manager.load_line_markup_layer()
        self.assertTrue(line.isValid())
        self.assertEqual(line.wkbType(), Qgis.WkbType.MultiLineString)

        point = manager.load_point_markup_layer()
        self.assertTrue(point.isValid())
        self.assertEqual(point.wkbType(), Qgis.WkbType.MultiPoint)

    def test_markup_layers_in_project(self):
        manager = MarkupManager()
        project = QgsProject()
        self.assertFalse(manager.project_has_all_markup_layers(project))
        self.assertFalse(manager.project_has_point_markup_layer(project))
        self.assertFalse(manager.project_has_line_markup_layer(project))
        self.assertFalse(manager.project_has_polygon_markup_layer(project))

        poly = manager.load_polygon_markup_layer()
        project.addMapLayer(poly)
        self.assertFalse(manager.project_has_all_markup_layers(project))
        self.assertFalse(manager.project_has_point_markup_layer(project))
        self.assertFalse(manager.project_has_line_markup_layer(project))
        self.assertTrue(manager.project_has_polygon_markup_layer(project))

        line = manager.load_line_markup_layer()
        project.addMapLayer(line)
        self.assertFalse(manager.project_has_all_markup_layers(project))
        self.assertFalse(manager.project_has_point_markup_layer(project))
        self.assertTrue(manager.project_has_line_markup_layer(project))
        self.assertTrue(manager.project_has_polygon_markup_layer(project))

        point = manager.load_point_markup_layer()
        project.addMapLayer(point)
        self.assertTrue(manager.project_has_all_markup_layers(project))
        self.assertTrue(manager.project_has_point_markup_layer(project))
        self.assertTrue(manager.project_has_line_markup_layer(project))
        self.assertTrue(manager.project_has_polygon_markup_layer(project))

    def test_add_markup_layers(self):
        manager = MarkupManager()
        project = QgsProject()
        manager.add_markup_layers_if_not_present(project)
        self.assertTrue(manager.project_has_all_markup_layers(project))

        project = QgsProject()
        project.addMapLayer(manager.load_point_markup_layer())
        manager.add_markup_layers_if_not_present(project)
        self.assertEqual(len(project.mapLayers()), 3)
        self.assertTrue(manager.project_has_all_markup_layers(project))

        project = QgsProject()
        project.addMapLayer(manager.load_line_markup_layer())
        manager.add_markup_layers_if_not_present(project)
        self.assertEqual(len(project.mapLayers()), 3)
        self.assertTrue(manager.project_has_all_markup_layers(project))

        project = QgsProject()
        project.addMapLayer(manager.load_point_markup_layer())
        manager.add_markup_layers_if_not_present(project)
        self.assertEqual(len(project.mapLayers()), 3)
        self.assertTrue(manager.project_has_all_markup_layers(project))

    def test_markup_group(self):
        manager = MarkupManager()
        project = QgsProject()
        manager.add_markup_layers_if_not_present(project)

        root = project.layerTreeRoot()
        markup_group = root.findGroup("Markup")
        self.assertIsNotNone(markup_group)
        self.assertTrue(markup_group.customProperty("_is_markup_group"))

        self.assertEqual(len(markup_group.children()), 3)

        # using existing group
        polygon_layer = project.mapLayersByName("Polygon Markup")[0]
        project.removeMapLayer(polygon_layer)
        self.assertEqual(len(markup_group.children()), 2)

        manager.add_markup_layers_if_not_present(project)
        self.assertEqual(len(markup_group.children()), 3)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMarkupManager)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
