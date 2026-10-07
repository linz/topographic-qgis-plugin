"""
GUI Enums
"""

from enum import Enum, auto


class ToolGroup(Enum):
    """
    Enum representing tool groups
    """

    Private = auto()
    Favorites = auto()
    Editing = auto()
    Digitizing = auto()
    Labeling = auto()
    LabelingReference = auto()
    Markup = auto()

    def to_string(self) -> str:
        return {
            ToolGroup.Editing: "Topographic editing",
            ToolGroup.Digitizing: "Digitize feature",
            ToolGroup.Labeling: "Labeling",
            ToolGroup.LabelingReference: "Label Reference Tools",
            ToolGroup.Markup: "Markup",
        }[self]


class PluginTool(Enum):
    """
    Enum representing inbuilt (plugin specific) tools
    """

    MarkupSelected = auto()
    GoToNextMarkup = auto()
    GoToPreviousMarkup = auto()
    ToggleSelectedMarkup = auto()
    DeleteCheckedMarkup = auto()
    ClearMarkup = auto()
    ReconsiderMarkup = auto()

    ChangeFeatureClass = auto()
    CopyToFeatureClass = auto()
    PastryDelete = auto()
    PastryCut = auto()
    ClearProductEdits = auto()

    SelectLabels = auto()
    CreateLabel = auto()
    ResetLabel = auto()
    RewrapLabel = auto()
    RedrawLabel = auto()

    CreateBufferInAnnotation1 = auto()
    CreateBufferInAnnotation2 = auto()
    ClearAnnotations = auto()
