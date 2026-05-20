from typing import Optional

from qgis.PyQt.QtCore import Qt, QCoreApplication, QObject
from qgis.core import QgsSettingsTree
from qgis.gui import QgisInterface

from .gui import ToolDock, ToolRegistry


class TopographicMappingPlugin:
    def __init__(self, iface: QgisInterface):
        self.iface = iface
        self._gui_owner = QObject()
        self._tool_dock: Optional[ToolDock] = None
        self._action_group = None
        self._tool_registry: Optional[ToolRegistry] = None

    def initGui(self) -> None:
        self._tool_dock = ToolDock(None)
        self._tool_dock.setObjectName("TopographicTools")
        self._tool_dock.setWindowTitle("Editing tools")

        self._tool_registry = ToolRegistry(self._gui_owner)
        self._tool_registry.init(self.iface)
        self._tool_registry.register_shortcuts()

        self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._tool_dock)

        self._tool_registry.populate_tool_dock(self._tool_dock)

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        self._tool_registry.unregister_shortcuts()

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
