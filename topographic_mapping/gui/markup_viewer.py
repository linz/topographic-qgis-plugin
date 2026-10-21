from typing import List, Tuple, Dict

from qgis.PyQt.QtCore import Qt, QObject, QModelIndex, QSortFilterProxyModel, QSize
from qgis.PyQt.QtGui import QBrush, QColor
from qgis.PyQt.QtWidgets import (
    QAction,
    QWidget,
    QVBoxLayout,
    QTableView,
    QHeaderView,
    QAbstractItemView,
    QToolButton,
    QSizePolicy,
    QMessageBox,
)

from qgis.core import (
    Qgis,
    QgsProject,
    QgsVectorLayer,
    QgsVariantUtils,
    QgsRectangle,
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsExpression,
)
from qgis.gui import QgsPanelWidget, QgsAttributeTableModel
from qgis.utils import iface

from topographic_mapping.core import MarkupManager
from .combined_layer_model import CombinedVectorLayerModel
from .responsive_table_widget import ResponsiveTableWidget
from .gui_utils import GuiUtils


class MarkupModel(QSortFilterProxyModel):
    """
    A model for showing marked up features
    """

    IS_OPEN_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, layers: List[QgsVectorLayer], parent: QObject | None = None):
        super().__init__(parent)

        self.layers = layers
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

        if role in (Qt.ItemDataRole.BackgroundRole, self.IS_OPEN_ROLE):
            source_index = self.mapToSource(index)
            open_string = self._combined_model.data(
                self._combined_model.index(source_index.row(), 3)
            )
            is_open = open_string != "false"
            if role == Qt.ItemDataRole.BackgroundRole:
                if not is_open:
                    return QBrush(QColor("#f0fff0"))
                else:
                    return QBrush(QColor("#fff0f0"))
            else:
                return is_open

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

        self.toolbar_widget = ResponsiveTableWidget()

        goto_next_markup_action = QAction("Go To Next Open Markup", self)
        goto_next_markup_action.setIcon(GuiUtils.get_colorized_icon("next.svg"))
        goto_next_markup_action.triggered.connect(self._go_to_next_open_markup)

        goto_prev_markup_action = QAction("Go To Previous Open Markup", self)
        goto_prev_markup_action.setIcon(GuiUtils.get_colorized_icon("prev.svg"))
        goto_prev_markup_action.triggered.connect(self._go_to_previous_open_markup)

        zoom_to_selected_markup_action = QAction("Zoom to Selected Markup", self)
        zoom_to_selected_markup_action.setIcon(
            GuiUtils.get_colorized_icon("zoom_to_selected.svg")
        )
        zoom_to_selected_markup_action.triggered.connect(self._zoom_to_selected_markup)

        delete_selected_markup_action = QAction("Delete Selected Markup", self)
        delete_selected_markup_action.setIcon(
            GuiUtils.get_colorized_icon("delete_selected.svg")
        )
        delete_selected_markup_action.triggered.connect(self._delete_selected_markup)

        delete_closed_markup_action = QAction("Delete All Closed Markup", self)
        delete_closed_markup_action.setIcon(
            GuiUtils.get_colorized_icon("delete_closed.svg")
        )
        delete_closed_markup_action.triggered.connect(self._delete_closed_markup)

        reopen_closed_markup_action = QAction("Reopen All Closed Markup", self)
        reopen_closed_markup_action.setIcon(
            GuiUtils.get_colorized_icon("reopen_closed.svg")
        )
        reopen_closed_markup_action.triggered.connect(self._reopen_closed_markup)

        clear_markup_action = QAction("Clear Markup", self)
        clear_markup_action.setIcon(GuiUtils.get_colorized_icon("delete.svg"))
        clear_markup_action.triggered.connect(self._clear_markup)

        for action in (
            goto_prev_markup_action,
            goto_next_markup_action,
            zoom_to_selected_markup_action,
            delete_selected_markup_action,
            delete_closed_markup_action,
            reopen_closed_markup_action,
            clear_markup_action,
        ):
            self.toolbar_widget.push_widget(self._create_button_for_action(action))

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
        vl.addWidget(self.toolbar_widget)
        vl.addWidget(self.table_view, 1)
        self.setLayout(vl)

        self.table_view.selectionModel().selectionChanged.connect(
            self.on_selection_changed
        )

    def _create_button_for_action(self, action: QAction):
        btn = QToolButton()
        btn.setDefaultAction(action)
        btn.setObjectName(action.objectName())
        btn.setAutoRaise(True)
        btn.setFixedHeight(36)
        btn.setIconSize(QSize(24, 24))
        btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return btn

    def on_selection_changed(self, selected, deselected):
        """
        Triggered whenever the user clicks an item in the table view.
        """
        if not selected.indexes():
            return

        index = selected.indexes()[0]
        layer, fid = self._table_model.get_source_layer_and_feature_id(index)
        if layer is None or fid is None:
            return

        for other_layer in self._table_model.layers:
            if other_layer == layer:
                continue

            other_layer.removeSelection()

        layer.selectByIds([fid])

        canvas = iface.mapCanvas()
        canvas.zoomToFeatureIds(layer, [fid])
        canvas.flashFeatureIds(layer, [fid])

    def _go_to_next_open_markup(self):
        """
        Respecting the current sort order of the table, finds the selected index
        and then selects the next row in the table where the "open" field is True
        """
        self._navigate_to_open_markup(is_previous=False)

    def _go_to_previous_open_markup(self):
        """
        Respecting the current sort order of the table, finds the selected index
        and then selects the previous row in the table where the "open" field is True
        """
        self._navigate_to_open_markup(is_previous=True)

    def _navigate_to_open_markup(self, is_previous: bool = False):
        """
        Respecting the current sort order of the table, finds the selected index
        and then selects the previous or next row in the table where the "open" field is True
        """
        total_rows = self._table_model.rowCount()
        if total_rows == 0:
            return

        current_row = self.table_view.currentIndex().row()

        # logic is cyclic
        if is_previous:
            if current_row <= 0:
                candidates = list(range(total_rows - 1, -1, -1))
            else:
                candidates = list(range(current_row - 1, -1, -1)) + list(
                    range(total_rows - 1, current_row - 1, -1)
                )
        else:
            if current_row < 0 or current_row >= total_rows - 1:
                candidates = list(range(0, total_rows))
            else:
                candidates = list(range(current_row + 1, total_rows)) + list(
                    range(0, current_row + 1)
                )

        for row in candidates:
            idx = self._table_model.index(row, 0)
            is_open = self._table_model.data(idx, MarkupModel.IS_OPEN_ROLE)

            if is_open:
                target_index = self._table_model.index(row, 0)
                self.table_view.setCurrentIndex(target_index)
                self.table_view.selectRow(row)
                self.table_view.scrollTo(
                    target_index, QAbstractItemView.ScrollHint.EnsureVisible
                )
                return

        iface.messageBar().pushWarning("", "No markups are currently open.")
        return

    def _zoom_to_selected_markup(self):
        """
        Finds the current selected indices in the table, and then zooms the canvas to the
        corresponding features
        """
        canvas = iface.mapCanvas()

        if not self.table_view.selectionModel().selectedIndexes():
            iface.messageBar().pushWarning(
                "Zoom to Selected Markup", "No selected markup features were found."
            )
            return

        dest_crs = canvas.mapSettings().destinationCrs()
        combined_box = QgsRectangle()

        for index in self.table_view.selectionModel().selectedIndexes():
            layer, fid = self._table_model.get_source_layer_and_feature_id(index)
            if layer is None or fid is None:
                continue

            feat = layer.getFeature(fid)
            if not feat.isValid() or not feat.hasGeometry():
                continue

            geom = feat.geometry()
            box = geom.boundingBox()
            if layer.crs() != dest_crs:
                transform = QgsCoordinateTransform(
                    layer.crs(), dest_crs, QgsProject.instance()
                )
                transform.setBallparkTransformsAreAppropriate(True)
                box = transform.transformBoundingBox(box)

            combined_box.combineExtentWith(box)

        if combined_box.isNull():
            return

        canvas.zoomToFeatureExtent(combined_box)
        canvas.refresh()

    def _delete_selected_markup(self):
        """
        Finds the selected indices in the table, and then deletes the corresponding features
        """
        if not self.table_view.selectionModel().selectedIndexes():
            return

        layer_fids = {}
        for index in self.table_view.selectionModel().selectedIndexes():
            layer, fid = self._table_model.get_source_layer_and_feature_id(index)
            if layer is None or fid is None:
                continue

            if not layer in layer_fids:
                layer_fids[layer] = set()

            layer_fids[layer].add(fid)

        if not layer_fids:
            return

        total_count = sum(len(fids) for fids in layer_fids.values())
        res = QMessageBox.question(
            self,
            "Delete Selected Markup",
            f"Are you sure you want to delete {total_count} selected markup feature(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res != QMessageBox.StandardButton.Yes:
            return

        for layer, fids in layer_fids.items():
            if not layer.isEditable():
                layer.startEditing()

            layer.deleteFeatures([f for f in fids])

            layer.commitChanges(False)
            layer.triggerRepaint()

    def _get_closed_markup_features(self) -> Dict[QgsVectorLayer, List[int]]:
        """
        Returns a dictionary of all closed features by markup layer
        """
        fids_by_layer = {}
        for layer in self._table_model.layers:
            request = (
                QgsFeatureRequest()
                .setFilterExpression(
                    QgsExpression.createFieldEqualityExpression(
                        MarkupManager.OPEN_FIELD, False
                    )
                )
                .setNoAttributes()
                .setFlags(Qgis.FeatureRequestFlag.NoGeometry)
            )
            closed_fids = []
            for feat in layer.getFeatures(request):
                closed_fids.append(feat.id())

            if closed_fids:
                fids_by_layer[layer] = closed_fids

        return fids_by_layer

    def _delete_closed_markup(self):
        """
        Deletes the markup rows from all the markup vector layers where the "open" field is False
        """
        closed_fids_by_layer = self._get_closed_markup_features()

        total_count = sum(len(fids) for fids in closed_fids_by_layer.values())
        if total_count == 0:
            iface.messageBar().pushWarning(
                "Delete Closed Markup", "No closed markup features were found."
            )
            return

        res = QMessageBox.question(
            self,
            "Delete All Closed Markup",
            f"Are you sure you want to delete all {total_count} closed markup feature(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res != QMessageBox.StandardButton.Yes:
            return

        for layer, fids in closed_fids_by_layer.items():
            if not layer.isEditable():
                layer.startEditing()

            layer.deleteFeatures(fids)

            layer.commitChanges(False)
            layer.triggerRepaint()

    def _reopen_closed_markup(self):
        """
        Changes the "open" field to True for all the markup vector layers
        """
        closed_fids_by_layer = self._get_closed_markup_features()

        total_count = sum(len(fids) for fids in closed_fids_by_layer.values())
        if total_count == 0:
            iface.messageBar().pushWarning(
                "Reopen Closed Markup", "No closed markup features to reopen."
            )
            return

        res = QMessageBox.question(
            self,
            "Reopen All Closed Markup",
            f"Are you sure you want to reopen all {total_count} closed markup feature(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res != QMessageBox.StandardButton.Yes:
            return

        for layer, fids in closed_fids_by_layer.items():
            open_idx = layer.fields().lookupField(MarkupManager.OPEN_FIELD)
            if open_idx == -1:
                continue

            if not layer.isEditable():
                layer.startEditing()

            for fid in fids:
                layer.changeAttributeValue(fid, open_idx, True)

            layer.commitChanges(False)
            layer.triggerRepaint()

    def _clear_markup(self):
        """
        Removes all features from all the markup vector layers
        """
        layers = self._table_model.layers
        total_count = sum(layer.featureCount() for layer in layers)

        if total_count == 0:
            iface.messageBar().pushWarning(
                "Clear Markup", "No markup features found to clear."
            )
            return

        res = QMessageBox.warning(
            self,
            "Clear Markup",
            f"Are you sure you want to delete ALL {total_count} markup feature(s)? "
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res != QMessageBox.StandardButton.Yes:
            return

        for layer in layers:
            if not layer.isEditable():
                layer.startEditing()

            fids = [feat.id() for feat in layer.getFeatures()]
            layer.deleteFeatures(fids)

            layer.commitChanges(False)
            layer.triggerRepaint()
