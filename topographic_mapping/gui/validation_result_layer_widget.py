from pathlib import Path
from dataclasses import dataclass

from qgis.PyQt import sip
from qgis.PyQt.QtCore import (
    Qt,
    QObject,
    QModelIndex,
    QItemSelection,
    pyqtSignal,
    QThread,
)
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QBrush, QColor, QPalette
from qgis.PyQt.QtWidgets import QWidget, QComboBox, QTreeView, QApplication

from qgis.core import Qgis, QgsProviderRegistry


@dataclass
class LayerDetails:
    """
    Encapsulates result layer details
    """

    name: str
    count: int


class LayerLoaderWorker(QThread):
    """
    Worker thread that handles the heavy file probing off the main GUI thread.
    """

    layers_found = pyqtSignal(Path, list)

    def __init__(self, folder_path: Path, parent: QObject | None = None):
        super().__init__(parent)
        self.folder_path = folder_path

    def run(self):
        if not self.folder_path.exists() or not self.folder_path.is_dir():
            return

        ogr_provider_metadata = QgsProviderRegistry.instance().providerMetadata("ogr")
        assert ogr_provider_metadata

        for db_file in self.folder_path.glob("*.gpkg"):
            if self.isInterruptionRequested():
                return

            sub_layers = ogr_provider_metadata.querySublayers(
                db_file.as_posix(), Qgis.SublayerQueryFlag.CountFeatures
            )
            this_file_layers = []
            for layer_details in sub_layers:
                this_file_layers.append(
                    LayerDetails(
                        name=layer_details.name(), count=layer_details.featureCount()
                    )
                )
            if this_file_layers:
                self.layers_found.emit(db_file, this_file_layers)


class DatabaseLayerTreeModel(QStandardItemModel):
    """
    A pure hierarchical model for presentation of databases with
    child layers (currently hardcoded to GPKG databases only!)
    Level 1: Database file (Non-selectable category)
    Level 2: Layers (Selectable items)
    """

    FilePathRole = Qt.ItemDataRole.UserRole + 1
    LayerNameRole = Qt.ItemDataRole.UserRole + 2
    FeatureCountRole = Qt.ItemDataRole.UserRole + 3

    needs_expand = pyqtSignal()

    def __init__(self, folder_path: Path, parent: QObject | None = None):
        super().__init__(parent)
        self.folder_path = folder_path
        self._worker: LayerLoaderWorker = None
        self.load_layers()

    def load_layers(self):
        if (
            self._worker
            and not sip.isdeleted(self._worker)
            and self._worker.isRunning()
        ):
            self._worker.requestInterruption()
            self._worker.layers_found.disconnect(self._populate_tree)

        self.clear()
        self._add_placeholder_item()

        self._worker = LayerLoaderWorker(self.folder_path, self)
        self._worker.layers_found.connect(self._populate_tree)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _add_placeholder_item(self):
        sys_palette = QApplication.palette()
        placeholder_color = sys_palette.color(QPalette.ColorRole.PlaceholderText)

        placeholder_item = QStandardItem("Select results to view…")
        placeholder_font = placeholder_item.font()
        placeholder_font.setItalic(True)
        placeholder_item.setFont(placeholder_font)
        placeholder_item.setForeground(QBrush(placeholder_color))
        placeholder_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        )

        self.invisibleRootItem().appendRow(placeholder_item)

    def _populate_tree(self, db_file: Path, details: list[LayerDetails]):
        file_item = QStandardItem(db_file.name)
        file_item.setFlags(Qt.ItemFlag.ItemIsEnabled)

        for layer_details in details:
            text = f"{layer_details.name} ({layer_details.count})"
            layer_item = QStandardItem(text)
            layer_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )

            layer_item.setData(db_file.as_posix(), self.FilePathRole)
            layer_item.setData(layer_details.name, self.LayerNameRole)
            layer_item.setData(layer_details.count, self.FeatureCountRole)

            file_item.appendRow(layer_item)

        if file_item.rowCount() > 0:
            self.invisibleRootItem().appendRow(file_item)
            self.needs_expand.emit()


class LayerSelectorWidget(QComboBox):
    layer_selected = pyqtSignal(str, str)

    def __init__(self, folder_to_scan: Path, parent: QWidget | None = None):
        super().__init__(parent)

        tree_view = QTreeView(self)
        tree_view.setHeaderHidden(True)
        tree_view.setRootIsDecorated(False)
        tree_view.setIndentation(10)
        tree_view.setItemsExpandable(True)

        self.setView(tree_view)

        self.model = DatabaseLayerTreeModel(folder_to_scan, self)
        self.setModel(self.model)
        self.model.needs_expand.connect(tree_view.expandAll)

        tree_view.expandAll()

        tree_view.selectionModel().selectionChanged.connect(self.on_item_selected)
        tree_view.selectionModel().selectionChanged.connect(self._update_combo_style)
        self.setCurrentIndex(-1)
        self.setCurrentIndex(0)

    def reload(self):
        self.model.load_layers()
        self.view().expandAll()

    def _update_combo_style(self, selected: QItemSelection, deselected: QItemSelection):
        """Dynamically applies placeholder styling to the closed combobox surface."""
        if not selected.indexes():
            return

        selected = selected.indexes()[0]
        palette = self.palette()
        font = self.font()
        sys_palette = QApplication.palette()

        if not selected.parent().isValid() and selected.row() == 0:
            # Apply placeholder styles
            font.setItalic(True)
            placeholder_color = sys_palette.color(QPalette.ColorRole.PlaceholderText)

            # Depending on OS styles, QComboBox uses either Text or ButtonText for its closed state
            palette.setColor(
                QPalette.ColorGroup.Active, QPalette.ColorRole.Text, placeholder_color
            )
            palette.setColor(
                QPalette.ColorGroup.Active,
                QPalette.ColorRole.ButtonText,
                placeholder_color,
            )
        else:
            # Revert to standard system styles
            font.setItalic(False)
            palette.setColor(
                QPalette.ColorGroup.Active,
                QPalette.ColorRole.Text,
                sys_palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text),
            )
            palette.setColor(
                QPalette.ColorGroup.Active,
                QPalette.ColorRole.ButtonText,
                sys_palette.color(
                    QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText
                ),
            )
        self.setPalette(palette)

    def on_item_selected(self, selected: QItemSelection, deselected: QItemSelection):
        if not selected.indexes():
            return

        selected = selected.indexes()[0]

        if not selected.isValid():
            return

        file_path = self.model.data(selected, DatabaseLayerTreeModel.FilePathRole)
        layer_name = self.model.data(selected, DatabaseLayerTreeModel.LayerNameRole)

        self.layer_selected.emit(file_path, layer_name)

    def selected_path(self) -> str | None:
        indexes = self.view().selectedIndexes()
        if not indexes:
            return None
        return self.model.data(
            self.view().selectedIndexes()[0], DatabaseLayerTreeModel.FilePathRole
        )

    def selected_layer(self) -> str | None:
        indexes = self.view().selectedIndexes()
        if not indexes:
            return None

        return self.model.data(
            self.view().selectedIndexes()[0], DatabaseLayerTreeModel.LayerNameRole
        )
