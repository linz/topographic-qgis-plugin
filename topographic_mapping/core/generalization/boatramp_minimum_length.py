"""
Boat ramp minimum length rule
"""

from typing import Dict, List
from qgis.core import (
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsProject,
    QgsFeatureRequest,
    QgsGeometry,
    QgsExpression,
    QgsSpatialIndex,
    QgsRectangle,
    QgsVectorLayer,
    QgsFeatureIterator,
)

from .generalization_rule import (
    CartographicGeneralizationRule,
    CartographicGeneralizationRuleContext,
    RuleFeedback,
    CartographicIssue,
)


class BoatRampMinimumLengthRule(CartographicGeneralizationRule):
    """
    Boat ramp minimum length rule
    """

    MINIMUM_LENGTH = 120
    TOLERANCE = 0.999

    def id(self) -> str:
        return "boat_ramp"

    def name(self) -> str:
        return "Boat Ramp Minimum Length"

    @staticmethod
    def get_boat_ramp_layer(
        context: CartographicGeneralizationRuleContext,
    ) -> QgsVectorLayer | None:
        layer = context.project_controller.layer_for_feature_type("structure_line")
        return layer

    @staticmethod
    def get_water_polygon_layer(
        context: CartographicGeneralizationRuleContext,
    ) -> QgsVectorLayer | None:
        layer = context.project_controller.layer_for_feature_type("water")
        return layer

    @staticmethod
    def create_distance_area(boat_ramp_layer: QgsVectorLayer) -> QgsDistanceArea:
        da = QgsDistanceArea()
        da.setSourceCrs(boat_ramp_layer.crs(), QgsProject.instance().transformContext())
        da.setEllipsoid(QgsProject.instance().ellipsoid())
        return da

    @staticmethod
    def build_water_polygon_index(
        water_layer: QgsVectorLayer, layer_extent: QgsRectangle
    ) -> QgsSpatialIndex:
        water_feature_it = water_layer.getFeatures(
            QgsFeatureRequest().setFilterRect(layer_extent)
        )
        water_index = QgsSpatialIndex(
            water_feature_it, flags=QgsSpatialIndex.Flag.FlagStoreFeatureGeometries
        )
        return water_index

    @staticmethod
    def get_boat_ramp_iterator(
        boat_ramp_layer: QgsVectorLayer,
        layer_extent: QgsRectangle | None,
        fids: List[int] | None,
    ) -> QgsFeatureIterator:
        request = QgsFeatureRequest()
        if layer_extent is not None:
            request.setFilterRect(layer_extent)

        if fids is not None:
            request.setFilterFids(fids)
        else:
            request.setFilterExpression(
                QgsExpression.createFieldEqualityExpression("type", "boatramp")
            )

        return boat_ramp_layer.getFeatures(request)

    def validate(
        self,
        context: CartographicGeneralizationRuleContext,
        parameters: Dict[str, object],
        feedback: RuleFeedback,
    ) -> List[CartographicIssue]:
        line_layer = self.get_boat_ramp_layer(context)
        if not line_layer:
            return []

        water_layer = self.get_water_polygon_layer(context)
        if not water_layer:
            return []

        da = self.create_distance_area(water_layer)
        if not da.willUseEllipsoid():
            return []

        ct = QgsCoordinateTransform(
            context.extent.crs(), line_layer.crs(), QgsProject.instance()
        )
        layer_extent = ct.transformBoundingBox(context.extent)

        water_index = self.build_water_polygon_index(water_layer, layer_extent)

        all_features = [
            f for f in self.get_boat_ramp_iterator(line_layer, layer_extent, fids=None)
        ]

        failures = []
        for idx, f in enumerate(all_features):
            feedback.setProgress(int(idx / len(all_features) * 100))

            geom = f.geometry()
            ramp_length = da.measureLength(geom)

            ramp_geom = geom.constGet()
            start_point = ramp_geom.startPoint()
            end_point = ramp_geom.endPoint()

            water_features = water_index.intersects(
                QgsRectangle(end_point.x(), end_point.y(), end_point.x(), end_point.y())
            )
            endpoint_in_water = False
            for water_feature in water_features:
                water_feature_geom = water_index.geometry(water_feature)
                if water_feature_geom.contains(end_point.x(), end_point.y()):
                    endpoint_in_water = True
                    break

            if not endpoint_in_water:
                water_features = water_index.intersects(
                    QgsRectangle(
                        start_point.x(),
                        start_point.y(),
                        start_point.x(),
                        start_point.y(),
                    )
                )
                for water_feature in water_features:
                    water_feature_geom = water_index.geometry(water_feature)
                    if water_feature_geom.contains(start_point.x(), start_point.y()):
                        endpoint_in_water = True
                        break

            is_sufficient_length = (
                ramp_length
                >= BoatRampMinimumLengthRule.MINIMUM_LENGTH
                * BoatRampMinimumLengthRule.TOLERANCE
            )
            if is_sufficient_length and endpoint_in_water:
                # endpoint in water, sufficient length => all good
                continue

            if not is_sufficient_length and endpoint_in_water:
                message = "Ramp too short ({} m)".format(round(ramp_length, 1))
            elif is_sufficient_length and not endpoint_in_water:
                message = "Ramp does not start or end in water"
            else:
                message = (
                    "Ramp too short ({} m) and does not start or end in water".format(
                        round(ramp_length, 1)
                    )
                )
            feedback.push_feedback(message)

            failures.append(
                CartographicIssue(
                    fid=f.id(),
                    message=message,
                    sort_value=ramp_length,
                    layer=line_layer,
                )
            )

        return failures

    def run(
        self,
        issues: List[CartographicIssue],
        context: CartographicGeneralizationRuleContext,
        parameters: Dict[str, object],
        feedback: RuleFeedback,
    ):
        line_layer = self.get_boat_ramp_layer(context)
        if not line_layer:
            return

        water_layer = self.get_water_polygon_layer(context)
        if not water_layer:
            return

        da = self.create_distance_area(water_layer)
        if not da.willUseEllipsoid():
            return

        fids = [issue.fid for issue in issues]
        all_features = [
            f
            for f in self.get_boat_ramp_iterator(
                line_layer, layer_extent=None, fids=fids
            )
        ]

        layer_extent = QgsRectangle()
        for f in all_features:
            layer_extent.combineExtentWith(f.geometry().boundingBox())

        line_layer.beginEditCommand(self.name())

        water_index = self.build_water_polygon_index(water_layer, layer_extent)

        for idx, f in enumerate(all_features):
            feedback.setProgress(int(idx / len(all_features) * 100))

            geom = f.geometry()
            ramp_length = da.measureLength(geom)
            if (
                ramp_length
                >= BoatRampMinimumLengthRule.MINIMUM_LENGTH
                * BoatRampMinimumLengthRule.TOLERANCE
            ):
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
