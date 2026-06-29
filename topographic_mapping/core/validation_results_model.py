from qgis.PyQt.QtCore import QAbstractTableModel, Qt, QModelIndex, QObject
from qgis.PyQt.QtGui import QColor


class ValidationResultModel(QAbstractTableModel):
    """
    A Qt Table Model to dynamically display validation JSON results.
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._headers = ["Result", "Rule", "Description"]
        self._data = []
        self._summary_message = ""

    def set_data(self, json_data: dict | None):
        self.beginResetModel()
        self._data = []
        self._parse_data(json_data or {})
        self.endResetModel()

    def _parse_data(self, json_data: dict):
        """Processes the raw JSON into an internal list of dictionaries."""
        results = {k: v for k, v in json_data.items() if isinstance(v, bool)}
        strings = {k: v for k, v in json_data.items() if isinstance(v, str)}

        for key, has_violation in results.items():
            about_key = f"{key}_about"

            # Fallback for plural mismatches (e.g., query_rules vs query_rule_about)
            if about_key not in strings and key.endswith("s"):
                fallback_key = f"{key[:-1]}_about"
                if fallback_key in strings:
                    about_key = fallback_key

            description = strings.get(about_key, "No description provided.")
            if description.lower().startswith("if true - "):
                description = description[len("if true - ") :]
            rule_name = key.replace("_", " ").title()

            self._data.append(
                {
                    "has_violation": has_violation,
                    "rule": rule_name,
                    "description": description,
                }
            )

        self._summary_message = strings.get("validation_completed_message", "")

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row_data = self._data[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return "❌" if row_data["has_violation"] else "✅"
            elif col == 1:
                return row_data["rule"]
            elif col == 2:
                return row_data["description"]
        elif role == Qt.ItemDataRole.BackgroundRole:
            if row_data["has_violation"]:
                return QColor("#fff0f0")
            else:
                return QColor("#f0fff0")
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 0:
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        elif role == Qt.ItemDataRole.ToolTipRole and col == 2:
            return row_data["description"]

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        """Provides the column titles."""
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self._headers[section]
        return None

    @property
    def summary_message(self) -> str:
        """Exposes the summary message so the UI can display it in a label."""
        return self._summary_message
