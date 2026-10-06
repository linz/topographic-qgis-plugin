"""
Map tool for interactively re-digitizing line geometry for labeled features.
"""

from qgis.core import (
    Qgis,
    QgsFeature,
    QgsGeometry,
)
from qgis.gui import (
    QgsAdvancedDigitizingDockWidget,
    QgsMapCanvas,
    QgsMapToolCapture,
    QgsMapToolDigitizeFeature,
    QgsRubberBand,
)

from topographic_mapping.core import LabelManager, ProjectController


class RedrawLabelTool(QgsMapToolDigitizeFeature):
    """
    A map tool for selecting a labeled feature and re-drawing its line geometry.
    """

    def __init__(
        self,
        canvas: QgsMapCanvas,
        cad_dock: QgsAdvancedDigitizingDockWidget,
        label_manager: LabelManager,
        project_controller: ProjectController,
    ):
        super().__init__(canvas, cad_dock, QgsMapToolCapture.CaptureMode.CaptureLine)

        self._canvas: QgsMapCanvas = canvas
        self._label_manager: LabelManager = label_manager
        self._project_controller: ProjectController = project_controller
        self._target_feature_id: int | None = None

        self._preview_rubber_band: QgsRubberBand | None = None

        self.digitizingCompleted.connect(self._on_digitizing_completed)

        self.transientGeometryChanged.connect(self._on_transient_geometry_changed)

    def set_target_feature(self, feature_id: int) -> None:
        """
        Explicitly sets the target feature ID to re-digitize.
        """
        self._target_feature_id = feature_id
        if not self._preview_rubber_band and self._target_feature_id is not None:
            self._preview_rubber_band = self.createRubberBandForLayer(
                self.layer(), {self._target_feature_id}
            )
            self._preview_rubber_band.setRenderedComponents(
                Qgis.RubberBandComponent.PreviewItems
            )

    def activate(self) -> None:
        if self._project_controller.label_target_layer():
            self.setLayer(self._project_controller.label_target_layer())
        if not self._preview_rubber_band and self._target_feature_id is not None:
            self._preview_rubber_band = self.createRubberBandForLayer(
                self.layer(), {self._target_feature_id}
            )
            self._preview_rubber_band.setRenderedComponents(
                Qgis.RubberBandComponent.PreviewItems
            )

        super().activate()

    def deactivate(self) -> None:
        if self._preview_rubber_band:
            self._preview_rubber_band = None
        super().deactivate()

    def _on_transient_geometry_changed(self, geometry):
        if self._preview_rubber_band:
            self._preview_rubber_band.setToGeometry(geometry, geometry.crs())

    def _on_digitizing_completed(self, digitized_feature: QgsFeature) -> None:
        """
        Slot triggered when new line digitizing is finished.
        Applies the captured geometry to the selected label feature.
        """
        new_geom: QgsGeometry = digitized_feature.geometry()
        if not new_geom or new_geom.isEmpty():
            return

        if not self.layer() or self._target_feature_id is None:
            return

        if not self.layer().isEditable():
            self.layer().startEditing()

        self.layer().beginEditCommand("Redraw label line geometry")
        self.layer().changeGeometry(self._target_feature_id, new_geom)
        self.layer().endEditCommand()

        self._canvas.refresh()
