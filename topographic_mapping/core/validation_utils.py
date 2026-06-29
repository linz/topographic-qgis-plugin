from pathlib import Path
import json

from qgis.PyQt.QtCore import QDate

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

    REPORT_FILE_NAME = "validation_summary_report.json"

    @staticmethod
    def result_path() -> Path:
        """
        Returns the path containing validation results
        """
        output_path = STORED_OBJECT_MANAGER.get_plugin_data_dir("validation_results")
        return output_path

    @staticmethod
    def get_last_validation_results() -> dict | None:
        """
        Retrieves the results of the last validation run
        """
        output_path = ValidationUtils.result_path()
        if not output_path.exists():
            return None

        report_file_name = output_path / ValidationUtils.REPORT_FILE_NAME
        if not report_file_name.exists():
            return None

        with open(report_file_name, "rt", encoding="utf8") as f:
            try:
                return json.loads(f.read())
            except json.JSONDecodeError:
                return None

    @staticmethod
    def generate_validation_command(
        db_path: str,
        extent: QgsReferencedRectangle | None = None,
        date: QDate | None = None,
    ) -> tuple[str, list[str]]:
        """
        Generates the command and arguments to use to launch the validation script
        """
        output_path = ValidationUtils.result_path()

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

        if date is not None and date.isValid():
            arguments.extend(["--date", date.toString("yyyy-MM-dd")])

        return program, arguments
