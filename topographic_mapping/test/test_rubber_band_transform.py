import unittest
from qgis.core import (
    QgsPointXY,
)

from topographic_mapping.core.geometry.rubber_band_transform import (
    PointRubberBandTransform,
)

from topographic_mapping.test.test_base import TopographicTestBase


class PointRubberBandTransformTest(TopographicTestBase):
    """Unit tests for PointRubberBandTransform."""

    def test_smoother_step_bounds_and_values(self):
        """Test quintic polynomial falloff values and boundary clamping."""
        self.assertEqual(PointRubberBandTransform.smoother_step(0.0), 1.0)
        self.assertEqual(PointRubberBandTransform.smoother_step(-0.5), 1.0)
        self.assertEqual(PointRubberBandTransform.smoother_step(1.0), 0.0)
        self.assertEqual(PointRubberBandTransform.smoother_step(1.5), 0.0)
        # Midpoint of quintic smoother_step is exactly 0.5
        self.assertAlmostEqual(
            PointRubberBandTransform.smoother_step(0.5), 0.5, places=6
        )

    def test_zero_stroke_or_radius_no_op(self):
        """Test that identical start/end points or zero radius leave points unmodified."""
        # Zero stroke distance
        trans_zero_stroke = PointRubberBandTransform(
            start=QgsPointXY(10.0, 10.0),
            end=QgsPointXY(10.0, 10.0),
            layer_radius=20.0,
        )
        ok, x, y, z, m = trans_zero_stroke.transformPoint(10.0, 10.0, 0.0, 0.0)
        self.assertTrue(ok)
        self.assertEqual((x, y), (10.0, 10.0))
        self.assertFalse(trans_zero_stroke.geometry_changed)

        # Zero radius
        trans_zero_radius = PointRubberBandTransform(
            start=QgsPointXY(0.0, 0.0),
            end=QgsPointXY(10.0, 0.0),
            layer_radius=0.0,
        )
        ok, x, y, z, m = trans_zero_radius.transformPoint(0.0, 0.0, 0.0, 0.0)
        self.assertTrue(ok)
        self.assertEqual((x, y), (0.0, 0.0))
        self.assertFalse(trans_zero_radius.geometry_changed)

    def test_points_behind_start_not_impacted(self):
        """Test that points with projection < 0 along the stroke vector do not move."""
        trans = PointRubberBandTransform(
            start=QgsPointXY(0.0, 0.0),
            end=QgsPointXY(10.0, 0.0),
            layer_radius=5.0,
        )
        # Directly behind start
        ok, x, y, _, _ = trans.transformPoint(-1.0, 0.0, 0.0, 0.0)
        self.assertEqual((x, y), (-1.0, 0.0))
        self.assertFalse(trans.geometry_changed)

        # Behind and diagonally offset
        ok, x, y, _, _ = trans.transformPoint(-0.001, 2.0, 0.0, 0.0)
        self.assertEqual((x, y), (-0.001, 2.0))
        self.assertFalse(trans.geometry_changed)

    def test_points_outside_lateral_radius_not_impacted(self):
        """Test that points further than layer_radius from centerline are untouched."""
        trans = PointRubberBandTransform(
            start=QgsPointXY(0.0, 0.0),
            end=QgsPointXY(10.0, 0.0),
            layer_radius=5.0,
        )
        # Alongside the stroke but lateral distance 5.1 > 5.0
        ok, x, y, _, _ = trans.transformPoint(5.0, 5.1, 0.0, 0.0)
        self.assertEqual((x, y), (5.0, 5.1))
        self.assertFalse(trans.geometry_changed)

    def test_stroke_path_full_displacement(self):
        """Test that points along centerline between start and end receive 100% displacement."""
        # Stroke vector is +10 in X
        trans = PointRubberBandTransform(
            start=QgsPointXY(0.0, 0.0),
            end=QgsPointXY(10.0, 0.0),
            layer_radius=5.0,
        )
        # Point at start moves to end
        ok, x, y, _, _ = trans.transformPoint(0.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(x, 10.0)
        self.assertAlmostEqual(y, 0.0)
        self.assertTrue(trans.geometry_changed)

        # Point halfway along stroke moves by +10.0 in X
        ok, x, y, _, _ = trans.transformPoint(5.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(x, 15.0)
        self.assertAlmostEqual(y, 0.0)

        # Point at end moves by +10.0 in X
        ok, x, y, _, _ = trans.transformPoint(10.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(x, 20.0)
        self.assertAlmostEqual(y, 0.0)

    def test_lateral_smootherstep_falloff(self):
        """Test that points laterally offset between 0 and radius attenuate smoothly."""
        trans = PointRubberBandTransform(
            start=QgsPointXY(0.0, 0.0),
            end=QgsPointXY(10.0, 0.0),
            layer_radius=10.0,
        )
        # Midpoint of stroke (x=5.0) with half lateral offset (y=5.0 -> t = 5/10 = 0.5)
        # smoother_step(0.5) = 0.5 -> displacement = 0.5 * (10.0, 0.0) = (5.0, 0.0)
        ok, x, y, _, _ = trans.transformPoint(5.0, 5.0, 0.0, 0.0)
        self.assertAlmostEqual(x, 10.0)
        self.assertAlmostEqual(y, 5.0)
        self.assertTrue(trans.geometry_changed)

    def test_forward_fade_beyond_end(self):
        """Test longitudinal attenuation past the end of the stroke vector."""
        # stroke_dist = 10.0, radius = 5.0 -> forward_fade_dist = max(5, 2 * 10) = 20.0
        trans = PointRubberBandTransform(
            start=QgsPointXY(0.0, 0.0),
            end=QgsPointXY(10.0, 0.0),
            layer_radius=5.0,
        )
        # Point halfway through the forward fade zone: x = 10.0 + 10.0 = 20.0 (t = 10/20 = 0.5)
        # w_long = smoother_step(0.5) = 0.5, w_lat = smoother_step(0) = 1.0 -> weight = 0.5
        ok, x, y, _, _ = trans.transformPoint(20.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(x, 25.0)
        self.assertAlmostEqual(y, 0.0)
        self.assertTrue(trans.geometry_changed)

        # Point at or beyond forward_fade_dist (x >= 30.0) must be untouched
        ok, x, y, _, _ = trans.transformPoint(30.0, 0.0, 0.0, 0.0)
        self.assertEqual((x, y), (30.0, 0.0))

        ok, x, y, _, _ = trans.transformPoint(35.0, 0.0, 0.0, 0.0)
        self.assertEqual((x, y), (35.0, 0.0))


if __name__ == "__main__":
    unittest.main()
