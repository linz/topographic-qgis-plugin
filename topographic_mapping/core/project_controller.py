import json
from pathlib import Path
from qgis.PyQt.QtCore import QObject

from qgis.core import (
    QgsProject,
    QgsMapLayer,
    QgsProviderRegistry,
    QgsVectorLayer,
    QgsEditorWidgetSetup,
    QgsDefaultValue,
    QgsExpression,
)

SCHEMAS_DIR = Path(__file__) / ".." / ".." / "schemas"


class ProjectController(QObject):
    def __init__(self, project: QgsProject, parent: QObject | None):
        super().__init__(parent)

        self._project = project

        for _, layer in self._project.mapLayers().items():
            self._initialize_layer(layer)

    def _initialize_layer(self, layer: QgsMapLayer):
        parts = QgsProviderRegistry.instance().decodeUri(
            layer.providerType(), layer.source()
        )
        layer_name = parts.get("layerName")
        if not layer_name:
            return

        schema_file = (SCHEMAS_DIR / (layer_name + ".json")).resolve()
        if schema_file.exists():
            with open(schema_file, "rt") as f:
                contents = json.loads(f.read())
            self._set_layer_schema(layer, contents)

    def _set_layer_schema(self, layer: QgsVectorLayer, schema: dict):
        properties = schema["properties"]
        fields = layer.fields()
        edit_form_config = layer.editFormConfig()
        for name, property in properties.items():
            field_index = fields.lookupField(name)
            if field_index < 0:
                continue

            edit_widget_setup = layer.editorWidgetSetup(field_index)
            description = property.get("description")
            if description:
                try:
                    layer.setFieldCustomComment(field_index, str(description))
                except AttributeError:
                    # requires QGIS 4.2
                    layer.setFieldAlias(field_index, str(description))

            if "minimum" in property:
                config = edit_widget_setup.config()
                config["Min"] = float(property["minimum"])
                config["Max"] = float(property["maximum"])
                edit_widget_setup = QgsEditorWidgetSetup("Range", config)

            elif "$ref" in property:
                ref = property["$ref"][len("#/$defs/") :]
                definition = schema["$defs"][ref]
                if "enum" in definition:
                    enum_values = definition["enum"]
                    config = edit_widget_setup.config()
                    config["map"] = {e: e for e in enum_values}
                    edit_widget_setup = QgsEditorWidgetSetup("ValueMap", config)

            if "default" in property:
                default_value = QgsDefaultValue(
                    QgsExpression.quotedValue(property["default"])
                )
                layer.setDefaultValueDefinition(field_index, default_value)

            layer.setEditorWidgetSetup(field_index, edit_widget_setup)

        layer.setEditFormConfig(edit_form_config)
