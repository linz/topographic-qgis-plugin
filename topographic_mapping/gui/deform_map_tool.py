"""
Geometry deformation tool
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

from qgis.core import Qgis, QgsGeometry, QgsProject, QgsVectorLayer
from qgis.gui import QgsMapTool, QgsMapCanvas, QgsRubberBand

from topographic_mapping.core.geometry.rubber_band_transform import RubberSheetingTool


class RubberSheetingMapTool(QgsMapTool):
    def __init__(self, canvas: QgsMapCanvas, radius: float):
        super().__init__(canvas)
        self.canvas = canvas
        self.radius = radius
        self.start_pt = None

        self.rb_line = QgsRubberBand(self.canvas, Qgis.GeometryType.Line)
        self.rb_line.setColor(QColor(255, 0, 0, 200))
        self.rb_line.setWidth(2)

        self.rb_radius = QgsRubberBand(self.canvas, Qgis.GeometryType.Polygon)
        self.rb_radius.setColor(QColor(0, 150, 255, 50))
        self.rb_radius.setStrokeColor(QColor(0, 150, 255, 200))
        self.rb_radius.setWidth(1)

    def reset(self):
        self.start_pt = None
        self.rb_line.reset(Qgis.GeometryType.Line)
        self.rb_radius.reset(Qgis.GeometryType.Polygon)

    def canvasReleaseEvent(self, event):
        pt = self.toMapCoordinates(event.pos())
        if event.button() == Qt.MouseButton.RightButton:
            self.reset()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.start_pt is None:
                self.start_pt = pt

                geom = QgsGeometry.fromPointXY(pt).buffer(self.radius, 36)
                self.rb_radius.setToGeometry(geom, None)
            else:
                end_pt = pt

                layers = []
                for _, layer in QgsProject.instance().mapLayers().items():
                    if isinstance(layer, QgsVectorLayer) and layer.isEditable():
                        layers.append(layer)

                tool = RubberSheetingTool(
                    layers=layers,
                    start_pt=self.start_pt,
                    end_pt=end_pt,
                    radius=self.radius,
                    crs=self.canvas.mapSettings().destinationCrs(),
                )
                tool.apply()
                self.reset()

    def canvasMoveEvent(self, event):
        if self.start_pt:
            pt = self.toMapCoordinates(event.pos())
            self.rb_line.reset(Qgis.GeometryType.Line)
            self.rb_line.addPoint(self.start_pt, False)
            self.rb_line.addPoint(pt, True)

    def deactivate(self):
        self.reset()
        super().deactivate()
