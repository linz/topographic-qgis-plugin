from typing import List, Tuple

from qgis.PyQt.QtCore import Qt, QObject, QModelIndex, QSortFilterProxyModel
from qgis.PyQt.QtGui import QBrush, QColor
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableView,
    QHeaderView,
    QAbstractItemView,
)

from qgis.core import QgsProject, QgsVectorLayer, QgsVariantUtils
from qgis.gui import QgsPanelWidget, QgsAttributeTableModel

from topographic_mapping.core import MarkupManager
from .combined_layer_model import CombinedVectorLayerModel


class MarkupModel(QSortFilterProxyModel):
    """
    A model for showing marked up features
    """

    def __init__(self, layers: List[QgsVectorLayer], parent: QObject | None = None):
        super().__init__(parent)

        self._visible_column_indices = [2, 3]

        self._combined_model = CombinedVectorLayerModel(layers, self)
        self.setSourceModel(self._combined_model)

        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortRole(Qt.ItemDataRole.EditRole)

    def filterAcceptsColumn(
        self, source_column: int, source_parent: QModelIndex
    ) -> bool:
        """
        Excludes columns whose underlying field name is in _hidden_fields.
        """
        if source_column not in self._visible_column_indices:
            return False

        return True

    def get_source_layer_and_feature_id(
        self, index: QModelIndex
    ) -> Tuple[QgsVectorLayer | None, int | None]:
        source_index = self.mapToSource(index)
        if not source_index.isValid():
            return None, None

        combined_model = self.sourceModel()
        orig_source_index = combined_model.mapToSource(source_index)
        if not orig_source_index.isValid():
            return None, None

        attr_model: QgsAttributeTableModel = orig_source_index.model()
        if not attr_model:
            return None, None

        layer: QgsVectorLayer = attr_model.layerCache().layer()
        if not layer:
            return None, None

        fid = attr_model.rowToId(orig_source_index.row())
        return layer, fid

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            if section == 0:
                return "Notes"
            elif section == 1:
                return "Open"

        return super().headerData(section, orientation, role)

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        src_model = self.sourceModel()
        if not src_model:
            return False

        left_val = src_model.data(left, Qt.ItemDataRole.DisplayRole)
        right_val = src_model.data(right, Qt.ItemDataRole.DisplayRole)

        left_is_null = QgsVariantUtils.isNull(left_val)
        right_is_null = QgsVariantUtils.isNull(right_val)

        if left_is_null and right_is_null:
            return False
        if left_is_null:
            return True
        if right_is_null:
            return False

        if isinstance(left_val, str) and isinstance(right_val, str):
            left_fold = left_val.casefold()
            right_fold = right_val.casefold()
            if left_fold != right_fold:
                return left_fold < right_fold
            return left_val < right_val

        try:
            return left_val < right_val
        except TypeError:
            return str(left_val).casefold() < str(right_val).casefold()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.BackgroundRole:
            source_index = self.mapToSource(index)
            open = self._combined_model.data(
                self._combined_model.index(source_index.row(), 3)
            )
            if open == "false":
                return QBrush(QColor("#f0fff0"))
            else:
                return QBrush(QColor("#fff0f0"))

        return super().data(index, role)

    def setData(
        self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        source_index = self.mapToSource(index)
        if not source_index.isValid():
            return False

        combined_model = self.sourceModel()
        orig_source_index = combined_model.mapToSource(source_index)
        if not orig_source_index.isValid():
            return False

        attr_model: QgsAttributeTableModel = orig_source_index.model()
        if not attr_model:
            return False

        layer: QgsVectorLayer = attr_model.layerCache().layer()
        if not layer or not layer.isEditable():
            return False

        fid = attr_model.rowToId(orig_source_index.row())
        field_idx: int = orig_source_index.column()

        success = layer.changeAttributeValue(fid, field_idx, value)
        if success:
            self.dataChanged.emit(
                index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
            )
            return True

        return False


class MarkupViewer(QgsPanelWidget):
    """
    A widget for showing marked up features
    """

    def __init__(self, markup_manager: MarkupManager, parent: QWidget | None = None):
        super().__init__(parent)
        self.setDockMode(True)
        self.setPanelTitle("Markup Viewer")

        self._markup_manager = markup_manager

        self._markup_manager.add_markup_layers_if_not_present(QgsProject.instance())

        self._table_model = MarkupModel(
            [
                self._markup_manager.project_polygon_markup_layer(
                    QgsProject.instance()
                ),
                self._markup_manager.project_line_markup_layer(QgsProject.instance()),
                self._markup_manager.project_point_markup_layer(QgsProject.instance()),
            ],
            self,
        )

        self.table_view = QTableView()
        self.table_view.setModel(self._table_model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table_view.horizontalHeader().setStretchLastSection(True)

        self.table_view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )

        self.table_view.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.table_view.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.table_view.setColumnWidth(0, int(self.table_view.width() / 2))
        self.table_view.horizontalHeader().setStretchLastSection(True)

        vl = QVBoxLayout()
        vl.setContentsMargins(0, 0, 6, 6)
        vl.addWidget(self.table_view, 1)
        self.setLayout(vl)

        self.table_view.selectionModel().selectionChanged.connect(
            self.on_selection_changed
        )

    def on_selection_changed(self, selected, deselected):
        """
        Triggered whenever the user clicks an item in the table view.
        """
        if not selected.indexes():
            return

        index = selected.indexes()[0]
        layer, fid = self._table_model.get_source_layer_and_feature_id(index)
        if layer is None:
            return

        layer.selectByIds([fid])
