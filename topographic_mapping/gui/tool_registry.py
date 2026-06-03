from collections import defaultdict
from dataclasses import dataclass

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import QAction
from qgis.gui import QgisInterface, QgsGui

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


EDITING_GROUP = "Topographic editing"
DIGITIZING_GROUP = "Digitize feature"

TOOLS = {
    EDITING_GROUP: [
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
    ],
    DIGITIZING_GROUP: [
        DigitizeTechniqueAction(
            "Digitize Straight Segments",
            ["mActionAddFeature", "mActionDigitizeWithSegment"],
            "duplicate.svg",
            "Digitize feature with straight line segments.",
        ),
        DigitizeTechniqueAction(
            "Digitize With Circular String",
            ["mActionAddFeature", "mActionDigitizeWithCurve"],
            "duplicate.svg",
            "Digitize feature with circular strings.",
        ),
        DigitizeTechniqueAction(
            "Digitize With Bezier",
            ["mActionAddFeature", "mActionDigitizeWithBezier"],
            "duplicate.svg",
            "Digitize feature with bezier curves.",
        ),
    ],
}


class ToolRegistry(QObject):
    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._actions = defaultdict(list)

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
            parent=self,
        )
        proxy_action.setObjectName(ToolRegistry.title_to_object_name(action.title))
        proxy_action.setCheckable(True)
        proxy_action.setIcon(GuiUtils.get_colorized_icon(action.icon))

        assert action.description[-1] == "."
        assert action.description[0].isupper()
        proxy_action.setProperty("description", action.description)
        self._actions[group].append(proxy_action)

    def populate_tool_dock(self, dock: ToolDock):
        for group, actions in self._actions.items():
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
