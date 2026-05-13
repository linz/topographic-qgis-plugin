from qgis.PyQt.QtCore import Qt, QCoreApplication
from .gui import ToolDock


class TopographicMappingPlugin:
    def __init__(self, iface):
        self.iface = iface
        self._tool_dock = None

    def initGui(self) -> None:
        self._tool_dock = ToolDock(None)
        self._tool_dock.setObjectName("TopographicTools")
        self._tool_dock.setWindowTitle("Editing tools")

        self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._tool_dock)

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        if self._tool_dock:
            self._tool_dock.deleteLater()

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
