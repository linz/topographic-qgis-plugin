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


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMarkupManager)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
