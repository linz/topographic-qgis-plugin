"""
StateManager: Manages project and editing states
"""

from qgis.PyQt.QtCore import QObject, pyqtSignal

from qgis.core import QgsMapLayer, QgsVectorLayer
from qgis.gui import QgisInterface

from .layer_utils import LayerUtils


class StateManager(QObject):
    """
    Manages project and editing states
    """

    # Emitted when the target editable layer is changed
    target_layer_changed = pyqtSignal(QgsMapLayer)

    def __init__(self, iface: QgisInterface, parent: QObject | None = None):
        super().__init__(parent)

        self._iface = iface
        self._current_target_layer: QgsVectorLayer | None = None

        self._iface.currentLayerChanged.connect(self._on_current_layer_changed)

    def target_layer(self) -> QgsVectorLayer | None:
        """
        Returns the current target layer, if set
        """
        return self._current_target_layer

    def set_target_layer(self, layer: QgsVectorLayer | None) -> bool:
        """
        Sets the current target layer.

        Returns True if the layer was accepted
        """
        if not LayerUtils.can_edit(layer):
            return False

        if not layer.isEditable():
            layer.startEditing()
        if layer != self._iface.activeLayer():
            self._iface.setActiveLayer(layer)
        return True

    def set_edit_target(self, layer: QgsVectorLayer, feature_id: int):
        """
        Sets the current edit target (both layer and feature)
        """
        if self.set_target_layer(layer):
            # only change selection if edit target was accepted
            layer.selectByIds([feature_id])

    def _on_current_layer_changed(self, layer: QgsMapLayer | None):
        """
        Triggered when the user changes the current project layer
        """
        target_layer = None
        if LayerUtils.can_edit(layer) and layer.isEditable():
            target_layer = layer

        if target_layer == self._current_target_layer:
            return

        self._current_target_layer = target_layer
        self.target_layer_changed.emit(self._current_target_layer)
