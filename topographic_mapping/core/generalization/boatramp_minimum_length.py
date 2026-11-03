"""
Boat ramp minimum length rule
"""

from typing import Dict
from qgis.core import (
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsProject,
    QgsFeatureRequest,
    QgsGeometry,
    QgsExpression,
    QgsSpatialIndex,
    QgsRectangle,
)

from .generalization_rule import (
    CartographicGeneralizationRule,
    CartographicGeneralizationRuleContext,
    RuleFeedback,
)


class BoatRampMinimumLengthRule(CartographicGeneralizationRule):
    """
    Boat ramp minimum length rule
    """

    MINIMUM_LENGTH = 120

    def id(self) -> str:
        return "boat_ramp"

    def name(self) -> str:
        return "Boat Ramp Minimum Length"

    def run(
        self,
        context: CartographicGeneralizationRuleContext,
        parameters: Dict[str, object],
        feedback: RuleFeedback,
    ):
        # get boat ramp layer
        line_layer = context.project_controller.layer_for_feature_type("structure_line")
        if not line_layer:
            return

        water_layer = context.project_controller.layer_for_feature_type("water")
        if not water_layer:
            return

        ct = QgsCoordinateTransform(
            context.extent.crs(), line_layer.crs(), QgsProject.instance()
        )
        layer_extent = ct.transformBoundingBox(context.extent)

        da = QgsDistanceArea()
        da.setSourceCrs(line_layer.crs(), QgsProject.instance().transformContext())

        da.setEllipsoid(QgsProject.instance().ellipsoid())
        if not da.willUseEllipsoid():
            return

        line_layer.beginEditCommand(self.name())

        water_feature_it = water_layer.getFeatures(
            QgsFeatureRequest().setFilterRect(layer_extent)
        )
        water_index = QgsSpatialIndex(
            water_feature_it, flags=QgsSpatialIndex.Flag.FlagStoreFeatureGeometries
        )

        request = (
            QgsFeatureRequest()
            .setFilterRect(layer_extent)
            .setFilterExpression(
                QgsExpression.createFieldEqualityExpression("type", "boatramp")
            )
        )

        all_features = [f for f in line_layer.getFeatures(request)]

        for idx, f in enumerate(all_features):
            feedback.setProgress(int(idx / len(all_features) * 100))

            geom = f.geometry()
            ramp_length = da.measureLength(geom)
            if ramp_length >= BoatRampMinimumLengthRule.MINIMUM_LENGTH * 0.999:
                continue

            feedback.push_feedback(
                "Boat ramp {} too short ({} m) - extending".format(
                    f["t50_fid"], round(ramp_length, 1)
                )
            )
            required_length_layer_crs = (
                geom.length() / ramp_length * BoatRampMinimumLengthRule.MINIMUM_LENGTH
            )

            new_bridge_line = geom.constGet().clone()
            amount_to_extend = required_length_layer_crs - new_bridge_line.length()

            new_bridge_line.extend(0, amount_to_extend)

            # check if line ends in water, if not, extend start...
            end_point = new_bridge_line.endPoint()
            water_features = water_index.intersects(
                QgsRectangle(end_point.x(), end_point.y(), end_point.x(), end_point.y())
            )
            end_in_water = False
            for water_feature in water_features:
                water_feature_geom = water_index.geometry(water_feature)
                if water_feature_geom.contains(end_point.x(), end_point.y()):
                    end_in_water = True
                    break

            if not end_in_water:
                feedback.push_feedback(
                    " end does not fall in water body, extending start instead"
                )
                new_bridge_line = geom.constGet().clone()
                new_bridge_line.extend(amount_to_extend, 0)

            line_layer.changeGeometry(f.id(), QgsGeometry(new_bridge_line))

        line_layer.endEditCommand()

        feedback.setProgress(100)
