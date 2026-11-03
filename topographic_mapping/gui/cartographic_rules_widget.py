from qgis.PyQt.QtCore import QModelIndex, QTimer
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListView,
    QAbstractItemView,
    QHBoxLayout,
    QPushButton,
    QProgressBar,
    QStackedWidget,
    QTableView,
)
from qgis.PyQt.QtGui import QFontMetrics

from qgis.core import QgsReferencedRectangle
from qgis.gui import QgsPanelWidget, QgsMapCanvas, QgsCodeEditorPython, QgsCodeEditor

from topographic_mapping.core import ProjectController
from topographic_mapping.core.generalization import (
    RULE_REGISTRY,
    CartographicRuleModel,
    CartographicRuleSortProxyModel,
    CartographicGeneralizationRuleContext,
    RuleFeedback,
    CartographicIssueTableModel,
    CartographicIssueSortFilterProxyModel,
)


class CartographicRulesWidget(QgsPanelWidget):
    """
    A widget for running and configuring cartographic rules
    """

    def __init__(
        self,
        canvas: QgsMapCanvas,
        project_controller: ProjectController,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setDockMode(True)
        self.setPanelTitle("Cartographic Rules")

        self._canvas: QgsMapCanvas = canvas
        self._project_controller: ProjectController = project_controller

        self._current_rule_id: str | None = None

        self._queued_zoom_and_flash_index: QModelIndex | None = None
        self._zoom_and_flash_timeout = QTimer()
        self._zoom_and_flash_timeout.setSingleShot(True)
        self._zoom_and_flash_timeout.setInterval(50)
        self._zoom_and_flash_timeout.timeout.connect(self._trigger_zoom_and_flash)

        self._model = CartographicRuleModel(RULE_REGISTRY, self)
        self._proxy_model = CartographicRuleSortProxyModel(self)
        self._proxy_model.setSourceModel(self._model)

        self.table_view = QListView()
        self.table_view.setModel(self._proxy_model)
        self.table_view.setAlternatingRowColors(True)

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

        fm = QFontMetrics(self.font())
        self.table_view.setFixedHeight(fm.height() * 5)

        vl = QVBoxLayout()
        vl.setContentsMargins(0, 0, 6, 6)
        vl.addWidget(self.table_view)

        self.config_container = QWidget()
        vl.addWidget(self.config_container)

        hl = QHBoxLayout()
        hl.setContentsMargins(0, 0, 0, 0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)

        hl.addWidget(self.progress_bar, 1)
        self.run_button = QPushButton("Run")
        hl.addWidget(self.run_button)

        vl.addLayout(hl)

        self.stacked_widget = QStackedWidget()

        self._output_widget = QgsCodeEditorPython(
            mode=QgsCodeEditor.Mode.OutputDisplay, flags=QgsCodeEditor.Flags()
        )
        self._output_widget.setReadOnly(True)
        self._output_widget.setLineNumbersVisible(False)
        self.stacked_widget.addWidget(self._output_widget)
        self.stacked_widget.setCurrentIndex(0)

        self.issues_table = QTableView()
        self.issues_model = CartographicIssueTableModel(parent=self)
        self.issues_proxy_model = CartographicIssueSortFilterProxyModel(parent=self)
        self.issues_proxy_model.setSourceModel(self.issues_model)

        self.issues_table.setModel(self.issues_proxy_model)
        self.issues_table.setAlternatingRowColors(True)

        self.issues_table.setColumnWidth(0, fm.horizontalAdvance("x") * 10)
        self.issues_table.horizontalHeader().setStretchLastSection(True)

        self.issues_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.issues_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.issues_table.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.issues_table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )

        self.stacked_widget.addWidget(self.issues_table)

        vl.addWidget(self.stacked_widget, 1)

        self.setLayout(vl)

        self.table_view.selectionModel().selectionChanged.connect(
            self.on_selection_changed
        )
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.run)

        self.issues_table.clicked.connect(self.on_issue_clicked)
        self.issues_table.selectionModel().selectionChanged.connect(
            self.on_issue_selection_changed
        )

    def on_selection_changed(self, selected, deselected):
        """
        Triggered whenever the user clicks an item in the table view.
        """
        if not selected.indexes():
            self.set_current_rule_id(None)
            return

        index = selected.indexes()[0]

        rule_id = index.data(CartographicRuleModel.RuleRole.RuleIdRole)
        self.set_current_rule_id(rule_id)

    def set_current_rule_id(self, rule_id: str | None):
        self._current_rule_id = rule_id
        if not self._current_rule_id:
            self.run_button.setEnabled(False)
            return

        self.run_button.setEnabled(True)

    def run(self):
        if not self._current_rule_id:
            return

        visible_extent = QgsReferencedRectangle(
            self._canvas.extent(), self._canvas.mapSettings().destinationCrs()
        )

        context = CartographicGeneralizationRuleContext(
            extent=visible_extent,
            project_controller=self._project_controller,
        )

        feedback = RuleFeedback()
        feedback.progressChanged.connect(self.set_progress)
        feedback.feedback_received.connect(self.set_feedback)

        self.progress_bar.resetFormat()
        self._output_widget.clear()
        self.stacked_widget.setCurrentIndex(0)

        # RULE_REGISTRY.run_rule(self._current_rule_id, context, {}, feedback)
        issues = RULE_REGISTRY.validate(self._current_rule_id, context, {}, feedback)
        self.issues_model.set_issues(issues)
        self.progress_bar.setFormat("Complete")
        if issues:
            self.stacked_widget.setCurrentIndex(1)

    def set_progress(self, progress: float):
        self.progress_bar.setValue(int(progress))

    def set_feedback(self, feedback: str):
        self._output_widget.append("{}\n".format(feedback))

    def _queue_zoom_and_flash(self, index: QModelIndex):
        """
        Queues the zoom and flash operation, after a short time-out
        """
        self._queued_zoom_and_flash_index = index

    def on_issue_clicked(self, index: QModelIndex):
        """
        Triggers every time a issue is clicked, even if already selected.
        """
        self._queue_zoom_and_flash(index)
        self._zoom_and_flash_timeout.start()

    def on_issue_selection_changed(self, selected, deselected):
        """
        Triggered whenever the user clicks an item in the list view.
        Pans and zooms the map to the geometry of the selected item(s).
        """
        if not selected.indexes():
            return

        index = selected.indexes()[0]
        self._queue_zoom_and_flash(index)

    def _trigger_zoom_and_flash(self):
        if self._queued_zoom_and_flash_index is None:
            return

        fid = self.issues_proxy_model.index_to_fid(self._queued_zoom_and_flash_index)
        layer = self.issues_proxy_model.index_to_layer(
            self._queued_zoom_and_flash_index
        )
        if not layer:
            return

        self._canvas.zoomToFeatureIds(layer, [fid])
        self._canvas.refresh()
        self._canvas.flashFeatureIds(layer, [fid])
