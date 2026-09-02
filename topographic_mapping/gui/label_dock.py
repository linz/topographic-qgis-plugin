from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QAction,
)
from qgis.core import QgsVectorLayer

from .tool_dock import ToolDock


class LabelDock(ToolDock):
    """
    A dock widget for display of labeling tools
    """

    target_layer_set = pyqtSignal(QgsVectorLayer)

    def __init__(self, edit_target_tool_action: QAction, parent):
        super().__init__(
            edit_target_tool_action, vertical_layout_offset=0, parent=parent
        )
