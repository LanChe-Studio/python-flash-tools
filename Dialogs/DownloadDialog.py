import os
import platform
import sys
import tarfile
import threading
import urllib
import zipfile

from PySide6.QtCore import QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QProgressBar,
                               QDialog,
                               QTextEdit)


class DownloadDialog(QDialog):
    """依赖下载对话框"""

    def __init__(self, tools, parent=None):
        super().__init__(parent)
        self.setWindowTitle("依赖未安装")
        self.setWindowIcon(QIcon(":/icons/download.png"))
        self.setGeometry(300, 300, 500, 300)
        self.tools = tools
        self.downloading = False
        self.download_success = False
        self.tool_paths = {}

        layout = QVBoxLayout()

        # 提示信息
        label = QLabel(f"以下工具缺失: {', '.join(tools)}\n是否现在下载?")
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
        self.download_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.download_btn.clicked.connect(self.start_download)
        self.later_btn = QPushButton("稍后设置")
        self.later_btn.setStyleSheet("background-color: #f44336; color: white; padding: 8px;")
        self.later_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.later_btn)
        btn_layout.addWidget(self.download_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def start_download(self):
        """开始下载依赖"""
        self.downloading = True
        self.download_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_output.setVisible(True)

        # 启动下载线程
        threading.Thread(target=self.download_tools, daemon=True).start()

    def download_tools(self):
        """下载工具"""
        self.log("开始下载缺失的工具...")
        self.progress_bar.setValue(0)

        tool_count = len(self.tools)
        downloaded_count = 0

        for tool in self.tools:
            if tool == "ADB":
                self.log("下载ADB工具...")
                tool_path = self.download_adb()
                if tool_path:
                    self.tool_paths["adb"] = tool_path
                    self.log(f"ADB下载成功: {tool_path}")
                    # 保存设置
                    settings = QSettings("PythonFlashTools", "FlashTool")
                    settings.setValue("adb_path", tool_path)
                    downloaded_count += 1
                else:
                    self.log("ADB下载失败")
            elif tool == "Fastboot":
                self.log("下载Fastboot工具...")
                tool_path = self.download_fastboot()
                if tool_path:
                    self.tool_paths["fastboot"] = tool_path
                    self.log(f"Fastboot下载成功: {tool_path}")
                    # 保存设置
                    settings = QSettings("PythonFlashTools", "FlashTool")
                    settings.setValue("fastboot_path", tool_path)
                    downloaded_count += 1
                else:
                    self.log("Fastboot下载失败")
            elif tool == "MTKClient":
                self.log("下载MTKClient工具...")
                tool_path = self.download_mtkclient()
                if tool_path:
                    self.tool_paths["mtk"] = tool_path
                    self.log(f"MTKClient下载成功: {tool_path}")
                    # 保存设置
                    settings = QSettings("PythonFlashTools", "FlashTool")
                    settings.setValue("mtk_path", tool_path)
                    downloaded_count += 1
                else:
                    self.log("MTKClient下载失败")

            # 更新进度
            progress = int(downloaded_count / tool_count * 100)
            self.progress_bar.setValue(progress)

        if downloaded_count == tool_count:
            self.log("所有工具下载完成!")
            self.download_success = True
            self.accept()
        else:
            self.log(f"部分工具下载失败 ({downloaded_count}/{tool_count})")
            self.download_btn.setEnabled(True)
            self.later_btn.setEnabled(True)

    def download_adb(self):
        """下载ADB工具"""
        system = platform.system().lower()
        mirrors = [
            f"https://dl.google.com/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.bfsu.edu.cn/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.tuna.tsinghua.edu.cn/github-release/android/platform-tools/LatestRelease/platform-tools-latest-{system}.zip"
        ]

        return self.download_tool("adb", mirrors)

    def download_fastboot(self):
        """下载Fastboot工具"""
        system = platform.system().lower()
        mirrors = [
            f"https://dl.google.com/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.bfsu.edu.cn/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.tuna.tsinghua.edu.cn/github-release/android/platform-tools/LatestRelease/platform-tools-latest-{system}.zip"
        ]

        return self.download_tool("fastboot", mirrors)

    def download_mtkclient(self):
        """下载MTKClient工具"""
        mirrors = [
            "https://github.com/bkerler/mtkclient/archive/refs/heads/main.zip",
            "https://ghproxy.com/https://github.com/bkerler/mtkclient/archive/refs/heads/main.zip"
        ]

        return self.download_tool("mtk", mirrors)

    def download_tool(self, tool_name, mirrors):
        """通用工具下载方法"""
        try:
            # 创建永久工具目录
            app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            tool_dir = os.path.join(app_dir, "tools", tool_name)
            os.makedirs(tool_dir, exist_ok=True)

            zip_path = os.path.join(tool_dir, f"{tool_name}.zip")
            downloaded = False

            # 下载进度回调
            def report_progress(count, block_size, total_size):
                if total_size > 0:
                    percent = min(100, int(count * block_size * 100 / total_size))
                    self.progress_bar.setValue(percent)

            for mirror in mirrors:
                try:
                    self.log(f"尝试从 {mirror} 下载...")
                    urllib.request.urlretrieve(mirror, zip_path, report_progress)
                    downloaded = True
                    self.log(f"{tool_name} 下载完成")
                    break
                except Exception as e:
                    self.log(f"下载失败: {str(e)}")
                    continue

            if not downloaded:
                self.log("所有镜像源下载失败")
                return None

            # 解压文件
            try:
                self.log("解压文件...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tool_dir)
            except zipfile.BadZipFile:
                try:
                    with tarfile.open(zip_path, 'r:*') as tar_ref:
                        tar_ref.extractall(tool_dir)
                except Exception as e:
                    self.log(f"解压失败: {str(e)}")
                    return None

            # 删除ZIP文件
            try:
                os.remove(zip_path)
            except:
                pass

            # 查找工具
            tool_path = None
            for root, dirs, files in os.walk(tool_dir):
                for file in files:
                    if tool_name == "mtk":
                        if file.lower() == "mtk.py":
                            tool_path = os.path.join(root, file)
                    else:
                        if file.lower().startswith(tool_name) and not file.endswith('.zip'):
                            tool_path = os.path.join(root, file)

                    if tool_path:
                        # 设置权限(非Windows)
                        if platform.system().lower() != "windows":
                            os.chmod(tool_path, 0o755)
                        self.log(f"找到工具: {tool_path}")
                        break
                if tool_path:
                    break

            if not tool_path:
                self.log(f"解压后未找到{tool_name}主文件")
                return None

            return tool_path
        except Exception as e:
            self.log(f"下载{tool_name}失败: {str(e)}")
            return None

    def log(self, message):
        """记录日志"""
        self.log_output.append(message)