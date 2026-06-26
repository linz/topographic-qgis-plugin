from qgis.PyQt import sip

from qgis.core import QgsVectorLayer, QgsVectorLayerCache
from qgis.gui import (
    QgsFeatureListView,
    QgsAttributeTableModel,
    QgsAttributeTableFilterModel,
    QgsMapCanvas,
    QgsFeatureListModel,
)
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QListView


class ValidationResultsViewer(QWidget):
    """
    An interactive widget that displays a list of validation errors
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._canvas: QgsMapCanvas | None = None
        self._layer = None
        self._layer_cache = None
        self._table_model = None
        self._filter_model = None
        self._feature_model = None
        self._list_view = None

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def set_canvas(self, canvas: QgsMapCanvas):
        self._canvas = canvas

    def set_source(self, layer: QgsVectorLayer):
        self._layer = layer

        if self._list_view:
            self._list_view.deleteLater()
        if self._feature_model:
            self._feature_model.deleteLater()
        if self._filter_model:
            self._filter_model.deleteLater()
        if self._table_model:
            self._table_model.deleteLater()
        if self._layer_cache:
            self._layer_cache.deleteLater()

        self._layer_cache = QgsVectorLayerCache(self._layer, 1000)

        self._table_model = QgsAttributeTableModel(self._layer_cache)
        self._table_model.loadLayer()

        self._filter_model = QgsAttributeTableFilterModel(
            self._canvas, self._table_model, parent=self
        )
        self._filter_model.setFilterMode(
            QgsAttributeTableFilterModel.FilterMode.ShowAll
        )

        self._feature_model = QgsFeatureListModel(self._filter_model, self)
        display_field = "warning"
        display_idx = self._layer.fields().lookupField(display_field)
        if display_idx >= 0:
            self._feature_model.setDisplayExpression(display_field)

        self._list_view = QListView()
        self._list_view.setModel(self._feature_model)
        self.layout().addWidget(self._list_view)

        self._list_view.selectionModel().selectionChanged.connect(
            self.on_selection_changed
        )

    def on_selection_changed(self, selected, deselected):
        """
        Triggered whenever the user clicks an item in the list view.
        Pans and zooms the map to the geometry of the selected item(s).
        """
        if not selected.indexes():
            return

        index = selected.indexes()[0]
        fid = self._feature_model.idxToFid(index)

        self._canvas.zoomToFeatureIds(self._layer, [fid])
        self._canvas.refresh()
        self._canvas.flashFeatureIds(self._layer, [fid])
