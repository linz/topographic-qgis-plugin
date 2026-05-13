"""
A QIconEngine which renders icons from raw SVG content
"""

from qgis.PyQt.QtCore import Qt, QByteArray, QRect, QRectF, QSize
from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter, QIconEngine
from qgis.PyQt.QtSvg import QSvgRenderer


class SvgMemoryIconEngine(QIconEngine):
    """
    A QIconEngine which renders icons from raw SVG content, preserving
    vector scalability of the icons
    """

    def __init__(self, svg_bytes: QByteArray):
        super().__init__()
        self.svg_bytes = svg_bytes

    def paint(
        self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State
    ):
        """
        Renders the icon to a painter
        """
        renderer = QSvgRenderer(self.svg_bytes)
        renderer.render(painter, QRectF(rect))

    def clone(self) -> QIconEngine:
        return SvgMemoryIconEngine(self.svg_bytes)

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        """
        Fallback for when Qt explicitly requests a rasterized pixmap
        """
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        self.paint(painter, QRect(0, 0, size.width(), size.height()), mode, state)
        painter.end()

        return pixmap
