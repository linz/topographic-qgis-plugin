"""
Geometry deformation tool
"""

from qgis.PyQt import sip
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QWidget, QGridLayout, QLabel

from qgis.core import Qgis, QgsGeometry, QgsProject, QgsVectorLayer
from qgis.gui import QgsMapTool, QgsMapCanvas, QgsRubberBand, QgsDoubleSpinBox
from qgis.utils import iface


from topographic_mapping.core.geometry.rubber_band_transform import RubberSheetingTool


class DeformWidget(QWidget):
    radius_changed = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Radius"), 0, 0)

        self._radius_spin = QgsDoubleSpinBox()
        self._radius_spin.setMinimum(0)
        self._radius_spin.setMaximum(99999)
        self._radius_spin.setDecimals(0)
        self._radius_spin.setSingleStep(100)
        self._radius_spin.setClearValue(100)
        self._radius_spin.setValue(30)
        layout.addWidget(self._radius_spin, 0, 1)

        self._radius_spin.valueChanged.connect(self.radius_changed)

        self.setLayout(layout)

    def set_radius(self, radius: float):
        self._radius_spin.setValue(radius)


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

        self._deform_widget: DeformWidget | None = None

    def activate(self) -> None:
        self.create_widget()
        super().activate()

    def create_widget(self):
        if not self.canvas:
            return

        self.delete_widget()
        self._deform_widget = DeformWidget()
        self._deform_widget.set_radius(self.radius)
        iface.addUserInputWidget(self._deform_widget)
        self._deform_widget.setFocus(Qt.FocusReason.TabFocusReason)
        self._deform_widget.radius_changed.connect(self._on_radius_changed)

    def delete_widget(self):
        if self._deform_widget is not None and not sip.isdeleted(self._deform_widget):
            self._deform_widget.deleteLater()
            self._deform_widget = None

    def reset(self):
        self.start_pt = None
        self.rb_line.reset(Qgis.GeometryType.Line)
        self.rb_radius.reset(Qgis.GeometryType.Polygon)

    def _on_radius_changed(self, radius: float):
        self.radius = radius

        if self.start_pt is not None:
            geom = QgsGeometry.fromPointXY(self.start_pt).buffer(self.radius, 36)
            self.rb_radius.setToGeometry(geom, None)

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

                for layer in iface.layerTreeView().selectedLayers():
                    if isinstance(layer, QgsVectorLayer) and layer.isEditable():
                        layers.append(layer)

                tool = RubberSheetingTool(
                    layers=layers,
                    start_pt=self.start_pt,
                    end_pt=end_pt,
                    radius=self.radius,
                    crs=self.canvas.mapSettings().destinationCrs(),
                    create_edit_commands=True,
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
        self.delete_widget()
        super().deactivate()
