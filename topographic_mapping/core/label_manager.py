"""
Label manager
"""

import json
from dataclasses import dataclass
from typing import Dict
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsVectorLayer,
    QgsFeatureRequest,
    QgsFeature,
    QgsRenderContext,
    QgsTextDocument,
    QgsTextDocumentMetrics,
    QgsMapToPixel,
)

from .project_controller import ProjectController
from .state_manager import StateManager

RESOURCES_DIR = Path(__file__) / ".." / ".." / "resources"


@dataclass()
class LabelProperties:
    """
    Encapsulates label properties
    """

    label_text: str | None = None
    label_feature: QgsFeature | None = None
    label_width: float | None = None


class LabelManager:
    """
    Responsible for labeling logic
    """

    _DEFINITIONS = {}

    def __init__(
        self, project_controller: ProjectController, state_manager: StateManager
    ):
        self._project_controller = project_controller
        self._state_manager = state_manager

    @staticmethod
    def label_defaults_dict() -> Dict:
        if not LabelManager._DEFINITIONS:
            definition_file = (RESOURCES_DIR / "label_defaults.json").resolve()
            with open(definition_file) as json_file:
                LabelManager._DEFINITIONS = json.load(json_file)

        return LabelManager._DEFINITIONS

    @staticmethod
    def style_for_feature_type(feature_type: str, sub_type: str | None) -> str:
        """
        Returns the label style name for a given feature type and subtype
        """
        label_definitions = LabelManager.label_defaults_dict()
        if feature_type not in label_definitions["styles_for_feature_types"]:
            return label_definitions["default_style"]

        styles_for_feature_types = label_definitions["styles_for_feature_types"]
        if isinstance(styles_for_feature_types[feature_type], str):
            return styles_for_feature_types[feature_type]

        if sub_type in styles_for_feature_types[feature_type]:
            return styles_for_feature_types[feature_type][sub_type]

        return label_definitions["default_style"]

    @staticmethod
    def style_definition(style_name: str) -> Dict[str, object]:
        """
        Returns the style definition for the specified style
        """
        label_definitions = LabelManager.label_defaults_dict()
        return label_definitions["label_styles"][style_name]

    @staticmethod
    def style_definition_for_feature_type(
        feature_type: str, sub_type: str | None
    ) -> Dict[str, object]:
        """
        Returns the style definition for the specified feature type
        """
        style_name = LabelManager.style_for_feature_type(feature_type, sub_type)
        return LabelManager.style_definition(style_name)

    def label_metrics(
        self, render_context: QgsRenderContext, text: str, label_feature: QgsFeature
    ) -> QgsTextDocumentMetrics | None:
        label_target = self._project_controller.label_target_layer()
        if not label_target:
            return None

        expression_context = label_target.createExpressionContext()
        expression_context.setFeature(label_feature)
        render_context.setExpressionContext(expression_context)

        label_settings = label_target.labeling().settings()
        text_format = label_settings.format()

        text_format.setDataDefinedProperties(label_settings.dataDefinedProperties())
        text_format.updateDataDefinedProperties(render_context)

        document = QgsTextDocument.fromTextAndFormat([text], text_format)

        text_metrics = QgsTextDocumentMetrics.calculateMetrics(
            document, text_format, render_context
        )
        return text_metrics

    def create_render_context(self) -> QgsRenderContext:
        """
        Creates a render context suitable for labeling calculations
        """
        label_target = self._project_controller.label_target_layer()

        rc = QgsRenderContext()

        ref_scale = 50000.0
        if (
            label_target
            and label_target.renderer()
            and label_target.renderer().referenceScale() > 0
        ):
            ref_scale = label_target.renderer().referenceScale()
        rc.setRendererScale(ref_scale)
        rc.setSymbologyReferenceScale(ref_scale)
        dpi = 96.0
        rc.setMapToPixel(
            QgsMapToPixel.fromScale(
                ref_scale,
                label_target.crs().mapUnits()
                if label_target
                else Qgis.DistanceUnit.Unknown,
                dpi,
            )
        )
        rc.setDpiTarget(dpi)
        rc.setScaleFactor(dpi / 25.4)
        return rc

    def create_label_feature(self, source_feature: QgsFeature) -> QgsFeature:
        """
        Creates a label feature corresponding to a source feature
        """
        # todo -- move to project controller
        feature_type = source_feature["type"]
        try:
            sub_type = source_feature["subtype"]
        except KeyError:
            sub_type = None

        style_defaults = LabelManager.style_definition_for_feature_type(
            feature_type, sub_type
        )

        new_feature = QgsFeature(self._project_controller.label_target_layer().fields())
        new_feature["text_string"] = source_feature["name"]
        for p, v in style_defaults.items():
            new_feature[p] = v

        return new_feature

    def get_width_for_label(
        self, label_feature: QgsFeature, render_context: QgsRenderContext
    ) -> float:
        """
        Returns the required map unit width for a feature's label
        """
        document_metrics = self.label_metrics(
            render_context, label_feature["text_string"], label_feature
        )

        # grow by a small amount to ensure text fully fits at different sizes/styles/zoom levels
        text_width_painter_units = (
            document_metrics.documentSize(
                Qgis.TextLayoutMode.Labeling, Qgis.TextOrientation.Horizontal
            ).width()
            * 1.02
        )

        return render_context.convertToMapUnits(
            text_width_painter_units, Qgis.RenderUnit.Pixels
        )

    def get_label_properties_for_feature(
        self, layer: QgsVectorLayer, fid: int
    ) -> LabelProperties:
        """
        Returns the required map unit width for a feature's label
        """
        label_target = self._project_controller.label_target_layer()
        if not label_target:
            return LabelProperties()

        if not label_target.isEditable():
            label_target.startEditing()

        rc = self.create_render_context()

        request = QgsFeatureRequest()
        request.setFilterFid(fid)
        # todo - project not private
        request.setDestinationCrs(
            label_target.crs(), self._project_controller._project.transformContext()
        )
        for feature in layer.getFeatures(request):
            label_feature = self.create_label_feature(feature)
            text_width_map_units = self.get_width_for_label(label_feature, rc)

            return LabelProperties(
                label_feature["text_string"], label_feature, text_width_map_units
            )

        return LabelProperties()
