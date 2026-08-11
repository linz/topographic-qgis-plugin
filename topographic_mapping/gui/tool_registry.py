from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict
from functools import partial

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import QAction

from qgis.core import Qgis
from qgis.gui import QgisInterface, QgsGui

from topographic_mapping.core import StateManager
from .gui_utils import GuiUtils
from .proxy_action import ProxyAction, CompoundProxyAction, DigitizeTechniqueProxyAction
from .tool_dock import ToolDock


@dataclass
class Action:
    """
    Encapsulates an action
    """

    title: str
    qgis_action_name: str
    icon: str
    description: str


@dataclass
class CompoundAction:
    """
    Encapsulates a compound action, where multiple actions
    must be checked to trigger the overall action
    """

    title: str
    qgis_action_names: list[str]
    icon: str
    description: str


@dataclass
class DigitizeTechniqueAction:
    """
    Encapsulates a digitizing technique action
    """

    title: str
    qgis_action_names: list[str]
    icon: str
    description: str
    geometry_types: list[Qgis.GeometryType]


@dataclass
class CustomAction:
    """
    Encapsulates a custom (plugin specific) action (currently single-shot actions only)
    """

    id: str
    title: str
    icon: str
    description: str
    requires_selection: bool = False


EDITING_GROUP = "Topographic editing"
DIGITIZING_GROUP = "Digitize feature"
LABELING_GROUP = "Labeling"

CHANGE_FEATURE_CLASS_ACTION = "CHANGE_FEATURE_CLASS_ACTION"
PASTRY_DELETE_ACTION = "PASTRY_DELETE_ACTION"
PASTRY_CUT_ACTION = "PASTRY_CUT_ACTION"
CLEAR_PRODUCT_EDITS = "CLEAR_PRODUCT_EDITS"
SELECT_LABELS_ACTION = "SELECT_LABELS_ACTION"
CREATE_LABEL_ACTION = "CREATE_LABEL_ACTION"
RESET_LABEL_ACTION = "RESET_LABEL_ACTION"
REWRAP_LABEL_ACTION = "REWRAP_LABEL_ACTION"

