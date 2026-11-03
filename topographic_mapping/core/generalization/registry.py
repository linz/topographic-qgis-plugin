"""
Cartographic rule registry
"""

from typing import Dict, List

from .generalization_rule import (
    CartographicGeneralizationRule,
    CartographicGeneralizationRuleContext,
    RuleFeedback,
    CartographicIssue,
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

    def validate(
        self,
        rule_id: str,
        context: CartographicGeneralizationRuleContext,
        parameters: Dict[str, object],
        feedback: RuleFeedback,
    ) -> List[CartographicIssue]:
        """
        Runs validation using a rule
        """
        rule = self.rule_by_id(rule_id)
        if rule is None:
            return []

        results = rule.validate(context, parameters, feedback)
        feedback.push_feedback("Complete")
        feedback.setProgress(100)
        return results

    def run_rule(
        self,
        rule_id: str,
        issues: List[CartographicIssue],
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

        rule.run(issues, context, parameters, feedback)
        feedback.push_feedback("Complete")
        feedback.setProgress(100)


RULE_REGISTRY = CartographicRuleRegistry()
