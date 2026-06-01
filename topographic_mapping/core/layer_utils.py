"""
Layer related utilities
"""

from qgis.core import QgsMapLayer, QgsVectorLayer, QgsProject, QgsVectorTileLayer


class LayerUtils:
    """
    Layer related utilities
    """

    @staticmethod
    def can_edit(layer: QgsMapLayer | None) -> bool:
        """
        Returns True if a layer is a valid editable target
        """
        return isinstance(layer, QgsVectorLayer) and not layer.readOnly()

    @staticmethod
    def valid_edit_target_layers(project: QgsProject) -> list[QgsVectorLayer]:
        """
        Returns a list of all valid editable layers in the project
        """
        all_layers = []
        for _, l in project.mapLayers().items():
            if LayerUtils.can_edit(l):
                all_layers.append(l)
        return all_layers

    @staticmethod
    def deselect_all(project: QgsProject):
        """
        Clears selections from all layers in the project
        """
        for _, l in project.mapLayers().items():
            if isinstance(l, QgsVectorLayer):
                l.removeSelection()
            elif isinstance(l, QgsVectorTileLayer):
                l.removeSelection()
