import os
from qgis.core import (
    Qgis,
    QgsSymbolLayer,
    QgsVectorLayer,
    QgsUnitTypes,
)
from qgis.gui import QgsSymbolLayerWidget
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtWidgets import QWidget

from ..gui_utils import GuiUtils
from topographic_mapping.core.symbol_layers.rock_outcrop import (
    RockOutcropMarkerSymbolLayer,
)

Ui_RockOutcropMarkerBaseWidget, _ = uic.loadUiType(
    GuiUtils.get_ui_file_path("widget_rock_outcrop_marker.ui")
)


class RockOutcropMarkerWidget(QgsSymbolLayerWidget, Ui_RockOutcropMarkerBaseWidget):
    """
    Configuration widget for RockOutcropMarkerSymbolLayer (QGIS 4 API).
    """

    @staticmethod
    def create(vector_layer: QgsVectorLayer):
        return RockOutcropMarkerWidget(vector_layer)

    def __init__(self, vector_layer: QgsVectorLayer, parent: QWidget = None):
        super().__init__(parent)
        self.setupUi(self)

        self._vector_layer: QgsVectorLayer | None = vector_layer
        self._layer: RockOutcropMarkerSymbolLayer | None = None

        valid_units = [
            Qgis.RenderUnit.Millimeters,
            Qgis.RenderUnit.MetersInMapUnits,
            Qgis.RenderUnit.MapUnits,
            Qgis.RenderUnit.Pixels,
            Qgis.RenderUnit.Points,
            Qgis.RenderUnit.Inches,
        ]
        self.mSizeUnitWidget.setUnits(valid_units)
        self.mOffsetUnitWidget.setUnits(valid_units)
        self.mStrokeWidthUnitWidget.setUnits(valid_units)

        self.variant_spin.setMinimum(1)
        self.variant_spin.setMaximum(3)
        self.variant_spin.setShowClearButton(False)
        self.variant_spin.valueChanged.connect(self._on_variant_changed)

        self.spinSize.valueChanged.connect(self._on_size_changed)
        self.mSizeUnitWidget.changed.connect(self._on_size_unit_changed)

        self.btnChangeColorStroke.colorChanged.connect(self._on_color_changed)
        self.spinAngle.valueChanged.connect(self._on_angle_changed)

        self.spinAngle.setClearValue(0)

        self.spinOffsetX.valueChanged.connect(self._on_offset_changed)
        self.spinOffsetY.valueChanged.connect(self._on_offset_changed)
        self.mOffsetUnitWidget.changed.connect(self._on_offset_unit_changed)

        self.mStrokeWidthSpinBox.valueChanged.connect(self._on_stroke_width_changed)
        self.mStrokeWidthUnitWidget.changed.connect(self._on_stroke_width_unit_changed)

    def setSymbolLayer(self, layer: QgsSymbolLayer):
        if not layer or not isinstance(layer, RockOutcropMarkerSymbolLayer):
            return

        self._layer = layer
        self._block_signals(True)

        self.spinSize.setValue(self._layer.size())
        self.mSizeUnitWidget.setUnit(self._layer.sizeUnit())
        self.mSizeUnitWidget.setMapUnitScale(self._layer.sizeMapUnitScale())

        self.btnChangeColorStroke.setColor(self._layer.color())
        self.spinAngle.setValue(self._layer.angle())

        self.spinOffsetX.setValue(self._layer.offset().x())
        self.spinOffsetY.setValue(self._layer.offset().y())
        self.mOffsetUnitWidget.setUnit(self._layer.offsetUnit())
        self.mOffsetUnitWidget.setMapUnitScale(self._layer.offsetMapUnitScale())

        self.mStrokeWidthSpinBox.setValue(self._layer.stroke_width())
        self.mStrokeWidthUnitWidget.setUnit(self._layer.stroke_width_unit())
        self.mStrokeWidthUnitWidget.setMapUnitScale(
            self._layer.stroke_width_map_unit_scale()
        )

        self.variant_spin.setValue(self._layer.variant())

        if False:
            # Register data-defined property override buttons using QGIS 4 scoped enums
            self.registerDataDefinedButton(
                self.mSizeDDBtn, QgsSymbolLayer.Property.Size
            )
            self.registerDataDefinedButton(
                self.mStrokeColorDDBtn, QgsSymbolLayer.Property.StrokeColor
            )
            self.registerDataDefinedButton(
                self.mAngleDDBtn, QgsSymbolLayer.Property.Angle
            )
            self.registerDataDefinedButton(
                self.mOffsetDDBtn, QgsSymbolLayer.Property.Offset
            )
            self.registerDataDefinedButton(
                self.mStrokeWidthDDBtn, QgsSymbolLayer.Property.StrokeWidth
            )

        self._block_signals(False)

    def symbolLayer(self) -> QgsSymbolLayer:
        return self._layer

    def _on_size_changed(self, value: float):
        if self._layer:
            self._layer.setSize(value)
            self.changed.emit()

    def _on_size_unit_changed(self):
        if self._layer:
            self._layer.setSizeUnit(self.mSizeUnitWidget.unit())
            self._layer.setSizeMapUnitScale(self.mSizeUnitWidget.getMapUnitScale())
            self.changed.emit()

    def _on_color_changed(self, color):
        if self._layer:
            self._layer.setColor(color)
            self.changed.emit()

    def _on_angle_changed(self, value: float):
        if self._layer:
            self._layer.setAngle(value)
            self._layer._angle = value
            self.changed.emit()

    def _on_offset_changed(self):
        if self._layer:
            self._layer.setOffset(
                QPointF(self.spinOffsetX.value(), self.spinOffsetY.value())
            )
            self.changed.emit()

    def _on_offset_unit_changed(self):
        if self._layer:
            self._layer.setOffsetUnit(self.mOffsetUnitWidget.unit())
            self._layer.setOffsetMapUnitScale(self.mOffsetUnitWidget.getMapUnitScale())
            self.changed.emit()

    def _on_stroke_width_changed(self, value: float):
        if self._layer:
            self._layer.set_stroke_width(value)
            self.changed.emit()

    def _on_stroke_width_unit_changed(self):
        if self._layer:
            self._layer.set_stroke_width_unit(self.mStrokeWidthUnitWidget.unit())
            self._layer.set_stroke_width_map_unit_scale(
                self.mStrokeWidthUnitWidget.getMapUnitScale()
            )
            self.changed.emit()

    def _on_variant_changed(self):
        if self._layer:
            self._layer.set_variant(self.variant_spin.value())
            self.changed.emit()

    def _block_signals(self, block: bool):
        self.spinSize.blockSignals(block)
        self.mSizeUnitWidget.blockSignals(block)
        self.btnChangeColorStroke.blockSignals(block)
        self.spinAngle.blockSignals(block)
        self.spinOffsetX.blockSignals(block)
        self.spinOffsetY.blockSignals(block)
        self.mOffsetUnitWidget.blockSignals(block)
        self.mStrokeWidthSpinBox.blockSignals(block)
        self.mStrokeWidthUnitWidget.blockSignals(block)
        self.variant_spin.blockSignals(block)
