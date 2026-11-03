import unittest
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
    QgsLineString,
)

from topographic_mapping.core.geometry.rubber_band_transform import RubberSheetingTool

from topographic_mapping.test.test_base import TopographicTestBase


class TestRubberSheetingTool(TopographicTestBase):
    """Integration tests for the multi-layer RubberSheetingTool."""

    def _create_line_layer(self, crs_authid="EPSG:4326") -> QgsVectorLayer:
        layer = QgsVectorLayer(f"LineString?crs={crs_authid}", "test_line", "memory")
        return layer

    def test_single_layer_feature_deformation(self):
        """Test deformation applied to a vector layer and cleaned up by GeometryUtils."""
        layer = self._create_line_layer("EPSG:4326")
        pr = layer.dataProvider()

        # Feature 1: Inside deform path crossing at x=5, y in [-2, 2]
        feat1 = QgsFeature()
        feat1.setGeometry(
            QgsGeometry(QgsLineString([QgsPointXY(5.0, -2.0), QgsPointXY(5.0, 2.0)]))
        )

        # Feature 2: Far outside deformation area at x=100
        feat2 = QgsFeature()
        feat2.setGeometry(
            QgsGeometry(
                QgsLineString([QgsPointXY(100.0, 0.0), QgsPointXY(100.0, 10.0)])
            )
        )

        pr.addFeatures([feat1, feat2])

        tool = RubberSheetingTool(
            layers=[layer],
            start_pt=QgsPointXY(0.0, 0.0),
            end_pt=QgsPointXY(10.0, 0.0),
            crs=QgsCoordinateReferenceSystem("EPSG:4326"),
            radius=5.0,
        )
        tool.apply()

        # Verify Feature 1 was deformed forward along +X
        modified_feat1 = layer.getFeature(1)
        geom1 = modified_feat1.geometry()
        self.assertEqual(
            geom1.asWkt(3),
            "LineString (14.897 -2, 14.996 -0.667, 14.996 0.667, 14.897 2)",
        )

        # Verify Feature 2 remains identical
        modified_feat2 = layer.getFeature(2)
        geom2 = modified_feat2.geometry()
        self.assertEqual(geom2.asWkt(), "LineString (100 0, 100 10)")

    def test_multiple_layers_deformation(self):
        """Test that multiple vector layers are processed in a single apply pass."""
        layer1 = self._create_line_layer("EPSG:4326")
        layer2 = self._create_line_layer("EPSG:4326")

        f1 = QgsFeature()
        f1.setGeometry(
            QgsGeometry(QgsLineString([QgsPointXY(2.0, -1.0), QgsPointXY(2.0, 1.0)]))
        )
        layer1.dataProvider().addFeatures([f1])

        f2 = QgsFeature()
        f2.setGeometry(
            QgsGeometry(QgsLineString([QgsPointXY(4.0, -1.0), QgsPointXY(4.0, 1.0)]))
        )
        layer2.dataProvider().addFeatures([f2])

        tool = RubberSheetingTool(
            layers=[layer1, layer2],
            start_pt=QgsPointXY(0.0, 0.0),
            end_pt=QgsPointXY(10.0, 0.0),
            crs=QgsCoordinateReferenceSystem("EPSG:4326"),
            radius=5.0,
        )
        tool.apply()

        # Both layers should have displaced vertices
        geom1 = layer1.getFeature(1).geometry()
        self.assertEqual(geom1.asWkt(3), "LineString (11.986 -1, 12 0, 11.986 1)")
        geom2 = layer2.getFeature(1).geometry()
        self.assertEqual(geom2.asWkt(3), "LineString (13.986 -1, 14 0, 13.986 1)")

    def test_crs_reprojection_handling(self):
        """Test transformation when tool CRS differs from layer CRS."""
        # Tool operates in WGS 84 (EPSG:4326)
        tool_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        # Layer in Web Mercator (EPSG:3857)
        layer_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        layer = self._create_line_layer("EPSG:3857")

        ct = QgsCoordinateTransform(tool_crs, layer_crs, QgsProject.instance())
        start_4326 = QgsPointXY(0.0, 0.0)
        end_4326 = QgsPointXY(1.0, 0.0)

        # Create line crossing between start and end in layer CRS
        mid_4326 = QgsPointXY(0.5, 0.0)
        mid_3857 = ct.transform(mid_4326)

        feat = QgsFeature()
        feat.setGeometry(
            QgsGeometry(
                QgsLineString(
                    [
                        QgsPointXY(mid_3857.x(), mid_3857.y() - 1000.0),
                        QgsPointXY(mid_3857.x(), mid_3857.y() + 1000.0),
                    ]
                )
            )
        )
        layer.dataProvider().addFeatures([feat])

        tool = RubberSheetingTool(
            layers=[layer],
            start_pt=start_4326,
            end_pt=end_4326,
            crs=tool_crs,
            radius=0.5,
        )
        tool.apply()

        modified_geom = layer.getFeature(1).geometry()
        self.assertFalse(modified_geom.isEmpty())
        # Vertices should be displaced in the positive X direction in EPSG:3857
        self.assertEqual(
            modified_geom.asWkt(2), "LineString (166979.11 -1000, 166979.11 1000)"
        )

    def test_edit_command_and_rollback(self):
        """Test that changes are wrapped in an edit command and can be rolled back."""
        layer = self._create_line_layer("EPSG:4326")
        feat = QgsFeature()
        feat.setGeometry(
            QgsGeometry(QgsLineString([QgsPointXY(5.0, -1.0), QgsPointXY(5.0, 1.0)]))
        )
        layer.dataProvider().addFeatures([feat])

        tool = RubberSheetingTool(
            layers=[layer],
            start_pt=QgsPointXY(0.0, 0.0),
            end_pt=QgsPointXY(10.0, 0.0),
            crs=QgsCoordinateReferenceSystem("EPSG:4326"),
            radius=5.0,
        )
        tool.apply()

        self.assertTrue(layer.isEditable())
        self.assertTrue(layer.undoStack().canUndo())

        # Rolling back should restore the original geometry exactly
        layer.rollBack()
        restored_geom = layer.getFeature(1).geometry()
        self.assertEqual(restored_geom.asWkt(), "LineString (5 -1, 5 1)")


if __name__ == "__main__":
    unittest.main()
