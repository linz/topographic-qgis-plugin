import unittest

from qgis.PyQt.QtCore import QCoreApplication, QDate

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

    def test_generate_validation_command_with_valid_date(self):
        """
        Tests that a valid QDate is formatted correctly and appended.
        """
        test_db_path = "/fake/path/to/database.gpkg"
        test_date = QDate(2023, 10, 31)

        program, arguments = ValidationUtils.generate_validation_command(
            test_db_path, date=test_date
        )

        self.assertIn("--date", arguments)
        date_idx = arguments.index("--date")
        self.assertEqual(arguments[date_idx + 1], "2023-10-31")

    def test_generate_validation_command_with_invalid_date(self):
        """
        Tests that an invalid QDate is gracefully ignored.
        """
        test_db_path = "/fake/path/to/database.gpkg"
        test_date = QDate()  # Default constructor creates an invalid date

        self.assertFalse(test_date.isValid())

        program, arguments = ValidationUtils.generate_validation_command(
            test_db_path, date=test_date
        )

        self.assertNotIn("--date", arguments)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestValidationUtils)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
