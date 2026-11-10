"""
Ford point on road rule
"""

from typing import Dict, List, Optional, Tuple
from qgis.core import (
    QgsAbstractGeometry,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsExpression,
    QgsFeature,
    QgsFeatureIterator,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsSpatialIndex,
    QgsVectorLayer,
)

from ..geometry import GeometryUtils
from .generalization_rule import (
    CartographicGeneralizationRule,
    CartographicGeneralizationRuleContext,
    CartographicIssue,
    RuleFeedback,
)


class FordPointOnRoadRule(CartographicGeneralizationRule):
    """
    Ford point on road rule
    """

    LENGTH = 120
    TOLERANCE = 0.5
    PROJECTED_CRS = QgsCoordinateReferenceSystem("EPSG:2193")

    def id(self) -> str:
        return "ford_point"

    def name(self) -> str:
        return "Ford Point on Road"

    @staticmethod
    def get_ford_layer(
        context: CartographicGeneralizationRuleContext,
    ) -> QgsVectorLayer | None:
        return context.project_controller.layer_for_feature_type("transport_point")

    @staticmethod
    def get_road_layer(
        context: CartographicGeneralizationRuleContext,
    ) -> QgsVectorLayer | None:
        return context.project_controller.layer_for_feature_type("road_line")

    @staticmethod
    def get_ford_point_iterator(
        ford_point_layer: QgsVectorLayer,
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
                QgsExpression.createFieldEqualityExpression("type", "ford")
            )

        return ford_point_layer.getFeatures(request)

    @staticmethod
    def create_distance_area(ford_point_layer: QgsVectorLayer) -> QgsDistanceArea:
        da = QgsDistanceArea()
        da.setSourceCrs(
            ford_point_layer.crs(), QgsProject.instance().transformContext()
        )
        da.setEllipsoid(QgsProject.instance().ellipsoid())
        return da

    @classmethod
    def build_road_index(
        cls, road_layer: QgsVectorLayer, layer_extent: QgsRectangle
    ) -> QgsSpatialIndex:
        feature_it = road_layer.getFeatures(
            QgsFeatureRequest()
            .setDestinationCrs(
                cls.PROJECTED_CRS,
                QgsProject.instance().transformContext(),
            )
            .setFilterRect(layer_extent)
        )
        return QgsSpatialIndex(
            feature_it, flags=QgsSpatialIndex.Flag.FlagStoreFeatureGeometries
        )

    @classmethod
    def build_road_index_for_ford(
        cls,
        road_layer: QgsVectorLayer,
        ford_feature: QgsFeature,
        ct_projected: QgsCoordinateTransform,
    ) -> Tuple[Optional[QgsSpatialIndex], Optional[QgsPointXY], Optional[QgsRectangle]]:
        """
        Builds a localized spatial index of roads directly in the vicinity of
        a single ford point.
        """
        geom = ford_feature.geometry()
        if geom.isNull() or geom.isEmpty():
            return None, None, None

        ford_point = QgsPointXY(geom.constGet())
        ford_point_projected = ct_projected.transform(ford_point)
        ford_search_rect = QgsRectangle.fromCenterAndSize(
            ford_point_projected, cls.LENGTH, cls.LENGTH
        )
        road_index = cls.build_road_index(road_layer, ford_search_rect)
        return road_index, ford_point_projected, ford_search_rect

    @classmethod
    def resolve_road_geometry(
        cls,
        ford_point_projected: QgsPointXY,
        ford_search_rect: QgsRectangle,
        road_index: QgsSpatialIndex,
    ) -> Tuple[bool, float, Optional[QgsAbstractGeometry]]:
        road_features = road_index.intersects(ford_search_rect)
        if not road_features:
            return False, float("inf"), None

        on_road = False
        min_dist = float("inf")
        min_point = None
        all_road_parts: List[QgsGeometry] = []
        target_point_geom = QgsGeometry.fromPointXY(ford_point_projected)

        for road_feature in road_features:
            road_feature_geom = road_index.geometry(road_feature)

            all_road_parts.append(road_feature_geom)
            nearest = road_feature_geom.nearestPoint(target_point_geom)
            dist = nearest.distance(target_point_geom)

            if dist < min_dist:
                min_dist = dist
                min_point = nearest
            if dist < cls.TOLERANCE:
                on_road = True

        if not on_road or min_point is None or not all_road_parts:
            return False, min_dist, None

        buffer = min_point.buffer(cls.LENGTH, 20)
        road = QgsGeometry.unaryUnion(all_road_parts)
        road = road.mergeLines()
        road_intersection = buffer.intersection(road)

        closest_part: Optional[QgsAbstractGeometry] = None
        closest_dist = float("inf")
        for part in road_intersection.parts():
            part_geom = QgsGeometry(part.clone())
            dist = part_geom.distance(target_point_geom)
            if dist < closest_dist:
                closest_dist = dist
                closest_part = part.clone()

        return True, min_dist, closest_part

    @classmethod
    def update_product_geometry(
        cls,
        ford_layer: QgsVectorLayer,
        feature: QgsFeature,
        new_part: QgsAbstractGeometry,
    ) -> None:
        """
        Applies the sliced road segment as the product geometry on the ford feature.
        """
        new_geom = QgsGeometry(new_part.clone())

        GeometryUtils.set_product_geom(feature, new_geom)
        ford_layer.updateFeature(feature)
    def validate(
        self,
        context: CartographicGeneralizationRuleContext,
        parameters: Dict[str, object],
        feedback: RuleFeedback,
    ) -> List[CartographicIssue]:
        ford_layer = self.get_ford_layer(context)
        if not ford_layer:
            return []

        road_layer = self.get_road_layer(context)
        if not road_layer:
            return []

        ct_layer = QgsCoordinateTransform(
            context.extent.crs(), ford_layer.crs(), QgsProject.instance()
        )
        layer_extent = ct_layer.transformBoundingBox(context.extent)

        all_features = list(
            self.get_ford_point_iterator(ford_layer, layer_extent, fids=None)
        )

        ct_projected = QgsCoordinateTransform(
            ford_layer.crs(),
            self.PROJECTED_CRS,
            QgsProject.instance(),
        )

        failures = []
        total = len(all_features)
        for idx, f in enumerate(all_features):
            if total > 0:
                feedback.setProgress(int(idx / total * 100))

            road_index, ford_point_projected, search_rect = (
                self.build_road_index_for_ford(road_layer, f, ct_projected)
            )

            on_road, min_dist, closest_part = self.resolve_road_geometry(
                ford_point_projected, search_rect, road_index
            )

            if not on_road or closest_part is None:
                failures.append(
                    CartographicIssue(
                        fid=f.id(),
                        message=f"Ford not on road ({round(min_dist, 2)} m)",
                        sort_value=999999999999 - min_dist,
                        layer=ford_layer,
                    )
                )
                continue

            existing_product_geom = GeometryUtils.product_geom(f)

            ct = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:2193"),
                ford_layer.crs(),
                QgsProject.instance(),
            )
            closest_part.transform(ct)

            if (
                existing_product_geom is None
                or not existing_product_geom.constGet().fuzzyEqual(closest_part)
            ):
                failures.append(
                    CartographicIssue(
                        fid=f.id(),
                        message="Product geometry does not match road geometry",
                        sort_value=0,
                        layer=ford_layer,
                    )
                )

        feedback.setProgress(100)
        return failures

    def run(
        self,
        issues: List[CartographicIssue],
        context: CartographicGeneralizationRuleContext,
        parameters: Dict[str, object],
        feedback: RuleFeedback,
    ) -> None:
        ford_layer = self.get_ford_layer(context)
        if not ford_layer:
            return

        road_layer = self.get_road_layer(context)
        if not road_layer:
            return

        fids = [issue.fid for issue in issues]
        if not fids:
            return

        all_features = list(
            self.get_ford_point_iterator(ford_layer, layer_extent=None, fids=fids)
        )
        if not all_features:
            return

        ct_projected = QgsCoordinateTransform(
            ford_layer.crs(),
            self.PROJECTED_CRS,
            QgsProject.instance(),
        )

        ford_layer.beginEditCommand(self.name())
        total = len(all_features)

        for idx, f in enumerate(all_features):
            if total > 0:
                feedback.setProgress(int(idx / total * 100))

            road_index, ford_point_projected, search_rect = (
                self.build_road_index_for_ford(road_layer, f, ct_projected)
            )
            if not road_index or not ford_point_projected or not search_rect:
                continue

            on_road, min_dist, closest_part = self.resolve_road_geometry(
                ford_point_projected, search_rect, road_index
            )

            if not on_road or closest_part is None:
                feedback.push_feedback(
                    f"Ford {f.id()} skipped: not on road ({round(min_dist, 2)} m away)"
                )
                continue

            existing_product_geom = GeometryUtils.product_geom(f)

            ct = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:2193"),
                ford_layer.crs(),
                QgsProject.instance(),
            )
            closest_part.transform(ct)

            if (
                existing_product_geom is None
                or not existing_product_geom.constGet().fuzzyEqual(closest_part)
            ):
                feedback.push_feedback(
                    f"Updating product geometry for ford {f.id()} to match road geometry"
                )
                self.update_product_geometry(ford_layer, f, closest_part)

        ford_layer.endEditCommand()
        feedback.setProgress(100)
