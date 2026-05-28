"""
LayerUtils Test.
"""

import unittest

from qgis.core import (
    QgsVectorLayer,
    QgsAnnotationLayer,
    QgsCoordinateTransformContext,
    QgsProject,
)

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

    def test_valid_edit_target_layers(self):
        """
        Tests valid_edit_target_layers
        """
        layer1 = QgsVectorLayer("Point?crs=epsg:4326", "test_layer", "memory")
        layer2 = QgsVectorLayer("Point?crs=epsg:4326", "test_layer2", "memory")
        layer3 = QgsVectorLayer("Point?crs=epsg:4326", "test_layer3", "memory")
        layer1.setReadOnly(True)
        layer2.startEditing()
        non_vector_layer = QgsAnnotationLayer(
            "test", QgsAnnotationLayer.LayerOptions(QgsCoordinateTransformContext())
        )
        p = QgsProject()
        p.addMapLayers([layer1, layer2, layer3, non_vector_layer])
        self.assertCountEqual(LayerUtils.valid_edit_target_layers(p), [layer2, layer3])


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(LayerUtilsTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
