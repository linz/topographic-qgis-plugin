from qgis.PyQt import sip
from qgis.PyQt.QtCore import Qt, pyqtSignal, QDate, QTimer
from qgis.PyQt.QtGui import QFontMetrics, QColor
from qgis.PyQt.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QScrollArea,
    QFrame,
    QGroupBox,
    QPushButton,
    QMessageBox,
    QTabWidget,
    QTableView,
    QComboBox,
)
from qgis.core import (
    QgsBlockingProcess,
    QgsTask,
    QgsApplication,
    QgsFeedback,
    QgsReferencedRectangle,
    QgsProviderRegistry,
    QgsVectorLayer,
    QgsRectangle,
    QgsCoordinateTransform,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCsException,
)
from qgis.gui import (
    QgsDockWidget,
    QgsCollapsibleGroupBoxBasic,
    QgsExtentWidget,
    QgsMapCanvas,
    QgsDateEdit,
    QgsCodeEditorPython,
    QgsCodeEditor,
    QgsFeatureListComboBox,
)

from . import GuiUtils
from ..core import ProjectController, ValidationUtils, ValidationResultModel
from ..settings import VALIDATION_COMMAND_WORKING_DIR, VALIDATION_COMMAND
from .validation_result_layer_widget import LayerSelectorWidget
from .validation_results_viewer import ValidationResultsViewer


class ValidationTask(QgsTask):
    on_error = pyqtSignal(str)
    on_message = pyqtSignal(str)

    def __init__(self, program: str, arguments: list[str], working_dir: str):
        super().__init__("Validating data")
        self._program = program
        self._arguments = arguments
        self._working_dir = working_dir

        self.result_code = None
        self.exit_status = None
        self.process_error = None
        self._feedback: QgsFeedback | None = None

    def cancel(self):
        if self._feedback:
            self._feedback.cancel()
        super().cancel()

    def run(self):
        self._feedback = QgsFeedback()
        process = QgsBlockingProcess(self._program, self._arguments)
        process.setWorkingDirectory(self._working_dir)

        def on_stdout(ba):
            val = ba.data().decode("UTF-8")
            on_stdout.buffer += val
            if on_stdout.buffer.endswith("\n") or on_stdout.buffer.endswith("\r"):
                # flush buffer
                self.on_message.emit(on_stdout.buffer.rstrip())
                on_stdout.buffer = ""

        on_stdout.progress = 0
        on_stdout.buffer = ""

        def on_stderr(ba):
            val = ba.data().decode("UTF-8")
            on_stderr.buffer += val

            if on_stderr.buffer.endswith("\n") or on_stderr.buffer.endswith("\r"):
                # flush buffer
                self.on_error.emit(on_stderr.buffer.rstrip())
                on_stderr.buffer = ""

        on_stderr.buffer = ""

        process.setStdErrHandler(on_stderr)
        process.setStdOutHandler(on_stdout)
        self.result_code = process.run(self._feedback)
        self.exit_status = process.exitStatus()
        self.process_error = process.processError()

        # fully flush message buffers
        if on_stdout.buffer:
            self.on_message.emit(on_stdout.buffer.rstrip())
        if on_stderr.buffer:
            self.on_error(on_stderr.buffer.rstrip())

        if self._feedback.isCanceled():
            return False

        self._feedback = None

        return True


