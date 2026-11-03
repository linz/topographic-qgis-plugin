"""
Cartographic generalization rules
"""

from typing import Dict
from abc import ABC, abstractmethod
from dataclasses import dataclass

from qgis.PyQt.QtCore import QObject, pyqtSignal

from qgis.core import (
    QgsReferencedRectangle,
    QgsFeedback,
)

from ..project_controller import ProjectController


@dataclass
class CartographicGeneralizationRuleContext:
    """
    Context for running cartographic rules
    """

    extent: QgsReferencedRectangle
    project_controller: ProjectController


@dataclass
class RuleFeedback(QgsFeedback):
    """
    Feedback for running cartographic rules
    """

    feedback_received = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

    def push_feedback(self, feedback: str):
        self.feedback_received.emit(feedback)


class CartographicGeneralizationRule(ABC):
    """
    Base class for generalization rules
    """

    @abstractmethod
    def id(self) -> str:
        """
        Returns the ID of the generalization rule
        """

    @abstractmethod
    def name(self) -> str:
        """
        Returns the name of the generalization rule
        """
        pass

    @abstractmethod
    def run(
        self,
        context: CartographicGeneralizationRuleContext,
        parameters: Dict[str, object],
        feedback: RuleFeedback,
    ):
        """
        Runs the generalization rule
        """
