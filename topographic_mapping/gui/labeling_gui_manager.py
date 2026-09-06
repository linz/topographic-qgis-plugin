"""
Labeling GUI manager
"""

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import QAction

from qgis.gui import QgsMapCanvas, QgsAdvancedDigitizingDockWidget, QgsMessageBar
from qgis.core import QgsFeature, QgsPoint, QgsGeometry, QgsLineString

from topographic_mapping.core import LabelManager, StateManager, ProjectController

from .tool_registry import (
    ToolRegistry,
    CREATE_LABEL_ACTION,
    RESET_LABEL_ACTION,
    SELECT_LABELS_ACTION,
)

from .digitize_label_tool import DigitizeLabelTool
from .select_by_label_tool import SelectByLabelRectangleTool


class LabelingGuiManager(QObject):
    """
    Labeling GUI manager
    """

    def __init__(
        self,
        canvas: QgsMapCanvas,
        cad_dock: QgsAdvancedDigitizingDockWidget,
        message_bar: QgsMessageBar,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._canvas: QgsMapCanvas = canvas
        self._cad_dock: QgsAdvancedDigitizingDockWidget = cad_dock
        self._message_bar: QgsMessageBar = message_bar
        self._label_manager: LabelManager | None = None
        self._project_controller: ProjectController | None = None
        self._state_manager: StateManager | None = None
        self._create_label_action: QAction | None = None
        self._select_labels_action: QAction | None = None
        self._reset_label_action: QAction | None = None

        self._select_by_label_tool: SelectByLabelRectangleTool = (
            SelectByLabelRectangleTool(self._canvas)
        )

        self._digitize_label_tool = DigitizeLabelTool(self._canvas, self._cad_dock)

    def unregister(self):
        if self._digitize_label_tool:
            self._digitize_label_tool.deleteLater()
            self._digitize_label_tool = None

    def set_label_manager(self, manager: LabelManager):
        self._label_manager = manager

    def set_state_manager(self, manager: StateManager):
        self._state_manager = manager

    def set_project_controller(self, controller: ProjectController):
        self._project_controller = controller

    def register_tools(self, tool_registry: ToolRegistry):
        self._select_labels_action = tool_registry.custom_action(SELECT_LABELS_ACTION)
        self._select_labels_action.triggered.connect(self._select_labels)

        self._create_label_action = tool_registry.custom_action(CREATE_LABEL_ACTION)
        self._create_label_action.triggered.connect(self._create_labels)

        self._reset_label_action = tool_registry.custom_action(RESET_LABEL_ACTION)
        self._reset_label_action.triggered.connect(self._reset_labels)

    def _select_labels(self):
        self._select_by_label_tool.set_label_layer(
            self._project_controller.label_target_layer()
        )
        self._canvas.setMapTool(self._select_by_label_tool)

    def _create_labels(self):
        target_layer = self._state_manager.target_layer()
        if not target_layer:
            # todo - warning
            print(" no target layer")
            return

        target_fids = target_layer.selectedFeatureIds()
        if not target_fids:
            self._message_bar.clearWidgets()
            self._message_bar.pushWarning(
                "", "Select a feature to create the label for first"
            )
            return

        target_fid = next(iter(target_fids))

        if not self._project_controller.label_target_layer():
            self._message_bar.clearWidgets()
            self._message_bar.pushWarning("", "No carto text layer found in project")
            return

        label_properties = self._label_manager.get_label_properties_for_feature(
            target_layer, target_fid
        )
        if not label_properties.label_text:
            self._message_bar.clearWidgets()
            self._message_bar.pushWarning("", "Selected feature has no label text")
            return

        label_layer = self._project_controller.label_target_layer()
        new_feature = QgsFeature(label_properties.label_feature)
        label_layer.addFeature(new_feature)

        self._digitize_label_tool.set_target_feature(new_feature.id())
        self._digitize_label_tool.set_target_layer(label_layer)
        self._digitize_label_tool.set_target_width(label_properties.label_width)

        self._digitize_label_tool._previous_tool = self._canvas.mapTool()

        self._canvas.setMapTool(self._digitize_label_tool)

    def _reset_labels(self):
        label_layer = self._project_controller.label_target_layer()
        if not label_layer:
            self._message_bar.clearWidgets()
            self._message_bar.pushWarning("", "No carto text layer found in project")
            return

        selected_label_fids = label_layer.selectedFeatureIds()
        if not selected_label_fids:
            self._message_bar.clearWidgets()
            self._message_bar.pushWarning("", "No labels are selected")
            return

        if not label_layer.isEditable():
            label_layer.startEditing()

        rc = self._label_manager.create_render_context()
        label_layer.beginEditCommand("Reset labels")
        for label_feature in label_layer.getSelectedFeatures():
            width = self._label_manager.get_width_for_label(label_feature, rc)

            label_geometry = label_feature.geometry()
            for part in label_geometry.constParts():
                start_pt = part.startPoint()
                break

            end_pt = QgsPoint(start_pt.x() + width, start_pt.y())
            line_geom = QgsGeometry(QgsLineString([start_pt, end_pt]))

            label_layer.changeGeometry(label_feature.id(), line_geom)
        label_layer.endEditCommand()
