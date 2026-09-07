"""
Manages layer styling for a project
"""

from typing import List, Dict
import json
import re
from pathlib import Path

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QEventLoop, QUrl
from qgis.PyQt.QtWidgets import QPushButton
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.PyQt.QtXml import QDomDocument

from qgis.core import (
    Qgis,
    QgsBlockingNetworkRequest,
    QgsTask,
    QgsFeedback,
    QgsNetworkAccessManager,
    QgsApplication,
    QgsMessageOutput,
    QgsMapLayerStyle,
)
from qgis.gui import QgsMessageBar

from topographic_mapping.core.project_controller import ProjectController
from topographic_mapping.core.stored_object_manager import STORED_OBJECT_MANAGER


class StyleManager:
    """
    Manages layer styling for a project
    """

    STYLE_URL_BASE = "https://raw.githubusercontent.com/linz/topographic-qgis/refs/heads/master/map-series/nztopo50/style-layer/"
    SVG_GRAPHICS_PATH = f"https://api.github.com/repos/linz/topographic-qgis/contents/map-series/nztopo50/symbol"
    PRODUCT_VIEW_STYLE_NAME = "Product View"

    def __init__(
        self, project_controller: ProjectController, message_bar: QgsMessageBar
    ):
        self._project_controller: ProjectController = project_controller
        self._message_bar: QgsMessageBar = message_bar
        self._message_item = None
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

        errors = self._download_task.errors[:]

        svg_dir = STORED_OBJECT_MANAGER.get_plugin_data_dir("svg")
        existing_svgs = (
            {p.name for p in svg_dir.glob("*.svg")} if svg_dir.exists() else set()
        )

        def _replace_svg_path(match: re.Match) -> str:
            nonlocal errors
            svg_name = match.group(2)
            if svg_name.startswith("topo"):
                svg_name = "nz" + svg_name
                if svg_name in existing_svgs:
                    errors.append(f"Renamed {svg_name} to nz{svg_name}")

            if svg_name.endswith("_poly.svg"):
                svg_name = svg_name[:-9] + ".svg"
                if svg_name in existing_svgs:
                    errors.append(f"Renamed {match.group(2)} to {svg_name}")

            if svg_name in existing_svgs:
                return f"localized:svg/{svg_name}"

            errors.append(f"SVG file {svg_name} is not stored in git repository")
            return match.group(0)

        for layer_name, layer in feature_type_layers:
            if layer_name not in styles:
                continue

            style_raw = styles[layer_name]
            doc = QDomDocument()

            # temporary hack to set localized data paths
            style_raw = re.sub(
                r'([^"\'>\s]*/)?([^"\'>\s]+\.svg)', _replace_svg_path, style_raw
            )

            # check XML validity before we proceed
            res, error_msg, _, __ = doc.setContent(style_raw)
            if res:
                layer_style_manager = layer.styleManager()
                layer_style_manager.removeStyle(self.PRODUCT_VIEW_STYLE_NAME)
                style_count = len(layer_style_manager.styles())
                layer_style_manager.addStyle(
                    self.PRODUCT_VIEW_STYLE_NAME, QgsMapLayerStyle(style_raw)
                )
                if style_count == 1 and layer_style_manager.styles() != [
                    self.PRODUCT_VIEW_STYLE_NAME
                ]:
                    # if only one style, remove the other
                    # TODO: handle real-world style name
                    layer_style_manager.removeStyle(
                        [
                            name
                            for name in layer_style_manager.styles()
                            if name != self.PRODUCT_VIEW_STYLE_NAME
                        ][0]
                    )
                layer.triggerRepaint()
            else:
                errors.append(error_msg)

        if errors:
            message_widget = self._message_bar.createMessage(
                "", "Some errors were encountered while updating layer styles."
            )
            details_button = QPushButton("Details")

            def show_warnings(_):
                if self._message_item and not sip.isdeleted(self._message_item):
                    self._message_bar.popWidget(self._message_item)
                    self._message_item = None

                dialog = QgsMessageOutput.createMessageOutput()
                dialog.setTitle("Update Layer Styles")
                long_message = "<p>Some errors were encountered while updating layer styles:</p><ul><li>"
                long_message += "</li><li>".join(errors)
                long_message += "</li></ul>"
                dialog.setMessage(
                    long_message, QgsMessageOutput.MessageType.MessageHtml
                )
                dialog.showMessage()

            details_button.clicked.connect(show_warnings)
            self._message_item = message_widget.layout().addWidget(details_button)
            self._message_bar.pushWidget(message_widget, Qgis.MessageLevel.Warning, 0)
        else:
            self._message_bar.pushSuccess("", "Layer styles successfully updated")


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
        self.errors: List[str] = []

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
            self.errors.append(f"Error parsing SVG metadata: {e}")

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
                        self.errors.append(f"Failed to write SVG {name}: {e}")
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
