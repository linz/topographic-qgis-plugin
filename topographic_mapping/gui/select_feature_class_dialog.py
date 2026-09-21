"""
A dialog for selecting feature classes
"""

from qgis.PyQt.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QDialogButtonBox,
    QLabel,
    QTreeView,
)
from qgis.PyQt.QtCore import QItemSelection

from qgis.gui import QgsFilterLineEdit

from .feature_type_model import FeatureTypeTreeModel, FeatureTypeFilterProxyModel


class SelectFeatureClassDialog(QDialog):
    """
    A dialog for selecting feature classes
    """

    def __init__(self, feature_types, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("Select Feature Class")

        vl = QVBoxLayout()

        self.label = QLabel("Select a feature class")
        vl.addWidget(self.label)
        self._filter_types_widget = QgsFilterLineEdit()
        self._filter_types_widget.setShowSearchIcon(True)
        self._filter_types_widget.setPlaceholderText("Filter types")
        vl.addWidget(self._filter_types_widget)
        self._feature_type_view = QTreeView()
        self._feature_type_view.setHeaderHidden(True)
        vl.addWidget(self._feature_type_view, 1)
        self._feature_type_model = FeatureTypeTreeModel(feature_types, self)
        self._feature_type_proxy_model = FeatureTypeFilterProxyModel(self)
        self._feature_type_view.setModel(self._feature_type_proxy_model)
        self._feature_type_proxy_model.setSourceModel(self._feature_type_model)
        self._filter_types_widget.cleared.connect(self._feature_type_view.expandAll)

        self._filter_types_widget.textChanged.connect(
            self._feature_type_proxy_model.set_filter_text
        )

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        vl.addWidget(self._button_box)
        self.setLayout(vl)

        self._feature_type_view.selectionModel().selectionChanged.connect(
            self._selected_feature_type_changed
        )

        self._feature_type_model.rowsInserted.connect(self._expand_rows)
        self._feature_type_view.expandAll()

        self._button_box.rejected.connect(self.reject)
        self._button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.accept
        )
        self._button_box.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)

    def _expand_rows(self, parent, first, last):
        for row in range(first, last + 1):
            proxy_index = self._feature_type_proxy_model.mapFromSource(
                self._feature_type_model.index(row, 0, parent)
            )
            self._feature_type_view.expand(proxy_index)

    def _selected_feature_type_changed(
        self, selected: QItemSelection, deselected: QItemSelection
    ):
        self._button_box.button(QDialogButtonBox.StandardButton.Apply).setEnabled(
            bool(selected.count())
        )

    def new_feature_type(self) -> list[str]:
        """
        Returns the new feature type for the selected features
        """
        selection = self._feature_type_view.selectionModel().selectedIndexes()
        if len(selection) == 0:
            return []

        selected_type_index = self._feature_type_proxy_model.mapToSource(selection[0])
        parent_feature_type = self._feature_type_model.data(
            selected_type_index, FeatureTypeTreeModel.PARENT_FEATURE_TYPE_ROLE
        )
        feature_type = self._feature_type_model.data(
            selected_type_index, FeatureTypeTreeModel.FEATURE_TYPE_ROLE
        )
        return [parent_feature_type, feature_type]
