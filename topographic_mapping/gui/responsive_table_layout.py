"""
Responsive table layout
"""

from typing import Optional, List

from qgis.PyQt.QtCore import Qt, QRect, QSize
from qgis.PyQt.QtWidgets import QLayout, QStyle, QWidget, QWidgetItem, QLayoutItem


class ResponsiveTableLayout(QLayout):
    """
    A responsive table layout which dynamically flows to multiple columns
    """

    def __init__(self, parent, hspacing: int, vspacing: int):
        super().__init__(parent)

        self.hspacing: int = hspacing
        self.vspacing: int = vspacing

        self._column_count: int = 1

        self.itemList: List[QLayoutItem] = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def horizontalSpacing(self) -> int:
        """
        Returns the horizontal spacing between items
        """
        if self.hspacing >= 0:
            return self.hspacing
        return self.smart_spacing(QStyle.PixelMetric.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self) -> int:
        """
        Returns the vertical spacing between items
        """
        if self.vspacing >= 0:
            return self.vspacing
        return self.smart_spacing(QStyle.PixelMetric.PM_LayoutVerticalSpacing)

    # QLayout interface
    # pylint: disable=missing-function-docstring
    def addItem(self, item: QLayoutItem):
        self.itemList.append(item)

    def count(self) -> int:
        return len(self.itemList)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self.itemList):
            return self.itemList[index]

        return None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)

        return None

    def expandingDirections(self):
        return Qt.Orientations()  # Qt.Orientation.Horizontal)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()

        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())

        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    # pylint: enable=missing-function-docstring

    def insert_widget(self, idx: int, widget: QWidget):
        """
        Inserts a widget into the layout at a given index
        """
        self.addChildWidget(widget)
        item = QWidgetItem(widget)
        self.itemList.insert(idx, item)
        self.invalidate()

    def column_count(self) -> int:
        """
        Returns the current column count
        """
        return self._column_count

    def _do_layout(self, rect: QRect, test_only: bool):  # pylint: disable=too-many-locals
        """
        Calculates the layout
        """
        margins = self.contentsMargins()
        left = margins.left()
        top = margins.top()
        right = margins.right()
        bottom = margins.bottom()

        effective_rect = rect.adjusted(left, top, -right, -bottom)

        col_count = int(effective_rect.width() / 400)

        col_count = max(1, col_count)

        space_x = self.horizontalSpacing()
        space_y = self.verticalSpacing()

        width_without_spacing = effective_rect.width() - (col_count - 1) * space_x
        col_width = int(width_without_spacing / col_count)

        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        y_offsets = [y]

        assigned_lines = []
        current_line_items = []

        visible_items = [i for i in self.itemList if not i.widget().isHidden()]

        if not visible_items:
            return 0

        for item in visible_items:
            next_x = x + col_width + space_x

            current_line_items.append(item)
            line_height = max(line_height, item.sizeHint().height())
            if len(current_line_items) == col_count:
                assigned_lines.append(current_line_items[:])
                current_line_items = []

                x = effective_rect.x()
                y = y + line_height + space_y
                y_offsets.append(y)

                next_x = x + item.minimumSize().width() + space_x
                line_height = 0

            x = next_x

        if current_line_items:
            assigned_lines.append(current_line_items[:])

        if not test_only:
            self._column_count = col_count
            for idx, line in enumerate(assigned_lines):
                y_offset = y_offsets[idx]

                x = effective_rect.left()
                for item in line:
                    item.setGeometry(
                        QRect(x, y_offset, col_width, item.sizeHint().height())
                    )

                    x += col_width + space_x

        return y + line_height - rect.y() + bottom

    def smart_spacing(self, pm: QStyle.PixelMetric) -> int:
        """
        Calculates spacing for the layout
        """
        parent = self.parent()
        if not parent:
            return -1

        if parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)

        return parent.spacing()
