"""
A point rubber band transformation
"""

from typing import List
from qgis.core import (
    QgsAbstractGeometryTransformer,
    QgsPointXY,
    QgsVector,
    QgsVectorLayer,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsCsException,
    QgsGeometry,
    QgsLineString,
    QgsFeatureRequest,
)

from .geometry_utils import GeometryUtils


class PointRubberBandTransform(QgsAbstractGeometryTransformer):
    def __init__(self, start: QgsPointXY, end: QgsPointXY, layer_radius):
        super().__init__()
        self.geometry_changed = False

        self.layer_start: QgsPointXY = start
        self.transform_vector: QgsVector = end - self.layer_start
        self.stroke_dist: float = self.transform_vector.length()

        if self.stroke_dist > 0:
            self.unit_dir: QgsVector = self.transform_vector.normalized()
        else:
            self.unit_dir = QgsVector(0.0, 0.0)

        self.layer_radius = layer_radius

        self.forward_fade_dist: float = max(self.layer_radius, 2.0 * self.stroke_dist)

    @staticmethod
    def smoother_step(t: float) -> float:
        """Quintic polynomial C2-continuous falloff."""
        if t <= 0.0:
            return 1.0
        if t >= 1.0:
            return 0.0
        return 1.0 - t * t * t * (t * (t * 6.0 - 15.0) + 10.0)

    def transformPoint(self, x: float, y: float, z: float, m: float):
        if self.stroke_dist == 0 or self.layer_radius <= 0:
            return True, x, y, z, m

        this_point = QgsPointXY(x, y)
        vector_to_this_point: QgsVector = this_point - self.layer_start

        projection_along_stroke: float = vector_to_this_point * self.unit_dir

        # nothing behind the start point is impacted
        if projection_along_stroke < 0:
            return True, x, y, z, m

        perpendicular_distance_from_centerline: float = abs(
            vector_to_this_point.crossProduct(self.unit_dir)
        )

        if perpendicular_distance_from_centerline > self.layer_radius:
            # too far from line, not affected
            return True, x, y, z, m

        # longitudinal weight
        if projection_along_stroke <= self.stroke_dist:
            # between start and end of line
            w_long = 1.0
        else:
            # past the end of line
            extension_past_line = projection_along_stroke - self.stroke_dist
            if extension_past_line >= self.forward_fade_dist:
                return True, x, y, z, m
            w_long = self.smoother_step(extension_past_line / self.forward_fade_dist)

        # lateral weight
        w_lat = self.smoother_step(
            perpendicular_distance_from_centerline / self.layer_radius
        )

        weight = w_lat * w_long

        if weight > 0:
            end_point: QgsPointXY = this_point + (self.transform_vector * weight)
            self.geometry_changed = True
            return True, end_point.x(), end_point.y(), z, m

        return True, x, y, z, m


class RubberSheetingTool:
    """
    Deforms multiple layers using rubber sheets
    """

    DENSIFY_FACTOR = 5

    def __init__(
        self,
        layers: List[QgsVectorLayer],
        start_pt: QgsPointXY,
        end_pt: QgsPointXY,
        crs: QgsCoordinateReferenceSystem,
        radius: float,
    ):
        self.layers: List[QgsVectorLayer] = layers
        self.start_pt: QgsPointXY = start_pt
        self.end_pt: QgsPointXY = end_pt
        self.radius: float = radius
        self.crs: QgsCoordinateReferenceSystem = crs

    def apply(self):
        for layer in self.layers:
            if not layer.isEditable():
                layer.startEditing()

            ct = QgsCoordinateTransform(self.crs, layer.crs(), QgsProject.instance())

            try:
                layer_start = ct.transform(self.start_pt)
                layer_end = ct.transform(self.end_pt)
            except QgsCsException:
                continue

            stroke_dist = layer_start.distance(layer_end)

            offset_pt = QgsPointXY(self.start_pt.x() + self.radius, self.start_pt.y())
            user_radius = layer_start.distance(ct.transform(offset_pt))

            min_safe_radius = 1.875 * stroke_dist
            layer_radius = max(user_radius, min_safe_radius)

            layer_deform_line = QgsGeometry(QgsLineString([layer_start, layer_end]))
            layer_deform_area = layer_deform_line.buffer(layer_radius, 16)
            layer_deform_area_engine = QgsGeometry.createGeometryEngine(
                layer_deform_area.constGet()
            )
            layer_deform_area_engine.prepareGeometry()

            layer_bounds = layer_deform_area.boundingBox()

            densify_distance = max(
                0.5, layer_end.distance(layer_start) / self.DENSIFY_FACTOR
            )

            layer_transformer = PointRubberBandTransform(
                layer_start,
                layer_end,
                layer_radius,
            )

            request = QgsFeatureRequest().setFilterRect(layer_bounds)
            for feature in layer.getFeatures(request):
                geom = feature.geometry()
                if not geom or geom.isEmpty():
                    continue

                if not layer_deform_area_engine.intersects(geom.constGet()):
                    continue

                densified_geom = geom.densifyByDistance(densify_distance)
                abs_geom = densified_geom.constGet().clone()

                layer_transformer.geometry_changed = False
                abs_geom.transform(layer_transformer)

                if layer_transformer.geometry_changed:
                    new_geom = QgsGeometry(abs_geom)
                    new_geom = GeometryUtils.remove_unnecessary_densified_vertices(
                        feature.geometry(), new_geom
                    )
                    layer.changeGeometry(feature.id(), new_geom)
