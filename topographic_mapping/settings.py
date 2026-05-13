from qgis.core import QgsSettingsEntryStringList, QgsSettingsTree, QgsSettingsException

SETTINGS_NODE = QgsSettingsTree.createPluginTreeNode("topographic_mapping")

FAVORITES = QgsSettingsEntryStringList("favorite_actions", SETTINGS_NODE, [])
