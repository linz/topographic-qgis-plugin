from typing import Optional

from qgis.PyQt.QtCore import Qt, QSize, QEvent, pyqtSignal, QItemSelection
from qgis.PyQt.QtGui import QPalette, QCursor
from qgis.PyQt.QtWidgets import (
    QToolButton,
    QActionGroup,
    QSizePolicy,
    QAction,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QGroupBox,
    QMenu,
    QTreeView,
)
from qgis.core import Qgis, QgsVectorLayer, QgsMapLayer
from qgis.gui import (
    QgsDockWidget,
    QgsCollapsibleGroupBox,
    QgsConfigureShortcutsDialog,
    QgsMapLayerComboBox,
    QgsFilterLineEdit,
)

from .feature_type_model import FeatureTypeTreeModel, FeatureTypeFilterProxyModel
from .responsive_table_widget import ResponsiveTableWidget
from ..core import ProjectController, StateManager
from topographic_mapping.settings import FAVORITES


class ToolDock(QgsDockWidget):
    """
    A dock widget for display of a set of tools
    """

    target_layer_set = pyqtSignal(QgsVectorLayer)

    def __init__(self, edit_target_tool_action: QAction, parent):
        super().__init__(parent)

        self._controller: ProjectController | None = None
        self._state_manager: StateManager | None = None

        self._vlayout = QVBoxLayout()
        self._vlayout.setContentsMargins(0, 10, 6, 0)
        self._vlayout.addWidget(QLabel("Current edit target"))

        hl = QHBoxLayout()
        self._target_layer_combo = QgsMapLayerComboBox()
        self._target_layer_combo.setFilters(
            Qgis.LayerFilter.WritableLayer | Qgis.LayerFilter.HasGeometry
        )
        hl.addWidget(self._target_layer_combo, 1)

        self._activate_edit_target_tool_button = self._create_button_for_action(
            edit_target_tool_action, edit_target_tool_action.property("description")
        )
        self._activate_edit_target_tool_button.setProperty("_no_favorite", True)
        hl.addWidget(self._activate_edit_target_tool_button)

        self._vlayout.addLayout(hl)

        self._description_label = QLabel()
        self._description_label.setWordWrap(True)
        self._vlayout.addWidget(self._description_label)

        self._digitize_widget = QWidget()
        digitize_vl = QVBoxLayout()
        digitize_vl.setContentsMargins(0, 0, 0, 0)
        digitize_vl.addWidget(QLabel("New feature type"))
        self._filter_types_widget = QgsFilterLineEdit()
        self._filter_types_widget.setShowSearchIcon(True)
        self._filter_types_widget.setPlaceholderText("Filter types")
        self._filter_types_widget.textChanged.connect(self._feature_type_filter_changed)
        digitize_vl.addWidget(self._filter_types_widget)
        self._feature_type_view = QTreeView()
        self._feature_type_view.setHeaderHidden(True)
        self._feature_type_model: FeatureTypeTreeModel | None = None
        self._feature_type_proxy_model: FeatureTypeFilterProxyModel | None = None
        self._filter_types_widget.cleared.connect(self._feature_type_view.expandAll)

        digitize_vl.addWidget(self._feature_type_view, 1)
        self._digitize_widget.setLayout(digitize_vl)
        self._vlayout.addWidget(self._digitize_widget)

        self._vlayout.addStretch()
        _widget = QWidget(self)
        _widget.setLayout(self._vlayout)
        self.setWidget(_widget)

        self._tool_groups = {}

        self._actions = []

        self._favorites = []
        self._favorites_group = self._create_tool_group("Favorites", collapsible=False)
        self._favorites_group.parent().hide()

        for favorite in FAVORITES.value():
            self._add_to_favorites(favorite, store=False)

        self._target_layer_combo.layerChanged.connect(self._on_target_layer_changed)

    def set_project_controller(self, controller: ProjectController):
        self._controller = controller
        self._set_feature_types(controller.feature_types)

    def set_state_manager(self, state_manager: StateManager):
        self._state_manager = state_manager

        self._state_manager.target_layer_changed.connect(self.set_target_layer)
        self.target_layer_set.connect(self._state_manager.set_target_layer)

    def _set_feature_types(self, feature_types):
        self._feature_type_model = FeatureTypeTreeModel(feature_types, self)
        self._feature_type_proxy_model = FeatureTypeFilterProxyModel(self)
        self._feature_type_proxy_model.setSourceModel(self._feature_type_model)
        self._feature_type_view.setModel(self._feature_type_proxy_model)
        self._feature_type_view.expandAll()
        self._feature_type_view.selectionModel().selectionChanged.connect(
            self._selected_feature_type_changed
        )

    def _create_heading_label(self, text: str) -> QLabel:
        label = QLabel(text)
        palette = label.palette()

        dark_color = palette.color(QPalette.ColorRole.Dark)
        bright_text_color = palette.color(QPalette.ColorRole.BrightText)
        palette.setColor(QPalette.ColorRole.Window, dark_color)
        palette.setColor(QPalette.ColorRole.WindowText, bright_text_color)
        label.setPalette(palette)

        label.setAutoFillBackground(True)
        label.setMargin(3)
        return label

    def _create_tool_group(
        self, group_title: str, collapsible: bool = True
    ) -> ResponsiveTableWidget:
        if collapsible:
            group_box = QgsCollapsibleGroupBox(group_title)
            group_box.setSettingGroup("ToolDock")
            group_box.setObjectName(f"toolGroup{group_title}")
        else:
            group_box = QGroupBox(group_title)
        group_box_layout = QVBoxLayout()
        group_box_layout.setContentsMargins(0, 0, 0, 0)
        group_box.setLayout(group_box_layout)

        if group_title == "Digitize feature":
            insert_index = self._vlayout.count() - 1
        else:
            insert_index = self._vlayout.count() - 3
        self._vlayout.insertWidget(insert_index, group_box)
        group_widget = ResponsiveTableWidget()
        group_box_layout.addWidget(group_widget)
        self._tool_groups[group_title] = group_widget
        return group_widget

    def _create_button_for_action(
        self, action: QAction, descriptive_string: Optional[str]
    ):
        btn = QToolButton()
        btn.setDefaultAction(action)
        btn.setObjectName(action.objectName())
        btn.setAutoRaise(True)
        btn.setFixedHeight(36)
        btn.setIconSize(QSize(24, 24))
        btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        btn.installEventFilter(self)
        btn.setProperty("description", descriptive_string)
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        btn.customContextMenuRequested.connect(self._create_context_menu)
        return btn

    def _create_context_menu(self):
        button = self.sender()
        menu = QMenu()
        if not button.property("_no_favorite"):
            action = QAction(f'Include "{button.text()}" in Favorites', menu)
            action.setCheckable(True)
            object_name = button.objectName()
            if object_name in self._favorites:
                action.setChecked(True)

            def _toggle_favorite(active: bool):
                if active:
                    self._add_to_favorites(object_name)
                else:
                    self._remove_from_favorites(object_name)

            action.toggled.connect(_toggle_favorite)
            menu.addAction(action)

        configure_shortcuts_action = QAction("Configure Keyboard Shortcuts…", menu)
        configure_shortcuts_action.triggered.connect(self._configure_shortcuts)
        menu.addAction(configure_shortcuts_action)

        menu.exec(QCursor.pos())

    def _configure_shortcuts(self):
        dlg = QgsConfigureShortcutsDialog(self)
        dlg.exec()

    def _add_to_favorites(self, object_name: str, store: bool = True):
        if object_name in self._favorites:
            return

        self._favorites.append(object_name)
        try:
            action = [a for a in self._actions if a.objectName() == object_name][0]
        except IndexError:
            return

        btn = self._create_button_for_action(action, action.property("description"))
        self._favorites_group.push_widget(btn)
        self._favorites_group.parent().show()
        if store:
            FAVORITES.setValue(self._favorites)

    def _remove_from_favorites(self, object_name: str):
        try:
            self._favorites.remove(object_name)
        except ValueError:
            return

        FAVORITES.setValue(self._favorites)
        w = [
            w for w in self._favorites_group.children() if w.objectName() == object_name
        ][0]
        w.deleteLater()
        if not self._favorites:
            self._favorites_group.parent().hide()

    def add_tool_action(
        self,
        action: QAction,
        group_title: str,
        descriptive_string: Optional[str] = None,
    ):
        """
        Adds a tool action to the toolbox
        """
        action.setProperty("description", descriptive_string)
        self._actions.append(action)
        tool_group_widget = self._tool_groups.get(group_title)
        if not tool_group_widget:
            tool_group_widget = self._create_tool_group(group_title)

        btn = self._create_button_for_action(action, descriptive_string)
        tool_group_widget.push_widget(btn)

        if action.objectName() in self._favorites:
            btn = self._create_button_for_action(action, descriptive_string)
            self._favorites_group.push_widget(btn)
            self._favorites_group.parent().show()

    def eventFilter(self, obj, event):
        if isinstance(obj, QToolButton):
            if event.type() == QEvent.Type.Enter:
                description = obj.property("description")
                shortcut = obj.defaultAction().shortcut()
                if not shortcut.isEmpty():
                    description += f"<br>(<i>{shortcut.toString()}</i>)"

                self._description_label.setText(description)
            elif event.type() == QEvent.Type.Leave:
                self._description_label.clear()

        return super().eventFilter(obj, event)

    def set_target_layer(self, layer: QgsMapLayer):
        self._target_layer_combo.setLayer(layer)

    def _on_target_layer_changed(self, layer: QgsMapLayer | None):
        self.target_layer_set.emit(layer)

    def _feature_type_filter_changed(self, text: str):
        if self._feature_type_proxy_model:
            self._feature_type_proxy_model.set_filter_text(text)

    def _selected_feature_type_changed(
        self, selected: QItemSelection, deselected: QItemSelection
    ):
        if not self._state_manager or not self._controller:
            return

        feature_type = None
        parent_feature_type = None
        if selected.indexes():
            selected_type_index = self._feature_type_proxy_model.mapToSource(
                selected.indexes()[0]
            )
            parent_feature_type = self._feature_type_model.data(
                selected_type_index, FeatureTypeTreeModel.PARENT_FEATURE_TYPE_ROLE
            )
            feature_type = self._feature_type_model.data(
                selected_type_index, FeatureTypeTreeModel.FEATURE_TYPE_ROLE
            )

        target_layer = self._controller.layer_for_feature_type(parent_feature_type)
        if target_layer:
            self._state_manager.set_target_layer(target_layer)

        self._state_manager.set_current_feature_type(feature_type)


# locator
