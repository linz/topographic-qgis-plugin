"""
Manages layer styling for a project
"""

from typing import List, Dict
import json
from pathlib import Path

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QEventLoop, QUrl
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.PyQt.QtXml import QDomDocument

from qgis.core import (
    QgsBlockingNetworkRequest,
    QgsTask,
    QgsFeedback,
    QgsNetworkAccessManager,
    QgsApplication,
)

from .project_controller import ProjectController
from .stored_object_manager import STORED_OBJECT_MANAGER


class StyleManager:
    """
    Manages layer styling for a project
    """

    STYLE_URL_BASE = "https://raw.githubusercontent.com/linz/topographic-qgis/refs/heads/master/map-series/nztopo50/style-layer/"
    SVG_GRAPHICS_PATH = f"https://api.github.com/repos/linz/topographic-qgis/contents/map-series/nztopo50/symbol"

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

        self._download_task = StyleDownloadTask(
            feature_types, STORED_OBJECT_MANAGER.get_plugin_data_dir("svg")
        )
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

    def __init__(self, feature_types: List[str], svg_dir: str | Path):
        QgsTask.__init__(self, "Fetching layer styles")
        self._feature_types = feature_types
        self._svg_dir = Path(svg_dir)
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
        nam = QgsNetworkAccessManager.instance()

        request = QNetworkRequest(QUrl(StyleManager.SVG_GRAPHICS_PATH))
        blocking_request = QgsBlockingNetworkRequest()
        err = blocking_request.get(request)

        if err != QgsBlockingNetworkRequest.ErrorCode.NoError:
            return True

        reply = blocking_request.reply()
        svg_files = []
        try:
            items = json.loads(bytes(reply.content()).decode("utf-8"))
            if isinstance(items, list):
                for item in items:
                    if item.get("type") == "file" and item.get("download_url"):
                        svg_files.append((item.get("name"), item.get("download_url")))
        except json.JSONDecodeError as e:
            print(f"Error parsing SVG metadata: {e}")

        if self.isCanceled() or self._feedback.isCanceled():
            self._feedback = None
            return False

        if svg_files and self._svg_dir:
            self._svg_dir.mkdir(parents=True, exist_ok=True)

        loop = QEventLoop()

        replies: List[QNetworkReply] = []
        pending_count = 0

        def _check_pending():
            nonlocal pending_count
            nonlocal loop
            pending_count -= 1
            if pending_count == 0 and loop and loop.isRunning():
                loop.quit()

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

            def _on_style_finished(
                _reply: QNetworkReply = reply, ft: str = feature_type
            ):
                nonlocal pending_count
                if _reply.error() == QNetworkReply.NetworkError.NoError:
                    self.styles[ft] = bytes(_reply.readAll()).decode("utf-8")

                _check_pending()

            reply.finished.connect(_on_style_finished)

        for file_name, download_url in svg_files:
            if self.isCanceled() or self._feedback.isCanceled():
                self._feedback = None
                return False

            svg_request = QNetworkRequest(QUrl(download_url))
            svg_reply = nam.get(svg_request)
            if svg_reply is None:
                continue

            replies.append(svg_reply)
            self._feedback.canceled.connect(svg_reply.abort)
            pending_count += 1

            def _on_svg_finished(
                _reply: QNetworkReply = svg_reply, name: str = file_name
            ):
                if _reply.error() == QNetworkReply.NetworkError.NoError:
                    file_path = self._svg_dir / name
                    try:
                        with open(file_path, "wb") as f:
                            f.write(bytes(_reply.readAll()))
                    except IOError as e:
                        print(f"Failed to write SVG {name}: {e}")
                _check_pending()

            svg_reply.finished.connect(_on_svg_finished)

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
