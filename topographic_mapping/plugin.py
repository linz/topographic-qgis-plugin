from pathlib import Path

from qgis.PyQt.QtCore import Qt, QCoreApplication, QObject, QDir
from qgis.PyQt.QtWidgets import QMenu, QAction, QMessageBox

from qgis.core import QgsSettingsTree, QgsProject, QgsApplication
from qgis.gui import QgisInterface

from .gui import (
    EditToolDock,
    ToolRegistry,
    SetTargetTool,
    SetTargetToolHandler,
    ValidationDock,
    PluginsOptionsFactory,
    LabelDock,
    EDITING_GROUP,
    DIGITIZING_GROUP,
    LABELING_GROUP,
    CREATE_LABEL_ACTION,
)
from .core import StateManager, ProjectController, DbUtils, LabelManager
from .core.symbol_layers import RockOutcropMarkerMetadata


class TopographicMappingPlugin:
    def __init__(self, iface: QgisInterface):
        self.iface = iface
        self._gui_owner = QObject()
        self._tool_dock: EditToolDock | None = None
        self._label_dock: LabelDock | None = None
        self._validation_dock: ValidationDock | None = None
        self._action_group = None
        self._tool_registry: ToolRegistry | None = None
        self._state_manager: StateManager | None = None
        self._set_target_tool: SetTargetTool | None = None
        self._set_target_tool_handler: SetTargetToolHandler | None = None
        self._project_controller: ProjectController | None = None
        self._label_manager: LabelManager | None = None
        self._menu: QMenu | None = None
        self._options_factory: PluginsOptionsFactory | None = None
        self._symbol_layer_metadata = []

    def initGui(self) -> None:
        self._symbol_layer_metadata = [RockOutcropMarkerMetadata()]
        for _metadata in self._symbol_layer_metadata:
            QgsApplication.symbolLayerRegistry().addSymbolLayerType(_metadata)

        self._project_controller = ProjectController(
            QgsProject.instance(), self._gui_owner
        )
        self._state_manager = StateManager(self.iface, QgsProject.instance())
        self._label_manager = LabelManager(
            self._project_controller, self._state_manager
        )
        self._tool_registry = ToolRegistry(self._gui_owner)

        self._tool_dock = EditToolDock(
            edit_target_tool_action=self._tool_registry.set_target_tool_action,
            parent=None,
        )
        self._tool_dock.setObjectName("TopographicTools")
        self._tool_dock.setWindowTitle("Editing tools")
        self._tool_dock.set_message_bar(self.iface.messageBar())

        self._label_dock = LabelDock(
            edit_target_tool_action=self._tool_registry.set_target_tool_action,
            parent=None,
        )
        self._label_dock.setObjectName("TopographicLabelTools")
        self._label_dock.setWindowTitle("Labeling tools")

        self._validation_dock = ValidationDock(
            parent=None,
        )
        self._validation_dock.setObjectName("TopographicValidation")
        self._validation_dock.setWindowTitle("Validation")
        self._validation_dock.set_map_canvas(self.iface.mapCanvas())

        self._tool_registry.init(self.iface)
        self._tool_registry.register_shortcuts()

        self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._tool_dock)
        self.iface.addTabifiedDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            self._label_dock,
            [self._tool_dock.objectName()],
        )
        self.iface.addTabifiedDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            self._validation_dock,
            [self._tool_dock.objectName(), self._label_dock.objectName()],
        )

        # defaults to closed
        self._validation_dock.close()

        self._tool_registry.populate_tool_dock(
            self._tool_dock, [EDITING_GROUP, DIGITIZING_GROUP]
        )
        self._tool_registry.populate_tool_dock(self._label_dock, [LABELING_GROUP])

        self._set_target_tool = SetTargetTool(self.iface.mapCanvas())
        self._set_target_tool_handler = SetTargetToolHandler(
            self._set_target_tool, self._tool_registry.set_target_tool_action
        )
        self.iface.registerMapToolHandler(self._set_target_tool_handler)
        self._set_target_tool.target_set.connect(self._state_manager.set_edit_target)

        self._tool_dock.set_project_controller(self._project_controller)
        self._tool_dock.set_state_manager(self._state_manager)
        self._label_dock.set_project_controller(self._project_controller)
        self._label_dock.set_state_manager(self._state_manager)

        self._validation_dock.set_project_controller(self._project_controller)

        self._menu = QMenu("TopoMapping")
        self.iface.mainWindow().menuBar().insertMenu(
            self.iface.firstRightStandardMenu().menuAction(), self._menu
        )
        validation_menu = QMenu("Validation", self._menu)
        self._menu.addMenu(validation_menu)

        self._menu.addSeparator()
        create_product_views_action = QAction("Create GPKG Product Views", self._menu)
        create_product_views_action.triggered.connect(self._create_product_views)
        self._menu.addAction(create_product_views_action)

        run_validation_action = QAction("Run Validation…", validation_menu)
        run_validation_action.triggered.connect(self.show_validation_dock)
        validation_menu.addAction(run_validation_action)

        self.options_factory = PluginsOptionsFactory()
        self.options_factory.setTitle("TopoMapping")
        self.iface.registerOptionsWidgetFactory(self.options_factory)

        self._tool_registry.custom_action(CREATE_LABEL_ACTION).triggered.connect(
            self._label_manager.create_labels
        )

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        self._tool_registry.unregister_shortcuts()
        self.iface.unregisterOptionsWidgetFactory(self.options_factory)

        if self._set_target_tool_handler:
            self.iface.unregisterMapToolHandler(self._set_target_tool_handler)
        if self._set_target_tool:
            self._set_target_tool.deleteLater()
            self._set_target_tool = None

        if self._tool_dock:
            self._tool_dock.deleteLater()
            self._tool_dock = None
        if self._label_dock:
            self._label_dock.deleteLater()
            self._label_dock = None
        if self._validation_dock:
            self._validation_dock.cleanup()
            self._validation_dock.deleteLater()
            self._validation_dock = None

        if self._menu:
            self._menu.deleteLater()
            self._menu = None
        if self._gui_owner:
            self._gui_owner.deleteLater()
            self._gui_owner = None

        if self._state_manager:
            self._state_manager.deleteLater()
            self._state_manager = None

        QgsSettingsTree.unregisterPluginTreeNode("topographic_mapping")

        for _metadata in self._symbol_layer_metadata:
            QgsApplication.symbolLayerRegistry().removeSymbolLayerType(_metadata)
        self._symbol_layer_metadata = []

    @staticmethod
    def tr(message) -> str:
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("TopographicMappingPlugin", message)

    def show_validation_dock(self):
        """
        Shows the validation dock
        """
        self._validation_dock.setUserVisible(True)

    def _create_product_views(self):
        """
        Creates database product views, if not existing
        """
        path = self._project_controller.working_geopackage_path()
        if not path:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Create Product Views",
                "No Topo data GeoPackage was detected in the current QGIS project",
            )
            return

        DbUtils.create_all_product_views(Path(path))
        QMessageBox.information(
            self.iface.mainWindow(),
            "Create Product Views",
            "Product views created in {}".format(QDir.toNativeSeparators(path)),
        )

    def _create_labels(self):
        print("create labels")
