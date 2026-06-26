from qgis.PyQt import sip
from qgis.PyQt.QtCore import Qt, pyqtSignal, QDate
from qgis.PyQt.QtGui import QFontMetrics
from qgis.PyQt.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QScrollArea,
    QFrame,
    QGroupBox,
    QPushButton,
    QMessageBox,
)
from qgis.core import (
    QgsBlockingProcess,
    QgsTask,
    QgsApplication,
    QgsFeedback,
    QgsReferencedRectangle,
)
from qgis.gui import (
    QgsDockWidget,
    QgsCollapsibleGroupBoxBasic,
    QgsExtentWidget,
    QgsMapCanvas,
    QgsDateEdit,
    QgsCodeEditorPython,
    QgsCodeEditor,
)

from . import GuiUtils
from ..core import ProjectController, ValidationUtils
from ..settings import VALIDATION_COMMAND_WORKING_DIR, VALIDATION_COMMAND


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
        self._stored_object_manager: StoredObjectManager | None = None

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

        self._output_widget = QgsCodeEditorPython(
            mode=QgsCodeEditor.Mode.OutputDisplay, flags=QgsCodeEditor.Flags()
        )
        self._output_widget.setReadOnly(True)
        self._output_widget.setLineNumbersVisible(False)

        fm = QFontMetrics(self.font())
        self._output_widget.setFixedHeight(fm.height() * 20)

        self._vlayout.addWidget(self._output_widget)

        self._vlayout.addStretch()

        _widget = QWidget()
        _widget.setLayout(self._vlayout)
        scroll_area.setWidget(_widget)
        self.setWidget(scroll_area)

        self._task: ValidationTask | None = None

    def set_map_canvas(self, canvas: QgsMapCanvas):
        self._extent_widget.setMapCanvas(canvas)
        self._extent_widget.setOutputExtentFromCurrent()

    def set_project_controller(self, controller: ProjectController):
        self._controller = controller

    def _get_filter_extent(self) -> QgsReferencedRectangle | None:
        """
        Gets the current filter extent
        """
        if not self._filter_by_extent_group.isChecked():
            return None

        return QgsReferencedRectangle(
            self._extent_widget.outputExtent(), self._extent_widget.outputCrs()
        )

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
            # todo -- error
            return

        gpkg_path = self._controller.working_geopackage_path()
        if not gpkg_path:
            # todo error
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
