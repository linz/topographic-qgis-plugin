from typing import List, Tuple, Dict, Callable

from qgis.PyQt.QtCore import QConcatenateTablesProxyModel, QObject
from qgis.core import QgsVectorLayer, QgsVectorLayerCache
from qgis.gui import QgsAttributeTableModel


class CombinedVectorLayerModel(QConcatenateTablesProxyModel):
    """
    A concatenated model for showing attributes from multiple vector layers at once
    """

    def __init__(self, layers: List[QgsVectorLayer], parent: QObject | None = None):
        super().__init__(parent)

        self._layer_ids: List[str] = []
        self._layer_caches: List[QgsVectorLayerCache] = []
        self._source_models: List[QgsAttributeTableModel] = []
        self._layer_connections: Dict[str, Callable] = {}

        for layer in layers:
            self.add_layer(layer)

    def add_layer(self, layer: QgsVectorLayer, cache_size: int = 1000) -> bool:
        """
        Adds a vector layer to the concatenated model and listens for its deletion signal.
        """
        if not layer or not layer.isValid():
            return False

        layer_id = layer.id()
        if layer_id in self._layer_ids:
            return False

        count = layer.featureCount()
        effective_cache = count if count > 0 else cache_size

        cache = QgsVectorLayerCache(layer, effective_cache, self)
        attr_model = QgsAttributeTableModel(cache)
        attr_model.loadLayer()

        self._layer_ids.append(layer_id)
        self._layer_caches.append(cache)
        self._source_models.append(attr_model)

        self.addSourceModel(attr_model)

        layer.willBeDeleted.connect(self.on_layer_will_be_deleted)

        return True

    def on_layer_will_be_deleted(self):
        layer = self.sender()
        layer_id = layer.id()
        if layer_id not in self._layer_ids:
            return False

        idx = self._layer_ids.index(layer_id)
        self._layer_ids.pop(idx)

        attr_model = self._source_models.pop(idx)
        cache = self._layer_caches.pop(idx)

        self.removeSourceModel(attr_model)

        attr_model.deleteLater()
        cache.deleteLater()

        return True

    def get_source_layer_and_row(
        self, proxy_row_index: int
    ) -> Tuple[QgsVectorLayer | None, int | None]:
        """
        Maps a row from the concatenated table back to its original source
        model and layer.
        """
        proxy_index = self.index(proxy_row_index, 0)
        source_index = self.mapToSource(proxy_index)
        source_model = source_index.model()

        try:
            source_pos = self._source_models.index(source_model)
            source_layer = self._layer_caches[source_pos].layer()
            return source_layer, source_index.row()
        except ValueError:
            return None, None