class ValidationDock(QgsDockWidget):
    """
    A dock widget for running validation tools
    """

    def __init__(self, parent):
        super().__init__(parent)

        self._controller: ProjectController | None = None

        scroll_area = QScrollArea()
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidgetResizable(True)
        scroll_area.setSizeAdjustPolicy(QScrollArea.SizeAdjustPolicy.AdjustToContents)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self._vlayout = QVBoxLayout()
        self._vlayout.setContentsMargins(0, 10, 6, 0)

        run_validation_group = QgsCollapsibleGroupBoxBasic("Run Validation")

        run_layout = QVBoxLayout()
        self._filter_by_extent_group = QGroupBox("Limit Extent")
        self._filter_by_extent_group.setCheckable(True)
        self._filter_by_extent_group.setChecked(False)
        run_layout.addWidget(self._filter_by_extent_group)
        self._extent_widget = QgsExtentWidget(
            None, QgsExtentWidget.WidgetStyle.ExpandedStyle
        )
        vl = QVBoxLayout()
        vl.addWidget(self._extent_widget)
        self._filter_by_extent_group.setLayout(vl)

        self._filter_by_map_sheet_group = QGroupBox("Limit by Map Sheet")
        self._filter_by_map_sheet_group.setCheckable(True)
        self._filter_by_map_sheet_group.setChecked(False)
        run_layout.addWidget(self._filter_by_map_sheet_group)
        vl = QVBoxLayout()

        self._map_sheet_combo = QgsFeatureListComboBox()
        vl.addWidget(self._map_sheet_combo)

        self._filter_by_map_sheet_group.setLayout(vl)

        self._filter_by_date_group = QGroupBox("Limit Date Range")
        self._filter_by_date_group.setCheckable(True)
        self._filter_by_date_group.setChecked(False)
        run_layout.addWidget(self._filter_by_date_group)
        self._date_widget = QgsDateEdit()
        self._date_widget.setAllowNull(False)
        self._date_widget.setDisplayFormat("yyyy-MM-dd")
        vl = QVBoxLayout()
        vl.addWidget(self._date_widget)
        self._filter_by_date_group.setLayout(vl)

        run_validation_group.setLayout(run_layout)

        self._vlayout.addWidget(run_validation_group)
        hl = QHBoxLayout()
        self._run_button = QPushButton("Run")
        self._run_button.setIcon(GuiUtils.get_icon("run.svg"))
        hl.addWidget(self._run_button)
        self._run_button.clicked.connect(self._run)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setIcon(GuiUtils.get_icon("cancel.svg"))
        hl.addWidget(self._cancel_button)
        self._cancel_button.clicked.connect(self._cancel)
        self._cancel_button.setEnabled(False)

        self._vlayout.addLayout(hl)

        self._results_tab_widget = QTabWidget()
        self._vlayout.addWidget(self._results_tab_widget)

        self._output_widget = QgsCodeEditorPython(
            mode=QgsCodeEditor.Mode.OutputDisplay, flags=QgsCodeEditor.Flags()
        )
        self._output_widget.setReadOnly(True)
        self._output_widget.setLineNumbersVisible(False)

        fm = QFontMetrics(self.font())
        self._results_tab_widget.addTab(self._output_widget, "Validation Output")

        self._results_table = QTableView()
        self._results_model = ValidationResultModel(self)
        last_results = ValidationUtils.get_last_validation_results()
        if last_results:
            self._results_model.set_data(last_results)
        self._results_table.setModel(self._results_model)
        self._results_table.horizontalHeader().setStretchLastSection(True)
        self._results_table.resizeColumnToContents(0)

        self._results_tab_widget.addTab(self._results_table, "Results")
        self._results_tab_widget.setCurrentIndex(1)
        self._results_tab_widget.setFixedHeight(fm.height() * 15)

        self._result_layer_widget = LayerSelectorWidget(ValidationUtils.result_path())
        self._vlayout.addWidget(self._result_layer_widget)

        self._results_viewer = ValidationResultsViewer()
        self._vlayout.addWidget(self._results_viewer)
        self._vlayout.addStretch()

        self._result_layer_changed_timer = QTimer()
        self._result_layer_changed_timer.setInterval(500)
        self._result_layer_changed_timer.setSingleShot(True)
        self._result_layer_changed_timer.timeout.connect(
            self._on_layer_selected_timeout
        )
        self._result_layer_widget.layer_selected.connect(self._on_layer_selected)

        _widget = QWidget()
        _widget.setLayout(self._vlayout)
        scroll_area.setWidget(_widget)
        self.setWidget(scroll_area)

        self._task: ValidationTask | None = None
        self._results_layer: QgsVectorLayer | None = None

    def cleanup(self):
        """
        Cleanup gracefully before dock destruction
        """
        self._map_sheet_combo.setSourceLayer(None)
        self._results_viewer.cleanup()

    def set_map_canvas(self, canvas: QgsMapCanvas):
        self._extent_widget.setMapCanvas(canvas)
        self._extent_widget.setOutputExtentFromCurrent()
        self._results_viewer.set_canvas(canvas)

    def set_project_controller(self, controller: ProjectController):
        self._controller = controller

        if self._controller.map_sheet_layer():
            self._set_map_sheet_layer()
        self._controller.map_sheet_layer_loaded.connect(self._set_map_sheet_layer)
        self._controller.map_sheet_layer_unloaded.connect(self._unset_map_sheet_layer)

    def _set_map_sheet_layer(self):
        layer = self._controller.map_sheet_layer()
        self._map_sheet_combo.setSourceLayer(layer)
        self._map_sheet_combo.setIdentifierFields(["fid"])
        self._map_sheet_combo.setFetchLimit(0)
        self._map_sheet_combo.setDisplayExpression(
            """"sheet_code" || ' (' || "sheet_name" || ')' """
        )

    def _unset_map_sheet_layer(self):
        self._map_sheet_combo.setSourceLayer(None)

    def _get_filter_extent(self) -> QgsRectangle | None:
        """
        Gets the current filter extent, in EPSG:4167
        """
        if (
            not self._filter_by_extent_group.isChecked()
            and not self._filter_by_map_sheet_group.isChecked()
        ):
            return None

        extent_rect = None
        if self._filter_by_extent_group.isChecked():
            transform = QgsCoordinateTransform(
                self._extent_widget.outputCrs(),
                QgsCoordinateReferenceSystem("EPSG:4167"),
                QgsProject.instance().transformContext(),
            )
            transform.setBallparkTransformsAreAppropriate(True)
            transform.setAllowFallbackTransforms(True)
            try:
                extent_rect = transform.transformBoundingBox(
                    self._extent_widget.outputExtent()
                )
            except QgsCsException:
                pass

        sheet_rect = None
        sheet_layer = self._controller and self._controller.map_sheet_layer()
        if sheet_layer and self._filter_by_map_sheet_group.isChecked():
            transform = QgsCoordinateTransform(
                sheet_layer.crs(),
                QgsCoordinateReferenceSystem("EPSG:4167"),
                QgsProject.instance().transformContext(),
            )
            transform.setBallparkTransformsAreAppropriate(True)
            transform.setAllowFallbackTransforms(True)
            sheet_features = sheet_layer.getFeatures(
                self._map_sheet_combo.currentFeatureRequest()
            )
            try:
                sheet_feature = next(sheet_features)
                try:
                    sheet_rect = transform.transformBoundingBox(
                        sheet_feature.geometry().boundingBox()
                    )
                    if not sheet_rect.isFinite():
                        sheet_rect = None
                except QgsCsException:
                    pass
            except StopIteration:
                pass

        if extent_rect is not None and sheet_rect is None:
            return extent_rect
        elif extent_rect is None and sheet_rect is not None:
            return sheet_rect
        elif extent_rect is None and sheet_rect is None:
            return None

        return sheet_rect.intersect(extent_rect)

    def _get_filter_date(self) -> QDate | None:
        """
        Gets the current filter date
        """
        if not self._filter_by_date_group.isChecked():
            return None

        return self._date_widget.date()

    def _run(self):
        if self._task and not sip.isdeleted(self._task):
            if (
                QMessageBox.warning(
                    self,
                    "Validation Running",
                    "A validation task is already running. Do you want to cancel that task?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                return

            self._task.cancel()
            self._task = None

        if not VALIDATION_COMMAND.value():
            QMessageBox.critical(
                self,
                "Validate Data",
                "No validation script command has not been set. Please configure via the Settings - Options - TopoMapping menu.",
                QMessageBox.StandardButton.Ok,
            )
            return

        gpkg_path = self._controller.working_geopackage_path()
        if not gpkg_path:
            QMessageBox.critical(
                self,
                "Validate Data",
                "The file path to the GeoPackage to validate for the current QGIS project could not be detected.",
                QMessageBox.StandardButton.Ok,
            )
            return

        program, arguments = ValidationUtils.generate_validation_command(
            gpkg_path, extent=self._get_filter_extent(), date=self._get_filter_date()
        )

        self._task = ValidationTask(
            program, arguments, VALIDATION_COMMAND_WORKING_DIR.value()
        )
        self._task.taskCompleted.connect(self._task_completed)
        self._task.taskTerminated.connect(self._task_terminated)

        self._task.on_message.connect(self._on_stdout)
        self._task.on_error.connect(self._on_stderr)
        self._output_widget.clear()
        self._cancel_button.setEnabled(True)
        self._results_tab_widget.setCurrentIndex(0)

        QgsApplication.taskManager().addTask(self._task)

    def _cancel(self):
        if not self._task or sip.isdeleted(self._task):
            return

        self._task.cancel()

    def _task_completed(self):
        if self.sender() != self._task:
            return
        self._cancel_button.setEnabled(False)
        self._task = None
        self._scroll_to_bottom_of_log()
        self._results_tab_widget.setCurrentIndex(1)

        self._results_model.set_data(ValidationUtils.get_last_validation_results())
        self._result_layer_widget.reload()

    def _task_terminated(self):
        if self.sender() != self._task:
            return

        canceled = self._task.isCanceled()
        self._cancel_button.setEnabled(False)
        exit_status = self._task.exit_status
        result_code = self._task.result_code
        process_error = self._task.process_error

        self._task = None

        self._output_widget.append("\n\n" + "Validation terminated!")
        if not canceled:
            self._output_widget.append("\n\n" + f"Exit status: {exit_status}")
            self._output_widget.append("\n" + f"Result code: {result_code}")
            self._output_widget.append("\n" + f"Process error: {process_error}")
        self._scroll_to_bottom_of_log()
        self._results_tab_widget.setCurrentIndex(0)

    def _on_stderr(self, s: str):
        sb = self._output_widget.verticalScrollBar()
        is_at_bottom = sb.value() == sb.maximum() if sb else True

        if self._output_widget.text() and self._output_widget.text()[-1] != "\n":
            s = "\n" + s
        self._output_widget.append(s)
        if is_at_bottom:
            self._scroll_to_bottom_of_log()

    def _on_stdout(self, s: str):
        sb = self._output_widget.verticalScrollBar()
        is_at_bottom = sb.value() == sb.maximum() if sb else True
        if self._output_widget.text() and self._output_widget.text()[-1] != "\n":
            s = "\n" + s
        self._output_widget.append(s)
        if is_at_bottom:
            self._scroll_to_bottom_of_log()

    def _scroll_to_bottom_of_log(self):
        sb = self._output_widget.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _on_layer_selected(self, path: str, layer: str):
        self._result_layer_changed_timer.start()

    def _on_layer_selected_timeout(self):
        if not self._result_layer_widget.selected_path():
            return

        parts = {
            "path": self._result_layer_widget.selected_path(),
            "layerName": self._result_layer_widget.selected_layer(),
        }
        source = QgsProviderRegistry.instance().encodeUri("ogr", parts)

        if self._results_layer is not None and not sip.isdeleted(self._results_layer):
            self._results_layer.commitChanges()

        self._results_layer = QgsVectorLayer(source, "results", "ogr")

        self._results_layer.startEditing()
        self._results_viewer.set_source(self._results_layer)
