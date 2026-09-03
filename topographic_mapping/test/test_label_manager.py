"""
LabelManager Test.
"""

import unittest
from copy import deepcopy

from topographic_mapping.core import LabelManager
from .test_base import TopographicTestBase
from .utilities import get_qgis_app

QGIS_APP = get_qgis_app()


class LabelManagerTest(TopographicTestBase):
    """Test LabelManager works."""

    def test_default_definitions(self):
        defs = LabelManager.label_defaults_dict()
        self.assertTrue(defs)
        self.assertIsInstance(defs, dict)

        # should be cached
        defs = LabelManager.label_defaults_dict()
        self.assertTrue(defs)
        self.assertIsInstance(defs, dict)

    def test_style_for_feature_type(self):
        previous_defs = deepcopy(LabelManager._DEFINITIONS)

        LabelManager._DEFINITIONS = {
            "label_styles": {},
            "styles_for_feature_types": {
                "water": "water_body",
                "water_line": "water_body",
                "water_point": "water_body",
                "geographic_name": "place_name",
                "marine": {"reef": "water_body"},
            },
            "default_style": "place_name",
        }

        self.assertEqual(
            LabelManager.style_for_feature_type("train_stations", None), "place_name"
        )
        self.assertEqual(
            LabelManager.style_for_feature_type("water", None), "water_body"
        )
        self.assertEqual(
            LabelManager.style_for_feature_type("water_line", None), "water_body"
        )
        self.assertEqual(
            LabelManager.style_for_feature_type("water_point", None), "water_body"
        )
        self.assertEqual(
            LabelManager.style_for_feature_type("geographic_name", None), "place_name"
        )
        self.assertEqual(
            LabelManager.style_for_feature_type("marine", None), "place_name"
        )
        self.assertEqual(
            LabelManager.style_for_feature_type("marine", "rocks"), "place_name"
        )
        self.assertEqual(
            LabelManager.style_for_feature_type("marine", "reef"), "water_body"
        )

        LabelManager._DEFINITIONS = deepcopy(previous_defs)

    def test_style_definition(self):
        previous_defs = deepcopy(LabelManager._DEFINITIONS)

        LabelManager._DEFINITIONS = {
            "label_styles": {
                "water_body": {
                    "font": "Nimbus Sans LINZ",
                    "style": "Italic",
                    "colour": "process_blue",
                    "size": 6,
                    "placement": "AL",
                },
                "place_name": {
                    "font": "Nimbus Sans LINZ",
                    "style": "Regular",
                    "colour": "black",
                    "size": 7.5,
                    "placement": "AL",
                },
            },
            "styles_for_feature_types": {},
            "default_style": "place_name",
        }

        self.assertEqual(
            LabelManager.style_definition("water_body")["colour"], "process_blue"
        )
        self.assertEqual(LabelManager.style_definition("place_name")["colour"], "black")

        LabelManager._DEFINITIONS = deepcopy(previous_defs)

    def test_style_definition_for_feature_type(self):
        previous_defs = deepcopy(LabelManager._DEFINITIONS)

        LabelManager._DEFINITIONS = {
            "label_styles": {
                "water_body": {
                    "font": "Nimbus Sans LINZ",
                    "style": "Italic",
                    "colour": "process_blue",
                    "size": 6,
                    "placement": "AL",
                },
                "place_name": {
                    "font": "Nimbus Sans LINZ",
                    "style": "Regular",
                    "colour": "black",
                    "size": 7.5,
                    "placement": "AL",
                },
            },
            "styles_for_feature_types": {
                "water": "water_body",
                "water_line": "water_body",
                "water_point": "water_body",
                "geographic_name": "place_name",
                "marine": {"reef": "water_body"},
            },
            "default_style": "place_name",
        }

        self.assertEqual(
            LabelManager.style_definition_for_feature_type("train_stations", None)[
                "colour"
            ],
            "black",
        )
        self.assertEqual(
            LabelManager.style_definition_for_feature_type("water_line", None)[
                "colour"
            ],
            "process_blue",
        )
        self.assertEqual(
            LabelManager.style_definition_for_feature_type("marine", "rocks")["colour"],
            "black",
        )
        self.assertEqual(
            LabelManager.style_definition_for_feature_type("marine", "reef")["colour"],
            "process_blue",
        )

        LabelManager._DEFINITIONS = deepcopy(previous_defs)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(LabelManagerTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
