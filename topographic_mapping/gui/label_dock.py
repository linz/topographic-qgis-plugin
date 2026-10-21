from qgis.PyQt import uic, sip

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QAction, QWidget, QLabel, QVBoxLayout, QGroupBox
from qgis.core import Qgis, QgsVectorLayer

from topographic_mapping.core import ProjectController, LabelManager

from .tool_dock import ToolDock
from .gui_utils import GuiUtils

Ui_LabelsBaseWidget, _ = uic.loadUiType(GuiUtils.get_ui_file_path("widget_labels.ui"))


class FeatureLabelSettingsWidget(QWidget, Ui_LabelsBaseWidget):
    """
    Configuration widget for feature label
    """

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setupUi(self)
        self._block_updates = False
        self._fid: int | None = None
        self._controller: ProjectController | None = None
        self._layer: QgsVectorLayer | None = None
        self.stacked_widget.setCurrentWidget(self.page_no_selection)
        self.text_string_line_edit.textChanged.connect(self._text_string_changed)

        self.font_size_spin_box.setClearValue(0, "Not set")
        self.line_offset_spin_box.setClearValue(0)

        self.font_word_spacing_spin_box.setClearValue(0, "Not set")
        self.font_letter_spacing_spin_box.setClearValue(0, "Not set")

        self.combo_char_placement.addItem("Default", Qgis.CurvedLabelMode.Default)
        self.combo_char_placement.addItem(
            "Stretch Character Spacing",
            Qgis.CurvedLabelMode.StretchCharacterSpacingToFitLine,
        )
        self.combo_char_placement.addItem(
            "Stretch Word Spacing", Qgis.CurvedLabelMode.StretchWordSpacingToFitLine
        )
        self.combo_char_placement.addItem(
            "Characters at Vertices", Qgis.CurvedLabelMode.PlaceCharactersAtVertices
        )

        self.combo_line_placement.addItem("On Line", Qgis.LabelLinePlacementFlag.OnLine)
        self.combo_line_placement.addItem(
            "Above Line", Qgis.LabelLinePlacementFlag.AboveLine
        )
        self.combo_line_placement.addItem(
            "Below Line", Qgis.LabelLinePlacementFlag.BelowLine
        )

        self.combo_text_anchor.addItem("Left", Qgis.TextAnchorPoint.StartOfText)
        self.combo_text_anchor.addItem("Centre", Qgis.TextAnchorPoint.CenterOfText)
        self.combo_text_anchor.addItem("Right", Qgis.TextAnchorPoint.EndOfText)

        self.font_size_spin_box.valueChanged.connect(self._font_size_changed)
        self.font_word_spacing_spin_box.valueChanged.connect(self._word_spacing_changed)
        self.font_letter_spacing_spin_box.valueChanged.connect(
            self._letter_spacing_changed
        )
        self.line_offset_spin_box.valueChanged.connect(self._line_offset_changed)
        self.combo_char_placement.currentIndexChanged.connect(
            self._char_placement_changed
        )
        self.combo_line_placement.currentIndexChanged.connect(
            self._line_placement_changed
        )
        self.combo_text_anchor.currentIndexChanged.connect(self._text_anchor_changed)
        self.anchor_widget.valueChanged.connect(self._label_anchor_changed)

    def set_project_controller(self, controller: ProjectController):
        self._controller = controller
        self._set_label_layer()
        self._controller.label_target_layer_changed.connect(self._set_label_layer)

    def _set_label_layer(self):
        if self._layer is not None and not sip.isdeleted(self._layer):
            # disconnect
            self._layer.selectionChanged.disconnect(self._selection_changed)

        self._layer = self._controller.label_target_layer()
        if self._layer is None:
            self.stacked_widget.setCurrentWidget(self.page_no_selection)
            return

        self._layer.selectionChanged.connect(self._selection_changed)
        self._selection_changed(self._layer.selectedFeatureIds(), [], False)

    def _selection_changed(self, selected, deselected, clear_and_select):
        if not selected or not self._layer:
            self._fid = None
            self.stacked_widget.setCurrentWidget(self.page_no_selection)
            return

        if len(selected) != 1:
            self._fid = None
            self.stacked_widget.setCurrentWidget(self.page_multiple_selection)
            return

        self.stacked_widget.setCurrentWidget(self.page_properties)

        self._fid = selected[0]

        feature = self._layer.getFeature(self._fid)
        self._block_updates = True
        self.text_string_line_edit.setText(feature[LabelManager.TEXT_SOURCE])

        char_placement = LabelManager.character_placement_from_string(
            feature[LabelManager.CHARACTER_PLACEMENT]
        )
        self.combo_char_placement.setCurrentIndex(
            self.combo_char_placement.findData(char_placement)
        )

        line_placement = LabelManager.line_placement_from_string(
            feature[LabelManager.LINE_PLACEMENT]
        )
        self.combo_line_placement.setCurrentIndex(
            self.combo_line_placement.findData(line_placement)
        )

        text_anchor = LabelManager.text_anchor_from_string(
            feature[LabelManager.TEXT_ANCHOR]
        )
        self.combo_text_anchor.setCurrentIndex(
            self.combo_text_anchor.findData(text_anchor)
        )

        if not feature[LabelManager.FONT_SIZE]:
            self.font_size_spin_box.clear()
        else:
            self.font_size_spin_box.setValue(feature[LabelManager.FONT_SIZE])

        if feature[LabelManager.LINE_OFFSET] is None:
            self.line_offset_spin_box.clear()
        else:
            self.line_offset_spin_box.setValue(feature[LabelManager.LINE_OFFSET])

        if feature[LabelManager.WORD_SPACING] is None:
            self.font_word_spacing_spin_box.clear()
        else:
            self.font_word_spacing_spin_box.setValue(feature[LabelManager.WORD_SPACING])
        if feature[LabelManager.CHARACTER_SPACING] is None:
            self.font_letter_spacing_spin_box.clear()
        else:
            self.font_letter_spacing_spin_box.setValue(
                feature[LabelManager.CHARACTER_SPACING]
            )

        if feature[LabelManager.LABEL_ANCHOR] is None:
            self.anchor_widget.setValue(0.5)
        else:
            self.anchor_widget.setValue(feature[LabelManager.LABEL_ANCHOR])

        self._update_widget_status()
        self._block_updates = False

    def _text_string_changed(self):
        if self._block_updates:
            return

        if not self._layer:
            return

        if not self._layer.isEditable():
            self._layer.startEditing()

        field_index = self._layer.fields().lookupField(LabelManager.TEXT_SOURCE)
        if field_index >= 0:
            self._layer.changeAttributeValue(
                self._fid, field_index, self.text_string_line_edit.text()
            )

    def _word_spacing_changed(self):
        if self._block_updates:
            return

        if not self._layer:
            return

        if not self._layer.isEditable():
            self._layer.startEditing()

        field_index = self._layer.fields().lookupField(LabelManager.WORD_SPACING)
        if field_index >= 0:
            self._layer.changeAttributeValue(
                self._fid, field_index, self.font_word_spacing_spin_box.value()
            )

    def _font_size_changed(self):
        if self._block_updates:
            return

        if not self._layer:
            return

        if not self._layer.isEditable():
            self._layer.startEditing()

        field_index = self._layer.fields().lookupField(LabelManager.FONT_SIZE)
        if field_index >= 0:
            self._layer.changeAttributeValue(
                self._fid, field_index, self.font_size_spin_box.value() or None
            )

    def _letter_spacing_changed(self):
        if self._block_updates:
            return

        if not self._layer:
            return

        if not self._layer.isEditable():
            self._layer.startEditing()

        field_index = self._layer.fields().lookupField(LabelManager.CHARACTER_SPACING)
        if field_index >= 0:
            self._layer.changeAttributeValue(
                self._fid, field_index, self.font_letter_spacing_spin_box.value()
            )

    def _char_placement_changed(self):
        if self._block_updates:
            return

        self._update_widget_status()

        if not self._layer:
            return

        if not self._layer.isEditable():
            self._layer.startEditing()

        field_index = self._layer.fields().lookupField(LabelManager.CHARACTER_PLACEMENT)
        if field_index >= 0:
            self._layer.changeAttributeValue(
                self._fid,
                field_index,
                LabelManager.character_placement_to_string(
                    self.combo_char_placement.currentData()
                ),
            )

    def _line_offset_changed(self):
        if self._block_updates:
            return

        if not self._layer:
            return

        if not self._layer.isEditable():
            self._layer.startEditing()

        field_index = self._layer.fields().lookupField(LabelManager.LINE_OFFSET)
        if field_index >= 0:
            self._layer.changeAttributeValue(
                self._fid, field_index, self.line_offset_spin_box.value()
            )

    def _line_placement_changed(self):
        if self._block_updates:
            return

        if not self._layer:
            return

        if not self._layer.isEditable():
            self._layer.startEditing()

        field_index = self._layer.fields().lookupField(LabelManager.LINE_PLACEMENT)
        if field_index >= 0:
            self._layer.changeAttributeValue(
                self._fid,
                field_index,
                LabelManager.line_placement_to_string(
                    self.combo_line_placement.currentData()
                ),
            )

    def _text_anchor_changed(self):
        if self._block_updates:
            return

        if not self._layer:
            return

        if not self._layer.isEditable():
            self._layer.startEditing()

        field_index = self._layer.fields().lookupField(LabelManager.TEXT_ANCHOR)
        if field_index >= 0:
            self._layer.changeAttributeValue(
                self._fid,
                field_index,
                LabelManager.text_anchor_to_string(
                    self.combo_text_anchor.currentData()
                ),
            )

    def _label_anchor_changed(self):
        if self._block_updates:
            return

        if not self._layer:
            return

        if not self._layer.isEditable():
            self._layer.startEditing()

        field_index = self._layer.fields().lookupField(LabelManager.LABEL_ANCHOR)
        if field_index >= 0:
            self._layer.changeAttributeValue(
                self._fid, field_index, self.anchor_widget.value()
            )

    def _update_widget_status(self):
        if self.combo_char_placement.currentData() == Qgis.CurvedLabelMode.Default:
            self.font_word_spacing_spin_box.setEnabled(True)
            self.font_letter_spacing_spin_box.setEnabled(True)
        elif (
            self.combo_char_placement.currentData()
            == Qgis.CurvedLabelMode.PlaceCharactersAtVertices
        ):
            self.font_word_spacing_spin_box.setEnabled(False)
            self.font_letter_spacing_spin_box.setEnabled(False)
        elif (
            self.combo_char_placement.currentData()
            == Qgis.CurvedLabelMode.StretchWordSpacingToFitLine
        ):
            self.font_word_spacing_spin_box.setEnabled(False)
            self.font_letter_spacing_spin_box.setEnabled(True)
        elif (
            self.combo_char_placement.currentData()
            == Qgis.CurvedLabelMode.StretchCharacterSpacingToFitLine
        ):
            self.font_word_spacing_spin_box.setEnabled(True)
            self.font_letter_spacing_spin_box.setEnabled(False)


class LabelDock(ToolDock):
    """
    A dock widget for display of labeling tools
    """

    target_layer_set = pyqtSignal(QgsVectorLayer)

    def __init__(self, edit_target_tool_action: QAction, parent):
        super().__init__(
            edit_target_tool_action, vertical_layout_offset=0, parent=parent
        )

        vl = self.main_layout()
        old_stretch = vl.itemAt(vl.count() - 1)
        vl.removeItem(old_stretch)

        group = QGroupBox()
        group.setTitle("Label Settings")

        vl.addWidget(group, 1)

        vl_child = QVBoxLayout()

        self._feature_settings_widget = FeatureLabelSettingsWidget()
        vl_child.addWidget(self._feature_settings_widget)

        group.setLayout(vl_child)

    def set_project_controller(self, controller: ProjectController):
        super().set_project_controller(controller)
        self._feature_settings_widget.set_project_controller(controller)
