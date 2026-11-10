"""
Geometry utilities
"""

import json

from typing import Tuple, List, Set

from qgis.core import (
    QgsPoint,
    QgsGeometry,
    QgsVertexId,
    QgsGeometryUtilsBase,
    Qgis,
    QgsLineString,
    QgsMultiLineString,
    QgsPolygon,
    QgsMultiPolygon,
    QgsFeature,
)


class GeometryUtils:
    """
    Geometry utilities
    """

    COMPARISON_PRECISION = 12

    @staticmethod
    def round_coordinates(p: QgsPoint) -> Tuple[float, float]:
        return (
            round(p.x(), GeometryUtils.COMPARISON_PRECISION),
            round(p.y(), GeometryUtils.COMPARISON_PRECISION),
        )

    @staticmethod
    def _filter_collinear_points(
        pts: List[QgsPoint],
        orig_coordinates: Set[Tuple[float, float]],
        sqr_tolerance: float,
    ) -> List[QgsPoint]:
        """
        Filters out collinear injected vertices.
        Vertices existing in orig_coordinates are unconditionally preserved.
        """
        if len(pts) <= 2:
            return pts

        stack: List[QgsPoint] = [pts[0]]

        for i in range(1, len(pts)):
            curr_pt = pts[i]

            while len(stack) >= 2:
                mid_pt = stack[-1]

                # never delete vertices that existed in the original geometry
                if GeometryUtils.round_coordinates(mid_pt) in orig_coordinates:
                    break

                prev_pt = stack[-2]

                sqr_dist, _, _ = QgsGeometryUtilsBase.sqrDistToLine(
                    mid_pt.x(),
                    mid_pt.y(),
                    prev_pt.x(),
                    prev_pt.y(),
                    curr_pt.x(),
                    curr_pt.y(),
                    1e-16,
                )

                if sqr_dist < sqr_tolerance:
                    stack.pop()
                else:
                    break

            stack.append(curr_pt)

        return stack

    @staticmethod
    def remove_unnecessary_densified_vertices(
        original_geom: QgsGeometry,
        modified_geom: QgsGeometry,
        sqr_tolerance: float = 1e-18,
    ) -> QgsGeometry:
        """
        Removes injected vertices from modified_geom that remained collinear,
        while unconditionally preserving all vertices that existed in original_geom.
        """
        if modified_geom.isEmpty() or original_geom.isEmpty():
            return QgsGeometry()

        # If no vertices were added during densification, return as-is
        if modified_geom.isExactlyEqual(original_geom):
            return QgsGeometry(original_geom)

        orig_coordinates = {
            GeometryUtils.round_coordinates(v) for v in original_geom.vertices()
        }

        abs_geom = modified_geom.constGet().clone()

        retained_parts: List[List[List[QgsPoint]]] = []

        for part_idx in range(abs_geom.partCount()):
            ring_count = abs_geom.ringCount(part_idx)
            rings_to_iterate = max(1, ring_count)
            part_rings: List[List[QgsPoint]] = []

            for ring_idx in range(rings_to_iterate):
                actual_ring = ring_idx if ring_count > 0 else 0
                v_count = abs_geom.vertexCount(part_idx, actual_ring)
                if v_count == 0:
                    continue

                pts = [
                    abs_geom.vertexAt(QgsVertexId(part_idx, actual_ring, v_i))
                    for v_i in range(v_count)
                ]

                filtered_pts = GeometryUtils._filter_collinear_points(
                    pts, orig_coordinates, sqr_tolerance
                )
                part_rings.append(filtered_pts)

            retained_parts.append(part_rings)

        if not retained_parts:
            return QgsGeometry()

        geom_type = modified_geom.type()
        is_multi = modified_geom.isMultipart()

        # reconstruct geometry
        if geom_type == Qgis.GeometryType.Line:
            if not is_multi:
                return QgsGeometry(QgsLineString(retained_parts[0][0]))
            else:
                mls = QgsMultiLineString()
                for part in retained_parts:
                    if part and part[0]:
                        mls.addGeometry(QgsLineString(part[0]))
                return QgsGeometry(mls)

        elif geom_type == Qgis.GeometryType.Polygon:
            if not is_multi:
                poly = QgsPolygon()
                poly.setExteriorRing(QgsLineString(retained_parts[0][0]))
                for int_ring in retained_parts[0][1:]:
                    poly.addInteriorRing(QgsLineString(int_ring))
                return QgsGeometry(poly)
            else:
                mpoly = QgsMultiPolygon()
                for part in retained_parts:
                    if part and part[0]:
                        poly = QgsPolygon()
                        poly.setExteriorRing(QgsLineString(part[0]))
                        for int_ring in part[1:]:
                            poly.addInteriorRing(QgsLineString(int_ring))
                        mpoly.addGeometry(poly)
                return QgsGeometry(mpoly)

        return QgsGeometry(modified_geom)

    @staticmethod
    def set_product_geom(feature: QgsFeature, geometry: QgsGeometry):
        """
        Sets the product view geometry for a feature.

        Does not actually commit these changes, that is the caller's responsibility.
        """
        current_metadata = feature["metadata"]
        if current_metadata:
            current_json = json.loads(current_metadata)
        else:
            current_json = {}

        current_json["geometry"] = geometry.asWkt()
        feature["metadata"] = json.dumps(current_json)
