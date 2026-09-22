from pathlib import Path

from qgis.PyQt.QtCore import Qt, QCoreApplication, QObject, QDir, QVariant
from qgis.PyQt.QtWidgets import QMenu, QAction, QMessageBox

from qgis.core import (
    Qgis,
    QgsSettingsTree,
    QgsProject,
    QgsApplication,
    QgsVectorLayerUtils,
    QgsFeatureSink,
    QgsFeatureRequest,
    QgsGeometry,
    QgsExpression,
    QgsFeature,
)
from qgis.gui import QgisInterface

from topographic_mapping.gui import (
    PluginTool,
    EditToolDock,
    ToolRegistry,
    SetTargetTool,
    SetTargetToolHandler,
    ValidationDock,
    PluginsOptionsFactory,
    LabelDock,
    ToolGroup,
    LabelingGuiManager,
    StyleManager,
    ChangeFeatureClassDialog,
    SelectFeatureClassDialog,
)
from .core import (
    StateManager,
    ProjectController,
    DbUtils,
    LabelManager,
    MarkupManager,
    STORED_OBJECT_MANAGER,
)
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
        self._style_manager: StyleManager | None = None
        self._label_manager: LabelManager | None = None
        self._markup_manager: MarkupManager | None = None
        self._label_gui_manager: LabelingGuiManager | None = None
        self._menu: QMenu | None = None
        self._options_factory: PluginsOptionsFactory | None = None
        self._symbol_layer_metadata = []

        QgsApplication.localizedDataPathRegistry().registerPath(
            STORED_OBJECT_MANAGER.get_base_plugin_data_dir().as_posix()
        )

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
        self._style_manager = StyleManager(
            self._project_controller, self.iface.messageBar()
        )

        self._tool_registry = ToolRegistry(self._gui_owner, self._state_manager)
        self._label_gui_manager = LabelingGuiManager(
            self.iface.mapCanvas(),
            self.iface.cadDockWidget(),
            self.iface.messageBar(),
            parent=self._gui_owner,
        )
        self._label_gui_manager.set_label_manager(self._label_manager)
        self._label_gui_manager.set_project_controller(self._project_controller)
        self._label_gui_manager.set_state_manager(self._state_manager)

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
            self._tool_dock, [ToolGroup.Editing, ToolGroup.Digitizing]
        )
        self._tool_registry.populate_tool_dock(self._label_dock, [ToolGroup.Labeling])
        self._label_gui_manager.register_tools(self._tool_registry)

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

        update_layer_styles_action = QAction("Update Layer Styles…", self._menu)
        update_layer_styles_action.triggered.connect(self._update_layer_styles)
        self._menu.addAction(update_layer_styles_action)

        run_validation_action = QAction("Run Validation…", validation_menu)
        run_validation_action.triggered.connect(self.show_validation_dock)
        validation_menu.addAction(run_validation_action)

        self._markup_manager = MarkupManager(self._gui_owner)

        self.options_factory = PluginsOptionsFactory()
        self.options_factory.setTitle("TopoMapping")
        self.iface.registerOptionsWidgetFactory(self.options_factory)

        change_feature_class_action = self._tool_registry.custom_action(
            PluginTool.ChangeFeatureClass
        )
        change_feature_class_action.triggered.connect(self._change_feature_class)

        pastry_delete_action = self._tool_registry.custom_action(
            PluginTool.PastryDelete
        )
        pastry_delete_action.triggered.connect(self._pastry_delete)

        pastry_cut_action = self._tool_registry.custom_action(PluginTool.PastryCut)
        pastry_cut_action.triggered.connect(self._pastry_cut)

        self._tool_registry.custom_action(
            PluginTool.ClearProductEdits
        ).triggered.connect(self._clear_product_edits)

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        self._label_gui_manager.unregister()
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

        if self._markup_manager:
            self._markup_manager.deleteLater()
            self._markup_manager = None

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

    def _update_layer_styles(self):
        """
        Updates layer styles
        """
        if (
            QMessageBox.question(
                self.iface.mainWindow(),
                "Update Layer Styles",
                "Are you sure you want to replace all existing layer styles with updated definitions?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            self._style_manager.download_styles()

    def _change_feature_class(self):
        current_layer = self._state_manager.target_layer()
        if current_layer is None:
            self.iface.messageBar().pushWarning(
                "", "Changing feature classes requires an active layer"
            )
            return

        current_selection = current_layer.selectedFeatureIds()
        if not current_selection:
            self.iface.messageBar().pushWarning(
                "", "Changing feature classes requires a selection"
            )
            return

        dlg = ChangeFeatureClassDialog(self._project_controller.feature_types)
        if dlg.exec():
            new_types = dlg.new_feature_type()
            message = "The selected features will be changed to the {} class. Attributes or geometry properties may be lost as a result. Are you sure you want to proceed?".format(
                new_types[-1]
            )
            if (
                QMessageBox.question(
                    self.iface.mainWindow(),
                    "Change Feature Class",
                    message,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.No
            ):
                return

            features = self._state_manager.target_layer().selectedFeatures()

            target_layer = self._project_controller.layer_for_feature_type(new_types[0])
            if not target_layer.isEditable():
                target_layer.startEditing()

            compatible_features = QgsVectorLayerUtils.makeFeaturesCompatible(
                features, target_layer, QgsFeatureSink.SinkFlag.RegeneratePrimaryKey
            )
            for f in compatible_features:
                f["type"] = new_types[1]

            current_layer.deleteFeatures(current_selection)
            target_layer.addFeatures(compatible_features)

    def _pastry_delete(self):
        current_layer = self._state_manager.target_layer()
        if current_layer is None:
            self.iface.messageBar().pushWarning(
                "", "Pastry delete requires an active layer"
            )
            return

        current_selection = current_layer.selectedFeatures()
        if not current_selection:
            self.iface.messageBar().pushWarning(
                "", "Pastry delete requires a selection"
            )
            return

        pastry_geom = QgsGeometry.unaryUnion([f.geometry() for f in current_selection])

        dlg = SelectFeatureClassDialog(self._project_controller.feature_types)
        dlg.setWindowTitle("Pastry Delete")
        dlg.label.setText(
            "Select target classes to pastry delete using the current selection"
        )
        if dlg.exec():
            target_types = dlg.new_feature_type()

            target_layer = self._project_controller.layer_for_feature_type(
                target_types[0]
            )
            if not target_layer.isEditable():
                target_layer.startEditing()

            req = QgsFeatureRequest()
            req.setFilterExpression(
                QgsExpression.createFieldEqualityExpression(
                    "type", target_types[1], QVariant.String
                )
            )
            req.setFilterRect(pastry_geom.boundingBox())
            cut_features = [f for f in target_layer.getFeatures(req)]

            geom_engine = QgsGeometry.createGeometryEngine(pastry_geom.constGet())
            geom_engine.prepareGeometry()

            target_layer.beginEditCommand("Pastry Delete")
            for f in cut_features:
                geom = f.geometry()
                if not geom_engine.intersects(geom.constGet()):
                    continue

                new_geom = geom.difference(pastry_geom)
                target_layer.changeGeometry(f.id(), new_geom)

            target_layer.endEditCommand()

    def _pastry_cut(self):
        current_layer = self._state_manager.target_layer()
        if current_layer is None:
            self.iface.messageBar().pushWarning(
                "", "Pastry cut requires an active layer"
            )
            return

        current_selection = current_layer.selectedFeatures()
        if not current_selection:
            self.iface.messageBar().pushWarning("", "Pastry cut requires a selection")
            return

        pastry_geom = QgsGeometry.unaryUnion([f.geometry() for f in current_selection])
        if pastry_geom.type() == Qgis.GeometryType.Polygon:
            pastry_geom = QgsGeometry(pastry_geom.constGet().boundary())
        elif pastry_geom.type() == Qgis.GeometryType.Point:
            self.iface.messageBar().pushWarning(
                "", "Pastry cut requires a polygon or line selection"
            )
            return

        dlg = SelectFeatureClassDialog(self._project_controller.feature_types)
        dlg.setWindowTitle("Pastry Cut")
        dlg.label.setText(
            "Select target classes to pastry cut using the current selection"
        )
        if dlg.exec():
            target_types = dlg.new_feature_type()

            target_layer = self._project_controller.layer_for_feature_type(
                target_types[0]
            )
            if not target_layer.isEditable():
                target_layer.startEditing()

            req = QgsFeatureRequest()
            req.setFilterExpression(
                QgsExpression.createFieldEqualityExpression(
                    "type", target_types[1], QVariant.String
                )
            )
            req.setFilterRect(pastry_geom.boundingBox())
            cut_features = [f for f in target_layer.getFeatures(req)]

            geom_engine = QgsGeometry.createGeometryEngine(pastry_geom.constGet())
            geom_engine.prepareGeometry()

            target_layer.beginEditCommand("Pastry Cut")
            for f in cut_features:
                geom = f.geometry()

                if not geom_engine.intersects(geom.constGet()):
                    continue

                new_parts = [geom]
                for pastry_part in pastry_geom.constParts():
                    new_parts_this_round = []
                    split_line = [v for v in pastry_part.vertices()]
                    for new_part in new_parts:
                        res, split_parts, _ = new_part.splitGeometry(split_line, False)
                        new_parts_this_round.append(new_part)
                        if res == Qgis.GeometryOperationResult.Success:
                            new_parts_this_round.extend(split_parts)
                    new_parts = new_parts_this_round

                old_part = new_parts[0]
                new_parts = new_parts[1:]
                target_layer.changeGeometry(f.id(), old_part)

                for part in new_parts:
                    new_feature = QgsFeature(f)
                    new_feature.setGeometry(part)
                    target_layer.addFeature(new_feature)

            target_layer.endEditCommand()

    def _clear_product_edits(self):
        """
        Clears product edits for selected features
        """
        if not self._project_controller:
            return

        gpkg_path = self._project_controller.working_geopackage_path()
        if not gpkg_path:
            return

        for layer in self._project_controller.editable_vector_layers_in_gpkg(gpkg_path):
            if layer.isEditable() and layer.editBuffer().isModified():
                self.iface.messageBar().pushWarning(
                    None,
                    "Cannot clear product view edits when layers have unsaved edits",
                )
                return False

        self._project_controller.reset_product_view_edits(gpkg_path)
        for layer in self._project_controller.editable_vector_layers_in_gpkg(gpkg_path):
            if layer.isEditable():
                layer.commitChanges(False)
