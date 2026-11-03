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
    SortRole = Qt.ItemDataRole.UserRole + 2


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

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._issues)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._issues)):
            return None

        issue = self._issues[index.row()]

        if role == IssueRole.FidRole:
            return issue.fid

        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return issue.fid
            elif index.column() == 1:
                return issue.message
        elif role == IssueRole.SortRole:
            return issue.sort_value
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() == 0:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        return None

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
        self.endResetModel()

    def add_issue(self, issue: CartographicIssue) -> None:
        """Appends a new issue dynamically."""
        row_idx = len(self._issues)
        self.beginInsertRows(QModelIndex(), row_idx, row_idx)
        self._issues.append(issue)
        self.endInsertRows()


class CartographicIssueSortFilterProxyModel(QSortFilterProxyModel):
    """
    Sort/filter proxy for CartographicIssueTableModel
    """

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.setSortRole(IssueRole.SortRole)
        self.setDynamicSortFilter(True)
        self.sort(0)
