"""
Cartographic rule registry
"""

from enum import IntEnum
from typing import Dict, List, Optional, Tuple

from qgis.PyQt.QtCore import (
    Qt,
    QObject,
    QModelIndex,
    QAbstractListModel,
    QSortFilterProxyModel,
)

from .generalization_rule import (
    CartographicGeneralizationRule,
    CartographicGeneralizationRuleContext,
    RuleFeedback,
)

from .bridge_minimum_length import BridgeMinimumLengthRule
from .boatramp_minimum_length import BoatRampMinimumLengthRule


class CartographicRuleRegistry:
    """
    Cartographic rule registry
    """

    def __init__(self):
        self._rules: List[CartographicGeneralizationRule] = [
            BridgeMinimumLengthRule(),
            BoatRampMinimumLengthRule(),
        ]

    def all_rules(self) -> Dict[str, str]:
        """
        Returns the dictionary of rule ID to name
        """
        return {rule.id(): rule.name() for rule in self._rules}

    def rule_by_id(self, rule_id: str) -> CartographicGeneralizationRule | None:
        for r in self._rules:
            if r.id() == rule_id:
                return r

        return None

    def run_rule(
        self,
        rule_id: str,
        context: CartographicGeneralizationRuleContext,
        parameters: Dict[str, object],
        feedback: RuleFeedback,
    ):
        """
        Runs a rule
        """
        rule = self.rule_by_id(rule_id)
        if rule is None:
            return

        rule.run(context, parameters, feedback)
        feedback.push_feedback("Complete")


RULE_REGISTRY = CartographicRuleRegistry()


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
