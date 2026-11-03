"""
Cartographic rule models
"""

from enum import IntEnum
from typing import List, Optional, Tuple

from qgis.PyQt.QtCore import (
    Qt,
    QObject,
    QModelIndex,
    QAbstractListModel,
    QSortFilterProxyModel,
    QAbstractTableModel,
)

from qgis.core import QgsVectorLayer

from .registry import CartographicRuleRegistry, RULE_REGISTRY
from .generalization_rule import CartographicIssue


class CartographicRuleModel(QAbstractListModel):
    """
    Qt model exposing rules from a CartographicRuleRegistry.
    """

    class RuleRole(IntEnum):
        """Custom model roles for cartographic rules."""

        RuleIdRole = Qt.ItemDataRole.UserRole + 1

    def __init__(
        self,
        registry: Optional[CartographicRuleRegistry] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._registry = registry or RULE_REGISTRY
        self._rules: List[Tuple[str, str]] = []
        self.reload()

    def reload(self) -> None:
        """Refreshes the internal cache from the registry."""
        self.beginResetModel()
        self._rules = list(self._registry.all_rules().items())
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rules)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rules)):
            return None

        rule_id, rule_name = self._rules[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return rule_name
        elif role == CartographicRuleModel.RuleRole.RuleIdRole:
            return rule_id

        return None


class CartographicRuleSortProxyModel(QSortFilterProxyModel):
    """
    Proxy model for cartographic rules model
    """

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.setSortRole(Qt.ItemDataRole.DisplayRole)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setDynamicSortFilter(True)
        self.sort(0, Qt.SortOrder.AscendingOrder)


class IssueRole(IntEnum):
    """Custom model roles for cartographic issues."""

    FidRole = Qt.ItemDataRole.UserRole + 1
    LayerRole = Qt.ItemDataRole.UserRole + 2
    SortRole = Qt.ItemDataRole.UserRole + 3


class CartographicIssueTableModel(QAbstractTableModel):
    """
    Table model presenting CartographicIssue records
    """

    COLUMNS: List[str] = ["ID", "Message"]

    def __init__(
        self,
        issues: List[CartographicIssue] | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._issues: List[CartographicIssue] = list(issues) if issues else []
        self._checked_issues: List[bool] = [False] * len(self._issues)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._issues)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = super().flags(index)
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._issues)):
            return None

        issue = self._issues[index.row()]

        if role == IssueRole.FidRole:
            return issue.fid
        elif role == IssueRole.SortRole:
            return issue.sort_value
        elif role == IssueRole.LayerRole:
            return issue.layer

        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return issue.fid
            elif index.column() == 1:
                return issue.message
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() == 0:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        elif role == Qt.ItemDataRole.CheckStateRole:
            if index.column() == 0:
                return (
                    Qt.CheckState.Checked
                    if self._checked_issues[index.row()]
                    else Qt.CheckState.Unchecked
                )

        return None

    def setData(
        self,
        index: QModelIndex,
        value,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not index.isValid() or not (0 <= index.row() < len(self._issues)):
            return False

        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            checked = value in (
                Qt.CheckState.Checked,
                Qt.CheckState.Checked.value,
                True,
            )
            if self._checked_issues[index.row()] != checked:
                self._checked_issues[index.row()] = checked
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
                return True
            return True

        return False

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self.COLUMNS)
        ):
            return self.COLUMNS[section]

        return super().headerData(section, orientation, role)

    def set_issues(self, issues: List[CartographicIssue]) -> None:
        """Replaces the dataset and resets the model."""
        self.beginResetModel()
        self._issues = list(issues)
        self._checked_issues = [False] * len(self._issues)
        self.endResetModel()

    def add_issue(self, issue: CartographicIssue) -> None:
        """Appends a new issue dynamically."""
        row_idx = len(self._issues)
        self.beginInsertRows(QModelIndex(), row_idx, row_idx)
        self._issues.append(issue)
        self._checked_issues.append(False)
        self.endInsertRows()

    def checked_issues(self) -> List[CartographicIssue]:
        """Returns the list of currently checked issues."""
        return [
            issue
            for issue, checked in zip(self._issues, self._checked_issues)
            if checked
        ]

    def set_all_checked(self, checked: bool = True) -> None:
        """Convenience method to check or uncheck all issues at once."""
        if not self._issues:
            return
        self._checked_issues = [checked] * len(self._issues)
        top_left = self.index(0, 0)
        bottom_right = self.index(len(self._issues) - 1, 0)
        self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])


class CartographicIssueSortFilterProxyModel(QSortFilterProxyModel):
    """
    Sort/filter proxy for CartographicIssueTableModel
    """

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.setSortRole(IssueRole.SortRole)
        self.setDynamicSortFilter(True)
        self.sort(0)

    def index_to_fid(self, index: QModelIndex) -> int:
        source_index = self.mapToSource(index)
        return source_index.data(IssueRole.FidRole)

    def index_to_layer(self, index: QModelIndex) -> QgsVectorLayer | None:
        source_index = self.mapToSource(index)
        return source_index.data(IssueRole.LayerRole)
