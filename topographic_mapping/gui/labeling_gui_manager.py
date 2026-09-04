"""
Labeling GUI manager
"""

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import QAction

from qgis.gui import QgsMapCanvas, QgsAdvancedDigitizingDockWidget

from topographic_mapping.core import LabelManager

from .tool_registry import ToolRegistry, CREATE_LABEL_ACTION

from .digitize_label_tool import DigitizeLabelTool


class LabelingGuiManager(QObject):
    """
    Labeling GUI manager
    """

    def __init__(
        self,
        canvas: QgsMapCanvas,
        cad_dock: QgsAdvancedDigitizingDockWidget,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._canvas: QgsMapCanvas = canvas
        self._cad_dock: QgsAdvancedDigitizingDockWidget = cad_dock
        self._label_manager: LabelManager | None = None
        self._create_label_action: QAction | None = None

        self._digitize_label_tool: DigitizeLabelTool | None = None

        self._digitize_label_tool = DigitizeLabelTool(self._canvas, self._cad_dock)

    def set_label_manager(self, manager: LabelManager):
        self._label_manager = manager

    def register_tools(self, tool_registry: ToolRegistry):
        self._create_label_action = tool_registry.custom_action(CREATE_LABEL_ACTION)

        self._create_label_action.triggered.connect(self._create_labels)

    def _create_labels(self):
        target_layer = self._state_manager.target_layer()
        if not target_layer:
            # todo - warning
            print(" no target layer")
            return

        target_fids = target_layer.selectedFeatureIds()
        if not target_fids:
            # todo - warning
            print(" no target features")
            return

        target_fid = next(iter(target_fids))

        label_properties = self._label_manager.get_label_properties_for_feature(
            target_layer, target_fid
        )
        if not label_properties.label_text:
            self.iface.messageBar().pushWarning(
                "", "Selected feature has no label text"
            )
            return

        label_layer = self._project_controller.label_target_layer()
        new_feature = QgsFeature(label_properties.label_feature)
        label_layer.addFeature(new_feature)

        self._digitize_label_tool.set_target_feature(new_feature.id())
        self._digitize_label_tool.set_target_layer(label_layer)
        self._digitize_label_tool.set_target_width(label_properties.label_width)

        self._digitize_label_tool._previous_tool = self.iface.mapCanvas().mapTool()

        self.iface.mapCanvas().setMapTool(self._digitize_label_tool)
