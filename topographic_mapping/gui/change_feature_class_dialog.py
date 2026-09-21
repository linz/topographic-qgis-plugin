"""
A dialog for changing the feature classes of the current selection
"""

from qgis.PyQt.QtWidgets import (
    QWidget,
)

from .select_feature_class_dialog import SelectFeatureClassDialog


class ChangeFeatureClassDialog(SelectFeatureClassDialog):
    """
    A dialog for changing the feature classes of the current selection
    """

    def __init__(self, feature_types, parent: QWidget | None = None):
        super().__init__(feature_types, parent)

        self.setWindowTitle("Change Selected Feature Class")
        self.label.setText("New class for selected features")
