from dataclasses import dataclass
import sys
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsGeometry,
    QgsLabelPosition,
    QgsPalLayerSettings,
    QgsVectorLayer,
)
from qgis.gui import (
    QgsAdvancedDigitizingDockWidget,
    QgsMapCanvas,
    QgsMapMouseEvent,
    QgsMapToolAdvancedDigitizing,
    QgsRubberBand,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QMouseEvent


class LabelDetails:
    """
    Encapsulates a label position and its associated vector layer and labeling settings.

    (Python port of the c++ QgsMapToolLabel class)
    """

    def __init__(
        self, pos: QgsLabelPosition | None = None, canvas: QgsMapCanvas | None = None
    ):

        self.pos: QgsLabelPosition | None = pos
        self.layer: QgsVectorLayer | None = None
        self.settings: QgsPalLayerSettings | None = None
        self.valid: bool = False

        if pos and canvas and pos.layerID:
            layer = canvas.layer(pos.layerID)
            if isinstance(layer, QgsVectorLayer):
                if layer.labelsEnabled():
                    self.layer = layer
                    if layer.labeling():
                        self.settings = layer.labeling().settings(pos.providerID)
                    self.valid = True


class MapToolLabel(QgsMapToolAdvancedDigitizing):
    """
    Python base class replicating QgsMapToolLabel C++ logic.

    Provides instant visual highlighting of hovered canvas labels and utility
    methods for querying and inspecting label positions.
    """

    def __init__(
        self,
        canvas: QgsMapCanvas,
        cad_dock: QgsAdvancedDigitizingDockWidget,
    ):
        super().__init__(canvas, cad_dock)
        self._canvas = canvas
        self._hover_rubber_band: QgsRubberBand | None = None

        self._current_label = LabelDetails()
        self._current_hover_label = LabelDetails()

    def deactivate(self) -> None:
        self.clear_hovered_label()
        super().deactivate()

    def canvasMoveEvent(self, e: QgsMapMouseEvent) -> None:
        self.update_hovered_label(e)
        super().canvasMoveEvent(e)

    def label_at_position(
        self, e: QgsMapMouseEvent
    ) -> tuple[bool, QgsLabelPosition | None]:
        """
        Finds the candidate label position at the given mouse event location.
        Filters non-vector layers and prioritizes active layers, unplaced labels, and smallest label bounds.
        """
        pt = e.mapPoint()
        labeling_results = self._canvas.labelingResults()
        if not labeling_results:
            return False, None

        label_pos_list = labeling_results.labelsAtPosition(pt)

        # filter out labels from non-vector layers
        filtered_list = []
        for pos in label_pos_list:
            if not pos.layerID:
                continue
            layer = self._canvas.layer(pos.layerID)
            if isinstance(layer, QgsVectorLayer):
                filtered_list.append(pos)

        if not filtered_list:
            return False, None

        # 2. Prioritize labels belonging to the active map canvas layer
        # TODO -- only labels from label layer
        active_layer = self._canvas.currentLayer()
        if isinstance(active_layer, QgsVectorLayer):
            active_labels = [p for p in filtered_list if p.layerID == active_layer.id()]
            if active_labels:
                filtered_list = active_labels

        # if multiple overlapping candidates remain, select the smallest area label
        if len(filtered_list) > 1:
            best_pos = min(
                filtered_list,
                key=lambda pos: (
                    pos.width * pos.height
                    if (pos.width * pos.height) > 0
                    else sys.float_info.max
                ),
            )
        else:
            best_pos = filtered_list[0]

        return True, best_pos

    def update_hovered_label(self, e: QgsMapMouseEvent):
        """
        Updates real-time hover feedback for labels under the cursor.
        """
        if not self._hover_rubber_band:
            self._hover_rubber_band = QgsRubberBand(
                self._canvas, Qgis.GeometryType.Polygon
            )
            self._hover_rubber_band.setWidth(2)
            self._hover_rubber_band.setSecondaryStrokeColor(QColor(255, 255, 255, 100))
            self._hover_rubber_band.setColor(QColor(200, 0, 120, 40))
            self._hover_rubber_band.setStrokeColor(QColor(200, 0, 120, 255))

        found, label_pos = self.label_at_position(e)
        if not found:
            self.clear_hovered_label()
            return

        new_hover_label = LabelDetails(label_pos, self._canvas)

        # Avoid redundant redraws if hovering the same feature label
        if (
            self._current_hover_label.valid
            and new_hover_label.layer == self._current_hover_label.layer
            and new_hover_label.pos.featureId == self._current_hover_label.pos.featureId
            and new_hover_label.pos.providerID
            == self._current_hover_label.pos.providerID
        ):
            return

        self._current_hover_label = new_hover_label

        self._hover_rubber_band.show()
        self._hover_rubber_band.reset(Qgis.GeometryType.Polygon)

        labeling_results = self._canvas.labelingResults()
        if labeling_results and label_pos.groupedLabelId != 0:
            all_positions = labeling_results.groupedLabelPositions(
                label_pos.groupedLabelId
            )
            geoms = [
                pos.labelGeometry
                for pos in all_positions
                if pos.labelGeometry and not pos.labelGeometry.isEmpty()
            ]

            if geoms:
                combined_geom = QgsGeometry.unaryUnion(geoms)
                hull_geom = combined_geom.concaveHullOfPolygons(0.2)
                self._hover_rubber_band.setToGeometry(hull_geom, None)
            else:
                self._hover_rubber_band.setToGeometry(label_pos.labelGeometry, None)
        else:
            self._hover_rubber_band.setToGeometry(label_pos.labelGeometry, None)

    def clear_hovered_label(self) -> None:
        """
        Hides the hover rubber band and clears hover state.
        """
        if self._hover_rubber_band:
            self._hover_rubber_band.hide()
        self._current_hover_label = LabelDetails()
