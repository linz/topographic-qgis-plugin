"""
Layer related utilities
"""

from qgis.core import QgsMapLayer, QgsVectorLayer


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