TOOLS = {
    EDITING_GROUP: [
        Action(
            "Edit Attributes",
            "mActionMultiEditAttributes",
            "edit_attributes.svg",
            "Populate or modify feature attributes.",
        ),
        CustomAction(
            CHANGE_FEATURE_CLASS_ACTION,
            "Change Class of Feature",
            "change_class.svg",
            "Change class of selected features.",
            requires_selection=True,
        ),
        Action(
            "Filter Out Points",
            "mActionSimplifyFeature",
            "simplify.svg",
            "Removes unnecessary vertices based on a set tolerance.",
        ),
        Action(
            "Buffer Objects",
            "mActionOffsetCurve",
            "buffer.svg",
            "Create buffer around features at user-defined distance.",
        ),
        Action(
            "Edit Points",
            "mActionVertexTool",
            "modify_vertex.svg",
            "Move, delete and add vertices on line/area features.",
        ),
        Action(
            "Split Features",
            "mActionSplitFeatures",
            "split.svg",
            "Split lines or polygons.",
        ),
        Action(
            "Join Features",
            "mActionMergeFeatures",
            "merge.svg",
            "Join lines or polygons.",
        ),
        Action(
            "Rotate Features",
            "mActionRotateFeature",
            "rotate_feature.svg",
            "Rotate line, area or multipoint features.",
        ),
        Action(
            "Rotate Points",
            "mActionRotatePointSymbols",
            "rotate_marker.svg",
            "Rotate point symbols to new orientation by sight.",
        ),
        Action(
            "Move Features",
            "mActionMoveFeature",
            "translate.svg",
            "Move single or multiple features.",
        ),
        Action(
            "Delete Features",
            "mActionDeleteSelected",
            "delete.svg",
            "Remove single or multiple features.",
        ),
        Action(
            "Copy Features",
            "mActionMoveFeatureCopy",
            "duplicate.svg",
            "Duplicate single or multiple features.",
        ),
        Action(
            "Create Hole in Object",
            "mActionAddRing",
            "create_hole.svg",
            "Cut a hole in a polygon feature.",
        ),
        Action(
            "Fill Hole in Object",
            "mActionDeleteRing",
            "fill_hole.svg",
            "Remove a hole or void from polygon features.",
        ),
        Action(
            "Reverse Order of Vertices",
            "mActionReverseLine",
            "reverse_line.svg",
            "Change direction of line feature.",
        ),
        CustomAction(
            PASTRY_DELETE_ACTION,
            "Pastry Delete",
            "pastry_delete.svg",
            "Remove parts of an object which intersect a related feature.",
            requires_selection=True,
        ),
        CustomAction(
            PASTRY_CUT_ACTION,
            "Pastry Cut",
            "pastry_cut.svg",
            "Split features using other features as cutting lines.",
            requires_selection=True,
        ),
        CustomAction(
            CLEAR_PRODUCT_EDITS,
            "Clear Product Data Edits",
            "delete_product_view.svg",
            "Clears the product view specific edits for the selected features.",
        ),
    ],
    DIGITIZING_GROUP: [
        DigitizeTechniqueAction(
            "Point Digitize",
            ["mActionAddFeature", "mActionDigitizeWithSegment"],
            "digitize_point.svg",
            "Digitize point features.",
            [Qgis.GeometryType.Point],
        ),
        DigitizeTechniqueAction(
            "Digitize Straight Segments",
            ["mActionAddFeature", "mActionDigitizeWithSegment"],
            "digitize_segment.svg",
            "Digitize feature with straight line segments.",
            [Qgis.GeometryType.Line, Qgis.GeometryType.Polygon],
        ),
        DigitizeTechniqueAction(
            "Digitize With Circular String",
            ["mActionAddFeature", "mActionDigitizeWithCurve"],
            "digitize_curve.svg",
            "Digitize feature with circular strings.",
            [Qgis.GeometryType.Line, Qgis.GeometryType.Polygon],
        ),
        DigitizeTechniqueAction(
            "Digitize With Bezier",
            ["mActionAddFeature", "mActionDigitizeWithBezier"],
            "digitize_bezier.svg",
            "Digitize feature with bezier curves.",
            [Qgis.GeometryType.Line, Qgis.GeometryType.Polygon],
        ),
        DigitizeTechniqueAction(
            "Stream Digitize",
            ["mActionAddFeature", "mActionStreamDigitize"],
            "digitize_stream.svg",
            "Digitize features immediately as mouse moves.",
            [Qgis.GeometryType.Line, Qgis.GeometryType.Polygon],
        ),
    ],
    LABELING_GROUP: [
        CustomAction(
            SELECT_LABELS_ACTION,
            "Select Labels",
            "select_label.svg",
            "Selects labels.",
        ),
        CustomAction(
            CREATE_LABEL_ACTION,
            "Create Label",
            "create_label.svg",
            "Creates labels for the selected features.",
        ),
        CustomAction(
            RESET_LABEL_ACTION,
            "Reset Label",
            "reset_label.svg",
            "Resets selected labels to their default appearance.",
        ),
        CustomAction(
            REWRAP_LABEL_ACTION,
            "Rewrap Label",
            "reset_label.svg",
            "Rewraps label text.",
        ),
    ],
}


