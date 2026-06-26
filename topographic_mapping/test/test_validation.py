import unittest

from qgis.PyQt.QtCore import QCoreApplication

from qgis.core import QgsRectangle, QgsReferencedRectangle, QgsCoordinateReferenceSystem

from topographic_mapping.core.stored_object_manager import STORED_OBJECT_MANAGER
from topographic_mapping.core.validation_utils import ValidationUtils
from topographic_mapping.settings import VALIDATION_COMMAND
from .test_base import TopographicTestBase
from .utilities import get_qgis_app

QGIS_APP = None


class TestValidationUtils(TopographicTestBase):
    """Test suite for ValidationUtils."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        QCoreApplication.setOrganizationName("TopographicMapping_Test")
        QCoreApplication.setOrganizationDomain("test.topographic.local")
        QCoreApplication.setApplicationName("TopographicMapping_TestApp")

        global QGIS_APP
        QGIS_APP = get_qgis_app()

        VALIDATION_COMMAND.setValue("python3 /path/to/validator.py --verbose")

    def test_generate_validation_command(self):
        """
        Tests that the validation command and its arguments are constructed correctly.
        """

        test_db_path = "/fake/path/to/database.gpkg"
        program, arguments = ValidationUtils.generate_validation_command(test_db_path)

        expected_output_path = STORED_OBJECT_MANAGER.get_plugin_data_dir(
            "validation_results"
        ).as_posix()

        self.assertEqual(program, "python3")
        expected_args = [
            "/path/to/validator.py",
            "--verbose",
            "--output-dir",
            expected_output_path,
            "--db-path",
            test_db_path,
        ]

        self.assertEqual(arguments, expected_args)

    def test_generate_validation_command_with_native_extent(self):
        """
        Tests command generation with an extent already in EPSG:4326.
        """
        test_db_path = "/fake/path/to/database.gpkg"

        rect = QgsRectangle(10.5, 20.5, 30.5, 40.5)
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        extent = QgsReferencedRectangle(rect, crs)

        program, arguments = ValidationUtils.generate_validation_command(
            test_db_path, extent
        )
        expected_output_path = STORED_OBJECT_MANAGER.get_plugin_data_dir(
            "validation_results"
        ).as_posix()

        expected_args = [
            "/path/to/validator.py",
            "--verbose",
            "--output-dir",
            expected_output_path,
            "--db-path",
            test_db_path,
            "--bbox",
            "10.5",
            "20.5",
            "30.5",
            "40.5",
        ]
        self.assertEqual(arguments, expected_args)

    def test_generate_validation_command_with_transformed_extent(self):
        """Tests command generation verifying bounding boxes are correctly transformed to EPSG:4326."""
        test_db_path = "/fake/path/to/database.gpkg"

        rect = QgsRectangle(-111319.49, -111319.49, 111319.49, 111319.49)
        crs = QgsCoordinateReferenceSystem("EPSG:3857")
        extent = QgsReferencedRectangle(rect, crs)

        program, arguments = ValidationUtils.generate_validation_command(
            test_db_path, extent
        )

        self.assertIn("--bbox", arguments)
        bbox_idx = arguments.index("--bbox")

        xmin = float(arguments[bbox_idx + 1])
        ymin = float(arguments[bbox_idx + 2])
        xmax = float(arguments[bbox_idx + 3])
        ymax = float(arguments[bbox_idx + 4])

        self.assertAlmostEqual(xmin, -1.0, places=2)
        self.assertAlmostEqual(ymin, -1.0, places=2)
        self.assertAlmostEqual(xmax, 1.0, places=2)
        self.assertAlmostEqual(ymax, 1.0, places=2)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestValidationUtils)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
