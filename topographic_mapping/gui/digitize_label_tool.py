from qgis.PyQt import sip
from qgis.core import (
    QgsGeometry,
    QgsPoint,
    QgsVectorLayer,
    QgsLineString,
    Qgis,
)
from qgis.gui import (
    QgsMapCanvas,
    QgsMapMouseEvent,
    QgsMapToolCapture,
    QgsMapTool,
    QgsRubberBand,
)
from qgis.PyQt.QtCore import Qt


class DigitizeLabelTool(QgsMapToolCapture):
    """
    Map tool that creates a horizontal line of fixed length starting from a left-clicked point.
    """

    def __init__(
        self,
        canvas: QgsMapCanvas,
        cad_dock_widget,
    ):
        super().__init__(
            canvas, cad_dock_widget, QgsMapToolCapture.CaptureMode.CaptureLine
        )
        self.canvas = canvas
        self._target_width: float | None = None
        self._target_layer: QgsVectorLayer | None = None
        self._target_fid: int | None = None
        self._previous_tool: QgsMapTool | None = None

        self._preview_band: QgsRubberBand | None = None

    def set_target_layer(self, layer: QgsVectorLayer) -> None:
        self._target_layer = layer

    def set_target_feature(self, fid: int) -> None:
        self._target_fid = fid

    def set_target_width(self, width: float) -> None:
        self._target_width = width

    def cancel_tool(self) -> None:
        """Hides the rubber band preview and unsets the tool from the map canvas."""
        self.remove_rubber_band()
        self.canvas.unsetMapTool(self)

    def activate(self) -> None:
        if self._preview_band and not sip.isdeleted(self._preview_band):
            del self._preview_band
        self._preview_band = None

        if self._target_fid is not None and self._target_layer is not None:
            self._preview_band = self.createRubberBandForLayer(
                self._target_layer, [self._target_fid]
            )
            # self._preview_band.setRenderedComponents(
            #    Qgis.RubberBandComponent.PreviewItems)
            self._preview_band.show()

    def remove_rubber_band(self):
        if self._preview_band and not sip.isdeleted(self._preview_band):
            del self._preview_band
        self._preview_band = None

    def deactivate(self) -> None:
        self.remove_rubber_band()
        super().deactivate()
        if self._previous_tool is not None and not sip.isdeleted(self._previous_tool):
            self.canvas.setMapTool(self._previous_tool)

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.cancel_tool()
            return
        super().keyPressEvent(e)

    def canvasMoveEvent(self, e: QgsMapMouseEvent | None) -> None:
        super().canvasMoveEvent(e)

        start_pt = e.mapPoint()
        end_pt = QgsPoint(start_pt.x() + self._target_width, start_pt.y())
        line_geom = QgsGeometry(QgsLineString([start_pt, end_pt]))
        self._preview_band.setToGeometry(line_geom, self._target_layer)

    def canvasReleaseEvent(self, e: QgsMapMouseEvent) -> None:
        if e.button() == Qt.MouseButton.RightButton:
            self.cancel_tool()
            return

        if e.button() != Qt.MouseButton.LeftButton:
            return

        if self._target_fid is None or self._target_width is None:
            return

        start_pt = e.mapPoint()
        end_pt = QgsPoint(start_pt.x() + self._target_width, start_pt.y())
        line_geom = QgsGeometry(QgsLineString([start_pt, end_pt]))

        self._target_layer.changeGeometry(self._target_fid, line_geom)
