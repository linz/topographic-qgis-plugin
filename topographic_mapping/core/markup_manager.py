from qgis.PyQt.QtCore import QObject


class MarkupManager(QObject):
    """
    Manages markup functionality
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
