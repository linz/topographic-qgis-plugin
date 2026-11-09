"""
Interactive label move tool
"""

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QPoint, Qt
from qgis.PyQt.QtGui import QCursor, QKeyEvent

from qgis.core import (
    Qgis,
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsLabelPosition,
    QgsPointXY,
    QgsVectorLayer,
    QgsCsException,
)
from qgis.gui import (
    QgsAdvancedDigitizingDockWidget,
    QgsMapCanvas,
    QgsMapMouseEvent,
    QgsMapToolAdvancedDigitizing,
    QgsRubberBand,
)
from topographic_mapping.core import LabelManager, ProjectController
from .label_tool_base import MapToolLabel


class MoveLabelTool(MapToolLabel):
    """
    A map tool for interactively moving labels
    """

    def __init__(
        self,
        canvas: QgsMapCanvas,
        cad_dock: QgsAdvancedDigitizingDockWidget,
        label_manager: LabelManager | None = None,
        project_controller: ProjectController | None = None,
    ):
        super().__init__(canvas, cad_dock)
        self._canvas: QgsMapCanvas = canvas
        self._label_manager: LabelManager | None = label_manager
        self._project_controller: ProjectController | None = project_controller

        self._is_moving: bool = False
        self._label_layer: QgsVectorLayer | None = None
        self._target_feature_id: int | None = None
        self._original_geometry: QgsGeometry | None = None
        self._current_geometry: QgsGeometry | None = None
        self._start_map_point: QgsPointXY | None = None

        self._press_pos: QPoint | None = None

        self._preview_rubber_band: QgsRubberBand | None = None

    def canvasPressEvent(self, e: QgsMapMouseEvent) -> None:
        if e.button() == Qt.MouseButton.RightButton:
            if self._is_moving:
                self._cancel_move()
            return

        if e.button() == Qt.MouseButton.LeftButton:
            if self._is_moving:
                self._finalize_move(e.mapPoint())
            else:
                self._press_pos = e.pos()
                found, label_pos = self.label_at_position(e)
                if found and label_pos:
                    self._start_move(label_pos, e.mapPoint())
            return

    def canvasMoveEvent(self, e: QgsMapMouseEvent) -> None:
        if self._is_moving:
            self._current_geometry = self._calculate_translated_geometry(e.mapPoint())
            if self._preview_rubber_band and self._label_layer:
                self._preview_rubber_band.setToGeometry(
                    self._current_geometry, self._label_layer.crs()
                )
            QgsMapToolAdvancedDigitizing.canvasMoveEvent(self, e)
        else:
            super().canvasMoveEvent(e)
            if self._hover_rubber_band.isVisible():
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            if self._is_moving:
                self._cancel_move()
                return
        super().keyPressEvent(e)

    def deactivate(self) -> None:
        self._cancel_move()
        super().deactivate()

    def _start_move(self, label_pos: QgsLabelPosition, start_point: QgsPointXY) -> None:
        if not label_pos or not label_pos.layerID or not self._project_controller:
            return

        layer = self._project_controller.label_target_layer()
        if not layer:
            return

        feat: QgsFeature = layer.getFeature(label_pos.featureId)
        if not feat.isValid() or not feat.geometry() or feat.geometry().isEmpty():
            return

        self._is_moving = True
        self._label_layer = layer
        self._target_feature_id = feat.id()
        self._original_geometry = QgsGeometry(feat.geometry())
        self._current_geometry = QgsGeometry(self._original_geometry)
        self._start_map_point = QgsPointXY(start_point)

        self.clear_hovered_label()

        self._cleanup_preview()
        self._preview_rubber_band = self.createRubberBandForLayer(
            self._label_layer, {self._target_feature_id}
        )
        self._preview_rubber_band.setRenderedComponents(
            Qgis.RubberBandComponent.PreviewItems
        )
        self._preview_rubber_band.setToGeometry(
            self._original_geometry, self._label_layer.crs()
        )
        self._preview_rubber_band.show()

        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def _calculate_translated_geometry(self, current_map_pt: QgsPointXY) -> QgsGeometry:
        if (
            not self._label_layer
            or not self._start_map_point
            or not self._original_geometry
        ):
            return QgsGeometry()

        try:
            ct = QgsCoordinateTransform(
                self._canvas.mapSettings().destinationCrs(),
                self._label_layer.crs(),
                self._canvas.mapSettings().transformContext(),
            )
            start_layer_pt = ct.transform(self._start_map_point)
            current_layer_pt = ct.transform(current_map_pt)
            dx = current_layer_pt.x() - start_layer_pt.x()
            dy = current_layer_pt.y() - start_layer_pt.y()
        except QgsCsException:
            dx = current_map_pt.x() - self._start_map_point.x()
            dy = current_map_pt.y() - self._start_map_point.y()

        new_geom = QgsGeometry(self._original_geometry)
        new_geom.translate(dx, dy)
        return new_geom

    def _finalize_move(self, end_map_point: QgsPointXY) -> None:
        if (
            not self._is_moving
            or not self._label_layer
            or self._target_feature_id is None
            or self._original_geometry is None
        ):
            self._cancel_move()
            return

        final_geom = self._calculate_translated_geometry(end_map_point)
        target_layer = self._label_layer
        feature_id = self._target_feature_id

        # cleanup
        self._cancel_move()

        if not target_layer.isEditable():
            if not target_layer.startEditing():
                return

        target_layer.beginEditCommand("Move label")
        target_layer.changeGeometry(feature_id, final_geom)
        target_layer.endEditCommand()

    def _cancel_move(self) -> None:
        self._cleanup_preview()
        self._is_moving = False
        self._label_layer = None
        self._target_feature_id = None
        self._original_geometry = None
        self._current_geometry = None
        self._start_map_point = None
        self._press_pos = None
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def _cleanup_preview(self) -> None:
        if self._preview_rubber_band:
            sip.delete(self._preview_rubber_band)
            self._preview_rubber_band = None
