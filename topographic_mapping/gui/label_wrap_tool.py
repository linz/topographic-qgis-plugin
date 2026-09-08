"""
Interactive label re-wrap tool
"""

from enum import Enum, auto
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsVector,
    QgsTextFormat,
    QgsRenderContext,
    QgsTextDocument,
    QgsTextDocumentMetrics,
    QgsTextRenderer,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvasItem, QgsMapCanvas, QgsMapMouseEvent, QgsMapTool
from qgis.PyQt.QtCore import QPointF, QRectF, QSizeF, Qt
from qgis.PyQt.QtGui import QBrush, QColor, QCursor, QKeyEvent, QPen, QPainter

from topographic_mapping.core import LabelManager, ProjectController


class InteractionMode(Enum):
    NONE = auto()
    MOVING = auto()
    RESIZING_RIGHT = auto()


class LabelSelectionCanvasItem(QgsMapCanvasItem):
    """
    Canvas item rendering the selection box, horizontal resize handles, and label preview.
    """

    HANDLE_SIZE_PX = 8

    def __init__(self, canvas: QgsMapCanvas):
        super().__init__(canvas)
        self._canvas = canvas
        self._map_pos = QgsPointXY(0, 0)
        self._map_unit_size: QSizeF = QSizeF()
        self._wrapped_text = ""
        self._text_format: QgsTextFormat | None = None
        self._layer: QgsVectorLayer | None = None
        self._is_active = False
        self._rect = QRectF()

        self._canvas.extentsChanged.connect(self._update_position)

    def set_label_state(
        self,
        map_pos: QgsPointXY,
        text: str,
        map_unit_size: QSizeF,
        text_format: QgsTextFormat,
        layer: QgsVectorLayer,
    ):
        """
        Sets the current label state and associated properties
        """
        self._map_pos = map_pos
        self._wrapped_text = text
        self._map_unit_size = map_unit_size
        self._text_format = text_format
        self._layer = layer
        self._is_active = True
        self._update_position()

    def hide_selection(self):
        """
        Hides the selection item
        """
        self._is_active = False
        self.update()

    def _update_position(self):
        if not self._is_active:
            return
        self.prepareGeometryChange()
        top_left_screen = self.toCanvasCoordinates(self._map_pos)

        bottom_right_map = self._map_pos + QgsVector(
            self._map_unit_size.width(), -self._map_unit_size.height()
        )
        bottom_right_screen = self.toCanvasCoordinates(bottom_right_map)

        self._rect = QRectF(top_left_screen, bottom_right_screen).normalized()
        self.update()

    def map_position(self) -> QgsPointXY:
        """
        Returns the current map position of the item
        """
        return self._map_pos

    def map_unit_width(self) -> float:
        """
        Returns the current item width (in map units)
        """
        return self._map_unit_size.width()

    def boundingRect(self) -> QRectF:
        pad = self.HANDLE_SIZE_PX
        return self._rect.adjusted(-pad, -pad, pad, pad)

    def _right_handle_rect(self) -> QRectF:
        cy = self._rect.center().y()
        hs = self.HANDLE_SIZE_PX
        return QRectF(self._rect.right() - hs / 2, cy - hs / 2, hs, hs)

    def interaction_mode_for_point(self, screen_pos: QPointF) -> InteractionMode:
        """
        Returns the interaction mode for the given screen point
        """
        if not self._is_active:
            return InteractionMode.NONE
        if self._right_handle_rect().contains(screen_pos):
            return InteractionMode.RESIZING_RIGHT
        if self._rect.contains(screen_pos):
            return InteractionMode.MOVING
        return InteractionMode.NONE

    def paint(self, painter: QPainter | None, option, widget=None):
        if not self._is_active or not painter:
            return

        # selection box rectangle
        box_pen = QPen(QColor(0, 120, 215), 1.5, Qt.PenStyle.DashLine)
        box_brush = QBrush(QColor(0, 120, 215, 25))
        painter.setPen(box_pen)
        painter.setBrush(box_brush)
        painter.drawRect(self._rect)

        # label preview text
        if self._text_format and self._wrapped_text and self._layer:
            rc = QgsRenderContext.fromMapSettings(self._canvas.mapSettings())
            rc.setPainter(painter)
            if self._layer.renderer():
                rc.setSymbologyReferenceScale(self._layer.renderer().referenceScale())

            lines = self._wrapped_text.split("\n")
            document = QgsTextDocument.fromTextAndFormat(lines, self._text_format)
            metrics = QgsTextDocumentMetrics.calculateMetrics(
                document, self._text_format, rc
            )

            QgsTextRenderer.drawDocument(
                self._rect,
                self._text_format,
                document,
                metrics,
                rc,
                Qgis.TextHorizontalAlignment.Left,
                Qgis.TextVerticalAlignment.Top,
            )

        # horizontal resize handles
        handle_pen = QPen(QColor(0, 120, 215), 1.5)
        handle_brush = QBrush(QColor(255, 255, 255))
        painter.setPen(handle_pen)
        painter.setBrush(handle_brush)

        painter.drawRect(self._right_handle_rect())


