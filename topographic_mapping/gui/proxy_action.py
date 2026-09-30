from typing import Optional

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import QAction, QMenu

from qgis.core import QgsVectorLayer, Qgis

from qgis.utils import iface


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

        if self._source_action.isCheckable():
            self._source_action.toggled.connect(self._source_action_triggered)
            self.toggled.connect(self._proxy_action_toggled)
        else:
            self.triggered.connect(self._proxy_action_triggered)

        self._source_action.enabledChanged.connect(self.setEnabled)
        self.setEnabled(self._source_action.isEnabled())

    def _proxy_action_triggered(self):
        self._source_action.trigger()

    def _proxy_action_toggled(self, checked: bool):
        if not checked:
            self._fallback_action.trigger()
        else:
            self._source_action.trigger()

    def _source_action_triggered(self, checked: bool):
        self.setChecked(checked)


class CompoundProxyAction(QAction):
    def __init__(
        self,
        title: str,
        source_actions: list[QAction],
        fallback_action: QAction,
        parent: Optional[QObject] = None,
    ):
        super().__init__(title, parent)

        self._source_actions = source_actions
        self._fallback_action = fallback_action

        for source_action in self._source_actions:
            if not source_action.isCheckable():
                raise AssertionError(
                    "Source action is not checkable for {}".format(title)
                )
            source_action.toggled.connect(self._source_action_triggered)
            source_action.enabledChanged.connect(self._source_action_enable_changed)
        self.toggled.connect(self._proxy_action_toggled)

        self._source_action_enable_changed()

    def _proxy_action_toggled(self, checked: bool):
        if checked:
            for source_action in self._source_actions:
                source_action.setChecked(True)

    def _source_action_triggered(self):
        all_checked = True
        for source_action in self._source_actions:
            all_checked &= source_action.isChecked()
        self.setChecked(all_checked)

    def _source_action_enable_changed(self):
        all_enabled = True

        for source_action in self._source_actions:
            all_enabled &= source_action.isEnabled()
        self.setEnabled(all_enabled)


class DigitizeTechniqueProxyAction(QAction):
    def __init__(
        self,
        title: str,
        source_actions: list[QAction],
        fallback_action: QAction,
        geometry_types: list[Qgis.GeometryType],
        parent: Optional[QObject] = None,
    ):
        super().__init__(title, parent)

        self._source_actions = source_actions
        self._geometry_types = geometry_types
        self._fallback_action = fallback_action

        for source_action in self._source_actions:
            if not source_action.isCheckable():
                raise AssertionError(
                    "Source action is not checkable for {}".format(title)
                )
            source_action.toggled.connect(self._source_action_triggered)
            source_action.enabledChanged.connect(self._source_action_enable_changed)
        self.toggled.connect(self._proxy_action_toggled)

        self._source_action_enable_changed()
        iface.currentLayerChanged.connect(self._source_action_enable_changed)

    def _proxy_action_toggled(self, checked: bool):
        if checked:
            for source_action in self._source_actions:
                source_action.trigger()

    def _source_action_triggered(self):
        all_checked = True
        for source_action in self._source_actions:
            all_checked &= source_action.isChecked()
        self.blockSignals(True)
        self.setChecked(all_checked)
        self.blockSignals(False)

    def _is_compatible_with_layer(self):
        active_layer = iface.activeLayer()
        if not isinstance(active_layer, QgsVectorLayer):
            return False

        if active_layer.geometryType() not in self._geometry_types:
            return False

        return active_layer.isEditable()

    def _source_action_enable_changed(self):
        _can_enable = self._is_compatible_with_layer()
        if not self._is_compatible_with_layer():
            _can_enable = False
        else:
            _can_enable = self._source_actions[0].isEnabled()

        self.setEnabled(_can_enable)
