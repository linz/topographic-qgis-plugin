import math
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsMarkerSymbolLayer,
    QgsSymbol,
    QgsSymbolLayerAbstractMetadata,
    QgsGeometryUtilsBase,
    QgsVector,
)
from qgis.PyQt.QtCore import QPointF, QRectF
from qgis.PyQt.QtGui import QBrush, QColor, QPen, QPolygonF


class RockOutcropMarkerSymbolLayer(QgsMarkerSymbolLayer):
    """
    Custom marker symbol layer for rock outcrop symbol
    """

    # Normalized coordinates relative to top-left for a reference size of 2
    RAW_POLYLINE_POINTS_V1 = (
        (
            (0.642, 1.567),
            (0.699, 0.980),
            (0.755, 0.603),
            (0.759, 0.561),
            (0.824, 0.393),
            (1.110, 0.351),
            (1.304, 0.309),
            (1.330, 0.561),
            (1.404, 1.190),
            (1.464, 1.567),
        ),
    )
    RAW_POLYLINE_POINTS_V2 = (
        (
            (0.496, 1.567),
            (0.542, 1.053),
            (0.593, 0.824),
            (0.916, 0.824),
            (0.965, 1.110),
            (1.060, 1.567),
        ),
        (
            (0.916, 0.824),
            (0.971, 0.509),
            (1.240, 0.481),
            (1.306, 0.881),
            (1.380, 1.225),
            (1.489, 1.568),
        ),
    )

    RAW_POLYLINE_POINTS_V3 = (
        (
            (0.401, 1.567),
            (0.455, 1.023),
            (0.517, 0.882),
            (0.795, 0.858),
            (0.923, 1.567),
        ),
        (
            (0.795, 0.858),
            (0.852, 0.457),
            (1.111, 0.480),
            (1.232, 1.567),
        ),
        (
            (1.140, 0.740),
            (1.534, 0.740),
            (1.550, 0.952),
            (1.597, 1.330),
            (1.675, 1.567),
        ),
    )

    def __init__(self, size=4.0, color=QColor(255, 0, 0), angle: float = 0.0):
        super().__init__()
        self._size = size
        self._color = color
        self._angle = -15  # angle
        self._variant = 3

    def layerType(self) -> str:
        return "RockOutcropMarker"

    def properties(self) -> dict:
        return {"size": self._size, "color": self._color.name(), "angle": self._angle}

    def clone(self) -> "RockOutcropMarkerSymbolLayer":
        cloned = RockOutcropMarkerSymbolLayer(
            self._size, QColor(self._color), self._angle
        )
        self.copyDataDefinedProperties(cloned)
        self.copyPaintEffect(cloned)
        return cloned

    def startRender(self, context):
        super().startRender(context)

    def stopRender(self, context):
        super().stopRender(context)

    def renderPoint(self, point: QPointF, context):
        painter = context.renderContext().painter()
        if not painter:
            return

        # Convert symbol size to painter units (pixels)
        scaled_size = context.renderContext().convertToPainterUnits(
            self._size, self.sizeUnit()
        )

        painter.save()

        pen = QPen(self._color)
        pen.setWidthF(1.0)
        painter.setPen(pen)

        half_width = scaled_size / 2.0
        y_offset = 0.567 * half_width

        # Pivot point (center of the horizontal baseline)
        pivot_x = point.x()
        pivot_y = point.y() + y_offset

        # Rotation matrix parameters (clockwise in Qt screen coordinates)
        rad = math.radians(self._angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        # Draw rotated baseline
        p1_x = pivot_x - (half_width * cos_a)
        p1_y = pivot_y - (half_width * sin_a)
        p2_x = pivot_x + (half_width * cos_a)
        p2_y = pivot_y + (half_width * sin_a)
        painter.drawLine(QPointF(p1_x, p1_y), QPointF(p2_x, p2_y))

        normalized_angle = (self._angle + 360) % 360
        needs_horizontal_mirror = 0 < normalized_angle < 90

        if self._variant == 1:
            raw_points = self.RAW_POLYLINE_POINTS_V1
        elif self._variant == 2:
            raw_points = self.RAW_POLYLINE_POINTS_V2
        else:
            raw_points = self.RAW_POLYLINE_POINTS_V3

        for ring_index, raw_point_ring in enumerate(raw_points):
            polyline_points = []
            for x_ref, y_ref in raw_point_ring:
                rx = (x_ref - 1.0) * half_width
                ry = (y_ref - 1.0) * half_width - y_offset

                if needs_horizontal_mirror:
                    rx = -rx

                polyline_points.append(QPointF(pivot_x + rx, pivot_y + ry))

            vert_shift_start = True
            vert_shift_end = True
            if ring_index > 0:
                vert_shift_start = False

            if vert_shift_start:
                # shift first and last point vertically to sit on the baseline
                _, intersection_x, intersection_y = (
                    QgsGeometryUtilsBase.lineIntersection(
                        p1_x,
                        p1_y,
                        QgsVector(p2_x - p1_x, p2_y - p1_y),
                        polyline_points[0].x(),
                        0,
                        QgsVector(0, 1),
                    )
                )
                vertical_shift = intersection_y - polyline_points[0].y()
                polyline_points[0] = QPointF(intersection_x, intersection_y)
                polyline_points[1] = QPointF(
                    polyline_points[1].x(), polyline_points[1].y() + vertical_shift / 2
                )

            if vert_shift_end:
                _, intersection_x, intersection_y = (
                    QgsGeometryUtilsBase.lineIntersection(
                        p1_x,
                        p1_y,
                        QgsVector(p2_x - p1_x, p2_y - p1_y),
                        polyline_points[-1].x(),
                        0,
                        QgsVector(0, 1),
                    )
                )
                vertical_shift = intersection_y - polyline_points[-1].y()
                polyline_points[-1] = QPointF(intersection_x, intersection_y)
                polyline_points[-2] = QPointF(
                    polyline_points[-2].x(),
                    polyline_points[-2].y() + vertical_shift / 2,
                )

            painter.drawPolyline(QPolygonF(polyline_points))

        painter.restore()


class RockOutcropMarkerMetadata(QgsSymbolLayerAbstractMetadata):
    def __init__(self):
        super().__init__("RockOutcropMarker", "Rock Outcrop", Qgis.SymbolType.Marker)

    def createSymbolLayer(self, props: dict) -> RockOutcropMarkerSymbolLayer:
        color = QColor(props.get("color", "#FF0000"))
        return RockOutcropMarkerSymbolLayer(
            size=float(props.get("size", 4.0)),
            color=color,
            angle=float(props.get("angle", 0)),
        )

    def createSymbolLayerWidget(self, layer):
        return None
