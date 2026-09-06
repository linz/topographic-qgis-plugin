"""
Map tool for selecting features by their labels
"""

from qgis.core import Qgis, QgsGeometry, QgsPointXY, QgsRectangle, QgsVectorLayer
from qgis.gui import QgsMapCanvas, QgsMapMouseEvent, QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt, QPoint
from qgis.PyQt.QtGui import QColor, QKeyEvent
from qgis.PyQt.QtWidgets import QApplication


class SelectByLabelRectangleTool(QgsMapTool):
    """
    Map tool that allows rectangular drag selection on label features,
    selecting their associated target vector layer features.
    """

    # to match QGIS behavior
    SINGLE_CLICK_BOX_SIZE_PX = 5

    def __init__(self, canvas: QgsMapCanvas):
        super().__init__(canvas)
        self._canvas = canvas
        self._label_layer: QgsVectorLayer | None = None

        self._start_map_point: QgsPointXY | None = None
        self._start_point: QPoint | None = None
        self._is_dragging = False

        self._rubber_band = QgsRubberBand(self._canvas, Qgis.GeometryType.Polygon)
        self._rubber_band.setColor(QColor(254, 178, 76, 63))
        self._rubber_band.setStrokeColor(QColor(254, 58, 29, 100))

    def set_label_layer(self, layer: QgsVectorLayer) -> None:
        self._label_layer = layer

    def canvasPressEvent(self, e: QgsMapMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._start_map_point = e.mapPoint()
            self._start_point = e.pos()
            self._is_dragging = True
            self._rubber_band.reset(Qgis.GeometryType.Polygon)

    def canvasMoveEvent(self, e: QgsMapMouseEvent) -> None:
        if not self._is_dragging or not self._start_point:
            return

        current_point = e.mapPoint()
        rect = QgsRectangle(self._start_map_point, current_point)
        self._rubber_band.setToGeometry(QgsGeometry.fromRect(rect), None)

    def canvasReleaseEvent(self, e: QgsMapMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton or not self._is_dragging:
            return

        self._is_dragging = False
        end_point = e.mapPoint()
        self._rubber_band.reset(Qgis.GeometryType.Polygon)

        drag_dist = e.pos() - self._start_point
        if drag_dist.manhattanLength() < QApplication.startDragDistance():
            # effectively a point click
            rect = self.expand_select_rectangle(end_point)
        else:
            rect = QgsRectangle(self._start_map_point, end_point)

        self._select_features_by_rendered_labels(rect, e.modifiers())
        self._start_point = None
        self._start_map_point = None

    def expand_select_rectangle(self, map_point: QgsPointXY) -> QgsRectangle:
        """
        Expands a single-click map point into a pixel-buffered selection bounding box.
        """
        transform = self._canvas.getCoordinateTransform()
        point = transform.transform(map_point)

        ll = transform.toMapCoordinates(
            int(point.x() - self.SINGLE_CLICK_BOX_SIZE_PX),
            int(point.y() + self.SINGLE_CLICK_BOX_SIZE_PX),
        )
        lr = transform.toMapCoordinates(
            int(point.x() + self.SINGLE_CLICK_BOX_SIZE_PX),
            int(point.y() + self.SINGLE_CLICK_BOX_SIZE_PX),
        )
        ur = transform.toMapCoordinates(
            int(point.x() + self.SINGLE_CLICK_BOX_SIZE_PX),
            int(point.y() - self.SINGLE_CLICK_BOX_SIZE_PX),
        )
        ul = transform.toMapCoordinates(
            int(point.x() - self.SINGLE_CLICK_BOX_SIZE_PX),
            int(point.y() - self.SINGLE_CLICK_BOX_SIZE_PX),
        )

        return QgsGeometry.fromPolygonXY([[ll, lr, ur, ul, ll]]).boundingBox()

    def _select_features_by_rendered_labels(
        self, rect: QgsRectangle, modifiers: Qt.KeyboardModifiers
    ) -> None:

        labeling_results = self._canvas.labelingResults()
        if not self._label_layer:
            return

        label_positions = labeling_results.labelsWithinRect(rect)

        target_fids = set()
        label_layer_id = self._label_layer.id()

        for pos in label_positions:
            if pos.layerID == label_layer_id:
                target_fids.add(pos.featureId)

        behavior = QgsVectorLayer.SelectBehavior.SetSelection
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            behavior = QgsVectorLayer.SelectBehavior.IntersectSelection
        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
            behavior = QgsVectorLayer.SelectBehavior.AddToSelection

        self._label_layer.selectByIds(list(target_fids), behavior)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.deactivate()
            self._canvas.unsetMapTool(self)
        super().keyPressEvent(e)

    def deactivate(self) -> None:
        self._rubber_band.reset(Qgis.GeometryType.Polygon)
        self._is_dragging = False
        self._start_point = None
        self._start_map_point = None
        super().deactivate()
