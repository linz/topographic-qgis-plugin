from typing import Optional

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import QAction, QMenu


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
            assert source_action.isCheckable()
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
        parent: Optional[QObject] = None,
    ):
        super().__init__(title, parent)

        self._source_actions = source_actions
        self._fallback_action = fallback_action

        for source_action in self._source_actions:
            assert source_action.isCheckable()
            source_action.toggled.connect(self._source_action_triggered)
            source_action.enabledChanged.connect(self._source_action_enable_changed)
        self.toggled.connect(self._proxy_action_toggled)

        self._source_action_enable_changed()

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

    def _source_action_enable_changed(self):
        self.setEnabled(self._source_actions[0].isEnabled())
