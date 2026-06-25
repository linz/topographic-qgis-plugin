from qgis.PyQt import uic

from qgis.gui import QgsOptionsPageWidget, QgsOptionsWidgetFactory, QgsFileWidget
from ..settings import VALIDATION_COMMAND, VALIDATION_COMMAND_WORKING_DIR
from .gui_utils import GuiUtils


OPTIONS_WIDGET, OPTIONS_BASE = uic.loadUiType(GuiUtils.get_ui_file_path("options.ui"))


class ConfigOptionsPage(OPTIONS_WIDGET, QgsOptionsPageWidget):
    """
    Plugin options widget
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.working_dir_widget.setStorageMode(QgsFileWidget.StorageMode.GetDirectory)

        self.edit_validation_script_command.setText(VALIDATION_COMMAND.value())
        self.working_dir_widget.setFilePath(VALIDATION_COMMAND_WORKING_DIR.value())

    def apply(self):
        """
        Applies the new settings
        """
        VALIDATION_COMMAND.setValue(self.edit_validation_script_command.text())
        VALIDATION_COMMAND_WORKING_DIR.setValue(self.working_dir_widget.filePath())


class PluginsOptionsFactory(QgsOptionsWidgetFactory):
    """
    Factory class for plugin options widget
    """

    def __init__(self):  # pylint: disable=useless-super-delegation
        super().__init__()

    def icon(self):  # pylint: disable=missing-function-docstring
        return GuiUtils.get_icon("icon.svg")

    def createWidget(self, parent):  # pylint: disable=missing-function-docstring
        return ConfigOptionsPage(parent)
