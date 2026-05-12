from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtWidgets import QToolButton, QButtonGroup, QSizePolicy
from qgis.gui import QgsDockWidget

from .responsive_table_widget import ResponsiveTableWidget


class ToolDock(QgsDockWidget):
    """
    A dock widget for display of a set of tools
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._widget = ResponsiveTableWidget()
        self._widget.resize(QSize(300, 300))
        self._widget.show()

        group = QButtonGroup(self._widget)
        for i in range(30):
            btn = QToolButton()
            btn.setAutoRaise(True)
            btn.setText(str(i))
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            self._widget.push_widget(btn)
            group.addButton(btn)
        self.setWidget(self._widget)
