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
    METADATA_FIELD_NAME = "metadata"

    @staticmethod
    def create_connection(db_path: Path) -> QgsAbstractDatabaseProviderConnection:
        """
        Creates a connection to a sqlite/geopackage database
        """
        metadata = QgsProviderRegistry.instance().providerMetadata("ogr")
        if metadata is None:
            raise AssertionError(
                "OGR provider is not available -- QGIS install is corrupted or not initialized correctly"
            )

        conn = metadata.createConnection(db_path.as_posix(), {})
        if not isinstance(conn, QgsAbstractDatabaseProviderConnection):
            raise RuntimeError(f"Failed to create a database connection for {db_path}")
        return conn

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

            exists = bool(
                [
                    t
                    for t in all_tables
                    if t.tableName() == f"{table.tableName()}_product_view"
                ]
            )
            if not exists:
                DbUtils.create_product_view(db_path, table.tableName())

    @staticmethod
    def create_product_view(db_path: Path, layer_name: str):
        """
        Creates the product view for a given layer
        """
        conn = DbUtils.create_connection(db_path)
        table_fields = conn.fields(None, layer_name)
        if table_fields.lookupField(DbUtils.METADATA_FIELD_NAME) == -1:
            conn.addField(
                QgsField(DbUtils.METADATA_FIELD_NAME, QVariant.String), "", layer_name
            )
            table_fields = conn.fields(None, layer_name)

        query = rf"SELECT geometry_type_name, srs_id, z, m FROM gpkg_geometry_columns WHERE table_name='{layer_name}'"
        res = conn.executeSql(query)
        geometry_type_name, srs_id, z, m = res[0]

        field_names = ", ".join(
            [
                f.name()
                for f in table_fields
                if f.name() not in (DbUtils.METADATA_FIELD_NAME, "geom")
            ]
        )

        view_name = f"{layer_name}_product_view"
        extracted_wkt = f"json_extract({DbUtils.METADATA_FIELD_NAME}, '$.geometry')"
        query = rf"""
                CREATE VIEW {view_name} AS 
                SELECT 
                    {field_names}, 
                    CAST(ST_AsBinary(GeomFromGPB(geom)) AS BLOB) AS {DbUtils.ORIGINAL_GEOM_NAME}, 
                    CASE 
                        WHEN {extracted_wkt} IS NOT NULL THEN AsGPB(GeomFromText({extracted_wkt}, {srs_id}))
                        ELSE geom 
                    END AS geom, 
                    {DbUtils.METADATA_FIELD_NAME} 
                FROM {layer_name};
                """
        conn.executeSql(query)

        # copy metadata from base table
        query = rf"SELECT last_change, min_x, min_y, max_x, max_y, srs_id  FROM gpkg_contents WHERE table_name='{layer_name}'"
        res = conn.executeSql(query)
        last_change, min_x, min_y, max_x, max_y, srs_id = res[0]
        query = rf"INSERT INTO gpkg_contents VALUES ('{view_name}', 'features', '{view_name}', NULL, '{last_change.toString(Qt.DateFormat.ISODateWithMs)}', {min_x}, {min_y}, {max_x}, {max_y}, {srs_id})"
        conn.executeSql(query)

        query = rf"INSERT INTO gpkg_geometry_columns VALUES ('{view_name}', 'geom', '{geometry_type_name}', {srs_id}, {z}, {m})"
        conn.executeSql(query)

        # create edit trigger
        field_update = [
            f"{field.name()} = NEW.{field.name()}"
            for field in table_fields
            if field.name() not in ("fid", "geom", DbUtils.METADATA_FIELD_NAME)
        ]

        new_wkt_expr = "CASE WHEN NEW.geom IS NULL THEN NULL ELSE AsText(GeomFromGPB(NEW.geom)) END"
        metadata_update = (
            f"{DbUtils.METADATA_FIELD_NAME} = CASE "
            f"WHEN NEW.geom IS NOT OLD.geom "
            f"THEN json_set(COALESCE(NEW.{DbUtils.METADATA_FIELD_NAME}, '{{}}'), '$.geometry', {new_wkt_expr}) "
            f"ELSE NEW.{DbUtils.METADATA_FIELD_NAME} END"
        )
        field_update.append(metadata_update)
        field_update = ", ".join(field_update)

        trigger_name = f"trg_update_{view_name}"
        query = rf"""CREATE TRIGGER {trigger_name} INSTEAD OF UPDATE ON {view_name} FOR EACH ROW BEGIN UPDATE {layer_name} SET {field_update} WHERE fid=OLD.fid; END;"""
        conn.executeSql(query)
