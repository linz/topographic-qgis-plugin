"""
Label manager
"""

from qgis.PyQt.QtGui import QFontMetricsF

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


class LabelManager:
    """
    Responsible for labeling logic
    """

    def __init__(
        self, project_controller: ProjectController, state_manager: StateManager
    ):
        self._project_controller = project_controller
        self._state_manager = state_manager

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

        rc = QgsRenderContext()

        ref_scale = 50000.0
        if label_target.renderer() and label_target.renderer().referenceScale() > 0:
            ref_scale = label_target.renderer().referenceScale()
        rc.setRendererScale(ref_scale)
        rc.setSymbologyReferenceScale(ref_scale)
        dpi = 96.0
        rc.setMapToPixel(
            QgsMapToPixel.fromScale(ref_scale, label_target.crs().mapUnits(), dpi)
        )
        rc.setDpiTarget(dpi)
        rc.setScaleFactor(dpi / 25.4)

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
