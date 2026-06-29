from pathlib import Path

from qgis.PyQt.QtCore import QObject

from qgis.core import QgsApplication


class StoredObjectManager(QObject):
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        self._plugin_data_path = (
            Path(QgsApplication.qgisSettingsDirPath()) / "TopoPlugin"
        )
        if not self._plugin_data_path.exists():
            self._plugin_data_path.mkdir(parents=True)

    def get_plugin_data_dir(self, dir_name: str) -> Path:
        """
        Returns the path to a directory within the plugin's stored data.

        The directory will be created if it does not exist
        """
        dir_path = self._plugin_data_path / dir_name
        if not dir_path.exists():
            dir_path.mkdir(parents=True)
        return dir_path

    def get_plugin_data_path(self, file_name: str) -> Path:
        """
        Returns the path to a data file within the plugin's stored data
        """
        return self._plugin_data_path / file_name


STORED_OBJECT_MANAGER = StoredObjectManager()
