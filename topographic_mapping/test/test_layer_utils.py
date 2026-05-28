"""
LayerUtils Test.
"""

import unittest

from qgis.core import QgsVectorLayer, QgsAnnotationLayer, QgsCoordinateTransformContext

from topographic_mapping.core import LayerUtils
from .test_base import TopographicTestBase
from .utilities import get_qgis_app

QGIS_APP = get_qgis_app()


class LayerUtilsTest(TopographicTestBase):
    """Test LayerUtils works."""

    def test_can_edit(self):
        """
        Tests set_target_layer with a valid, editable layer.
        """
        self.assertFalse(LayerUtils.can_edit(None))
        layer = QgsVectorLayer("Point?crs=epsg:4326", "test_layer3", "memory")
        self.assertTrue(LayerUtils.can_edit(layer))

        layer.setReadOnly(True)
        self.assertFalse(LayerUtils.can_edit(layer))

        non_vector_layer = QgsAnnotationLayer(
            "test", QgsAnnotationLayer.LayerOptions(QgsCoordinateTransformContext())
        )
        self.assertFalse(LayerUtils.can_edit(non_vector_layer))


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(LayerUtilsTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
