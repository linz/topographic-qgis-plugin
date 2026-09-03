"""
Label manager
"""

import json
from typing import Dict
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsVectorLayer,
    QgsFeatureRequest,
    QgsFeature,
    QgsLineString,
    QgsRenderContext,
    QgsTextDocument,
    QgsTextDocumentMetrics,
    QgsMapToPixel,
)

from .project_controller import ProjectController
from .state_manager import StateManager

RESOURCES_DIR = Path(__file__) / ".." / ".." / "resources"


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

    def create_labels(self):
        """
        Creates labels for the active target features
        """
        if not self._state_manager.target_layer():
            # todo - warning
            print(" no target layer")
            return

        target_fids = self._state_manager.target_layer().selectedFeatureIds()
        if not target_fids:
            # todo - warning
            print(" no target features")
            return

        self.create_labels_for_features(self._state_manager.target_layer(), target_fids)

    def label_metrics(
        self, render_context: QgsRenderContext, text: str
    ) -> QgsTextDocumentMetrics:
        label_target = self._project_controller.label_target_layer()
        if not label_target:
            return

        # TODO -- define from dictionary!
        label_settings = label_target.labeling().settings()
        text_format = label_settings.format()

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

    def get_label_width_for_feature(self, layer: QgsVectorLayer, fid: int) -> float:
        """
        Returns the required map unit width for a feature's label
        """
        label_target = self._project_controller.label_target_layer()
        if not label_target:
            # todo - warning
            return 0

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
            # todo -- move to project controller
            feature_type = feature["type"]

            label_text = feature["name"]

            document_metrics = self.label_metrics(rc, label_text)

            text_width_painter_units = document_metrics.documentSize(
                Qgis.TextLayoutMode.Labeling, Qgis.TextOrientation.Horizontal
            ).width()

            text_width_map_units = rc.convertToMapUnits(
                text_width_painter_units, Qgis.RenderUnit.Pixels
            )
            return label_text, text_width_map_units

        return 0

    def create_labels_for_features(self, layer: QgsVectorLayer, fids):
        """
        Creates labels for the specified features
        """
        label_target = self._project_controller.label_target_layer()
        if not label_target:
            # todo - warning
            return

        if not label_target.isEditable():
            label_target.startEditing()

        rc = self.create_render_context()

        request = QgsFeatureRequest()
        request.setFilterFids(fids)
        # todo - project not private
        request.setDestinationCrs(
            label_target.crs(), self._project_controller._project.transformContext()
        )
        for feature in layer.getFeatures(request):
            # todo -- move to project controller
            feature_type = feature["type"]

            label_text = feature["name"]

            document_metrics = self.label_metrics(rc, label_text)

            text_width_painter_units = document_metrics.documentSize(
                Qgis.TextLayoutMode.Labeling, Qgis.TextOrientation.Horizontal
            ).width()

            text_width_map_units = rc.convertToMapUnits(
                text_width_painter_units, Qgis.RenderUnit.Pixels
            )

            ref_point = feature.geometry().centroid().asPoint()

            label_feature = QgsFeature(label_target.fields())
            label_feature["text_string"] = label_text
            geom = QgsLineString(
                [ref_point, ref_point.project(text_width_map_units, 90)]
            )
            label_feature.setGeometry(geom)

            label_target.addFeature(label_feature)
