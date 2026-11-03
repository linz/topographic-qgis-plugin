"""
Bridge minimum length rule
"""

from typing import Dict, List
from qgis.core import (
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsProject,
    QgsFeatureRequest,
    QgsPointXY,
    QgsVectorLayer,
)

from ..geometry.rubber_band_transform import RubberSheetingTool
from .generalization_rule import (
    CartographicGeneralizationRule,
    CartographicGeneralizationRuleContext,
    RuleFeedback,
    CartographicIssue,
)


class BridgeMinimumLengthRule(CartographicGeneralizationRule):
    """
    Bridge minimum length rule
    """

    MINIMUM_LENGTH = 120
    TOLERANCE = 0.999
    TARGET_LAYERS = [
        "road_line",
    ]

    def id(self) -> str:
        return "bridge_length"

    def name(self) -> str:
        return "Bridge Object Minimum Length"

    @staticmethod
    def get_bridge_layer(
        context: CartographicGeneralizationRuleContext,
    ) -> QgsVectorLayer | None:
        layer = context.project_controller.layer_for_feature_type("bridge_line")
        return layer

    @staticmethod
    def get_water_polygon_layer(
        context: CartographicGeneralizationRuleContext,
    ) -> QgsVectorLayer | None:
        layer = context.project_controller.layer_for_feature_type("water")
        return layer

    @staticmethod
    def create_distance_area(bridge_layer: QgsVectorLayer) -> QgsDistanceArea:
        da = QgsDistanceArea()
        da.setSourceCrs(bridge_layer.crs(), QgsProject.instance().transformContext())
        da.setEllipsoid(QgsProject.instance().ellipsoid())
        return da

    def validate(
        self,
        context: CartographicGeneralizationRuleContext,
        parameters: Dict[str, object],
        feedback: RuleFeedback,
    ) -> List[CartographicIssue]:
        bridge_layer = self.get_bridge_layer(context)
        if not bridge_layer:
            return []

        da = self.create_distance_area(bridge_layer)
        if not da.willUseEllipsoid():
            return []

        ct = QgsCoordinateTransform(
            context.extent.crs(), bridge_layer.crs(), QgsProject.instance()
        )
        layer_extent = ct.transformBoundingBox(context.extent)

        request = QgsFeatureRequest().setFilterRect(layer_extent)
        all_features = [f for f in bridge_layer.getFeatures(request)]

        failures = []
        for idx, f in enumerate(all_features):
            feedback.setProgress(int(idx / len(all_features) * 100))

            geom = f.geometry()
            bridge_length = da.measureLength(geom)
            if (
                bridge_length
                >= BridgeMinimumLengthRule.MINIMUM_LENGTH
                * BridgeMinimumLengthRule.TOLERANCE
            ):
                continue

            message = "Bridge too short ({} m)".format(round(bridge_length, 1))
            feedback.push_feedback(message)

            failures.append(
                CartographicIssue(fid=f.id(), message=message, sort_value=bridge_length)
            )
        return failures

    def run(
        self,
        context: CartographicGeneralizationRuleContext,
        parameters: Dict[str, object],
        feedback: RuleFeedback,
    ):
        bridge_layer = self.get_bridge_layer(context)
        if not bridge_layer:
            return

        da = self.create_distance_area(bridge_layer)
        if not da.willUseEllipsoid():
            return

        ct = QgsCoordinateTransform(
            context.extent.crs(), bridge_layer.crs(), QgsProject.instance()
        )
        layer_extent = ct.transformBoundingBox(context.extent)

        target_layers = [
            context.project_controller.layer_for_feature_type(ft)
            for ft in BridgeMinimumLengthRule.TARGET_LAYERS
        ]
        target_layers.append(bridge_layer)

        for layer in target_layers:
            layer.beginEditCommand(self.name())

        request = QgsFeatureRequest().setFilterRect(layer_extent)

        all_features = [f for f in bridge_layer.getFeatures(request)]

        for idx, f in enumerate(all_features):
            feedback.setProgress(int(idx / len(all_features) * 100))

            geom = f.geometry()
            bridge_length = da.measureLength(geom)
            if bridge_length >= BridgeMinimumLengthRule.MINIMUM_LENGTH * 0.999:
                continue

            feedback.push_feedback(
                "Bridge {} too short ({} m) - extending".format(
                    f["t50_fid"], round(bridge_length, 1)
                )
            )
            required_length_layer_crs = (
                geom.length() / bridge_length * BridgeMinimumLengthRule.MINIMUM_LENGTH
            )

            current_start_point = geom.constGet().startPoint()
            current_end_point = geom.constGet().endPoint()
            new_bridge_line = geom.constGet().clone()
            amount_to_extend = required_length_layer_crs - new_bridge_line.length()

            new_bridge_line.extend(amount_to_extend * 0.5, amount_to_extend * 0.5)

            new_start_point = new_bridge_line.startPoint()
            new_end_point = new_bridge_line.endPoint()

            tool = RubberSheetingTool(
                target_layers,
                QgsPointXY(current_start_point),
                QgsPointXY(new_start_point),
                bridge_layer.crs(),
                required_length_layer_crs,
            )
            tool.apply()

            tool = RubberSheetingTool(
                target_layers,
                QgsPointXY(current_end_point),
                QgsPointXY(new_end_point),
                bridge_layer.crs(),
                required_length_layer_crs,
            )
            tool.apply()

        for layer in target_layers:
            layer.endEditCommand()

        feedback.setProgress(100)
