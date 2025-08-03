import os

from PySide6.QtCore import QFile, QIODevice
from PySide6.QtCore import QUrl, QObject, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from Tool import Tool


class FileDownloader(QObject):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, url: str, save_path: str):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.manager = QNetworkAccessManager()
        self.reply = None
        self.file = None

    def start(self):
        request = QNetworkRequest(QUrl(self.url))
        self.reply = self.manager.get(request)
        self.reply.downloadProgress.connect(self.on_progress)
        self.reply.finished.connect(self.on_finished)
        self.reply.errorOccurred.connect(self.on_error)

        self.file = QFile(self.save_path)
        self.file.open(QIODevice.OpenModeFlag.WriteOnly)
        self.reply.readyRead.connect(self.on_ready_read)

    def on_progress(self, received, total):
        if total > 0:
            percent = int(received * 100 / total)
            self.progress.emit(percent)
        else:
            self.progress.emit(100)

    def on_ready_read(self):
        self.file.write(self.reply.readAll())

    def on_finished(self):
        self.file.close()
        self.reply.deleteLater()
        self.finished.emit(self.save_path)

    def on_error(self, code):
        self.file.close()
        self.reply.abort()
        self.error.emit(f"下载失败：{code}")

class ToolDownloader(FileDownloader):
    finished = Signal(object, int)  # Tool, mirror
    error = Signal(str, object, int)  # msg, tool, mirror
    def __init__(self, tool: Tool, mirror: int):
        super().__init__(tool.get_mirrors()[mirror], os.path.join(tool.get_path(), f"{tool.name}.PFTDownloading"))
        self.tool = tool
        self.mirror = mirror

    def on_finished(self):
        self.file.close()
        self.reply.deleteLater()
        self.finished.emit(self.tool, self.mirror)

    def on_error(self, code):
        self.file.close()
        self.reply.abort()
        self.error.emit(f"下载失败：{code}", self.tool, self.mirror)