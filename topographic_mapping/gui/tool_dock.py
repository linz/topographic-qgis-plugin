from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtGui import QPalette
from qgis.PyQt.QtWidgets import (
    QToolButton,
    QActionGroup,
    QSizePolicy,
    QAction,
    QVBoxLayout,
    QWidget,
    QLabel,
)
from qgis.gui import QgsDockWidget

from .gui_utils import GuiUtils
from .responsive_table_widget import ResponsiveTableWidget


class ToolDock(QgsDockWidget):
    """
    A dock widget for display of a set of tools
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._vlayout = QVBoxLayout()
        self._vlayout.setContentsMargins(0, 0, 6, 0)
        self._vlayout.addStretch()
        _widget = QWidget(self)
        _widget.setLayout(self._vlayout)
        self.setWidget(_widget)

        self._tool_groups = {}

        self._action_group = QActionGroup(self)

        for title in ("Topographic editing", "Labeling"):
            for i in range(30):
                action = QAction(str(i), self)
                action.setCheckable(True)
                if i % 2 == 1:
                    action.setIcon(GuiUtils.get_colorized_icon("buffer.svg"))
                else:
                    action.setIcon(GuiUtils.get_colorized_icon("simplify.svg"))
                self._action_group.addAction(action)
                self.add_tool_action(action, title)

    def _create_heading_label(self, text: str):
        label = QLabel(text)
        palette = label.palette()

        dark_color = palette.color(QPalette.ColorRole.Dark)
        bright_text_color = palette.color(QPalette.ColorRole.BrightText)
        palette.setColor(QPalette.ColorRole.Window, dark_color)
        palette.setColor(QPalette.ColorRole.WindowText, bright_text_color)
        label.setPalette(palette)

        label.setAutoFillBackground(True)
        label.setMargin(3)
        return label

    def _create_tool_group(self, group_title: str):
        title = self._create_heading_label(group_title)

        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vlayout.insertWidget(self._vlayout.count() - 1, title)
        group_widget = ResponsiveTableWidget()
        self._vlayout.insertWidget(self._vlayout.count() - 1, group_widget)
        self._tool_groups[group_title] = group_widget
        return group_widget

    def add_tool_action(self, action: QAction, group_title: str):
        """
        Adds a tool action to the toolbox
        """
        tool_group_widget = self._tool_groups.get(group_title)
        if not tool_group_widget:
            tool_group_widget = self._create_tool_group(group_title)

        btn = QToolButton()
        btn.setDefaultAction(action)
        btn.setAutoRaise(True)
        btn.setFixedHeight(36)
        btn.setIconSize(QSize(24, 24))
        btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        tool_group_widget.push_widget(btn)
