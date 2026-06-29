from qgis.PyQt.QtCore import QModelIndex, QObject, Qt, QRect, QEvent
from qgis.PyQt.QtGui import QColor, QPainter
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QAbstractItemView,
    QStyle,
    QStyleOptionButton,
    QCheckBox,
)


from qgis.core import (
    QgsVectorLayer,
    QgsVectorLayerCache,
    QgsAttributeTableConfig,
    QgsConditionalStyle,
    QgsEditorWidgetSetup,
)
from qgis.gui import (
    QgsAttributeTableModel,
    QgsAttributeTableFilterModel,
    QgsAttributeTableDelegate,
    QgsMapCanvas,
    QgsTableView,
    QgsAttributeEditorContext,
)

from qgis.utils import iface


class ValidationAttributeTableDelegate(QgsAttributeTableDelegate):
    def __init__(self, checkbox_columns: list[int], parent: QObject | None):
        super().__init__(parent)
        self._checkbox_columns = checkbox_columns

    def paint(self, painter: QPainter, option, index: QModelIndex):
        model = index.model()

        if False and index.column() in self._checkbox_columns:
            value = model.data(index, Qt.ItemDataRole.EditRole)
            is_checked = bool(value)

            opt = option
            style = opt.widget.style()
            style.drawPrimitive(
                QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, opt.widget
            )

            cb_opt = QStyleOptionButton()
            cb_opt.state = (
                QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
            )
            if is_checked:
                cb_opt.state |= QStyle.StateFlag.State_On
            else:
                cb_opt.state |= QStyle.StateFlag.State_Off

            indicator_rect = style.subElementRect(
                QStyle.SubElement.SE_CheckBoxIndicator, cb_opt, opt.widget
            )
            x = 0  # opt.rect.x() + (
            #     opt.rect.width() - indicator_rect.width()) // 2
            y = opt.rect.y() + (opt.rect.height() - indicator_rect.height()) // 2
            cb_opt.rect = QRect(x, y, indicator_rect.width(), indicator_rect.height())

            style.drawPrimitive(
                QStyle.PrimitiveElement.PE_IndicatorCheckBox,
                cb_opt,
                painter,
                opt.widget,
            )

            return

        super().paint(painter, option, index)


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
        self._list_view = None
        self._delegate = None

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def cleanup(self):
        """
        Cleanup gracefully before dock destruction
        """
        if self._list_view:
            self._list_view.deleteLater()
        if self._delegate:
            self._delegate.deleteLater()
        if self._filter_model:
            self._filter_model.deleteLater()
        if self._table_model:
            self._table_model.deleteLater()
        if self._layer_cache:
            self._layer_cache.deleteLater()

    def set_canvas(self, canvas: QgsMapCanvas):
        self._canvas = canvas

    def set_source(self, layer: QgsVectorLayer):
        self._layer = layer

        self.cleanup()

        self._layer_cache = QgsVectorLayerCache(self._layer, 1000, self)

        self._table_model = QgsAttributeTableModel(self._layer_cache, self)
        self._table_model.loadLayer()

        self._filter_model = QgsAttributeTableFilterModel(
            self._canvas, self._table_model, parent=self
        )
        self._filter_model.setFilterMode(
            QgsAttributeTableFilterModel.FilterMode.ShowAll
        )

        self._configure_results_layer(layer)

        config = QgsAttributeTableConfig()
        open_config = QgsAttributeTableConfig.ColumnConfig()
        open_config.name = "open"
        warning_config = QgsAttributeTableConfig.ColumnConfig()
        warning_config.name = "warning"
        notes_config = QgsAttributeTableConfig.ColumnConfig()
        notes_config.name = "notes"
        columns = [open_config, warning_config, notes_config]
        for field in self._layer.fields():
            if field.name() not in ("open", "warning", "notes"):
                hidden_config = QgsAttributeTableConfig.ColumnConfig()
                hidden_config.hidden = True
                hidden_config.name = field.name()
                columns.append(hidden_config)

        config.setColumns(columns)
        self._filter_model.setAttributeTableConfig(config)

        self._list_view = QgsTableView()
        self._list_view.setModel(self._filter_model)
        self.layout().addWidget(self._list_view)
        self._list_view.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self._list_view.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self._list_view.setColumnWidth(1, int(self._list_view.width() / 2))
        self._list_view.horizontalHeader().setStretchLastSection(True)

        self._list_view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._list_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )

        self._list_view.selectionModel().selectionChanged.connect(
            self.on_selection_changed
        )

        self._delegate = ValidationAttributeTableDelegate([0], self)
        self._list_view.setItemDelegate(self._delegate)
        self._list_view.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)

        context = QgsAttributeEditorContext()
        context.setVectorLayerTools(iface.vectorLayerTools())

        self._table_model.setEditorContext(context)

    @staticmethod
    def _configure_results_layer(layer: QgsVectorLayer):
        """
        Configures a results layer, setting up appropriate field
        and table configuration
        """
        open_field_index = layer.fields().lookupField("open")
        layer.setFieldAlias(open_field_index, "Open")
        warning_field_index = layer.fields().lookupField("warning")
        layer.setFieldAlias(warning_field_index, "Warning")
        notes_field_index = layer.fields().lookupField("notes")
        layer.setFieldAlias(notes_field_index, "Notes")

        open_field = layer.fields()[open_field_index]
        setup = QgsEditorWidgetSetup("CheckBox", {})
        open_field.setEditorWidgetSetup(setup)

        edit_form_config = layer.editFormConfig()
        edit_form_config.setReadOnly(warning_field_index, True)
        layer.setEditFormConfig(edit_form_config)

        closed_row_style = QgsConditionalStyle()
        closed_row_style.setRule('not "open"')
        closed_row_style.setBackgroundColor(QColor("#f0fff0"))
        open_row_style = QgsConditionalStyle()
        open_row_style.setRule('"open"')
        open_row_style.setBackgroundColor(QColor("#fff0f0"))

        layer.conditionalStyles().setRowStyles([closed_row_style, open_row_style])

    def on_selection_changed(self, selected, deselected):
        """
        Triggered whenever the user clicks an item in the list view.
        Pans and zooms the map to the geometry of the selected item(s).
        """
        if not selected.indexes():
            return

        index = selected.indexes()[0]
        fid = self._filter_model.rowToId(index)

        self._canvas.zoomToFeatureIds(self._layer, [fid])
        self._canvas.refresh()
        self._canvas.flashFeatureIds(self._layer, [fid])