class RewrapLabelTool(QgsMapTool):
    """
    A map tool for selecting, moving, and horizontally wrapping canvas labels.
    """

    def __init__(
        self,
        canvas: QgsMapCanvas,
        label_manager: LabelManager,
        project_controller: ProjectController,
    ):
        super().__init__(canvas)
        self._canvas: QgsMapCanvas = canvas
        self._label_manager: LabelManager = label_manager
        self._project_controller: ProjectController = project_controller

        self._selection_item: LabelSelectionCanvasItem = LabelSelectionCanvasItem(
            self._canvas
        )
        self._selected_feature: QgsFeature | None = None
        self._move_delta_map_units = 0
        self._mode: InteractionMode = InteractionMode.NONE

        self._drag_start_screen: QPointF = QPointF()
        self._drag_start_map: QgsPointXY = QgsPointXY()
        self._initial_width_map_units: float = 0.0

    def canvasPressEvent(self, e: QgsMapMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return

        screen_pos = QPointF(e.pos())
        self._mode = self._selection_item.interaction_mode_for_point(screen_pos)

        if self._mode != InteractionMode.NONE:
            # handle dragging existing selection
            self._drag_start_screen = screen_pos
            self._drag_start_map = self._selection_item.map_position()
            self._initial_width_map_units = self._selection_item.map_unit_width()

            if self._mode == InteractionMode.RESIZING_RIGHT:
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            elif self._mode == InteractionMode.MOVING:
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            return

        # default to selecting labels at click location
        self._select_label_at_pos(e.mapPoint())

    def canvasMoveEvent(self, e: QgsMapMouseEvent) -> None:
        screen_pos = QPointF(e.pos())

        if self._mode == InteractionMode.NONE:
            # change cursor when hovering over handles/box
            hover_mode = self._selection_item.interaction_mode_for_point(screen_pos)
            if hover_mode == InteractionMode.RESIZING_RIGHT:
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            elif hover_mode == InteractionMode.MOVING:
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return

        dx_pixels = screen_pos.x() - self._drag_start_screen.x()
        dx_map_units = dx_pixels * self._canvas.mapUnitsPerPixel()
        # no smaller than 20 pixels
        min_width_map_units = 20 * self._canvas.mapUnitsPerPixel()

        rc = self._label_manager.create_render_context()
        text_format = self._label_manager.get_text_format(self._selected_feature, rc)

        if self._mode == InteractionMode.RESIZING_RIGHT:
            new_width = max(
                min_width_map_units, self._initial_width_map_units + dx_map_units
            )

            text, size = self._label_manager.wrap_label_text(
                self._selected_feature, text_format, new_width, rc
            )
            self._selection_item.set_label_state(
                self._drag_start_map,
                text,
                size,
                text_format,
                self._project_controller.label_target_layer(),
            )

        elif self._mode == InteractionMode.MOVING:
            dy_pixels = screen_pos.y() - self._drag_start_screen.y()
            new_map_pos = QgsPointXY(
                self._drag_start_map.x() + dx_map_units,
                self._drag_start_map.y()
                - (dy_pixels * self._canvas.mapUnitsPerPixel()),
            )
            text, size = self._label_manager.wrap_label_text(
                self._selected_feature,
                text_format,
                self._selection_item.map_unit_width(),
                rc,
            )
            self._selection_item.set_label_state(
                new_map_pos,
                text,
                size,
                text_format,
                self._project_controller.label_target_layer(),
            )

    def canvasReleaseEvent(self, e: QgsMapMouseEvent) -> None:
        if (
            e.button() == Qt.MouseButton.LeftButton
            and self._mode != InteractionMode.NONE
        ):
            self._mode = InteractionMode.NONE
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        elif e.button() == Qt.MouseButton.RightButton:
            # right-click commits edits and completes operation
            if self._selected_feature:
                self._commit_label_changes()
                self._clear_selection()

    def _select_label_at_pos(self, click_map_point: QgsPointXY) -> None:
        """
        Sets the selected label by click
        """
        labeling_results = self._canvas.labelingResults()
        label_layer = self._project_controller.label_target_layer()

        if not labeling_results or not label_layer:
            self._clear_selection()
            return

        # find carto text labels at clicked point
        label_positions = labeling_results.labelsAtPosition(click_map_point)
        matching_pos = next(
            (p for p in label_positions if p.layerID == label_layer.id()), None
        )
        if not matching_pos:
            self._clear_selection()
            return

        feat = label_layer.getFeature(matching_pos.featureId)
        if not feat.isValid() or not feat.geometry() or feat.geometry().isEmpty():
            self._clear_selection()
            return

        # strip all existing line breaks from original text
        text_val = feat.attribute("text_string")
        if text_val is not None:
            clean_text = " ".join(str(text_val).splitlines())
            feat["text_string"] = clean_text

        # collect all rendered label positions for this feature
        feature_labels = [
            label
            for label in labeling_results.allLabels()
            if label.featureId == matching_pos.featureId
            and label.layerID == label_layer.id()
        ]
        if not feature_labels:
            self._clear_selection()
            return

        first_label_parts = [l for l in feature_labels if l.subPartId == 0]
        first_label = min(
            first_label_parts,
            key=lambda lbl: lbl.groupedPositionIndex,
        )
        first_cp = first_label.cornerPoints
        top_left_pt = first_cp[3]
        bottom_left_pt = first_cp[0]

        self._selected_feature = feat
        initial_label_pos = QgsPointXY(top_left_pt.x(), top_left_pt.y())
        feature_geom = feat.geometry()
        for part in feature_geom.parts():
            initial_feature_start_pt = part.startPoint()
            break

        self._move_delta_map_units = bottom_left_pt.distance(
            QgsPointXY(initial_feature_start_pt)
        )

        rc = self._label_manager.create_render_context()

        # start off with the horizontal, single-line version of the label
        text_format = self._label_manager.get_text_format(feat, rc)
        unwrapped_text, size_map_units = self._label_manager.wrap_label_text(
            feat, text_format, None, rc
        )

        self._selection_item.set_label_state(
            initial_label_pos,
            unwrapped_text,
            size_map_units,
            text_format,
            label_layer,
        )

    def _commit_label_changes(self) -> None:
        """
        Writes updated position geometry and wrapped text to the target label layer.
        """
        label_layer = self._project_controller.label_target_layer()
        if not label_layer or not self._selected_feature:
            return

        if not label_layer.isEditable():
            label_layer.startEditing()

        rc = self._label_manager.create_render_context()
        text_format = self._label_manager.get_text_format(self._selected_feature, rc)

        current_map_pos = self._selection_item.map_position()
        current_map_pos.setY(current_map_pos.y() - self._move_delta_map_units)

        wrapped_text = self._selection_item._wrapped_text
        lines = [line for line in wrapped_text.split("\n")] if wrapped_text else [""]

        doc = QgsTextDocument.fromTextAndFormat(lines, text_format)
        metrics = QgsTextDocumentMetrics.calculateMetrics(doc, text_format, rc)
        doc_size_px = metrics.documentSize(
            Qgis.TextLayoutMode.Labeling, Qgis.TextOrientation.Horizontal
        )
        total_height_map = rc.convertToMapUnits(
            doc_size_px.height(), Qgis.RenderUnit.Pixels
        )
        num_lines = len(lines)
        line_height_map = total_height_map / num_lines if num_lines > 0 else 0.0

        polylines = []
        for i, line_text in enumerate(lines):
            line_doc = QgsTextDocument.fromTextAndFormat([line_text], text_format)
            line_metrics = QgsTextDocumentMetrics.calculateMetrics(
                line_doc, text_format, rc
            )
            line_width_px = line_metrics.documentSize(
                Qgis.TextLayoutMode.Labeling, Qgis.TextOrientation.Horizontal
            ).width()
            line_width_map = rc.convertToMapUnits(line_width_px, Qgis.RenderUnit.Pixels)

            line_x = current_map_pos.x()
            line_y = current_map_pos.y() - ((i + 1) * line_height_map)

            pt_start = QgsPointXY(line_x, line_y)
            pt_end = QgsPointXY(line_x + line_width_map, line_y)
            polylines.append([pt_start, pt_end])

        new_geom = QgsGeometry.fromMultiPolylineXY(polylines)

        label_layer.beginEditCommand("Modify label placement and wrapping")

        field_idx = label_layer.fields().indexOf("text_string")
        if field_idx != -1:
            label_layer.changeAttributeValue(
                self._selected_feature.id(), field_idx, wrapped_text
            )

        label_layer.changeGeometry(self._selected_feature.id(), new_geom)
        label_layer.endEditCommand()
        self._canvas.refresh()

    def _clear_selection(self):
        """
        Clears the current label selection
        """
        self._selected_feature = None
        self._mode = InteractionMode.NONE
        self._selection_item.hide_selection()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._selected_feature:
                self._commit_label_changes()
                self._clear_selection()
            return
        elif e.key() == Qt.Key.Key_Escape:
            self._clear_selection()
            return
        super().keyPressEvent(e)

    def deactivate(self) -> None:
        self._clear_selection()
        super().deactivate()
