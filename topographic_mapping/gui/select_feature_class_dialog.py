"""
A dialog for selecting feature classes
"""

from typing import Tuple

from qgis.PyQt.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QDialogButtonBox,
    QLabel,
)

from .feature_type_widget import FeatureTypeWidget


class SelectFeatureClassDialog(QDialog):
    """
    A dialog for selecting feature classes
    """

    def __init__(self, feature_types, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("Select Feature Class")

        vl = QVBoxLayout()

        self.label = QLabel("Select a feature class")
        vl.addWidget(self.label)

        self._feature_type_widget = FeatureTypeWidget()
        vl.addWidget(self._feature_type_widget, 1)
        self._feature_type_widget.set_feature_types(feature_types)

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        vl.addWidget(self._button_box)
        self.setLayout(vl)

        self._feature_type_widget.selected_feature_type_changed.connect(
            self._selected_feature_type_changed
        )

        self._button_box.rejected.connect(self.reject)
        self._button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.accept
        )
        self._button_box.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)

    def _selected_feature_type_changed(
        self, parent_feature_type: str, feature_type: str
    ):
        self._button_box.button(QDialogButtonBox.StandardButton.Apply).setEnabled(
            bool(parent_feature_type)
        )

    def new_feature_type(self) -> Tuple[str | None, str | None]:
        """
        Returns the new feature type for the selected features
        """
        return self._feature_type_widget.selected_feature_type()