class ToolRegistry(QObject):
    def __init__(self, parent: QObject, state_manager: StateManager):
        super().__init__(parent)
        self._actions = defaultdict(list)
        self._state_manager = state_manager

        # built in actions
        self.set_target_tool_action = QAction(self)
        self.set_target_tool_action.setText("Set Edit Target")
        self.set_target_tool_action.setCheckable(True)
        self.set_target_tool_action.setIcon(
            GuiUtils.get_colorized_icon("set_edit_target.svg")
        )
        self.set_target_tool_action.setObjectName(
            ToolRegistry.title_to_object_name(self.set_target_tool_action.text())
        )
        self.set_target_tool_action.setProperty(
            "description",
            "Sets the current edit target by selecting features on the map",
        )
        self._actions["_private"].append(self.set_target_tool_action)
        self._custom_actions: Dict[str, QAction] = {}

    @staticmethod
    def title_to_object_name(title: str) -> str:
        return title.replace(" ", "")

    def init(self, iface: QgisInterface):
        for group, actions in TOOLS.items():
            for action in actions:
                if isinstance(action, Action):
                    self._process_action(action, group, iface)
                elif isinstance(action, CompoundAction):
                    self._process_compound_action(action, group, iface)
                elif isinstance(action, DigitizeTechniqueAction):
                    self._process_digitize_technique_action(action, group, iface)
                elif isinstance(action, CustomAction):
                    self._process_custom_action(action, group, iface)
                else:
                    assert False

    def _process_action(self, action: Action, group: str, iface: QgisInterface):
        source_action: QAction = iface.mainWindow().findChild(
            QAction, action.qgis_action_name
        )
        fallback_action = iface.actionPan()
        proxy_action = ProxyAction(
            action.title,
            source_action=source_action,
            fallback_action=fallback_action,
            parent=self,
        )
        proxy_action.setObjectName(ToolRegistry.title_to_object_name(action.title))
        proxy_action.setCheckable(source_action.isCheckable())
        proxy_action.setIcon(GuiUtils.get_colorized_icon(action.icon))

        assert action.description[-1] == "."
        assert action.description[0].isupper()
        proxy_action.setProperty("description", action.description)
        self._actions[group].append(proxy_action)

    def _process_compound_action(
        self, action: CompoundAction, group: str, iface: QgisInterface
    ):
        source_actions: list[QAction] = [
            iface.mainWindow().findChild(QAction, qgis_action_name)
            for qgis_action_name in action.qgis_action_names
        ]

        fallback_action = iface.actionPan()
        proxy_action = CompoundProxyAction(
            action.title,
            source_actions=source_actions,
            fallback_action=fallback_action,
            parent=self,
        )
        proxy_action.setObjectName(ToolRegistry.title_to_object_name(action.title))
        proxy_action.setCheckable(True)
        proxy_action.setIcon(GuiUtils.get_colorized_icon(action.icon))

        assert action.description[-1] == "."
        assert action.description[0].isupper()
        proxy_action.setProperty("description", action.description)
        self._actions[group].append(proxy_action)

    def _process_digitize_technique_action(
        self, action: DigitizeTechniqueAction, group: str, iface: QgisInterface
    ):
        source_actions: list[QAction] = [
            iface.mainWindow().findChild(QAction, qgis_action_name)
            for qgis_action_name in action.qgis_action_names
        ]

        fallback_action = iface.actionPan()
        proxy_action = DigitizeTechniqueProxyAction(
            action.title,
            source_actions=source_actions,
            fallback_action=fallback_action,
            geometry_types=action.geometry_types,
            parent=self,
        )
        proxy_action.setObjectName(ToolRegistry.title_to_object_name(action.title))
        proxy_action.setCheckable(True)
        proxy_action.setIcon(GuiUtils.get_colorized_icon(action.icon))

        assert action.description[-1] == "."
        assert action.description[0].isupper()
        proxy_action.setProperty("description", action.description)
        self._actions[group].append(proxy_action)

    def _process_custom_action(
        self, action: CustomAction, group: str, iface: QgisInterface
    ):
        new_action = QAction()
        new_action.setText(action.title)
        new_action.setObjectName(ToolRegistry.title_to_object_name(action.title))
        new_action.setIcon(GuiUtils.get_colorized_icon(action.icon))

        assert action.description[-1] == "."
        assert action.description[0].isupper()
        new_action.setProperty("description", action.description)
        self._actions[group].append(new_action)
        self._custom_actions[action.id] = new_action

        if action.requires_selection:
            self._state_manager.target_layer_changed.connect(
                partial(self._custom_action_update_state, new_action)
            )
            self._state_manager.current_layer_selection_changed.connect(
                partial(self._custom_action_update_state, new_action)
            )
            self._custom_action_update_state(new_action)

    def _custom_action_update_state(self, action: QAction):
        action.setEnabled(
            self._state_manager.target_layer() is not None
            and self._state_manager.target_layer().selectedFeatureCount() > 0
        )

    def custom_action(self, action_id: str) -> QAction:
        """
        Returns the custom action with specified ID
        """
        return self._custom_actions[action_id]

    def populate_tool_dock(self, dock: ToolDock, groups: List[str]):
        for group, actions in self._actions.items():
            if group not in groups:
                continue

            if group[0] == "_":
                continue

            for action in actions:
                dock.add_tool_action(
                    action,
                    group,
                    action.property("description"),
                    is_digitizing_action=group == DIGITIZING_GROUP,
                )

    def register_shortcuts(self):
        for group, actions in self._actions.items():
            for action in actions:
                QgsGui.shortcutsManager().registerAction(action)

    def unregister_shortcuts(self):
        for group, actions in self._actions.items():
            for action in actions:
                QgsGui.shortcutsManager().unregisterAction(action)
