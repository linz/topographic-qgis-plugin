"""
DbUtils Test.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsRectangle,
    QgsVectorLayer,
    QgsGeometry,
)

from topographic_mapping.core import DbUtils
from .test_base import TopographicTestBase
from .utilities import get_qgis_app

QGIS_APP = get_qgis_app()


class DbUtilsTest(TopographicTestBase):
    """Test DbUtils works."""

    def test_create_product_view(self):
        """
        Test automatic creation of product views
        """
        gpkg_path = self.get_test_data_path("test_db.gpkg")
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = Path(temp_dir) / "db.gpkg"
            shutil.copy(gpkg_path, data_path)

            original_layer = QgsVectorLayer(
                data_path.as_posix() + "|layername=ferry_crossing"
            )
            self.assertTrue(original_layer.isValid())
            # product_geom should not exist yet
            self.assertEqual(original_layer.fields().lookupField("product_geom"), -1)
            del original_layer

            self.assertFalse(DbUtils.product_view_exists(data_path, "ferry_crossing"))

            DbUtils.create_product_view(data_path, "ferry_crossing")

            self.assertTrue(DbUtils.product_view_exists(data_path, "ferry_crossing"))

            original_layer = QgsVectorLayer(
                data_path.as_posix() + "|layername=ferry_crossing"
            )
            self.assertTrue(original_layer.isValid())
            # product_geom should now exist
            self.assertNotEqual(original_layer.fields().lookupField("product_geom"), -1)

            # product view should be loaded as a vector layer
            product_view = QgsVectorLayer(
                data_path.as_posix() + "|layername=ferry_crossing_product_view"
            )
            self.assertTrue(product_view.isValid())
            self.assertEqual(product_view.wkbType(), Qgis.WkbType.LineString)
            self.assertEqual(
                product_view.crs(), QgsCoordinateReferenceSystem("EPSG:2193")
            )
            self.assertEqual(product_view.featureCount(), 3)
            self.assertEqual(
                product_view.extent(),
                QgsRectangle(
                    1329641.53013898991048336,
                    4897953.70219323970377445,
                    1701870.74363599997013807,
                    6097301.61298200022429228,
                ),
            )
            self.assertEqual(
                [f.name() for f in product_view.fields()],
                [
                    "fid",
                    "id",
                    "t50_fid",
                    "type",
                    "updated_at",
                    "created_at",
                    "original_geom",
                    "product_geom",
                ],
            )
            self.assertTrue(product_view.startEditing())
            f = next(product_view.getFeatures())
            self.assertEqual(
                f.geometry().asWkt(1),
                (
                    "LineString (1699423.9 6095306.3, 1699921.5 6095532.1, 1700041.3 6095651.9, "
                    "1701096.6 6096730.2, 1701585 6097191, 1701870.7 6097301.6)"
                ),
            )

            self.assertTrue(
                product_view.changeGeometry(
                    f.id(),
                    QgsGeometry.fromWkt(
                        "LineString (1699423.9 6095306.3, 1699921.5 6095542.1)"
                    ),
                )
            )
            self.assertTrue(product_view.commitChanges())

            del original_layer
            del product_view
            original_layer = QgsVectorLayer(
                data_path.as_posix() + "|layername=ferry_crossing"
            )
            updated_feature = original_layer.getFeature(f.id())
            self.assertEqual(
                updated_feature.geometry().asWkt(1),
                (
                    "LineString (1699423.9 6095306.3, 1699921.5 6095532.1, 1700041.3 6095651.9, "
                    "1701096.6 6096730.2, 1701585 6097191, 1701870.7 6097301.6)"
                ),
            )

            product_view = QgsVectorLayer(
                data_path.as_posix() + "|layername=ferry_crossing_product_view"
            )
            product_feature = product_view.getFeature(f.id())
            self.assertEqual(
                product_feature.geometry().asWkt(1),
                "LineString (1699423.9 6095306.3, 1699921.5 6095542.1)",
            )


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(DbUtilsTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
