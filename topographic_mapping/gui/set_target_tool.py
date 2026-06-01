from qgis.PyQt.QtCore import pyqtSignal, Qt, QPoint
from qgis.PyQt.QtGui import QColor


from qgis.core import (
    QgsApplication,
    Qgis,
    QgsVectorLayer,
    QgsIdentifyContext,
    QgsGeometry,
    QgsProject,
    QgsRectangle,
    QgsMapLayer,
)
from qgis.gui import (
    QgsMapToolIdentify,
    QgsMapMouseEvent,
    QgsIdentifyMenu,
    QgsMapCanvas,
    QgsRubberBand,
    QgsAbstractMapToolHandler,
)

from ..core import LayerUtils


class SetTargetTool(QgsMapToolIdentify):
    """
    Custom map tool for setting edit targets
    """

    target_set = pyqtSignal(QgsVectorLayer, int)

    def __init__(self, canvas: QgsMapCanvas):
        super().__init__(canvas)
        self.rubber_band: QgsRubberBand | None = None
        self.start_point: QPoint | None = None
        self.is_dragging: bool = False

        self.setCursor(QgsApplication.getThemeCursor(QgsApplication.Cursor.Select))

    def canvasPressEvent(self, event: QgsMapMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = self.toMapCoordinates(event.position().toPoint())
            self.is_dragging = False

            if not self.rubber_band:
                self.rubber_band = QgsRubberBand(
                    self.canvas(), Qgis.GeometryType.Polygon
                )
                self.rubber_band.setColor(QColor(0, 120, 255, 65))
                self.rubber_band.setStrokeColor(QColor(0, 120, 255, 255))
                self.rubber_band.setWidth(1)

            self.rubber_band.reset(Qgis.GeometryType.Polygon)

    def canvasMoveEvent(self, event: QgsMapMouseEvent):
        if not self.start_point or not (event.buttons() & Qt.MouseButton.LeftButton):
            return

        self.is_dragging = True
        current_point = self.toMapCoordinates(event.position().toPoint())

        rect = QgsRectangle(self.start_point, current_point)
        self.rubber_band.setToGeometry(QgsGeometry.fromRect(rect), None)

    def canvasReleaseEvent(self, event: QgsMapMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.rubber_band:
            self.rubber_band.hide()

        current_point = self.toMapCoordinates(event.position().toPoint())
        if self.is_dragging and self.start_point:
            rect = QgsRectangle(self.start_point, current_point)
            geom = QgsGeometry.fromRect(rect)
        else:
            geom = QgsGeometry.fromPointXY(current_point)

        self.start_point = None
        self.is_dragging = False

        context = QgsIdentifyContext()
        layer_list = LayerUtils.valid_edit_target_layers(QgsProject.instance())

        identify_results = self.identify(
            geom,
            QgsMapToolIdentify.IdentifyMode.TopDownAll,
            layer_list,
            QgsMapToolIdentify.Type.VectorLayer,
            context,
        )
        menu = QgsIdentifyMenu(self.canvas())
        menu.setExecWithSingleResult(True)
        menu.setAllowMultipleReturn(False)
        menu.setMaxFeatureDisplay(20)
        res = menu.exec(identify_results, event.globalPosition().toPoint())
        if not res:
            return

        target = res[0]
        self.target_set.emit(target.mLayer, target.mFeature.id())


class SetTargetToolHandler(QgsAbstractMapToolHandler):
    """
    Map tool handler for the SetTargetTool
    """

    def __init__(self, tool, action):
        super().__init__(tool, action)

    def isCompatibleWithLayer(
        self, layer: QgsMapLayer | None, context: QgsAbstractMapToolHandler.Context
    ):
        return True
