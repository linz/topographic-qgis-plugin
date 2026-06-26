from qgis.core import (
    QgsRunProcess,
    QgsReferencedRectangle,
    QgsProject,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsCsException,
)

from .stored_object_manager import STORED_OBJECT_MANAGER
from ..settings import VALIDATION_COMMAND


class ValidationUtils:
    """
    Contains utilities for the validation tools
    """

    @staticmethod
    def generate_validation_command(
        db_path: str, extent: QgsReferencedRectangle | None = None
    ) -> tuple[str, list[str]]:
        """
        Generates the command and arguments to use to launch the validation script
        """
        output_path = STORED_OBJECT_MANAGER.get_plugin_data_dir("validation_results")

        program, *arguments = QgsRunProcess.splitCommand(VALIDATION_COMMAND.value())
        arguments.extend(["--output-dir", output_path.as_posix()])
        arguments.extend(["--db-path", db_path])

        if extent is not None:
            transform = QgsCoordinateTransform(
                extent.crs(),
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance().transformContext(),
            )
            transform.setBallparkTransformsAreAppropriate(True)
            transform.setAllowFallbackTransforms(True)

            try:
                extent_4326 = transform.transformBoundingBox(extent)
                arguments.extend(
                    [
                        "--bbox",
                        str(extent_4326.xMinimum()),
                        str(extent_4326.yMinimum()),
                        str(extent_4326.xMaximum()),
                        str(extent_4326.yMaximum()),
                    ]
                )
            except QgsCsException:
                pass

        return program, arguments
