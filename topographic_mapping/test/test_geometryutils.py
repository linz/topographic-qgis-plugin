"""
Geometry Utils Test.
"""

from qgis.core import QgsGeometry, QgsPointXY, QgsLineString

from topographic_mapping.core.geometry.geometry_utils import GeometryUtils
from topographic_mapping.test.test_base import TopographicTestBase


class GeometryUtilsTest(TopographicTestBase):
    """Test GeometryUtils work."""

    def test_empty_geometry(self):
        """Test that empty inputs return an empty geometry."""
        orig = QgsGeometry()
        modified = QgsGeometry()
        result = GeometryUtils.remove_unnecessary_densified_vertices(orig, modified)
        self.assertTrue(result.isEmpty())

    def test_identical_geometries(self):
        """Test that identical geometries return unchanged."""
        line = QgsGeometry(QgsLineString([QgsPointXY(0.0, 0.0), QgsPointXY(10.0, 0.0)]))
        result = GeometryUtils.remove_unnecessary_densified_vertices(line, line)
        self.assertEqual(result.asWkt(), "LineString (0 0, 10 0)")

    def test_densified_straight_line_removes_injected(self):
        """Test that injected collinear vertices along a straight line are completely stripped."""
        orig = QgsGeometry(QgsLineString([QgsPointXY(0.0, 0.0), QgsPointXY(10.0, 0.0)]))
        # Densified line with 4 injected vertices along the segment
        modified = QgsGeometry(
            QgsGeometry(
                QgsLineString(
                    [
                        QgsPointXY(0.0, 0.0),
                        QgsPointXY(2.0, 0.0),
                        QgsPointXY(4.0, 0.0),
                        QgsPointXY(6.0, 0.0),
                        QgsPointXY(8.0, 0.0),
                        QgsPointXY(10.0, 0.0),
                    ]
                )
            )
        )

        result = GeometryUtils.remove_unnecessary_densified_vertices(orig, modified)
        self.assertEqual(result.asWkt(), "LineString (0 0, 10 0)")

    def test_preserves_original_collinear_vertices(self):
        """Test that collinear vertices that existed in the original geometry are unconditionally retained."""
        orig = QgsGeometry(
            QgsLineString(
                [QgsPointXY(0.0, 0.0), QgsPointXY(5.0, 0.0), QgsPointXY(10.0, 0.0)]
            )
        )
        # Injected vertices added at 2.5 and 7.5
        modified = QgsGeometry(
            QgsLineString(
                [
                    QgsPointXY(0.0, 0.0),
                    QgsPointXY(2.5, 0.0),
                    QgsPointXY(5.0, 0.0),
                    QgsPointXY(7.5, 0.0),
                    QgsPointXY(10.0, 0.0),
                ]
            )
        )

        result = GeometryUtils.remove_unnecessary_densified_vertices(orig, modified)
        self.assertEqual(result.asWkt(), "LineString (0 0, 5 0, 10 0)")

    def test_retains_deformed_injected_vertices(self):
        """Test that injected vertices that have been bent/deformed are preserved."""
        orig = QgsGeometry(QgsLineString([QgsPointXY(0.0, 0.0), QgsPointXY(10.0, 0.0)]))
        # Injected vertex at (5.0, 2.0) has been deformed off the straight line
        modified = QgsGeometry(
            QgsLineString(
                [QgsPointXY(0.0, 0.0), QgsPointXY(5.0, 2.0), QgsPointXY(10.0, 0.0)]
            )
        )

        result = GeometryUtils.remove_unnecessary_densified_vertices(orig, modified)
        self.assertEqual(result.asWkt(), "LineString (0 0, 5 2, 10 0)")

    def test_partially_deformed_line(self):
        """Test mixed line where some injected vertices bent while others remained flat."""
        orig = QgsGeometry(QgsLineString([QgsPointXY(0.0, 0.0), QgsPointXY(20.0, 0.0)]))
        modified = QgsGeometry(
            QgsLineString(
                [
                    QgsPointXY(0.0, 0.0),
                    QgsPointXY(2.0, 0.0),
                    QgsPointXY(5.0, 0.0),
                    QgsPointXY(10.0, 3.0),
                    QgsPointXY(15.0, 0.0),
                    QgsPointXY(18.0, 0.0),
                    QgsPointXY(20.0, 0.0),
                ]
            )
        )

        result = GeometryUtils.remove_unnecessary_densified_vertices(orig, modified)
        self.assertEqual(result.asWkt(), "LineString (0 0, 5 0, 10 3, 15 0, 20 0)")

    def test_polygon_ring_vertex_cleanup(self):
        """Test that collinear injected vertices on polygon boundaries are removed while shapes are preserved."""
        # Square polygon (5 vertices including closure)
        orig = QgsGeometry.fromPolygonXY(
            [
                [
                    QgsPointXY(0.0, 0.0),
                    QgsPointXY(10.0, 0.0),
                    QgsPointXY(10.0, 10.0),
                    QgsPointXY(0.0, 10.0),
                    QgsPointXY(0.0, 0.0),
                ]
            ]
        )
        # Add collinear vertex (5, 0) on bottom edge and deformed vertex (10, 5) -> (12, 5) on right edge
        modified = QgsGeometry.fromPolygonXY(
            [
                [
                    QgsPointXY(0.0, 0.0),
                    QgsPointXY(5.0, 0.0),  # Collinear (should be removed)
                    QgsPointXY(10.0, 0.0),
                    QgsPointXY(12.0, 5.0),  # Deformed (must be retained)
                    QgsPointXY(10.0, 10.0),
                    QgsPointXY(0.0, 10.0),
                    QgsPointXY(0.0, 0.0),
                ]
            ]
        )

        result = GeometryUtils.remove_unnecessary_densified_vertices(orig, modified)
        self.assertEqual(
            result.asWkt(), "Polygon ((0 0, 10 0, 12 5, 10 10, 0 10, 0 0))"
        )

    def test_multi_part_geometry(self):
        """Test that multi-part geometries correctly handle multiple parts."""
        line1_orig = [QgsPointXY(0.0, 0.0), QgsPointXY(10.0, 0.0)]
        line2_orig = [QgsPointXY(0.0, 20.0), QgsPointXY(10.0, 20.0)]
        orig = QgsGeometry.fromMultiPolylineXY([line1_orig, line2_orig])

        # Part 1 has an unbent injected vertex at (5, 0)
        line1_mod = [QgsPointXY(0.0, 0.0), QgsPointXY(5.0, 0.0), QgsPointXY(10.0, 0.0)]
        # Part 2 has a bent injected vertex at (5, 23)
        line2_mod = [
            QgsPointXY(0.0, 20.0),
            QgsPointXY(5.0, 23.0),
            QgsPointXY(10.0, 20.0),
        ]
        modified = QgsGeometry.fromMultiPolylineXY([line1_mod, line2_mod])

        result = GeometryUtils.remove_unnecessary_densified_vertices(orig, modified)
        self.assertEqual(
            result.asWkt(), "MultiLineString ((0 0, 10 0),(0 20, 5 23, 10 20))"
        )
