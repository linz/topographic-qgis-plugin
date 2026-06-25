from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QVBoxLayout, QWidget, QScrollArea, QFrame, QGroupBox
from qgis.gui import (
    QgsDockWidget,
    QgsCollapsibleGroupBoxBasic,
    QgsExtentWidget,
    QgsMapCanvas,
    QgsDateEdit,
)


class ValidationDock(QgsDockWidget):
    """
    A dock widget for running validation tools
    """

    def __init__(self, parent):
        super().__init__(parent)

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
        self._vlayout.addStretch()

        _widget = QWidget()
        _widget.setLayout(self._vlayout)
        scroll_area.setWidget(_widget)
        self.setWidget(scroll_area)

    def set_map_canvas(self, canvas: QgsMapCanvas):
        self._extent_widget.setMapCanvas(canvas)
        self._extent_widget.setOutputExtentFromCurrent()
