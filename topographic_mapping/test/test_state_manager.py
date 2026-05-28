"""
StateManager Test.
"""

import unittest

from qgis.core import QgsVectorLayer
from qgis.gui import QgsMapCanvas
from topographic_mapping.core import StateManager
from .utilities import get_qgis_app
from .qgis_interface import QgisInterface
from .test_base import TopographicTestBase
from qgis.PyQt.QtTest import QSignalSpy

QGIS_APP = get_qgis_app()


class StateManagerTest(TopographicTestBase):
    """Test StateManager works."""

    def setUp(self):
        super().setUp()

        self.canvas = QgsMapCanvas()
        self.mock_iface = QgisInterface(self.canvas)

        # Create a valid QGIS memory layer for testing
        self.memory_layer = QgsVectorLayer(
            "Point?crs=epsg:4326", "test_layer1", "memory"
        )
        self.assertTrue(self.memory_layer.isValid())
        self.memory_layer2 = QgsVectorLayer(
            "Point?crs=epsg:4326", "test_layer2", "memory"
        )
        self.assertTrue(self.memory_layer2.isValid())

        self.memory_layer3 = QgsVectorLayer(
            "Point?crs=epsg:4326", "test_layer3", "memory"
        )
        self.assertTrue(self.memory_layer3.isValid())
        self.memory_layer3.setReadOnly(True)

    def testSetTargetLayerValid(self):
        """
        Tests set_target_layer with a valid, editable layer.
        """
        state_manager = StateManager(self.mock_iface)
        self.assertFalse(self.memory_layer.isEditable())
        layer_changed_spy = QSignalSpy(self.mock_iface.currentLayerChanged)

        state_manager.set_target_layer(self.memory_layer)
        self.assertEqual(state_manager.target_layer(), self.memory_layer)

        # Manager should have started an edit session and set it active
        self.assertTrue(self.memory_layer.isEditable())
        self.assertEqual(len(layer_changed_spy), 1)

        state_manager.set_target_layer(self.memory_layer)
        self.assertEqual(len(layer_changed_spy), 1)
        self.assertEqual(state_manager.target_layer(), self.memory_layer)

        self.memory_layer2.startEditing()
        state_manager.set_target_layer(self.memory_layer2)
        self.assertEqual(len(layer_changed_spy), 2)
        self.assertEqual(state_manager.target_layer(), self.memory_layer2)

        # cannot set to read-only layer
        state_manager.set_target_layer(self.memory_layer3)
        self.assertEqual(len(layer_changed_spy), 2)
        self.assertEqual(state_manager.target_layer(), self.memory_layer2)

    def testOnCurrentLayerChangedValid(self):
        """
        Tests iface layer changes
        """
        self.memory_layer.startEditing()
        self.memory_layer2.rollBack()
        state_manager = StateManager(self.mock_iface)

        # Track signal emission
        emitted_layers = []
        state_manager.target_layer_changed.connect(
            lambda layer: emitted_layers.append(layer)
        )

        self.mock_iface.setActiveLayer(self.memory_layer)
        self.assertEqual(state_manager.target_layer(), self.memory_layer)

        self.assertEqual(len(emitted_layers), 1)
        self.assertEqual(emitted_layers[-1], self.memory_layer)

        self.mock_iface.setActiveLayer(self.memory_layer)
        self.assertEqual(state_manager.target_layer(), self.memory_layer)
        self.assertEqual(len(emitted_layers), 1)

        # not editable layer
        self.assertFalse(self.memory_layer2.isEditable())
        self.mock_iface.setActiveLayer(self.memory_layer2)
        self.assertIsNone(state_manager.target_layer())
        self.assertEqual(len(emitted_layers), 2)
        self.assertEqual(emitted_layers[-1], None)

        self.mock_iface.setActiveLayer(self.memory_layer)
        self.assertEqual(state_manager.target_layer(), self.memory_layer)
        self.assertEqual(len(emitted_layers), 3)
        self.assertEqual(emitted_layers[-1], self.memory_layer)

        # read only layer
        self.mock_iface.setActiveLayer(self.memory_layer3)
        self.assertIsNone(state_manager.target_layer())
        self.assertEqual(len(emitted_layers), 4)
        self.assertEqual(emitted_layers[-1], None)

        # no extra signal for changing to another invalid layer
        self.mock_iface.setActiveLayer(self.memory_layer2)
        self.assertIsNone(state_manager.target_layer())
        self.assertEqual(len(emitted_layers), 4)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(StateManagerTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
