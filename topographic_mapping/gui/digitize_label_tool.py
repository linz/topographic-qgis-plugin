from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsPoint,
    QgsVectorLayer,
    QgsLineString,
    Qgis,
)
from qgis.gui import QgsMapCanvas, QgsMapMouseEvent, QgsMapToolCapture
from qgis.PyQt.QtCore import Qt


class DigitizeLabelTool(QgsMapToolCapture):
    """
    Map tool that creates a horizontal line of fixed length starting from a left-clicked point.
    """

    def __init__(
        self,
        canvas: QgsMapCanvas,
        fixed_width: float,
        target_layer: QgsVectorLayer,
        cad_dock_widget,
        fid: int,
    ):
        super().__init__(canvas, cad_dock_widget, QgsMapToolCapture.CaptureLine)
        self.canvas = canvas
        self.fixed_width = fixed_width
        self._target_layer = target_layer
        self._target_fid = fid

        self._preview_band = self.createRubberBandForLayer(
            self._target_layer, [self._target_fid]
        )
        # self._preview_band.setRenderedComponents(Qgis.RubberBandComponent.PreviewItems)
        self._preview_band.show()

    def cancel_tool(self) -> None:
        """Hides the rubber band preview and unsets the tool from the map canvas."""
        if self._preview_band:
            self._preview_band.hide()
        self.canvas.unsetMapTool(self)

    def deactivate(self) -> None:
        if self._preview_band:
            self._preview_band.hide()
        super().deactivate()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.cancel_tool()
            return
        super().keyPressEvent(e)

    def canvasMoveEvent(self, e: QgsMapMouseEvent | None) -> None:
        super().canvasMoveEvent(e)

        start_pt = e.mapPoint()
        end_pt = QgsPoint(start_pt.x() + self.fixed_width, start_pt.y())
        line_geom = QgsGeometry(QgsLineString([start_pt, end_pt]))
        self._preview_band.setToGeometry(line_geom, self._target_layer)

    def canvasReleaseEvent(self, e: QgsMapMouseEvent) -> None:
        if e.button() == Qt.MouseButton.RightButton:
            self.cancel_tool()
            return

        if e.button() != Qt.MouseButton.LeftButton:
            return

        start_pt = e.mapPoint()
        end_pt = QgsPoint(start_pt.x() + self.fixed_width, start_pt.y())
        line_geom = QgsGeometry(QgsLineString([start_pt, end_pt]))

        self._target_layer.changeGeometry(self._target_fid, line_geom)
