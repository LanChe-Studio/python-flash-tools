import os
import platform
import tarfile
import zipfile

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QProgressBar,
                               QDialog,
                               QTextEdit)

from FileDownloader import ToolDownloader
from Tool import Tool


class DownloadDialog(QDialog):
    """依赖下载对话框"""

    def __init__(self, tools: list[Tool], parent=None):
        super().__init__(parent)
        self._downloader = None
        self.setWindowTitle("依赖未安装")
        self.setWindowIcon(QIcon(":/icons/download.png"))
        self.setGeometry(300, 300, 500, 300)
        self.tools = tools
        self.downloading = False
        self.download_success = False
        self.tool_paths = {}
        self.__downloading_tool = -1
        self.__downloaded_success = 0

        layout = QVBoxLayout()

        # 提示信息
        label = QLabel(f"以下工具缺失: {', '.join(tool.name for tool in tools)}\n是否现在下载?")
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 12pt; padding: 10px;")
        layout.addWidget(label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("height: 25px;")
        layout.addWidget(self.progress_bar)

        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setVisible(False)
        self.log_output.setStyleSheet("font-family: monospace; font-size: 10pt;")
        layout.addWidget(self.log_output)

        # 按钮布局
        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("现在下载")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; 
                color: white; 
                font-weight: bold; 
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.download_btn.clicked.connect(self.start_download)
        self.later_btn = QPushButton("稍后设置")
        self.later_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336; 
                color: white; 
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.later_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.later_btn)
        btn_layout.addWidget(self.download_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def start_download(self):
        """开始下载依赖"""
        self.log('开始下载')
        self.downloading = True
        self.download_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_output.setVisible(True)

        # 启动下载线程
        self.download_tools()

    def download_tools(self):
        """下载工具"""
        self.log("开始下载缺失的工具...")

        self.__download_next()

    def __download_complete(self):
        """工具全部下载完成(无论成功与否)"""
        if self.__downloaded_success == len(self.tools):
            self.log("所有工具下载完成!")
            self.download_success = True
            self.accept()
        else:
            self.log(f"部分工具下载失败 ({self.__downloaded_success}/{len(self.tools)})")
        self.downloading = False
        self.download_btn.setEnabled(True)
        self.later_btn.setEnabled(True)


    def __download_next(self):
        """下载下一个工具"""
        self.__downloading_tool += 1
        if self.__downloading_tool >= len(self.tools):
            self.log("所有工具下载完成!")
            self.__download_complete()
            return
        self.download_tool(self.tools[self.__downloading_tool])


    def download_tool(self, tool: Tool, mirror: int = 0):
        """用指定镜像下载工具"""
        self.log(f"下载{tool.name}工具...")
        self.progress_bar.setValue(0)

        try:
            # 创建工具目录
            os.makedirs(tool.get_path(), exist_ok=True)

            self.log(f"尝试从 {tool.get_mirrors()[mirror]} 下载...")

            # 创建downloader
            self._downloader = ToolDownloader(tool, mirror)

            # 绑定触发器
            self._downloader.progress.connect(self.progress_bar.setValue)
            self._downloader.finished.connect(self.__download_succeed)
            self._downloader.error.connect(self.__download_failed)
            self._downloader.start()
        except Exception as e:
            self.log(f"下载{tool.name}失败: {str(e)}")


    def __download_succeed(self, tool: Tool, mirror: int):
        """工具下载完成"""
        self.log(f"{tool.name} 下载完成")

        # 解压失败,当作下载失败处理
        if not self.__unzip_tool(tool):
            self.__download_failed("", tool, mirror)
            return

        # 下载成功,下载下一个工具
        self.__downloaded_success += 1
        self.__download_next()


    def __download_failed(self, msg: str, tool: Tool, mirror: int):
        """工具下载失败"""
        self.log(msg)

        # 使用下一个镜像下载
        mirror += 1
        if mirror >= len(tool.get_mirrors()):
            # 所有镜像尝试完毕,工具下载失败,下载下一个工具
            self.log(f"{tool.name} 所有镜像下载失败")
            self.__download_next()
            return

        # 尝试下一个镜像
        self.download_tool(tool, mirror)


    def __unzip_tool(self, tool: Tool):
        zip_path = os.path.join(tool.get_path(), f"{tool.name}.PFTDownloading")

        # 解压文件
        if not os.path.exists(zip_path):
            self.log(f"{tool.name} 下载完成但未找到压缩包，可能下载失败")
            return False

        self.log("解压文件...")

        try:
            if zipfile.is_zipfile(zip_path):
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tool.get_path())
            elif tarfile.is_tarfile(zip_path):
                with tarfile.open(zip_path, 'r:*') as tar_ref:
                    tar_ref.extractall(tool.get_path())
            else:
                self.log(f"{tool.name} 下载完成但压缩包格式不支持")
                return False
        except (zipfile.BadZipFile, tarfile.ReadError) as e:
            self.log(f"{tool.name} 解压失败：{str(e)}")
            return False


        # 删除ZIP文件
        os.remove(zip_path)

        # 添加可运行权限
        if platform.system().lower() != "windows":
            self.log(f"检测到非windows系统,为工具{tool.name}添加可运行权限")
            for runnable_file in tool.get_runnable_files():
                runnable_file_full = os.path.join(tool.get_path(), runnable_file)
                if not os.path.exists(runnable_file_full):
                    self.log(f"{tool.name} 下载完成但未找到可执行文件，可能下载失败")
                    return False
                os.chmod(runnable_file_full, 0o755)

        return True



    def log(self, message):
        """记录日志"""
        QTimer.singleShot(0, lambda: self.log_output.append(message))