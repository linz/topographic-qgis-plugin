from typing import Optional

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import QAction


class ProxyAction(QAction):
    def __init__(
        self,
        title: str,
        source_action: QAction,
        fallback_action: QAction,
        parent: Optional[QObject] = None,
    ):
        super().__init__(title, parent)

        self._source_action = source_action
        self._fallback_action = fallback_action

        self._source_action.toggled.connect(self._source_action_triggered)
        self.toggled.connect(self._proxy_action_toggled)

    def _proxy_action_toggled(self, checked: bool):
        if not checked:
            self._fallback_action.trigger()
        else:
            self._source_action.trigger()

    def _source_action_triggered(self, checked: bool):
        self.setChecked(checked)
