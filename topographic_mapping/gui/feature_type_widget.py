from typing import Tuple

from qgis.PyQt.QtCore import pyqtSignal, QItemSelection, QItemSelectionModel
from qgis.PyQt.QtGui import QFontMetrics
from qgis.PyQt.QtWidgets import QVBoxLayout, QWidget, QTreeView, QAbstractItemView
from qgis.gui import QgsFilterLineEdit

from .feature_type_model import FeatureTypeTreeModel, FeatureTypeFilterProxyModel
from ..core import ProjectController


class FeatureTypeWidget(QWidget):
    """
    QTreeView showing feature type hierarchy, and filter bar
    """

    selected_feature_type_changed = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)

        vl = QVBoxLayout()
        vl.setContentsMargins(0, 0, 0, 0)

        fm = QFontMetrics(self.font())

        self._filter_types_widget = QgsFilterLineEdit()
        self._filter_types_widget.setShowSearchIcon(True)
        self._filter_types_widget.setPlaceholderText("Filter types")
        self._filter_types_widget.textChanged.connect(self._feature_type_filter_changed)
        vl.addWidget(self._filter_types_widget)

        self._feature_type_view = QTreeView()
        self._feature_type_view.setHeaderHidden(True)
        self._feature_type_model: FeatureTypeTreeModel | None = None
        self._feature_type_proxy_model: FeatureTypeFilterProxyModel | None = None
        self._filter_types_widget.cleared.connect(self._feature_type_view.expandAll)

        self._feature_type_view.setFixedHeight(fm.height() * 20)
        self._feature_type_view.setItemsExpandable(False)
        self._feature_type_view.collapsed.connect(self._feature_type_view.expand)

        vl.addWidget(self._feature_type_view, 1)
        self.setLayout(vl)

    def set_project_controller(self, controller: ProjectController):
        self.set_feature_types(controller.feature_types)
        controller.feature_types_found.connect(self._feature_type_model.add_types)
        controller.feature_types_removed.connect(self._feature_type_model.remove_types)

    def set_feature_types(self, feature_types):
        self._feature_type_model = FeatureTypeTreeModel(feature_types, self)
        self._feature_type_proxy_model = FeatureTypeFilterProxyModel(self)
        self._feature_type_proxy_model.setSourceModel(self._feature_type_model)
        self._feature_type_view.setModel(self._feature_type_proxy_model)
        self._feature_type_view.selectionModel().selectionChanged.connect(
            self._selected_feature_type_changed
        )
        self._feature_type_model.rowsInserted.connect(self._expand_rows)
        self._feature_type_view.expandAll()

    def _expand_rows(self, parent, first, last):
        for row in range(first, last + 1):
            proxy_index = self._feature_type_proxy_model.mapFromSource(
                self._feature_type_model.index(row, 0, parent)
            )
            self._feature_type_view.expand(proxy_index)

    def _feature_type_filter_changed(self, text: str):
        if self._feature_type_proxy_model:
            self._feature_type_proxy_model.set_filter_text(text)

    def _selected_feature_type_changed(
        self, selected: QItemSelection, deselected: QItemSelection
    ):
        feature_type = None
        parent_feature_type = None
        if selected.indexes():
            selected_type_index = self._feature_type_proxy_model.mapToSource(
                selected.indexes()[0]
            )
            parent_feature_type = self._feature_type_model.data(
                selected_type_index, FeatureTypeTreeModel.PARENT_FEATURE_TYPE_ROLE
            )
            feature_type = self._feature_type_model.data(
                selected_type_index, FeatureTypeTreeModel.FEATURE_TYPE_ROLE
            )

        self.selected_feature_type_changed.emit(parent_feature_type, feature_type)

    def selected_feature_type(self) -> Tuple[str | None, str | None]:
        """
        Returns the selected feature type
        """
        selection = self._feature_type_view.selectionModel().selectedIndexes()
        if len(selection) == 0:
            return None, None

        selected_type_index = self._feature_type_proxy_model.mapToSource(selection[0])
        parent_feature_type = self._feature_type_model.data(
            selected_type_index, FeatureTypeTreeModel.PARENT_FEATURE_TYPE_ROLE
        )
        feature_type = self._feature_type_model.data(
            selected_type_index, FeatureTypeTreeModel.FEATURE_TYPE_ROLE
        )
        return parent_feature_type, feature_type

    def set_selected_type(
        self, parent_feature_type: str | None, feature_type: str | None
    ):
        if parent_feature_type is None:
            self._feature_type_view.selectionModel().clear()
            return

        model_index = self._feature_type_model.find_index(
            parent_feature_type, feature_type
        )
        proxy_index = self._feature_type_proxy_model.mapFromSource(model_index)
        self._feature_type_view.selectionModel().select(
            proxy_index, QItemSelectionModel.SelectionFlag.ClearAndSelect
        )
        self._feature_type_view.scrollTo(
            proxy_index, QAbstractItemView.ScrollHint.EnsureVisible
        )
