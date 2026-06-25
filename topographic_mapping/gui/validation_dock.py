from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QFrame,
    QGroupBox,
    QPushButton,
)

from qgis.core import (
    QgsRunProcess,
    QgsBlockingProcess,
    QgsTask,
    QgsApplication,
    QgsFeedback,
)
from qgis.gui import (
    QgsDockWidget,
    QgsCollapsibleGroupBoxBasic,
    QgsExtentWidget,
    QgsMapCanvas,
    QgsDateEdit,
)

from ..core import ProjectController
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
        self._run_button = QPushButton("Run")
        self._vlayout.addWidget(self._run_button)
        self._run_button.clicked.connect(self._run)
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

    def _run(self):
        if not VALIDATION_COMMAND.value():
            # todo -- error
            return

        gpkg_path = self._controller.working_geopackage_path()
        if not gpkg_path:
            # todo error
            return

        program, *arguments = QgsRunProcess.splitCommand(VALIDATION_COMMAND.value())
        arguments.extend(["--output-dir", "/home/nyall/Temporary/ttt"])
        arguments.extend(["--db-path", gpkg_path])
        # arguments.extend(["--bbox", "174.8", "-41.3", "174.9", "-41.2"])

        self._task = ValidationTask(
            program, arguments, VALIDATION_COMMAND_WORKING_DIR.value()
        )

        self._task.on_message.connect(self._on_stdout)
        self._task.on_error.connect(self._on_stderr)

        QgsApplication.taskManager().addTask(self._task)

    def _on_stderr(self, s: str):
        print(s)

    def _on_stdout(self, s: str):
        print(s)
