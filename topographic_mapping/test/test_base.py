from pathlib import Path
import unittest


class TopographicTestBase(unittest.TestCase):
    """
    Test base class
    """

    @staticmethod
    def get_test_data_path(file_name: str) -> Path:
        """
        Gets the full path to a test data file
        """
        return Path(__file__).parent / "data" / file_name
