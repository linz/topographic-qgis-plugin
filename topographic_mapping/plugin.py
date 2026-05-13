from qgis.PyQt.QtCore import Qt, QCoreApplication, QObject
from qgis.PyQt.QtWidgets import QAction, QActionGroup
from qgis.core import QgsSettingsTree

from .gui import ToolDock, GuiUtils


class TopographicMappingPlugin:
    def __init__(self, iface):
        self.iface = iface
        self._gui_owner = QObject()
        self._tool_dock = None
        self._action_group = None

    def initGui(self) -> None:
        self._tool_dock = ToolDock(None)
        self._tool_dock.setObjectName("TopographicTools")
        self._tool_dock.setWindowTitle("Editing tools")

        self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._tool_dock)

        j = 0

        self._action_group = QActionGroup(self._gui_owner)

        for title in ("Topographic editing", "Labeling"):
            for i in range(30):
                j += 1
                action = QAction(str(i), self._gui_owner)
                action.setObjectName(f"EditingTool{j}")
                action.setCheckable(True)
                if i % 2 == 1:
                    action.setIcon(GuiUtils.get_colorized_icon("buffer.svg"))
                else:
                    action.setIcon(GuiUtils.get_colorized_icon("simplify.svg"))
                self._action_group.addAction(action)
                description = (
                    f"Here is some explanatory text for {title} action number {i}"
                )
                self._tool_dock.add_tool_action(action, title, description)

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        if self._tool_dock:
            self._tool_dock.deleteLater()
        if self._gui_owner:
            self._gui_owner.deleteLater()

        QgsSettingsTree.unregisterPluginTreeNode("topographic_mapping")

    @staticmethod
    def tr(message) -> str:
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("TopographicMappingPlugin", message)
