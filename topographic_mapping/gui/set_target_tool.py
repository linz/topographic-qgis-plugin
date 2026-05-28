from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsVectorLayer, QgsIdentifyContext, QgsGeometry, QgsProject
from qgis.gui import QgsMapToolIdentify, QgsMapMouseEvent, QgsIdentifyMenu, QgsMapCanvas

from ..core import LayerUtils

class SetTargetTool(QgsMapToolIdentify):
    """
    Custom map tool for setting edit targets
    """

    target_set = pyqtSignal(QgsVectorLayer, int)

    def __init__(self, canvas: QgsMapCanvas):
        super().__init__(canvas)

    def canvasReleaseEvent(self, event: QgsMapMouseEvent):
        context = QgsIdentifyContext()
        layer_list = LayerUtils.valid_edit_target_layers(QgsProject.instance())

        geom = QgsGeometry.fromPointXY(
            self.toMapCoordinates(event.position().toPoint())
        )

        identify_results = self.identify(
            geom,
            QgsMapToolIdentify.IdentifyMode.TopDownAll,
            layer_list,
            QgsMapToolIdentify.Type.VectorLayer,
            context,
        )
        menu = QgsIdentifyMenu(self.canvas())
        menu.setExecWithSingleResult(True)
        menu.setAllowMultipleReturn(False)
        res = menu.exec(identify_results, event.globalPosition().toPoint())
        if not res:
            return

        target = res[0]
        self.target_set.emit(target.mLayer, target.mFeature.id())
