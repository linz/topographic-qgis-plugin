import unittest

from qgis.PyQt.QtCore import Qt, QModelIndex
from qgis.PyQt.QtGui import QColor

from .test_base import TopographicTestBase
from .utilities import get_qgis_app

from topographic_mapping.core import ValidationResultModel

QGIS_APP = get_qgis_app()


class TestValidationResultModel(TopographicTestBase):
    """Test suite for the ValidationResultModel."""

    def setUp(self):
        super().setUp()

        self.sample_json = {
            "feature_not_on_layers_about": "If True - does not lie on layer.",
            "feature_not_on_layers": True,
            "query_rule_about": "If True - meets query rule.",
            "query_rules": False,
            "missing_desc_rule": True,
            "validation_completed_message": "All processes completed successfully.",
        }

        self.model = ValidationResultModel()
        self.model.set_data(self.sample_json)

    def test_row_and_column_counts(self):
        """Tests that the model dimensions match the data."""
        self.assertEqual(self.model.rowCount(), 3)
        self.assertEqual(self.model.columnCount(), 3)

    def test_headers(self):
        """Tests that the header data returns the correct strings."""
        self.assertEqual(
            self.model.headerData(
                0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            ),
            "Result",
        )
        self.assertEqual(
            self.model.headerData(
                1, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            ),
            "Rule",
        )
        self.assertEqual(
            self.model.headerData(
                2, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            ),
            "Description",
        )
        self.assertIsNone(
            self.model.headerData(
                0, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole
            )
        )

    def test_display_role_data(self):
        """Tests that the text and emojis are generated correctly."""
        # Test Row 0 (feature_not_on_layers -> True)
        idx_0_0 = self.model.index(0, 0)
        idx_0_1 = self.model.index(0, 1)
        idx_0_2 = self.model.index(0, 2)

        self.assertEqual(self.model.data(idx_0_0, Qt.ItemDataRole.DisplayRole), "❌")
        self.assertEqual(
            self.model.data(idx_0_1, Qt.ItemDataRole.DisplayRole),
            "Feature Not On Layers",
        )
        self.assertEqual(
            self.model.data(idx_0_2, Qt.ItemDataRole.DisplayRole),
            "does not lie on layer.",
        )

        # Test Row 1 (query_rules -> False). Also verifies plural fallback logic.
        idx_1_0 = self.model.index(1, 0)
        idx_1_1 = self.model.index(1, 1)
        idx_1_2 = self.model.index(1, 2)

        self.assertEqual(self.model.data(idx_1_0, Qt.ItemDataRole.DisplayRole), "✅")
        self.assertEqual(
            self.model.data(idx_1_1, Qt.ItemDataRole.DisplayRole), "Query Rules"
        )
        self.assertEqual(
            self.model.data(idx_1_2, Qt.ItemDataRole.DisplayRole), "meets query rule."
        )

    def test_missing_description_fallback(self):
        """Tests that a missing '_about' key falls back safely."""
        idx_2_2 = self.model.index(2, 2)
        self.assertEqual(
            self.model.data(idx_2_2, Qt.ItemDataRole.DisplayRole),
            "No description provided.",
        )

    def test_background_role_colors(self):
        """Tests that the background colors accurately reflect the true/false status."""
        idx_true = self.model.index(0, 0)  # feature_not_on_layers is True
        idx_false = self.model.index(1, 0)  # query_rules is False

        color_true = self.model.data(idx_true, Qt.ItemDataRole.BackgroundRole)
        color_false = self.model.data(idx_false, Qt.ItemDataRole.BackgroundRole)

        self.assertIsInstance(color_true, QColor)
        self.assertEqual(color_true.name(), "#fff0f0")

        self.assertIsInstance(color_false, QColor)
        self.assertEqual(color_false.name(), "#f0fff0")

    def test_text_alignment_and_tooltips(self):
        """Tests alignment and tooltip roles."""
        idx_status = self.model.index(0, 0)
        idx_desc = self.model.index(0, 2)

        # Status column should be centered
        self.assertEqual(
            self.model.data(idx_status, Qt.ItemDataRole.TextAlignmentRole),
            Qt.AlignmentFlag.AlignCenter,
        )

        # Description column should be left-aligned
        self.assertEqual(
            self.model.data(idx_desc, Qt.ItemDataRole.TextAlignmentRole),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

        # Description column should have a tooltip
        self.assertEqual(
            self.model.data(idx_desc, Qt.ItemDataRole.ToolTipRole),
            "does not lie on layer.",
        )

    def test_summary_message_property(self):
        """Tests that the summary message is extracted cleanly."""
        self.assertEqual(
            self.model.summary_message, "All processes completed successfully."
        )

    def test_reload_data(self):
        """
        Test loading new results
        """
        self.model.set_data(
            {
                "feature_not_on_layers_about": "If True - does not lie on layer.",
                "feature_not_on_layers": True,
                "validation_completed_message": "All processes completed successfully.",
            }
        )
        self.assertEqual(self.model.rowCount(), 1)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestValidationResultModel)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
