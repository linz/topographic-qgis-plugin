"""
Tests for QGIS functionality.
"""

import unittest
from qgis.core import QgsProviderRegistry
from topographic_mapping.test.utilities import get_qgis_app

from topographic_mapping.test.test_base import TopographicTestBase

QGIS_APP = get_qgis_app()


class QGISTest(TopographicTestBase):
    """Test the QGIS Environment"""

    def test_qgis_environment(self):
        """QGIS environment has the expected providers"""

        r = QgsProviderRegistry.instance()
        self.assertIn("gdal", r.providerList())
        self.assertIn("ogr", r.providerList())


if __name__ == "__main__":
    unittest.main()
