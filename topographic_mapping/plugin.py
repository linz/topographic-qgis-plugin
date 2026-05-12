from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsProject, Qgis


from .gui.gui_utils import GuiUtils



class TopographicMappingPlugin:
    def __init__(self, iface):
        self.iface = iface

    def initGui(self) -> None:
        pass

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        pass

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
