from qgis.PyQt.QtCore import Qt, pyqtSignal, QItemSelection
from qgis.PyQt.QtGui import QFontMetrics
from qgis.PyQt.QtWidgets import (
    QToolButton,
    QSizePolicy,
    QAction,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QTreeView,
    QButtonGroup,
)
from qgis.core import QgsVectorLayer
from qgis.gui import (
    QgsFilterLineEdit,
)
from qgis.utils import OverrideCursor

from .feature_type_model import FeatureTypeTreeModel, FeatureTypeFilterProxyModel
from ..core import ProjectController, EditMode
from .tool_dock import ToolDock


class EditToolDock(ToolDock):
    """
    A dock widget for display of a set of editing tools
    """

    target_layer_set = pyqtSignal(QgsVectorLayer)

    def __init__(self, edit_target_tool_action: QAction, parent):
        super().__init__(edit_target_tool_action, parent)

        edit_mode_layout = QHBoxLayout()
        self._button_edit_real_data = QToolButton()
        self._button_edit_real_data.setCheckable(True)
        self._button_edit_real_data.setText("Real World")
        self._button_edit_real_data.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )

        self._button_edit_product_data = QToolButton()
        self._button_edit_product_data.setCheckable(True)
        self._button_edit_product_data.setText("Product Data")
        self._button_edit_product_data.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )

        self._button_edit_real_data.toggled.connect(self._toggle_real_data)
        self._button_edit_product_data.toggled.connect(self._toggle_product_data)

        edit_mode_layout.addWidget(self._button_edit_real_data)
        edit_mode_layout.addWidget(self._button_edit_product_data)
        self._edit_mode_group = QButtonGroup(self)
        self._edit_mode_group.addButton(self._button_edit_real_data)
        self._edit_mode_group.addButton(self._button_edit_product_data)

        self._vlayout.insertLayout(0, edit_mode_layout)

        fm = QFontMetrics(self.font())

        self._digitize_widget = QWidget()
        digitize_vl = QVBoxLayout()
        digitize_vl.setContentsMargins(0, 0, 0, 0)
        digitize_vl.addWidget(QLabel("New feature type"))
        self._filter_types_widget = QgsFilterLineEdit()
        self._filter_types_widget.setShowSearchIcon(True)
        self._filter_types_widget.setPlaceholderText("Filter types")
        self._filter_types_widget.textChanged.connect(self._feature_type_filter_changed)
        digitize_vl.addWidget(self._filter_types_widget)
        self._feature_type_view = QTreeView()
        self._feature_type_view.setHeaderHidden(True)
        self._feature_type_model: FeatureTypeTreeModel | None = None
        self._feature_type_proxy_model: FeatureTypeFilterProxyModel | None = None
        self._filter_types_widget.cleared.connect(self._feature_type_view.expandAll)

        self._feature_type_view.setFixedHeight(fm.height() * 20)

        digitize_vl.addWidget(self._feature_type_view, 1)
        self._digitize_widget.setLayout(digitize_vl)
        self._vlayout.insertWidget(5, self._digitize_widget)
        self._digitize_description_label = QLabel()
        self._digitize_description_label.setWordWrap(True)
        self._vlayout.insertWidget(6, self._digitize_description_label)

    def set_project_controller(self, controller: ProjectController):
        super().set_project_controller(controller)
        self._set_feature_types(controller.feature_types)
        self._controller.feature_types_found.connect(self._feature_type_model.add_types)
        self._controller.feature_types_removed.connect(
            self._feature_type_model.remove_types
        )

    def _set_feature_types(self, feature_types):
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
        if not self._state_manager or not self._controller:
            return

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

        target_layer = self._controller.layer_for_feature_type(parent_feature_type)
        if target_layer:
            self._state_manager.set_target_layer(target_layer)

        self._state_manager.set_current_feature_type(feature_type)

    def _toggle_real_data(self, enabled: bool):
        if not enabled or not self._controller:
            return

        gpkg_path = self._controller.working_geopackage_path()
        if not gpkg_path:
            return

        with OverrideCursor(Qt.CursorShape.WaitCursor):
            self._controller.set_edit_mode(gpkg_path, EditMode.RealWorld)

    def _toggle_product_data(self, enabled: bool):
        if not enabled or not self._controller:
            return

        gpkg_path = self._controller.working_geopackage_path()
        if not gpkg_path:
            return

        with OverrideCursor(Qt.CursorShape.WaitCursor):
            self._controller.set_edit_mode(gpkg_path, EditMode.ProductData)


# locator
