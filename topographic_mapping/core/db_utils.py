from qgis.PyQt.QtCore import QVariant, Qt

from qgis.core import (
    QgsProviderRegistry,
    QgsAbstractDatabaseProviderConnection,
    QgsField,
)

from pathlib import Path


class DbUtils:
    """
    Contains database related utilities
    """

    ORIGINAL_GEOM_NAME = "original_geom"
    PRODUCT_GEOM_NAME = "product_geom"

    @staticmethod
    def create_connection(db_path: Path) -> QgsAbstractDatabaseProviderConnection:
        """
        Creates a connection to a sqlite/geopackage database
        """
        metadata = QgsProviderRegistry.instance().providerMetadata("ogr")
        assert metadata

        return metadata.createConnection(db_path.as_posix(), {})

    @staticmethod
    def product_view_exists(db_path: Path, layer_name: str) -> bool:
        """
        Returns True if the product view for a layer exists
        """
        conn = DbUtils.create_connection(db_path)
        view_name = f"{layer_name}_product_view"
        return conn.tableExists("", view_name)

    @staticmethod
    def create_all_product_views(db_path: Path):
        """
        Creates all required product views
        """
        conn = DbUtils.create_connection(db_path)

        all_tables = conn.tables(
            "", QgsAbstractDatabaseProviderConnection.TableFlag.Vector
        )
        for table in all_tables:
            if "product_view" in table.tableName():
                continue

            if not DbUtils.product_view_exists(db_path, table.tableName()):
                DbUtils.create_product_view(db_path, table.tableName())

    @staticmethod
    def create_product_view(db_path: Path, layer_name: str):
        """
        Creates the product view for a given layer
        """
        conn = DbUtils.create_connection(db_path)
        table_fields = conn.fields(None, layer_name)
        field_names = ", ".join(
            [
                f.name()
                for f in table_fields
                if f.name() not in (DbUtils.PRODUCT_GEOM_NAME, "geom")
            ]
        )

        if table_fields.lookupField(DbUtils.PRODUCT_GEOM_NAME):
            conn.addField(
                QgsField(DbUtils.PRODUCT_GEOM_NAME, QVariant.ByteArray), "", layer_name
            )

        view_name = f"{layer_name}_product_view"
        query = rf"CREATE VIEW {view_name} AS SELECT {field_names}, CAST(ST_AsBinary(GeomFromGPB(geom))AS BLOB) as {DbUtils.ORIGINAL_GEOM_NAME}, CASE WHEN {DbUtils.PRODUCT_GEOM_NAME} is NOT NULL then {DbUtils.PRODUCT_GEOM_NAME} ELSE geom END AS geom, {DbUtils.PRODUCT_GEOM_NAME} FROM {layer_name};"
        conn.executeSql(query)

        # copy metadata from base table
        query = rf"SELECT last_change, min_x, min_y, max_x, max_y, srs_id  FROM gpkg_contents WHERE table_name='{layer_name}'"
        res = conn.executeSql(query)
        last_change, min_x, min_y, max_x, max_y, srs_id = res[0]
        query = rf"INSERT INTO gpkg_contents VALUES ('{view_name}', 'features', '{view_name}', NULL, '{last_change.toString(Qt.DateFormat.ISODateWithMs)}', {min_x}, {min_y}, {max_x}, {max_y}, {srs_id})"
        conn.executeSql(query)

        query = rf"SELECT geometry_type_name, srs_id, z, m  FROM gpkg_geometry_columns WHERE table_name='{layer_name}'"
        res = conn.executeSql(query)
        geometry_type_name, srs_id, z, m = res[0]
        query = rf"INSERT INTO gpkg_geometry_columns VALUES ('{view_name}', 'geom', '{geometry_type_name}', {srs_id}, {z}, {m})"
        conn.executeSql(query)

        # create edit trigger
        field_update = ", ".join(
            [
                f"{field.name()} = NEW.{field.name()}"
                for field in table_fields
                if field.name() not in ("fid", "geom")
            ]
        )
        field_update += f", {DbUtils.PRODUCT_GEOM_NAME} = CASE WHEN NEW.geom != OLD.geom THEN NEW.geom ELSE {DbUtils.PRODUCT_GEOM_NAME} END"

        trigger_name = f"trg_update_{view_name}"
        query = rf"""CREATE TRIGGER {trigger_name} INSTEAD OF UPDATE ON {view_name} FOR EACH ROW BEGIN UPDATE {layer_name} SET {field_update} WHERE fid=OLD.fid; END;"""
        conn.executeSql(query)
