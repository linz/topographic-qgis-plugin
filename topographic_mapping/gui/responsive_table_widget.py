from qgis.PyQt.QtWidgets import QSizePolicy, QWidget

from .responsive_table_layout import ResponsiveTableLayout


class ResponsiveTableWidget(QWidget):
    """
    A responsive table widget
    """

    VERTICAL_SPACING = 10
    HORIZONTAL_SPACING = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._layout = ResponsiveTableLayout(parent=None)
        self.setLayout(self._layout)

        self._layout.setContentsMargins(0, 0, 16, 16)

        self._widgets = []

    def clear(self):
        """
        Clears all widget from the table
        """
        for w in self._widgets:
            w.deleteLater()
            self._layout.takeAt(0)
        self._widgets = []

    def column_count(self) -> int:
        """
        Returns the table column count
        """
        return self._layout.column_count()

    def replace_widget(self, old_widget: QWidget, new_widget: QWidget):
        """
        Replaces a widget in the table
        """
        idx = self._widgets.index(old_widget)
        self._widgets[idx].setParent(None)
        self._widgets[idx].deleteLater()

        self._widgets[idx] = new_widget
        self._widgets[idx].setParent(self)

        self._layout.insert_widget(idx, new_widget)

        self._layout.takeAt(idx + 1)

    def push_widget(self, widget: QWidget):
        """
        Pushes a widget to the table
        """
        self._widgets.append(widget)
        self._layout.addWidget(widget)

    def remove_widget(self, widget: QWidget):
        """
        Removes a widget from the table
        """
        idx = self._widgets.index(widget)
        self._widgets[idx].setParent(None)
        self._widgets[idx].deleteLater()
        self._layout.takeAt(idx)
        del self._widgets[idx]
