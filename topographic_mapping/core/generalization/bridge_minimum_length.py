"""
Bridge minimum length rule
"""

from typing import Dict, List, Tuple
from qgis.core import (
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsProject,
    QgsFeatureRequest,
    QgsPointXY,
    QgsVectorLayer,
    QgsGeometry,
)
from qgis.analysis import QgsVectorLayerDirector, QgsGraphBuilder

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
    T_INTERSECTION_SEARCH_DIST = 120
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
    def get_road_layer(
        context: CartographicGeneralizationRuleContext,
    ) -> QgsVectorLayer | None:
        layer = context.project_controller.layer_for_feature_type("road_line")
        return layer

    @staticmethod
    def create_distance_area(bridge_layer: QgsVectorLayer) -> QgsDistanceArea:
        da = QgsDistanceArea()
        da.setSourceCrs(bridge_layer.crs(), QgsProject.instance().transformContext())
        da.setEllipsoid(QgsProject.instance().ellipsoid())
        return da

    @classmethod
    def check_t_intersections_with_network(
        cls,
        bridge_geom: QgsGeometry,
        road_layer: QgsVectorLayer | None,
        bridge_layer: QgsVectorLayer,
        search_distance: float,
        tolerance: float = 0.00000001,
    ) -> Tuple[bool, bool]:
        """
        Checks for "T" intersections within a distance of a bridge

        Returns tuple of start/end having T intersections within the distance
        """
        if road_layer is None or bridge_geom.isNull() or bridge_geom.isEmpty():
            return False, False

        bridge_line = bridge_geom.constGet()
        if bridge_line is None:
            return False, False

        p_start = QgsPointXY(bridge_line.startPoint())
        p_end = QgsPointXY(bridge_line.endPoint())
        bridge_len = bridge_geom.length()
        if bridge_len <= 0:
            return False, False

        search_box = bridge_geom.boundingBox()
        search_box.grow(search_distance)

        # Build a temporary memory layer for local network analysis
        request = (
            QgsFeatureRequest()
            .setDestinationCrs(
                bridge_layer.crs(), QgsProject.instance().transformContext()
            )
            .setFilterRect(search_box)
        )
        local_features_layer = road_layer.materialize(request)
        if local_features_layer.featureCount() == 0:
            return False, False

        director = QgsVectorLayerDirector(
            local_features_layer,
            directionFieldId=-1,
            directDirectionValue="",
            reverseDirectionValue="",
            bothDirectionValue="",
            defaultDirection=QgsVectorLayerDirector.Direction.DirectionBoth,
        )
        builder = QgsGraphBuilder(
            bridge_layer.crs(),
            otfEnabled=True,
            topologyTolerance=tolerance,
        )

        director.makeGraph(builder, [p_start, p_end])
        graph = builder.graph()

        start_has_t = False
        end_has_t = False

        # Inspect graph vertices for degree 3 (T-intersections)
        for v_idx in range(graph.vertexCount()):
            vertex = graph.vertex(v_idx)
            v_point = vertex.point()

            # Find distinct connected neighbor vertices
            neighbors = set()
            for edge_id in vertex.outgoingEdges():
                edge = graph.edge(edge_id)
                neighbors.add(edge.toVertex())
            for edge_id in vertex.incomingEdges():
                edge = graph.edge(edge_id)
                neighbors.add(edge.fromVertex())

            if len(neighbors) == 3:
                d_start = (
                    (v_point.x() - p_start.x()) ** 2 + (v_point.y() - p_start.y()) ** 2
                ) ** 0.5
                d_end = (
                    (v_point.x() - p_end.x()) ** 2 + (v_point.y() - p_end.y()) ** 2
                ) ** 0.5

                if d_start <= search_distance and d_start <= d_end:
                    start_has_t = True
                elif d_end <= search_distance and d_end < d_start:
                    end_has_t = True

            if start_has_t and end_has_t:
                break

        return start_has_t, end_has_t

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
                CartographicIssue(
                    fid=f.id(),
                    message=message,
                    sort_value=bridge_length,
                    layer=bridge_layer,
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
        bridge_layer = self.get_bridge_layer(context)
        if not bridge_layer:
            return

        da = self.create_distance_area(bridge_layer)
        if not da.willUseEllipsoid():
            return

        target_layers = [
            context.project_controller.layer_for_feature_type(ft)
            for ft in BridgeMinimumLengthRule.TARGET_LAYERS
        ]
        target_layers.append(bridge_layer)
        road_layer = self.get_road_layer(context)

        for layer in target_layers:
            layer.beginEditCommand(self.name())

        fids = [issue.fid for issue in issues]

        request = QgsFeatureRequest().setFilterFids(fids)

        all_features = [f for f in bridge_layer.getFeatures(request)]

        for idx, f in enumerate(all_features):
            feedback.setProgress(int(idx / len(all_features) * 100))

            geom = f.geometry()
            bridge_length = da.measureLength(geom)
            if bridge_length >= BridgeMinimumLengthRule.MINIMUM_LENGTH * 0.999:
                continue

            required_length_layer_crs = (
                geom.length() / bridge_length * BridgeMinimumLengthRule.MINIMUM_LENGTH
            )

            t_intersection_search_dist_layer_crs = (
                geom.length()
                / bridge_length
                * BridgeMinimumLengthRule.T_INTERSECTION_SEARCH_DIST
            )

            current_start_point = geom.constGet().startPoint()
            current_end_point = geom.constGet().endPoint()
            new_bridge_line = geom.constGet().clone()
            amount_to_extend = required_length_layer_crs - new_bridge_line.length()
            if amount_to_extend <= 0:
                continue

            start_has_t, end_has_t = self.check_t_intersections_with_network(
                geom, road_layer, bridge_layer, t_intersection_search_dist_layer_crs
            )

            if start_has_t and not end_has_t:
                extend_start = 0.0
                extend_end = amount_to_extend
                feedback.push_feedback(
                    "Bridge {} too short ({} m) - T-intersection at start is fixed; extending end".format(
                        f["t50_fid"],
                        round(bridge_length, 1),
                    )
                )
            elif end_has_t and not start_has_t:
                extend_start = amount_to_extend
                extend_end = 0.0
                feedback.push_feedback(
                    "Bridge {} too short ({} m) - T-intersection at end is fixed; extending start".format(
                        f["t50_fid"],
                        round(bridge_length, 1),
                    )
                )
            else:
                extend_start = amount_to_extend * 0.5
                extend_end = amount_to_extend * 0.5
                split_reason = (
                    "T-intersections on both sides"
                    if (start_has_t and end_has_t)
                    else "no T-intersection constraints"
                )
                feedback.push_feedback(
                    "Bridge {} too short ({} m) - No T-intersections (50/50 split)".format(
                        f["t50_fid"], round(bridge_length, 1), split_reason
                    )
                )

            new_bridge_line.extend(extend_start, extend_end)

            new_start_point = new_bridge_line.startPoint()
            new_end_point = new_bridge_line.endPoint()

            if extend_start > 0:
                tool = RubberSheetingTool(
                    target_layers,
                    QgsPointXY(current_start_point),
                    QgsPointXY(new_start_point),
                    bridge_layer.crs(),
                    required_length_layer_crs,
                )
                tool.apply()

            if extend_end > 0:
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
