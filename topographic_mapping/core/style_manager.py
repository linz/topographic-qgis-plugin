"""
Manages layer styling for a project
"""

from typing import List, Dict

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QEventLoop, QUrl
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.PyQt.QtXml import QDomDocument

from qgis.core import (
    QgsProject,
    QgsTask,
    QgsFeedback,
    QgsNetworkAccessManager,
    QgsApplication,
)

from .project_controller import ProjectController


class StyleManager:
    """
    Manages layer styling for a project
    """

    STYLE_URL_BASE = "https://raw.githubusercontent.com/linz/topographic-qgis/refs/heads/master/map-series/nztopo50/style-layer/"

    def __init__(self, project_controller: ProjectController):
        self._project_controller = project_controller
        self._download_task: StyleDownloadTask | None = None

    @staticmethod
    def url_for_style(feature_type: str) -> str | None:
        """
        Returns the url for the raw style for the specified feature type
        """
        return StyleManager.STYLE_URL_BASE + feature_type + "_map.qml"

    def download_styles(self):
        if self._download_task is not None and not sip.isdeleted(self._download_task):
            return

        feature_type_layers = self._project_controller.feature_layer_names()
        feature_types = [l[0] for l in feature_type_layers]

        self._download_task = StyleDownloadTask(feature_types)
        self._download_task.taskCompleted.connect(self._apply_styles)
        QgsApplication.taskManager().addTask(self._download_task)

    def _apply_styles(self):
        if self._download_task is None or sip.isdeleted(self._download_task):
            self._download_task = None
            return

        styles = self._download_task.styles
        feature_type_layers = self._project_controller.feature_layer_names()

        for layer_name, layer in feature_type_layers:
            if layer_name not in styles:
                continue

            style_raw = styles[layer_name]
            doc = QDomDocument()
            res, error_msg, _, __ = doc.setContent(style_raw)
            if res:
                res, error_msg = layer.importNamedStyle(doc)
                if error_msg:
                    print(error_msg)
                layer.triggerRepaint()
            else:
                print(error_msg)


class StyleDownloadTask(QgsTask):
    """
    A background task for downloading layer styles
    """

    def __init__(self, feature_types: List[str]):
        QgsTask.__init__(self, "Fetching layer styles")
        self._feature_types = feature_types
        self._feedback: QgsFeedback | None = None
        self.styles: Dict[str, str] = {}

    def cancel(self) -> None:
        super().cancel()
        if self._feedback:
            self._feedback.cancel()

    def run(self) -> bool:
        if not self._feature_types:
            return True

        self._feedback = QgsFeedback()
        loop = QEventLoop()
        nam = QgsNetworkAccessManager.instance()

        replies: List[QNetworkReply] = []
        pending_count = 0

        for feature_type in self._feature_types:
            if self.isCanceled() or self._feedback.isCanceled():
                self._feedback = None
                return False

            url = StyleManager.url_for_style(feature_type)
            if not url:
                continue

            request = QNetworkRequest(QUrl(url))
            reply = nam.get(request)
            if reply is None:
                continue

            replies.append(reply)
            self._feedback.canceled.connect(reply.abort)
            pending_count += 1

            def _on_finished(_reply: QNetworkReply = reply, ft: str = feature_type):
                nonlocal pending_count
                if _reply.error() == QNetworkReply.NetworkError.NoError:
                    self.styles[ft] = bytes(_reply.readAll()).decode("utf-8")

                pending_count -= 1
                if pending_count == 0 and loop and loop.isRunning():
                    loop.quit()

            reply.finished.connect(_on_finished)

        if pending_count == 0:
            self._feedback = None
            return True

        loop.exec()

        for r in replies:
            r.deleteLater()
        replies.clear()

        was_canceled = self.isCanceled() or self._feedback.isCanceled()

        self._feedback = None
        return not was_canceled
