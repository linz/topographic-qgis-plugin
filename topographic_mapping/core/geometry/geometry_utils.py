"""
Geometry utilities
"""

from typing import Tuple

from qgis.core import QgsPoint, QgsGeometry, QgsVertexId, QgsGeometryUtilsBase


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

        for part_idx in range(abs_geom.partCount()):
            ring_count = abs_geom.ringCount(part_idx)
            rings_to_iterate = max(1, ring_count)

            for ring_idx in range(rings_to_iterate):
                actual_ring = ring_idx if ring_count > 0 else 0

                # Iterate backwards so deletions never shift indices of upcoming vertices.
                # Endpoints (index 0 and count - 1) are skipped and always preserved.
                v_idx = abs_geom.vertexCount(part_idx, actual_ring) - 2

                while v_idx > 0:
                    vid_curr = QgsVertexId(part_idx, actual_ring, v_idx)
                    p_curr = abs_geom.vertexAt(vid_curr)

                    # never delete vertices that existed in the original geometry
                    if GeometryUtils.round_coordinates(p_curr) in orig_coordinates:
                        v_idx -= 1
                        continue

                    # is the injected vertex strictly collinear
                    vid_prev = QgsVertexId(part_idx, actual_ring, v_idx - 1)
                    vid_next = QgsVertexId(part_idx, actual_ring, v_idx + 1)
                    p_prev = abs_geom.vertexAt(vid_prev)
                    p_next = abs_geom.vertexAt(vid_next)

                    sqr_dist, _, _ = QgsGeometryUtilsBase.sqrDistToLine(
                        p_curr.x(),
                        p_curr.y(),
                        p_prev.x(),
                        p_prev.y(),
                        p_next.x(),
                        p_next.y(),
                        1e-16,
                    )

                    # if it didn't bend/change shape, strip it out
                    if sqr_dist < sqr_tolerance:
                        abs_geom.deleteVertex(vid_curr)

                    v_idx -= 1

        return QgsGeometry(abs_geom)
