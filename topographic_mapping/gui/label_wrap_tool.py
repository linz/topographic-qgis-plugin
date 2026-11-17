"""
Interactive label re-wrap tool
"""

from enum import Enum, auto
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsRenderContext,
    QgsStringUtils,
    QgsTextDocument,
    QgsTextDocumentMetrics,
    QgsTextFormat,
    QgsVectorLayer,
    QgsMemoryProviderUtils,
)
from qgis.gui import (
    QgsMapCanvasItem,
    QgsMapCanvas,
    QgsMapMouseEvent,
    QgsAdvancedDigitizingDockWidget,
    QgsAlignmentComboBox,
    QgsDoubleSpinBox,
    QgsRubberBand,
)
from qgis.utils import iface

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QPointF, QRectF, Qt, pyqtSignal
from qgis.PyQt.QtGui import QBrush, QColor, QCursor, QImage, QKeyEvent, QPen, QPainter
from qgis.PyQt.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
)

from topographic_mapping.core import LabelManager, ProjectController
from .label_tool_base import MapToolLabel


class InteractionMode(Enum):
    NONE = auto()
    MOVING = auto()
    RESIZING_RIGHT = auto()


class LabelSelectionCanvasItem(QgsMapCanvasItem):
    """
    Canvas item rendering the selection box and horizontal resize handle
    directly from the rendered bounds of QgsVectorLayerLabelRubberBandPreview.
    """

    HANDLE_SIZE_PX = 8

    def __init__(self, canvas: QgsMapCanvas):
        super().__init__(canvas)
        self._canvas = canvas
        self._is_active = False
        self._rect = QRectF()

    def set_rendered_rect(self, canvas_rect: QRectF):
        """
        Sets the selection box rectangle in canvas pixel coordinates.
        """
        self.prepareGeometryChange()
        self._rect = canvas_rect.normalized()
        self._is_active = self._rect.isValid() and not self._rect.isEmpty()
        self.update()

    def hide_selection(self):
        """
        Hides the selection item.
        """
        self.prepareGeometryChange()
        self._is_active = False
        self._rect = QRectF()
        self.update()

    def boundingRect(self) -> QRectF:
        pad = self.HANDLE_SIZE_PX
        return self._rect.adjusted(-pad, -pad, pad, pad)

    def _right_handle_rect(self) -> QRectF:
        cy = self._rect.center().y()
        hs = self.HANDLE_SIZE_PX
        return QRectF(self._rect.right() - hs / 2, cy - hs / 2, hs, hs)

    def interaction_mode_for_point(self, screen_pos: QPointF) -> InteractionMode:
        """
        Returns the interaction mode for the given screen point.
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

        # horizontal resize handle
        handle_pen = QPen(QColor(0, 120, 215), 1.5)
        handle_brush = QBrush(QColor(255, 255, 255))
        painter.setPen(handle_pen)
        painter.setBrush(handle_brush)
        painter.drawRect(self._right_handle_rect())


class ReflowTextWidget(QWidget):
    alignment_changed = pyqtSignal(Qgis.TextHorizontalAlignment)
    line_height_changed = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Alignment"), 0, 0)

        self._alignment_combo = QgsAlignmentComboBox()
        layout.addWidget(self._alignment_combo, 0, 1)

        layout.addWidget(QLabel("Line height"), 1, 0)

        self._line_height_spin = QgsDoubleSpinBox()
        self._line_height_spin.setMinimum(0)
        self._line_height_spin.setMaximum(3)
        self._line_height_spin.setDecimals(2)
        self._line_height_spin.setSingleStep(0.1)
        self._line_height_spin.setClearValue(1)
        self._line_height_spin.setValue(1)
        layout.addWidget(self._line_height_spin, 1, 1)

        self._alignment_combo.changed.connect(self._on_alignment_changed)
        self._line_height_spin.valueChanged.connect(self.line_height_changed)

        self.setLayout(layout)

    def set_alignment(self, alignment: Qgis.TextHorizontalAlignment):
        self._alignment_combo.setCurrentAlignment(alignment)

    def _on_alignment_changed(self):
        self.alignment_changed.emit(self._alignment_combo.horizontalAlignment())

    def set_line_height(self, line_height: float):
        self._line_height_spin.setValue(line_height)


class RewrapLabelTool(MapToolLabel):
    """
    A map tool for selecting, moving, and horizontally wrapping canvas labels
    using an isolated in-memory layer and QgsVectorLayerLabelRubberBandPreview.
    """

    def __init__(
        self,
        canvas: QgsMapCanvas,
        cad_dock: QgsAdvancedDigitizingDockWidget,
        label_manager: LabelManager,
        project_controller: ProjectController,
    ):
        super().__init__(canvas, cad_dock)
        self._canvas: QgsMapCanvas = canvas
        self._label_manager: LabelManager = label_manager
        self._project_controller: ProjectController = project_controller

        self._selection_item = LabelSelectionCanvasItem(self._canvas)
        self._preview_rubber_band = QgsRubberBand(self._canvas, Qgis.GeometryType.Line)
        self._preview_rubber_band.setRenderedComponents(
            Qgis.RubberBandComponent.PreviewItems
        )
        self._preview_rubber_band.setIconSize(2)
        self._preview_rubber_band.setWidth(0)

        self._selected_feature: QgsFeature | None = None
        self._preview_layer: QgsVectorLayer | None = None
        self._preview_fid: int | None = None

        self._anchor_layer_pos: QgsPointXY = QgsPointXY()
        self._wrap_width_map_units: float = 0.0
        self._wrapped_text: str = ""
        self._mode: InteractionMode = InteractionMode.NONE

        self._drag_start_screen: QPointF = QPointF()
        self._drag_start_anchor: QgsPointXY = QgsPointXY()
        self._initial_width_map_units: float = 0.0

        self._horizontal_align: Qgis.TextHorizontalAlignment = (
            Qgis.TextHorizontalAlignment.Left
        )
        self._line_height: float = 1.0

        self._reflow_widget: ReflowTextWidget | None = None
        self._canvas.extentsChanged.connect(self._on_canvas_extents_changed)

    def create_widget(self):
        if not self._canvas:
            return

        self.delete_widget()
        self._reflow_widget = ReflowTextWidget()
        self._reflow_widget.set_alignment(self._horizontal_align)
        self._reflow_widget.set_line_height(self._line_height)
        iface.addUserInputWidget(self._reflow_widget)
        self._reflow_widget.setFocus(Qt.FocusReason.TabFocusReason)
        self._reflow_widget.alignment_changed.connect(self._on_alignment_changed)
        self._reflow_widget.line_height_changed.connect(self._on_line_height_changed)

    def delete_widget(self):
        if self._reflow_widget is not None and not sip.isdeleted(self._reflow_widget):
            self._reflow_widget.deleteLater()
            self._reflow_widget = None

    def _create_feature_render_context(
        self, feature: QgsFeature
    ) -> tuple[QgsRenderContext, QgsTextFormat]:
        """
        Builds a QgsRenderContext and resolved QgsTextFormat matching the
        layer reference scale and feature expression scope used during rendering.
        """
        rc = self._label_manager.create_render_context()
        label_layer = (
            self._preview_layer or self._project_controller.label_target_layer()
        )
        if label_layer:
            if label_layer.renderer():
                rc.setSymbologyReferenceScale(label_layer.renderer().referenceScale())
            rc.expressionContext().appendScope(
                label_layer.createExpressionContextScope()
            )

        if feature is not None:
            rc.expressionContext().setFeature(feature)
            rc.expressionContext().setFields(feature.fields())

        text_format = self._label_manager.get_text_format(feature, rc)
        text_format.updateDataDefinedProperties(rc)
        return rc, text_format

    def canvasPressEvent(self, e: QgsMapMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return

        screen_pos = QPointF(e.pos())
        self._mode = self._selection_item.interaction_mode_for_point(screen_pos)

        if self._mode != InteractionMode.NONE:
            self._drag_start_screen = screen_pos
            self._drag_start_anchor = QgsPointXY(self._anchor_layer_pos)
            self._initial_width_map_units = self._wrap_width_map_units

            if self._mode == InteractionMode.RESIZING_RIGHT:
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            elif self._mode == InteractionMode.MOVING:
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))

            self.create_widget()
            return

        self._select_label_at_pos(e.mapPoint())

    def canvasMoveEvent(self, e: QgsMapMouseEvent) -> None:
        screen_pos = QPointF(e.pos())

        if self._mode == InteractionMode.NONE:
            hover_mode = self._selection_item.interaction_mode_for_point(screen_pos)
            if hover_mode == InteractionMode.RESIZING_RIGHT:
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
                self.clear_hovered_label()
            elif hover_mode == InteractionMode.MOVING:
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
                self.clear_hovered_label()
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                super().canvasMoveEvent(e)
            return

        if not self._selected_feature or not self._preview_layer:
            return

        dx_pixels = screen_pos.x() - self._drag_start_screen.x()
        dx_map_units = dx_pixels * self._canvas.mapUnitsPerPixel()
        min_width_map_units = 20 * self._canvas.mapUnitsPerPixel()

        if self._mode == InteractionMode.RESIZING_RIGHT:
            rc, text_format = self._create_feature_render_context(
                self._selected_feature
            )
            new_width = max(
                min_width_map_units, self._initial_width_map_units + dx_map_units
            )
            self._wrap_width_map_units = new_width
            text, _ = self._label_manager.wrap_label_text(
                self._selected_feature, text_format, new_width, rc, self._line_height
            )
            self._update_label_preview(text)

        elif self._mode == InteractionMode.MOVING:
            start_layer_pt = self.toLayerCoordinates(
                self._preview_layer, self._drag_start_screen.toPoint()
            )
            curr_layer_pt = self.toLayerCoordinates(
                self._preview_layer, screen_pos.toPoint()
            )
            self._anchor_layer_pos = QgsPointXY(
                self._drag_start_anchor.x() + (curr_layer_pt.x() - start_layer_pt.x()),
                self._drag_start_anchor.y() + (curr_layer_pt.y() - start_layer_pt.y()),
            )
            self._update_label_preview(self._wrapped_text)

    def canvasReleaseEvent(self, e: QgsMapMouseEvent) -> None:
        if (
            e.button() == Qt.MouseButton.LeftButton
            and self._mode != InteractionMode.NONE
        ):
            self._mode = InteractionMode.NONE
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        elif e.button() == Qt.MouseButton.RightButton:
            if self._selected_feature:
                self._commit_label_changes()
                self._clear_selection()

    def _create_preview_layer(
        self, source_layer: QgsVectorLayer, source_feature: QgsFeature
    ) -> tuple[QgsVectorLayer | None, int | None]:
        """
        Creates a standalone in-memory QgsVectorLayer with a single copy of the
        feature and the source layer's labeling configuration.
        """
        preview_layer = QgsMemoryProviderUtils.createMemoryLayer(
            "label_preview",
            source_layer.fields(),
            source_layer.wkbType(),
            source_layer.crs(),
            False,
        )
        if not preview_layer or not preview_layer.isValid():
            return None, None

        for key in source_layer.customPropertyKeys():
            preview_layer.setCustomProperty(key, source_layer.customProperty(key))

        if source_layer.labeling():
            preview_layer.setLabeling(source_layer.labeling().clone())
        preview_layer.setLabelsEnabled(source_layer.labelsEnabled())

        if source_layer.renderer():
            preview_layer.setRenderer(source_layer.renderer().clone())

        temp_feat = QgsFeature(preview_layer.fields())
        temp_feat.setGeometry(QgsGeometry(source_feature.geometry()))
        temp_feat.setAttributes(source_feature.attributes())

        ok, added = preview_layer.dataProvider().addFeatures([temp_feat])
        if not ok or not added:
            return None, None

        return preview_layer, added[0].id()

    def _sync_rubber_band_bounds(self) -> None:
        """
        Updates the selection box directly from QgsRubberBand::boundingRect()
        after QgsVectorLayerLabelRubberBandPreview computes the rendered label bounds.
        """
        if self._selected_feature is None or self._preview_layer is None:
            return

        # need to do a render first, so that the bounds are calculated
        dpi = self._canvas.mapSettings().outputDpi()
        dpm = round(dpi / 0.0254)
        img = QImage(1, 1, QImage.Format.Format_ARGB32_Premultiplied)
        img.setDotsPerMeterX(dpm)
        img.setDotsPerMeterY(dpm)

        painter = QPainter(img)
        try:
            self._preview_rubber_band.paint(painter)
        finally:
            painter.end()

        rendered_rect = self._preview_rubber_band.boundingRect().translated(
            self._preview_rubber_band.pos()
        )
        self._selection_item.set_rendered_rect(rendered_rect)

    def _on_canvas_extents_changed(self) -> None:
        if self._selected_feature is not None and self._preview_layer is not None:
            self._sync_rubber_band_bounds()

    def _select_label_at_pos(self, click_map_point: QgsPointXY) -> None:
        """
        Sets the selected label by click and initializes its memory preview layer.
        """
        labeling_results = self._canvas.labelingResults()
        label_layer = self._project_controller.label_target_layer()

        if not labeling_results or not label_layer:
            self._clear_selection()
            return

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

        self._clear_selection()
        self.clear_hovered_label()

        # strip all existing line breaks and line-edge whitespace from original text
        text_val = feat.attribute("text_string")
        if text_val is not None:
            clean_text = " ".join(
                part.strip() for part in str(text_val).splitlines() if part.strip()
            )
            feat["text_string"] = clean_text

        preview_layer, preview_fid = self._create_preview_layer(label_layer, feat)
        if preview_layer is None or preview_fid is None:
            return

        self._selected_feature = feat
        self._preview_layer = preview_layer
        self._preview_fid = preview_fid

        feature_geom = feat.geometry()
        first_part_start = next(feature_geom.parts()).startPoint()
        self._anchor_layer_pos = QgsPointXY(
            feature_geom.boundingBox().xMinimum(),
            first_part_start.y(),
        )

        rc, text_format = self._create_feature_render_context(feat)
        unwrapped_text, size_map_units = self._label_manager.wrap_label_text(
            feat, text_format, None, rc, self._line_height
        )
        self._wrap_width_map_units = size_map_units.width()

        self._update_label_preview(unwrapped_text, force_refresh=True)
        self.create_widget()

    def _build_label_geometry(self, wrapped_text: str) -> QgsGeometry:
        """
        Builds the MultiLineString baseline geometry shared identically by both
        the preview rubber band and the final layer commit.
        """
        rc, text_format = self._create_feature_render_context(self._selected_feature)
        text_format.setLineHeight(text_format.lineHeight() * self._line_height)
        cap = text_format.capitalization()

        raw_lines = wrapped_text.split("\n") if wrapped_text else [""]
        display_lines = [QgsStringUtils.capitalize(line, cap) for line in raw_lines]

        doc = QgsTextDocument.fromTextAndFormat(display_lines, text_format)
        metrics = QgsTextDocumentMetrics.calculateMetrics(doc, text_format, rc)
        doc_size_px = metrics.documentSize(
            Qgis.TextLayoutMode.Labeling, Qgis.TextOrientation.Horizontal
        )
        total_height_map = rc.convertToMapUnits(
            doc_size_px.height(), Qgis.RenderUnit.Pixels
        )
        max_width_map = rc.convertToMapUnits(
            doc_size_px.width(), Qgis.RenderUnit.Pixels
        )
        line_height_map = (
            total_height_map / len(display_lines) if display_lines else 0.0
        )

        polylines = []
        for i, line_text in enumerate(display_lines):
            line_doc = QgsTextDocument.fromTextAndFormat([line_text], text_format)
            line_metrics = QgsTextDocumentMetrics.calculateMetrics(
                line_doc, text_format, rc
            )
            line_width_px = line_metrics.documentSize(
                Qgis.TextLayoutMode.Labeling, Qgis.TextOrientation.Horizontal
            ).width()
            line_width_map = max(
                rc.convertToMapUnits(line_width_px, Qgis.RenderUnit.Pixels),
                1e-6,
            )

            if self._horizontal_align == Qgis.TextHorizontalAlignment.Center:
                line_x = (
                    self._anchor_layer_pos.x() + (max_width_map - line_width_map) / 2
                )
            elif self._horizontal_align == Qgis.TextHorizontalAlignment.Right:
                line_x = self._anchor_layer_pos.x() + (max_width_map - line_width_map)
            else:
                line_x = self._anchor_layer_pos.x()

            line_y = self._anchor_layer_pos.y() - (i * line_height_map)
            polylines.append(
                [
                    QgsPointXY(line_x, line_y),
                    QgsPointXY(line_x + line_width_map, line_y),
                ]
            )

        return QgsGeometry.fromMultiPolylineXY(polylines)

    def _update_label_preview(
        self,
        wrapped_text: str,
        force_refresh: bool = False,
    ) -> None:
        if (
            not self._selected_feature
            or self._preview_layer is None
            or self._preview_fid is None
        ):
            return

        new_geom = self._build_label_geometry(wrapped_text)
        text_changed = wrapped_text != self._wrapped_text
        self._wrapped_text = wrapped_text

        if text_changed or force_refresh:
            field_idx = self._preview_layer.fields().indexOf("text_string")
            if field_idx != -1:
                self._preview_layer.dataProvider().changeAttributeValues(
                    {self._preview_fid: {field_idx: wrapped_text}}
                )

            self._preview_rubber_band.clearPreviewItems()
            self.prepareRubberBandForLayer(
                self._preview_rubber_band,
                self._preview_layer,
                [self._preview_fid],
            )

        self._preview_rubber_band.setToGeometry(new_geom, self._preview_layer)
        self._sync_rubber_band_bounds()

    def _commit_label_changes(self) -> None:
        """
        Writes updated position geometry and wrapped text to the target label layer.
        """
        label_layer = self._project_controller.label_target_layer()
        if not label_layer or not self._selected_feature:
            return

        if not label_layer.isEditable():
            label_layer.startEditing()

        final_geom = self._build_label_geometry(self._wrapped_text)

        label_layer.beginEditCommand("Modify label placement and wrapping")

        field_idx = label_layer.fields().indexOf("text_string")
        if field_idx != -1:
            label_layer.changeAttributeValue(
                self._selected_feature.id(), field_idx, self._wrapped_text
            )

        label_layer.changeGeometry(self._selected_feature.id(), final_geom)
        label_layer.endEditCommand()
        self._canvas.refresh()

    def _clear_selection(self):
        """
        Clears the current label selection and releases the temporary preview layer.
        """
        self._selected_feature = None
        self._wrapped_text = ""
        self._wrap_width_map_units = 0.0
        self._mode = InteractionMode.NONE
        self._selection_item.hide_selection()
        self._preview_rubber_band.clearPreviewItems()
        self._preview_rubber_band.reset(Qgis.GeometryType.Line)
        self._preview_layer = None
        self._preview_fid = None
        self.delete_widget()

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

    def _on_alignment_changed(self, alignment: Qgis.TextHorizontalAlignment):
        self._horizontal_align = alignment
        if self._selected_feature is not None:
            self._update_label_preview(self._wrapped_text)

    def _on_line_height_changed(self, line_height: float):
        self._line_height = line_height
        if self._selected_feature is not None:
            rc, text_format = self._create_feature_render_context(
                self._selected_feature
            )
            text, _ = self._label_manager.wrap_label_text(
                self._selected_feature,
                text_format,
                self._wrap_width_map_units,
                rc,
                self._line_height,
            )
            self._update_label_preview(text, force_refresh=True)
