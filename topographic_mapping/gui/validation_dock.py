from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QFrame,
    QGroupBox,
    QPushButton,
)

from qgis.core import QgsRunProcess, QgsBlockingProcess
from qgis.gui import (
    QgsDockWidget,
    QgsCollapsibleGroupBoxBasic,
    QgsExtentWidget,
    QgsMapCanvas,
    QgsDateEdit,
)

from ..core import ProjectController
from ..settings import VALIDATION_COMMAND_WORKING_DIR, VALIDATION_COMMAND


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
        arguments.extend(["--db-path", gpkg_path])

        arguments.extend(["--output-dir", "/home/nyall/Temporary/ttt"])

        process = QgsBlockingProcess(program, arguments)
        process.setWorkingDirectory(VALIDATION_COMMAND_WORKING_DIR.value())

        def on_stderr(s):
            print(s)

        def on_stdout(s):
            print(s)

        process.setStdErrHandler(on_stderr)
        process.setStdOutHandler(on_stdout)
        process.run()
        print(process.exitStatus())
        print(process.processError())
