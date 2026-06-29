from qgis.core import (
    QgsSettingsEntryStringList,
    QgsSettingsTree,
    QgsSettingsEntryString,
)

SETTINGS_NODE = QgsSettingsTree.createPluginTreeNode("topographic_mapping")

FAVORITES = QgsSettingsEntryStringList("favorite_actions", SETTINGS_NODE, [])
VALIDATION_COMMAND = QgsSettingsEntryString("validation_command", SETTINGS_NODE, "")
VALIDATION_COMMAND_WORKING_DIR = QgsSettingsEntryString(
    "validation_command_work_dir", SETTINGS_NODE, ""
)
