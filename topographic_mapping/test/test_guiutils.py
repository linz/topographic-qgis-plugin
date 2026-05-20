"""
GUI Utils Test.
"""

import unittest
from topographic_mapping.gui.gui_utils import GuiUtils
from topographic_mapping.test.utilities import get_qgis_app


from topographic_mapping.test.test_base import TopographicTestBase

QGIS_APP = get_qgis_app()


class GuiUtilsTest(TopographicTestBase):
    """Test GuiUtils work."""

    def testGetIcon(self):
        """
        Tests get_icon
        """
        self.assertFalse(GuiUtils.get_icon("buffer.svg").isNull())
        self.assertTrue(GuiUtils.get_icon("not_an_icon.svg").isNull())

    @unittest.skip("no ui files yet")
    def testGetUiFilePath(self):
        """
        Tests get_ui_file_path svg path
        """
        self.assertTrue(GuiUtils.get_ui_file_path("dockwidget_main.ui"))
        self.assertIn(
            "dockwidget_main.ui", GuiUtils.get_ui_file_path("dockwidget_main.ui")
        )
        self.assertFalse(GuiUtils.get_ui_file_path("not_a_form.ui"))

    def testGetIconSvg(self):
        """
        Tests get_icon svg path
        """
        self.assertTrue(GuiUtils.get_icon_svg("buffer.svg"))
        self.assertIn("buffer.svg", GuiUtils.get_icon_svg("buffer.svg"))
        self.assertFalse(GuiUtils.get_icon_svg("not_an_icon.svg"))


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(GuiUtilsTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
