"""
CombinedVectorLayerModel Test.
"""

import unittest

from qgis.PyQt import sip
from qgis.PyQt.QtCore import Qt, QCoreApplication, QEvent
from qgis.core import (
    QgsFeature,
    QgsProject,
    QgsVectorLayer,
)

from topographic_mapping.gui.combined_layer_model import CombinedVectorLayerModel
from .test_base import TopographicTestBase
from .utilities import get_qgis_app

QGIS_APP = get_qgis_app()


class CombinedVectorLayerModelTest(TopographicTestBase):
    """
    Test CombinedVectorLayerModel.
    """

    def _create_memory_layer(self, name: str, values: list) -> QgsVectorLayer:
        """
        Creates a memory vector layer populated with test features.
        """
        layer = QgsVectorLayer("Point?crs=epsg:4326&field=label:string", name, "memory")
        self.assertTrue(layer.isValid())

        features = []
        for val in values:
            feat = QgsFeature(layer.fields())
            feat.setAttribute("label", val)
            features.append(feat)

        layer.dataProvider().addFeatures(features)
        return layer

    def test_concatenation_row_count(self):
        """
        Tests that rows from multiple valid layers are properly combined.
        """
        layer1 = self._create_memory_layer("layer_1", ["A1", "A2"])
        layer2 = self._create_memory_layer("layer_2", ["B1", "B2", "B3"])

        model = CombinedVectorLayerModel([layer1, layer2])

        self.assertEqual(model.rowCount(), 5)
        self.assertEqual(len(model._source_models), 2)
        self.assertEqual(len(model._layer_caches), 2)

    def test_handles_invalid_and_none_layers(self):
        """
        Tests that None or invalid vector layers are ignored gracefully without throwing errors.
        """
        valid_layer = self._create_memory_layer("valid_layer", ["Val1", "Val2"])
        invalid_layer = QgsVectorLayer("invalid_source_path.shp", "broken", "ogr")
        self.assertFalse(invalid_layer.isValid())

        model = CombinedVectorLayerModel([None, invalid_layer, valid_layer])

        # Only the valid layer should be added
        self.assertEqual(len(model._source_models), 1)
        self.assertEqual(model.rowCount(), 2)

    def test_get_source_layer_and_row(self):
        """
        Tests mapping proxy model rows back to their underlying source layer and original row indices.
        """
        layer1 = self._create_memory_layer("layer_1", ["A1", "A2"])
        layer2 = self._create_memory_layer("layer_2", ["B1", "B2", "B3"])

        model = CombinedVectorLayerModel([layer1, layer2])

        # Rows 0 and 1 should map to layer1
        src_layer_0, src_row_0 = model.get_source_layer_and_row(0)
        self.assertEqual(src_layer_0, layer1)
        self.assertEqual(src_row_0, 0)

        src_layer_1, src_row_1 = model.get_source_layer_and_row(1)
        self.assertEqual(src_layer_1, layer1)
        self.assertEqual(src_row_1, 1)

        # Rows 2, 3, and 4 should map to layer2 (rows 0, 1, and 2 in source model)
        src_layer_2, src_row_2 = model.get_source_layer_and_row(2)
        self.assertEqual(src_layer_2, layer2)
        self.assertEqual(src_row_2, 0)

        src_layer_4, src_row_4 = model.get_source_layer_and_row(4)
        self.assertEqual(src_layer_4, layer2)
        self.assertEqual(src_row_4, 2)

    def test_get_source_layer_and_row_out_of_bounds(self):
        """
        Tests that an invalid or out-of-bounds row index safely returns (None, None).
        """
        layer = self._create_memory_layer("layer_1", ["A1"])
        model = CombinedVectorLayerModel([layer])

        # Negative index and index exceeding rowCount
        src_layer_neg, src_row_neg = model.get_source_layer_and_row(-1)
        self.assertIsNone(src_layer_neg)
        self.assertIsNone(src_row_neg)

        src_layer_oob, src_row_oob = model.get_source_layer_and_row(99)
        self.assertIsNone(src_layer_oob)
        self.assertIsNone(src_row_oob)

    def test_data_retrieval(self):
        """
        Tests that display data across different layers can be read via the proxy model.
        """
        layer1 = self._create_memory_layer("layer_1", ["Alpha"])
        layer2 = self._create_memory_layer("layer_2", ["Beta"])

        model = CombinedVectorLayerModel([layer1, layer2])

        # Cell at row 0 (layer 1)
        index_0 = model.index(0, 0)
        self.assertEqual(model.data(index_0, Qt.ItemDataRole.DisplayRole), "Alpha")

        # Cell at row 1 (layer 2)
        index_1 = model.index(1, 0)
        self.assertEqual(model.data(index_1, Qt.ItemDataRole.DisplayRole), "Beta")

    def test_layer_deletion_via_project(self):
        """
        Tests that when a layer is removed and destroyed via QgsProject,
        the model automatically removes the source model and adjusts rows.
        """
        layer1 = self._create_memory_layer("layer_1", ["A1", "A2"])
        layer2 = self._create_memory_layer("layer_2", ["B1", "B2", "B3"])

        model = CombinedVectorLayerModel([layer1, layer2])
        self.assertEqual(model.rowCount(), 5)
        self.assertEqual(len(model._source_models), 2)
        self.assertEqual(len(model._layer_caches), 2)

        sip.delete(layer1)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        # Model should have cleaned up layer1 automatically
        self.assertEqual(model.rowCount(), 3)
        self.assertEqual(len(model._source_models), 1)
        self.assertEqual(len(model._layer_caches), 1)

        src_layer_0, src_row_0 = model.get_source_layer_and_row(0)
        self.assertEqual(src_layer_0, layer2)
        self.assertEqual(src_row_0, 0)
        self.assertEqual(
            model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole), "B1"
        )

        src_layer_oob, src_row_oob = model.get_source_layer_and_row(4)
        self.assertIsNone(src_layer_oob)
        self.assertIsNone(src_row_oob)

    def test_empty_model_after_all_layers_deleted(self):
        """
        Tests that the model remains operational and returns valid empty states
        when all constituent layers are destroyed.
        """
        layer1 = self._create_memory_layer("layer_1", ["A1"])
        model = CombinedVectorLayerModel([layer1])
        self.assertEqual(model.rowCount(), 1)

        sip.delete(layer1)

        self.assertEqual(model.rowCount(), 0)
        self.assertEqual(len(model._source_models), 0)
        self.assertEqual(len(model._layer_caches), 0)
        self.assertIsNone(model.get_source_layer_and_row(0)[0])


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(CombinedVectorLayerModelTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
