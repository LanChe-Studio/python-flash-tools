import os
import sys
import time
import threading
import subprocess
import platform
import tempfile
import urllib.request
import zipfile
import shutil
import tarfile
import re
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QProgressBar,
                             QFileDialog, QMessageBox, QGroupBox, QDialog, 
                             QTabWidget, QTextEdit, QLineEdit, QPlainTextEdit, QCheckBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QSettings
from PyQt5.QtGui import QFont, QTextCursor, QColor

def backup_partition_fastboot(self, partition, output_path):
    """使用Fastboot备份分区"""
    if not self.fastboot_path:
        self.last_error = "Fastboot工具未找到"
        return False
        
    try:
        # 获取分区大小
        result = subprocess.run([self.fastboot_path, "getvar", f"partition-size:{partition}"],
                             capture_output=True, text=True, encoding='utf-8', errors='ignore',
                             timeout=60)
        if result.returncode != 0:
            self.last_error = f"无法获取分区大小: {result.stderr or '未知错误'}"
            return False
            
        # 解析分区大小
        size_line = [line for line in result.stdout.splitlines() if "partition-size" in line]
        if not size_line:
            self.last_error = "无法解析分区大小"
            return False
            
        size_str = size_line[0].split(":")[1].strip()
        if not size_str.isdigit():
            self.last_error = f"无效的分区大小: {size_str}"
            return False
            
        partition_size = int(size_str)
        
        # 备份分区
        with open(output_path, 'wb') as f:
            result = subprocess.run([self.fastboot_path, "fetch", f"{partition}"],
                                 stdout=f, stderr=subprocess.PIPE,
                                 timeout=300)
            
        if result.returncode == 0:
            actual_size = os.path.getsize(output_path)
            if actual_size == partition_size:
                return True
            else:
                self.last_error = f"备份文件大小不匹配: 预期 {partition_size} 字节, 实际 {actual_size} 字节"
                return False
        else:
            self.last_error = result.stderr.decode('utf-8', 'ignore') if result.stderr else "未知错误"
            return False
    except Exception as e:
        self.last_error = str(e)
        return False

class DownloadDialog(QDialog):
    """依赖下载对话框"""
    def __init__(self, tools, parent=None):
        super().__init__(parent)
        self.setWindowTitle("依赖未安装")
        self.setGeometry(300, 300, 500, 300)
        self.tools = tools
        self.downloading = False
        
        layout = QVBoxLayout()
        
        # 提示信息
        label = QLabel(f"以下工具缺失: {', '.join(tools)}\n是否现在下载?")
        label.setWordWrap(True)
        layout.addWidget(label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setVisible(False)
        layout.addWidget(self.log_output)
        
        # 按钮布局
        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("现在下载")
        self.download_btn.clicked.connect(self.start_download)
        self.later_btn = QPushButton("稍后设置")
        self.later_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.later_btn)
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
        
        for tool in self.tools:
            if tool == "ADB":
                self.log("下载ADB工具...")
                self.download_adb()
            elif tool == "Fastboot":
                self.log("下载Fastboot工具...")
                self.download_fastboot()
            elif tool == "MTKClient":
                self.log("下载MTKClient工具...")
                self.download_mtkclient()
        
        self.log("所有工具下载完成!")
        self.accept()
    
    def download_adb(self):
        """下载ADB工具"""
        system = platform.system().lower()
        mirrors = [
            f"https://dl.google.com/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.bfsu.edu.cn/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.tuna.tsinghua.edu.cn/github-release/android/platform-tools/LatestRelease/platform-tools-latest-{system}.zip"
        ]
        
        self.download_tool("adb", mirrors)
    
    def download_fastboot(self):
        """下载Fastboot工具"""
        system = platform.system().lower()
        mirrors = [
            f"https://dl.google.com/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.bfsu.edu.cn/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.tuna.tsinghua.edu.cn/github-release/android/platform-tools/LatestRelease/platform-tools-latest-{system}.zip"
        ]
        
        self.download_tool("fastboot", mirrors)
    
    def download_mtkclient(self):
        """下载MTKClient工具"""
        mirrors = [
            "https://github.com/bkerler/mtkclient/archive/refs/heads/main.zip",
            "https://ghproxy.com/https://github.com/bkerler/mtkclient/archive/refs/heads/main.zip"
        ]
        
        self.download_tool("mtk", mirrors)
    
    def download_tool(self, tool_name, mirrors):
        """通用工具下载方法"""
        try:
            temp_dir = tempfile.mkdtemp(prefix=f"{tool_name}_temp_")
            zip_path = os.path.join(temp_dir, f"{tool_name}.zip")
            downloaded = False
            
            # 下载进度回调
            def report_progress(count, block_size, total_size):
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
                return
            
            # 解压文件
            try:
                self.log("解压文件...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            except zipfile.BadZipFile:
                try:
                    with tarfile.open(zip_path, 'r:*') as tar_ref:
                        tar_ref.extractall(temp_dir)
                except Exception as e:
                    self.log(f"解压失败: {str(e)}")
                    return
            
            # 查找工具
            tool_path = None
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().startswith(tool_name) and not file.endswith('.zip'):
                        tool_path = os.path.join(root, file)
                        # 设置权限(非Windows)
                        if platform.system().lower() != "windows":
                            os.chmod(tool_path, 0o755)
                        self.log(f"找到工具: {tool_path}")
                        break
                if tool_path:
                    break
            
            if not tool_path:
                self.log(f"解压后未找到{tool_name}主文件")
            
        except Exception as e:
            self.log(f"下载{tool_name}失败: {str(e)}")
            return None
    
    def log(self, message):
        """记录日志"""
        self.log_output.append(message)

class DebugLogDialog(QDialog):
    """Debug日志对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("调试日志")
        self.setGeometry(200, 200, 800, 500)
        
        layout = QVBoxLayout()
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("font-family: monospace; font-size: 10pt;")
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        close_btn.setFixedWidth(100)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addWidget(self.log_output)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def append_log(self, message):
        """安全添加日志"""
        self.log_output.moveCursor(QTextCursor.End)
        self.log_output.insertPlainText(message + "\n")
        self.log_output.moveCursor(QTextCursor.End)

class SettingsDialog(QDialog):
    """设置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setGeometry(200, 200, 500, 400)
        
        self.settings = QSettings("PythonFlashTools", "FlashTool")
        
        layout = QVBoxLayout()
        
        # ADB路径设置
        adb_group = QGroupBox("ADB设置")
        adb_layout = QVBoxLayout()
        
        self.adb_path_edit = QLineEdit()
        self.adb_path_edit.setPlaceholderText("自动检测或自定义ADB路径")
        adb_browse_btn = QPushButton("浏览...")
        adb_browse_btn.clicked.connect(self._browse_adb_path)
        
        adb_path_layout = QHBoxLayout()
        adb_path_layout.addWidget(self.adb_path_edit)
        adb_path_layout.addWidget(adb_browse_btn)
        
        adb_layout.addLayout(adb_path_layout)
        adb_group.setLayout(adb_layout)
        
        # Fastboot路径设置
        fastboot_group = QGroupBox("Fastboot设置")
        fastboot_layout = QVBoxLayout()
        
        self.fastboot_path_edit = QLineEdit()
        self.fastboot_path_edit.setPlaceholderText("自动检测或自定义Fastboot路径")
        fastboot_browse_btn = QPushButton("浏览...")
        fastboot_browse_btn.clicked.connect(self._browse_fastboot_path)
        
        fastboot_path_layout = QHBoxLayout()
        fastboot_path_layout.addWidget(self.fastboot_path_edit)
        fastboot_path_layout.addWidget(fastboot_browse_btn)
        
        fastboot_layout.addLayout(fastboot_path_layout)
        fastboot_group.setLayout(fastboot_layout)
        
        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save_settings)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        # 加载当前设置
        self._load_settings()
        
        # 组装布局
        layout.addWidget(adb_group)
        layout.addWidget(fastboot_group)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def _browse_adb_path(self):
        """浏览ADB路径"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择ADB可执行文件", "", 
            "可执行文件 (*.exe);;所有文件 (*)")
        
        if file_path:
            self.adb_path_edit.setText(file_path)
    
    def _browse_fastboot_path(self):
        """浏览Fastboot路径"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Fastboot可执行文件", "", 
            "可执行文件 (*.exe);;所有文件 (*)")
        
        if file_path:
            self.fastboot_path_edit.setText(file_path)
    
    def _load_settings(self):
        """加载设置"""
        self.adb_path_edit.setText(self.settings.value("adb_path", ""))
        self.fastboot_path_edit.setText(self.settings.value("fastboot_path", ""))
    
    def _save_settings(self):
        """保存设置"""
        self.settings.setValue("adb_path", self.adb_path_edit.text())
        self.settings.setValue("fastboot_path", self.fastboot_path_edit.text())
        self.accept()

class ADB:
    """ADB工具管理类"""
    def __init__(self, host='127.0.0.1', port=5037):
        self.host = host
        self.port = port
        self.adb_path = None
        self.fastboot_path = None
        self.last_error = ""
        self.temp_dir = None
        self.settings = QSettings("PythonFlashTools", "FlashTool")
        self._init_adb()
        self._init_fastboot()

    def _get_platform_specific_name(self, tool):
        """获取平台特定的可执行文件名"""
        return f"{tool}.exe" if platform.system().lower() == "windows" else tool

    def _find_tool(self, tool_name, version_cmd, common_paths):
        """通用工具查找方法"""
        # 首先检查用户自定义路径
        custom_path = self.settings.value(f"{tool_name}_path", "")
        if custom_path and os.path.exists(custom_path):
            try:
                result = subprocess.run([custom_path, version_cmd], 
                                      capture_output=True, text=True, 
                                      encoding='utf-8', errors='ignore', 
                                      timeout=2)
                if result.returncode == 0:
                    return custom_path
            except:
                pass
        
        # 查找系统PATH中的工具
        tool_exec = self._get_platform_specific_name(tool_name)
        try:
            result = subprocess.run([tool_exec, version_cmd], 
                                  capture_output=True, text=True, 
                                  encoding='utf-8', errors='ignore', 
                                  timeout=2)
            if result.returncode == 0:
                return tool_exec
        except:
            pass
        
        # 查找常见路径中的工具
        for path in common_paths:
            if not os.path.exists(path):
                continue
            try:
                result = subprocess.run([path, version_cmd], 
                                      capture_output=True, text=True, 
                                      encoding='utf-8', errors='ignore', 
                                      timeout=2)
                if result.returncode == 0:
                    return path
            except:
                continue
                
        return None

    def _init_adb(self):
        """初始化ADB"""
        common_paths = [
            "/usr/bin/adb",
            "/usr/local/bin/adb",
            os.path.join(os.environ.get("ANDROID_HOME", ""), "platform-tools", "adb"),
            os.path.join(os.environ.get("ANDROID_SDK_ROOT", ""), "platform-tools", "adb"),
            "C:\\Program Files (x86)\\Android\\android-sdk\\platform-tools\\adb.exe",
            os.path.expanduser("~/Library/Android/sdk/platform-tools/adb")
        ]
        
        adb_path = self._find_tool("adb", "version", common_paths)
        if adb_path:
            self.adb_path = adb_path
            return
        
        # 尝试下载ADB
        system = platform.system().lower()
        mirrors = [
            f"https://dl.google.com/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.bfsu.edu.cn/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.tuna.tsinghua.edu.cn/github-release/android/platform-tools/LatestRelease/platform-tools-latest-{system}.zip"
        ]
        
        self.adb_path = self._download_tool("adb", mirrors)

    def _init_fastboot(self):
        """初始化Fastboot"""
        common_paths = [
            "/usr/bin/fastboot",
            "/usr/local/bin/fastboot",
            os.path.join(os.environ.get("ANDROID_HOME", ""), "platform-tools", "fastboot"),
            os.path.join(os.environ.get("ANDROID_SDK_ROOT", ""), "platform-tools", "fastboot"),
            "C:\\Program Files (x86)\\Android\\android-sdk\\platform-tools\\fastboot.exe",
            os.path.expanduser("~/Library/Android/sdk/platform-tools/fastboot")
        ]
        
        fastboot_path = self._find_tool("fastboot", "--version", common_paths)
        if fastboot_path:
            self.fastboot_path = fastboot_path
            return
        
        # 尝试下载Fastboot
        system = platform.system().lower()
        mirrors = [
            f"https://dl.google.com/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.bfsu.edu.cn/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.tuna.tsinghua.edu.cn/github-release/android/platform-tools/LatestRelease/platform-tools-latest-{system}.zip"
        ]
        
        self.fastboot_path = self._download_tool("fastboot", mirrors)

    def _download_tool(self, tool_name, mirrors):
        """下载工具"""
        try:
            if not self.temp_dir:
                self.temp_dir = tempfile.mkdtemp(prefix=f"{tool_name}_temp_")
            
            zip_path = os.path.join(self.temp_dir, f"{tool_name}.zip")
            downloaded = False
            
            for mirror in mirrors:
                try:
                    print(f"尝试从 {mirror} 下载{tool_name}...")
                    urllib.request.urlretrieve(mirror, zip_path)
                    downloaded = True
                    print("下载完成")
                    break
                except Exception as e:
                    print(f"下载失败: {str(e)}")
                    continue
            
            if not downloaded:
                self.last_error = "所有镜像源下载失败"
                return None
            
            # 解压文件
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(self.temp_dir)
            except zipfile.BadZipFile:
                try:
                    with tarfile.open(zip_path, 'r:*') as tar_ref:
                        tar_ref.extractall(self.temp_dir)
                except Exception as e:
                    self.last_error = f"解压失败: {str(e)}"
                    return None
            
            # 查找工具
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    if file.lower().startswith(tool_name) and not file.endswith('.zip'):
                        tool_path = os.path.join(root, file)
                        # 设置权限(非Windows)
                        if platform.system().lower() != "windows":
                            os.chmod(tool_path, 0o755)
                        return tool_path
            
            self.last_error = f"解压后未找到{tool_name}主文件"
            return None
        except Exception as e:
            self.last_error = f"下载{tool_name}失败: {str(e)}"
            return None

    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                print(f"清理临时目录失败: {str(e)}")

    def _ensure_adb_server(self):
        """确保ADB服务器运行"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return False
            
        try:
            # 先杀死可能存在的旧服务器进程
            subprocess.run([self.adb_path, "kill-server"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL,
                         timeout=5)
            
            # 启动新服务器
            subprocess.run([self.adb_path, "start-server"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL,
                         timeout=10)
            
            # 等待服务器完全启动
            time.sleep(2)
            return True
        except Exception as e:
            self.last_error = f"启动ADB服务失败: {str(e)}"
            return False
    
    def devices(self):
        """获取设备列表"""
        if not self._ensure_adb_server():
            return []
            
        try:
            result = subprocess.run([self.adb_path, "devices"], 
                                  capture_output=True, 
                                  text=True,
                                  encoding='utf-8',
                                  errors='ignore',
                                  timeout=10)
            if result.returncode == 0:
                # 解析设备列表
                devices = []
                for line in result.stdout.splitlines():
                    if line and not line.startswith('List of') and '\t' in line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            devices.append((parts[0], parts[1]))
                return devices
        except Exception as e:
            self.last_error = str(e)
            
        return []

    def fastboot_devices(self):
        """获取fastboot设备列表"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return []
            
        try:
            result = subprocess.run([self.fastboot_path, "devices"], 
                                  capture_output=True, 
                                  text=True,
                                  encoding='utf-8',
                                  errors='ignore',
                                  timeout=10)
            if result.returncode == 0:
                # 解析设备列表
                devices = []
                for line in result.stdout.splitlines():
                    if line and '\t' in line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            devices.append((parts[0], parts[1]))
                return devices
        except Exception as e:
            self.last_error = str(e)
            
        return []
    
    def reboot(self, mode=None):
        """重启设备"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return False, "ADB工具未找到"
            
        cmd = [self.adb_path, "reboot"]
        if mode in ["bootloader", "recovery"]:
            cmd.append(mode)
            
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                  timeout=15, encoding='utf-8', errors='ignore')
            
            # 检查授权问题
            output = result.stdout + result.stderr
            if "unauthorized" in output or "device unauthorized" in output:
                self.last_error = "设备未授权，请检查设备屏幕并确认授权"
                return False, self.last_error
            
            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "未知错误"
                return False, self.last_error
            return True, ""
        except Exception as e:
            self.last_error = str(e)
            return False, str(e)

    def fastboot_reboot(self):
        """Fastboot模式重启"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False, "Fastboot工具未找到"
            
        try:
            result = subprocess.run([self.fastboot_path, "reboot"], 
                                  capture_output=True,
                                  text=True,
                                  encoding='utf-8',
                                  errors='ignore',
                                  timeout=15)
            
            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "未知错误"
                return False, self.last_error
            return True, ""
        except Exception as e:
            self.last_error = str(e)
            return False, str(e)

    def execute_adb_command(self, command):
        """执行ADB命令"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return None
            
        try:
            result = subprocess.run([self.adb_path] + command.split(),
                                  capture_output=True,
                                  text=True,
                                  timeout=60,
                                  encoding='utf-8',
                                  errors='ignore')
            
            # 检查授权问题
            output = result.stdout + result.stderr
            if "unauthorized" in output or "device unauthorized" in output:
                return {
                    'success': False,
                    'output': result.stdout,
                    'error': "设备未授权，请检查设备屏幕并确认授权"
                }
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            }
        except Exception as e:
            self.last_error = str(e)
            return None

    def execute_fastboot_command(self, command):
        """执行Fastboot命令"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return None
            
        try:
            result = subprocess.run([self.fastboot_path] + command.split(),
                                  capture_output=True,
                                  text=True,
                                  timeout=60,
                                  encoding='utf-8',
                                  errors='ignore')
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            }
        except Exception as e:
            self.last_error = str(e)
            return None

    def unlock_bootloader(self):
        """解锁Bootloader"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False, "Fastboot工具未找到"
            
        try:
            result = subprocess.run([self.fastboot_path, "flashing", "unlock"],
                                  capture_output=True,
                                  text=True,
                                  timeout=60,
                                  encoding='utf-8',
                                  errors='ignore')
            if result.returncode != 0:
                result = subprocess.run([self.fastboot_path, "oem", "unlock"],
                                      capture_output=True,
                                      text=True,
                                      timeout=60,
                                      encoding='utf-8',
                                      errors='ignore')
            
            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "解锁失败"
                return False, self.last_error
            return True, ""
        except Exception as e:
            self.last_error = str(e)
            return False, str(e)

    def lock_bootloader(self):
        """锁定Bootloader"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False, "Fastboot工具未找到"
            
        try:
            result = subprocess.run([self.fastboot_path, "flashing", "lock"],
                                  capture_output=True,
                                  text=True,
                                  timeout=60,
                                  encoding='utf-8',
                                  errors='ignore')
            if result.returncode != 0:
                result = subprocess.run([self.fastboot_path, "oem", "lock"],
                                      capture_output=True,
                                      text=True,
                                      timeout=60,
                                      encoding='utf-8',
                                      errors='ignore')
            
            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "锁定失败"
                return False, self.last_error
            return True, ""
        except Exception as e:
            self.last_error = str(e)
            return False, str(e)

    def flash_partition(self, partition, image_path):
        """刷入分区"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False
            
        try:
            # 增加重试机制
            max_retries = 5
            retry_count = 0
            success = False
            error_log = []
            
            while not success and retry_count < max_retries:
                try:
                    # 检查设备连接
                    devices = self.fastboot_devices()
                    if not devices:
                        error_log.append(f"第{retry_count+1}次重试: 未检测到Fastboot设备")
                        time.sleep(2)
                        retry_count += 1
                        continue
                    
                    # 执行刷入命令
                    result = subprocess.run([self.fastboot_path, "flash", partition, image_path],
                                          capture_output=True, text=True, encoding='utf-8', errors='ignore',
                                          timeout=300)
                    if result.returncode == 0:
                        return True
                    else:
                        error_msg = result.stderr.strip() or result.stdout.strip() or "刷入失败"
                        error_log.append(f"第{retry_count+1}次刷入失败: {error_msg}")
                        time.sleep(2)
                        retry_count += 1
                except Exception as e:
                    error_log.append(f"刷入异常: {str(e)}")
                    time.sleep(2)
                    retry_count += 1
            
            self.last_error = "; ".join(error_log)
            return False
        except Exception as e:
            self.last_error = str(e)
            return False

class FlashTool(QMainWindow):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str, str)
    mode_signal = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Flash Tools V1.5-Lite")
        self.setGeometry(100, 100, 800, 600)
        
        # 初始化变量
        self.current_mode = None
        self.device_id = None
        self.adb = ADB()
        self.debug_log_dialog = None
        self.firmware_path = ""
        self.backup_path = ""
        self.operation_in_progress = False
        self.settings_dialog = None
        self.settings = QSettings("PythonFlashTools", "FlashTool")
        self.running = True  # 设备检测线程运行标志
        
        # 连接信号
        self.log_signal.connect(self._log_message)
        self.progress_signal.connect(self._update_progress)
        self.status_signal.connect(self._update_status)
        self.mode_signal.connect(self._handle_mode_change)
        
        self._init_ui()
        self._start_device_check()
        self._check_tools()  # 检查工具依赖
    
    def _check_tools(self):
        """检查工具依赖"""
        missing_tools = []
        if not self.adb.adb_path:
            missing_tools.append("ADB")
        if not self.adb.fastboot_path:
            missing_tools.append("Fastboot")
        
        if missing_tools:
            download_dialog = DownloadDialog(missing_tools, self)
            if download_dialog.exec_() == QDialog.Accepted:
                # 重新初始化ADB类以加载下载的工具
                self.adb = ADB()
                self.log_signal.emit("工具已下载并初始化完成")
            else:
                self.log_signal.emit("您可以在设置中配置工具路径")
    
    def _init_ui(self):
        """初始化用户界面"""
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 设备标签页
        device_tab = QWidget()
        self._init_device_tab(device_tab)
        self.tabs.addTab(device_tab, "设备")
        
        # 刷机标签页
        flash_tab = QWidget()
        self._init_flash_tab(flash_tab)
        self.tabs.addTab(flash_tab, "刷机")
        
        # 备份标签页
        backup_tab = QWidget()
        self._init_backup_tab(backup_tab)
        self.tabs.addTab(backup_tab, "备份")
        
        # ADB命令标签页
        adb_tab = QWidget()
        self._init_adb_tab(adb_tab)
        self.tabs.addTab(adb_tab, "ADB命令")
        
        # Fastboot命令标签页
        fastboot_tab = QWidget()
        self._init_fastboot_tab(fastboot_tab)
        self.tabs.addTab(fastboot_tab, "Fastboot命令")
        
        # BL解锁标签页
        unlock_tab = QWidget()
        self._init_unlock_tab(unlock_tab)
        self.tabs.addTab(unlock_tab, "BL解锁")
        
        # 底部状态栏
        self.status_bar = QLabel()
        self.status_bar.setStyleSheet("font-size: 10pt; padding: 5px;")
        
        # 工具按钮
        tool_btn_layout = QHBoxLayout()
        self.settings_btn = QPushButton("设置")
        self.settings_btn.clicked.connect(self._show_settings)
        self.debug_btn = QPushButton("调试日志")
        self.debug_btn.clicked.connect(self._show_debug_log)
        self.about_btn = QPushButton("关于")
        self.about_btn.clicked.connect(self._show_about)
        
        tool_btn_layout.addStretch()
        tool_btn_layout.addWidget(self.settings_btn)
        tool_btn_layout.addWidget(self.debug_btn)
        tool_btn_layout.addWidget(self.about_btn)
        
        # 组装主界面
        layout.addWidget(self.tabs)
        layout.addWidget(self.status_bar)
        layout.addLayout(tool_btn_layout)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
        # 初始化Debug日志对话框
        self.debug_log_dialog = DebugLogDialog(self)
        self.settings_dialog = SettingsDialog(self)
    
    def _init_device_tab(self, tab):
        """初始化设备标签页"""
        layout = QVBoxLayout()
        
        # 设备状态
        self.device_status = QLabel("等待设备连接...")
        self.device_status.setStyleSheet("font-size: 12pt; font-weight: bold;")
        
        # 设备信息
        self.device_info = QLabel()
        self.device_info.setStyleSheet("font-size: 10pt;")
        
        # 设备详细信息
        self.device_details = QLabel("设备详细信息将在此显示")
        self.device_details.setStyleSheet("font-size: 9pt;")
        self.device_details.setWordWrap(True)
        
        # 模式切换按钮
        btn_layout = QHBoxLayout()
        self.bootloader_btn = QPushButton("进入Bootloader")
        self.bootloader_btn.clicked.connect(self._enter_bootloader)
        self.recovery_btn = QPushButton("进入Recovery")
        self.recovery_btn.clicked.connect(self._enter_recovery)
        self.reboot_btn = QPushButton("重启设备")
        self.reboot_btn.clicked.connect(self._reboot_device)
        
        btn_layout.addWidget(self.bootloader_btn)
        btn_layout.addWidget(self.recovery_btn)
        btn_layout.addWidget(self.reboot_btn)
        
        # ADB工具状态
        self.adb_status = QLabel("ADB: 检测中...")
        self.fastboot_status = QLabel("Fastboot: 检测中...")
        
        # 组装布局
        layout.addWidget(self.device_status)
        layout.addWidget(self.device_info)
        layout.addWidget(self.device_details)
        layout.addLayout(btn_layout)
        layout.addWidget(self.adb_status)
        layout.addWidget(self.fastboot_status)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def _init_flash_tab(self, tab):
        """初始化刷机标签页"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 固件选择
        file_layout = QHBoxLayout()
        self.file_label = QLabel("未选择固件")
        select_btn = QPushButton("选择固件")
        select_btn.clicked.connect(self._select_firmware)
        
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(select_btn)
        
        # 分区选择
        self.partition_combo = QComboBox()
        self.partition_combo.addItems(["全部", "boot", "recovery", "system", "vendor", "userdata", "cache", "vbmeta"])
        
        # 刷机按钮
        self.flash_btn = QPushButton("开始刷机")
        self.flash_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.flash_btn.clicked.connect(self._start_flashing)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("QProgressBar { height: 20px; }")
        
        # 组装布局
        layout.addLayout(file_layout)
        layout.addWidget(self.partition_combo)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.flash_btn)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def _init_backup_tab(self, tab):
        """初始化备份标签页"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 备份路径选择
        path_layout = QHBoxLayout()
        self.backup_path_label = QLabel("未选择备份路径")
        select_btn = QPushButton("选择路径")
        select_btn.clicked.connect(self._select_backup_path)
        
        path_layout.addWidget(self.backup_path_label)
        path_layout.addWidget(select_btn)
        
        # 分区选择
        self.backup_partition_combo = QComboBox()
        self.backup_partition_combo.addItems(["boot", "recovery", "system", "vendor", "userdata", "cache"])
        
        # 备份按钮
        self.backup_btn = QPushButton("开始备份")
        self.backup_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.backup_btn.clicked.connect(self._start_backup)
        
        # 组装布局
        layout.addLayout(path_layout)
        layout.addWidget(self.backup_partition_combo)
        layout.addWidget(self.backup_btn)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def _init_adb_tab(self, tab):
        """初始化ADB命令标签页"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 命令输入
        self.adb_command_input = QLineEdit()
        self.adb_command_input.setPlaceholderText("输入ADB命令，例如: shell ls /sdcard")
        
        # 执行按钮
        execute_btn = QPushButton("执行ADB命令")
        execute_btn.clicked.connect(self._execute_adb_command)
        
        # 输出显示
        self.adb_output = QPlainTextEdit()
        self.adb_output.setReadOnly(True)
        self.adb_output.setStyleSheet("font-family: monospace;")
        
        # 常用命令按钮
        common_commands_layout = QHBoxLayout()
        common_commands = [
            ("设备信息", "shell getprop"),
            ("文件列表", "shell ls /sdcard"),
            ("截图", "shell screencap -p /sdcard/screenshot.png"),
            ("拉取文件", "pull /sdcard/screenshot.png")
        ]
        
        for text, cmd in common_commands:
            btn = QPushButton(text)
            btn.setProperty("command", cmd)
            btn.clicked.connect(lambda _, cmd=cmd: self._set_adb_command(cmd))
            common_commands_layout.addWidget(btn)
        
        # 组装布局
        layout.addWidget(self.adb_command_input)
        layout.addWidget(execute_btn)
        layout.addLayout(common_commands_layout)
        layout.addWidget(self.adb_output)
        
        tab.setLayout(layout)
    
    def _init_fastboot_tab(self, tab):
        """初始化Fastboot命令标签页"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 命令输入
        self.fastboot_command_input = QLineEdit()
        self.fastboot_command_input.setPlaceholderText("输入Fastboot命令，例如: devices")
        
        # 执行按钮
        execute_btn = QPushButton("执行Fastboot命令")
        execute_btn.clicked.connect(self._execute_fastboot_command)
        
        # 输出显示
        self.fastboot_output = QPlainTextEdit()
        self.fastboot_output.setReadOnly(True)
        self.fastboot_output.setStyleSheet("font-family: monospace;")
        
        # 常用命令按钮
        common_commands_layout = QHBoxLayout()
        common_commands = [
            ("设备列表", "devices"),
            ("重启", "reboot"),
            ("进入Recovery", "reboot recovery"),
            ("刷入boot", "flash boot boot.img")
        ]
        
        for text, cmd in common_commands:
            btn = QPushButton(text)
            btn.setProperty("command", cmd)
            btn.clicked.connect(lambda _, cmd=cmd: self._set_fastboot_command(cmd))
            common_commands_layout.addWidget(btn)
        
        # 组装布局
        layout.addWidget(self.fastboot_command_input)
        layout.addWidget(execute_btn)
        layout.addLayout(common_commands_layout)
        layout.addWidget(self.fastboot_output)
        
        tab.setLayout(layout)
    
    def _init_unlock_tab(self, tab):
        """初始化BL解锁标签页"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 警告信息
        warning_label = QLabel(
            "警告: 解锁Bootloader会清除设备上的所有数据!\n\n" +
            "请在操作前备份重要数据。某些设备可能需要先申请解锁许可。"
        )
        warning_label.setStyleSheet("color: red; font-weight: bold;")
        warning_label.setWordWrap(True)
        
        # 解锁按钮
        unlock_btn = QPushButton("解锁Bootloader")
        unlock_btn.setStyleSheet("background-color: #ff4444; color: white; font-weight: bold;")
        unlock_btn.clicked.connect(self._unlock_bootloader)
        
        # 锁定按钮
        lock_btn = QPushButton("锁定Bootloader")
        lock_btn.setStyleSheet("background-color: #4444ff; color: white; font-weight: bold;")
        lock_btn.clicked.connect(self._lock_bootloader)
        
        # 状态显示
        self.unlock_status = QLabel("设备状态: 未知")
        
        # 组装布局
        layout.addWidget(warning_label)
        layout.addWidget(unlock_btn)
        layout.addWidget(lock_btn)
        layout.addWidget(self.unlock_status)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def _start_device_check(self):
        """启动设备检测线程"""
        self.running = True
        
        def check_loop():
            while self.running:
                try:
                    # 检查ADB设备
                    adb_devices = self.adb.devices()
                    if adb_devices:
                        self.mode_signal.emit("adb", adb_devices[0][0])
                        self._update_device_details(adb_devices[0][0])
                        time.sleep(3)
                        continue
                except Exception as e:
                    self.log_signal.emit(f"ADB设备检测错误: {str(e)}")
                
                # 检查Fastboot设备
                try:
                    fastboot_devices = self.adb.fastboot_devices()
                    if fastboot_devices:
                        self.mode_signal.emit("fastboot", fastboot_devices[0][0])
                        self._update_device_details(fastboot_devices[0][0])
                        time.sleep(3)
                        continue
                except Exception as e:
                    self.log_signal.emit(f"Fastboot设备检测错误: {str(e)}")
                
                # 没有检测到设备
                self.mode_signal.emit(None, None)
                self.device_details.setText("设备详细信息将在此显示")
                time.sleep(3)
        
        self.check_thread = threading.Thread(target=check_loop, daemon=True)
        self.check_thread.start()
    
    def _update_device_details(self, device_id):
        """更新设备详细信息"""
        try:
            if self.current_mode == "adb":
                # 获取设备信息
                result = self.adb.execute_adb_command(f"-s {device_id} shell getprop")
                if result and result['success']:
                    props = result['output'].splitlines()
                    details = []
                    
                    # 提取重要属性
                    important_props = {
                        "ro.product.model": "型号",
                        "ro.product.brand": "品牌",
                        "ro.product.name": "产品名",
                        "ro.build.version.release": "Android版本",
                        "ro.build.id": "构建ID",
                        "ro.serialno": "序列号"
                    }
                    
                    for prop in props:
                        if "]: [" in prop:
                            key, value = prop.split("]: [")
                            key = key.strip("[")
                            value = value.strip("]")
                            if key in important_props:
                                details.append(f"{important_props[key]}: {value}")
                    
                    self.device_details.setText("\n".join(details))
                else:
                    self.device_details.setText("无法获取设备详细信息")
            
            elif self.current_mode == "fastboot":
                # 获取fastboot设备信息
                result = self.adb.execute_fastboot_command(f"-s {device_id} getvar all")
                if result and result['success']:
                    self.device_details.setText(result['output'])
                else:
                    self.device_details.setText("无法获取设备详细信息")
            
        except Exception as e:
            self.log_signal.emit(f"获取设备详细信息错误: {str(e)}")
    
    def _handle_mode_change(self, mode, device_id):
        """处理设备模式变化"""
        if mode == self.current_mode and device_id == self.device_id:
            return
            
        self.current_mode = mode
        self.device_id = device_id
        
        if mode == "adb":
            self.device_status.setText("ADB模式")
            self.device_info.setText(f"设备ID: {device_id}")
            self._update_button_states()
        elif mode == "fastboot":
            self.device_status.setText("Fastboot模式")
            self.device_info.setText(f"设备ID: {device_id}")
            self._update_button_states()
        else:
            self.device_status.setText("未连接设备")
            self.device_info.setText("")
            self._update_button_states()
    
    def _update_button_states(self):
        """更新按钮状态"""
        has_device = self.current_mode is not None
        
        self.bootloader_btn.setEnabled(has_device and self.current_mode == "adb")
        self.recovery_btn.setEnabled(has_device and self.current_mode == "adb")
        self.reboot_btn.setEnabled(has_device)
        self.flash_btn.setEnabled(has_device and bool(self.firmware_path))
        self.backup_btn.setEnabled(has_device and bool(self.backup_path) and self.current_mode == "fastboot")
    
    def _update_status(self, status_type, message):
        """更新状态显示"""
        if status_type == "adb":
            self.adb_status.setText(f"ADB: {message}")
        elif status_type == "fastboot":
            self.fastboot_status.setText(f"Fastboot: {message}")
    
    def _log_message(self, message):
        """记录日志消息"""
        self.status_bar.setText(message)
        if self.debug_log_dialog:
            self.debug_log_dialog.append_log(message)
    
    def _update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
    
    def _show_settings(self):
        """显示设置对话框"""
        if self.settings_dialog.exec_() == QDialog.Accepted:
            # 重新初始化ADB以应用新的路径设置
            self.adb = ADB()
            self.log_signal.emit("设置已保存并应用")
    
    def _show_debug_log(self):
        """显示调试日志"""
        self.debug_log_dialog.show()
    
    def _show_about(self):
        """显示关于信息"""
        about_text = (
            "Python Flash Tools V1.5-Lite\n"
            "Powered by LanChe-Studio\n\n"
            "开源项目: https://github.com/LanChe-Studio/python-flash-tools\n"
            "开源协议: GPL 3.0"
        )
        QMessageBox.information(self, "关于", about_text)
    
    def _enter_bootloader(self):
        """进入Bootloader模式"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        self.log_signal.emit("尝试进入Bootloader模式...")
        
        try:
            success, error = self.adb.reboot("bootloader")
            if success:
                self.log_signal.emit("设备正在重启到Bootloader...")
            else:
                self.log_signal.emit(f"操作失败: {error}")
        except Exception as e:
            self.log_signal.emit(f"操作异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _enter_recovery(self):
        """进入Recovery模式"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        self.log_signal.emit("尝试进入Recovery模式...")
        
        try:
            success, error = self.adb.reboot("recovery")
            if success:
                self.log_signal.emit("设备正在重启到Recovery...")
            else:
                self.log_signal.emit(f"操作失败: {error}")
        except Exception as e:
            self.log_signal.emit(f"操作异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _reboot_device(self):
        """重启设备"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        self.log_signal.emit("正在重启设备...")
        
        try:
            if self.current_mode == "adb":
                success, error = self.adb.reboot()
                if not success:
                    self.log_signal.emit(f"重启失败: {error}")
            elif self.current_mode == "fastboot":
                success, error = self.adb.fastboot_reboot()
                if not success:
                    self.log_signal.emit(f"重启失败: {error}")
            else:
                self.log_signal.emit("当前模式不支持重启")
        except Exception as e:
            self.log_signal.emit(f"操作异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _select_firmware(self):
        """选择固件文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择固件文件", "", 
            "固件文件 (*.zip *.tgz *.tar.gz *.img *.bin);;所有文件 (*)")
            
        if file_path:
            self.firmware_path = file_path
            self.file_label.setText(os.path.basename(file_path))
            self._update_button_states()
            self.log_signal.emit(f"已选择固件: {file_path}")
    
    def _select_backup_path(self):
        """选择备份路径"""
        backup_dir = QFileDialog.getExistingDirectory(self, "选择备份目录")
        
        if backup_dir:
            self.backup_path = backup_dir
            self.backup_path_label.setText(os.path.basename(backup_dir))
            self._update_button_states()
            self.log_signal.emit(f"已选择备份路径: {backup_dir}")
    
    def _set_adb_command(self, command):
        """设置ADB命令"""
        self.adb_command_input.setText(command)
    
    def _execute_adb_command(self):
        """执行ADB命令"""
        if self.operation_in_progress:
            return
            
        command = self.adb_command_input.text().strip()
        if not command:
            self.log_signal.emit("请输入ADB命令")
            return
            
        self.operation_in_progress = True
        self.log_signal.emit(f"执行ADB命令: {command}")
        
        try:
            result = self.adb.execute_adb_command(command)
            if result is None:
                self.adb_output.setPlainText(f"执行失败: {self.adb.last_error}")
            else:
                output = ""
                if result['output']:
                    output += f"输出:\n{result['output']}\n\n"
                if result['error']:
                    output += f"错误:\n{result['error']}\n\n"
                output += f"结果: {'成功' if result['success'] else '失败'}"
                self.adb_output.setPlainText(output)
                self.log_signal.emit(f"ADB命令执行{'成功' if result['success'] else '失败'}")
        except Exception as e:
            self.adb_output.setPlainText(f"执行异常: {str(e)}")
            self.log_signal.emit(f"ADB命令执行异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _set_fastboot_command(self, command):
        """设置Fastboot命令"""
        self.fastboot_command_input.setText(command)
    
    def _execute_fastboot_command(self):
        """执行Fastboot命令"""
        if self.operation_in_progress:
            return
            
        command = self.fastboot_command_input.text().strip()
        if not command:
            self.log_signal.emit("请输入Fastboot命令")
            return
            
        self.operation_in_progress = True
        self.log_signal.emit(f"执行Fastboot命令: {command}")
        
        try:
            result = self.adb.execute_fastboot_command(command)
            if result is None:
                self.fastboot_output.setPlainText(f"执行失败: {self.adb.last_error}")
            else:
                output = ""
                if result['output']:
                    output += f"输出:\n{result['output']}\n\n"
                if result['error']:
                    output += f"错误:\n{result['error']}\n\n"
                output += f"结果: {'成功' if result['success'] else '失败'}"
                self.fastboot_output.setPlainText(output)
                self.log_signal.emit(f"Fastboot命令执行{'成功' if result['success'] else '失败'}")
        except Exception as e:
            self.fastboot_output.setPlainText(f"执行异常: {str(e)}")
            self.log_signal.emit(f"Fastboot命令执行异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _unlock_bootloader(self):
        """解锁Bootloader"""
        if self.operation_in_progress:
            return
            
        reply = QMessageBox.warning(
            self, "警告",
            "解锁Bootloader会清除设备上的所有数据!\n\n确定要继续吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        self.operation_in_progress = True
        self.log_signal.emit("正在尝试解锁Bootloader...")
        
        try:
            success, error = self.adb.unlock_bootloader()
            if success:
                self.log_signal.emit("解锁Bootloader成功! 设备将自动重启")
                self.unlock_status.setText("设备状态: 已解锁")
            else:
                self.log_signal.emit(f"解锁失败: {error}")
                self.unlock_status.setText("设备状态: 解锁失败")
        except Exception as e:
            self.log_signal.emit(f"解锁异常: {str(e)}")
            self.unlock_status.setText("设备状态: 解锁异常")
        finally:
            self.operation_in_progress = False
    
    def _lock_bootloader(self):
        """锁定Bootloader"""
        if self.operation_in_progress:
            return
            
        reply = QMessageBox.warning(
            self, "警告",
            "锁定Bootloader可能会影响系统更新和某些功能!\n\n确定要继续吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        self.operation_in_progress = True
        self.log_signal.emit("正在尝试锁定Bootloader...")
        
        try:
            success, error = self.adb.lock_bootloader()
            if success:
                self.log_signal.emit("锁定Bootloader成功! 设备将自动重启")
                self.unlock_status.setText("设备状态: 已锁定")
            else:
                self.log_signal.emit(f"锁定失败: {error}")
                self.unlock_status.setText("设备状态: 锁定失败")
        except Exception as e:
            self.log_signal.emit(f"锁定异常: {str(e)}")
            self.unlock_status.setText("设备状态: 锁定异常")
        finally:
            self.operation_in_progress = False
    
    def _start_flashing(self):
        """开始刷机"""
        if self.operation_in_progress or not self.firmware_path:
            return
            
        # 检查设备状态
        if self.current_mode != "fastboot":
            QMessageBox.warning(self, "警告", "设备未处于Fastboot模式，无法刷机")
            return
            
        reply = QMessageBox.question(
            self, "确认",
            "确定要刷机吗? 此操作有风险!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_flash, daemon=True).start()
    
    def _start_backup(self):
        """开始备份"""
        if self.operation_in_progress or not self.backup_path:
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_backup, daemon=True).start()
    
    def _execute_flash(self):
        """执行刷机"""
        try:
            partition = self.partition_combo.currentText()
            self.log_signal.emit(f"开始刷写 {partition} 分区...")
            self.progress_signal.emit(0)
            
            # 如果是单个分区且固件是img或bin文件
            if partition != "全部" and (self.firmware_path.lower().endswith('.img') or 
                                       self.firmware_path.lower().endswith('.bin')):
                self.log_signal.emit(f"正在刷入 {partition} 分区...")
                
                if self.adb.flash_partition(partition, self.firmware_path):
                    self.log_signal.emit(f"{partition} 分区刷入成功!")
                    self.progress_signal.emit(100)
                else:
                    self.log_signal.emit(f"{partition} 分区刷入失败: {self.adb.last_error}")
                    self.progress_signal.emit(0)
            else:
                # 处理固件包（zip/tar.gz等）
                temp_dir = tempfile.mkdtemp(prefix="firmware_")
                try:
                    # 解压固件包
                    if self.firmware_path.lower().endswith('.zip'):
                        with zipfile.ZipFile(self.firmware_path, 'r') as zip_ref:
                            zip_ref.extractall(temp_dir)
                    elif self.firmware_path.lower().endswith('.tar.gz') or self.firmware_path.lower().endswith('.tgz'):
                        with tarfile.open(self.firmware_path, 'r:gz') as tar_ref:
                            tar_ref.extractall(temp_dir)
                    else:
                        temp_dir = os.path.dirname(self.firmware_path)
                    
                    if partition == "全部":
                        # 查找所有镜像文件
                        img_files = []
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file.lower().endswith('.img') or file.lower().endswith('.bin'):
                                    img_files.append(os.path.join(root, file))
                        
                        if not img_files:
                            self.log_signal.emit("在固件包中未找到任何镜像文件")
                            return
                        
                        total = len(img_files)
                        for i, img_file in enumerate(img_files):
                            # 提取分区名（不带扩展名）
                            partition_name = os.path.splitext(os.path.basename(img_file))[0]
                            self.log_signal.emit(f"正在刷写分区: {partition_name}")
                            
                            if self.adb.flash_partition(partition_name, img_file):
                                self.log_signal.emit(f"{partition_name} 刷写成功")
                            else:
                                self.log_signal.emit(f"{partition_name} 刷写失败: {self.adb.last_error}")
                            
                            # 更新进度
                            progress = int((i + 1) / total * 100)
                            self.progress_signal.emit(progress)
                        
                        self.log_signal.emit("所有分区刷写完成")
                    else:
                        # 查找特定分区镜像
                        img_file = None
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file.lower().endswith(f"{partition}.img") or file.lower().endswith(f"{partition}.bin"):
                                    img_file = os.path.join(root, file)
                                    break
                            if img_file:
                                break
                        
                        if img_file:
                            self.log_signal.emit(f"找到分区镜像: {os.path.basename(img_file)}")
                            self.progress_signal.emit(50)
                            
                            if self.adb.flash_partition(partition, img_file):
                                self.log_signal.emit(f"{partition} 分区刷入成功!")
                                self.progress_signal.emit(100)
                            else:
                                self.log_signal.emit(f"{partition} 分区刷入失败: {self.adb.last_error}")
                                self.progress_signal.emit(0)
                        else:
                            self.log_signal.emit(f"在固件包中未找到 {partition} 分区镜像")
                finally:
                    if temp_dir != os.path.dirname(self.firmware_path):
                        shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            self.log_signal.emit(f"刷机失败: {str(e)}")
            self.progress_signal.emit(0)
        finally:
            self.operation_in_progress = False
    
    def _execute_backup(self):
        """执行备份"""
        try:
            partition = self.backup_partition_combo.currentText()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(self.backup_path, f"{partition}_backup_{timestamp}.img")
            
            self.log_signal.emit(f"开始备份 {partition} 分区...")
            
            if self.current_mode == "fastboot":
                if self.adb.backup_partition_fastboot(partition, backup_file):
                    self.log_signal.emit(f"备份成功: {backup_file}")
                else:
                    self.log_signal.emit(f"备份失败: {self.adb.last_error}")
            else:
                self.log_signal.emit("当前设备未处于Fastboot模式，无法备份")
        except Exception as e:
            self.log_signal.emit(f"备份失败: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.operation_in_progress:
            QMessageBox.warning(self, "警告", "请等待当前操作完成")
            event.ignore()
        else:
            # 停止设备检测线程
            self.running = False
            # 等待线程结束，最多1秒
            if hasattr(self, 'check_thread') and self.check_thread.is_alive():
                self.check_thread.join(timeout=1.0)
            
            self.adb.cleanup()
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 设置全局字体为微软雅黑
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    tool = FlashTool()
    tool.show()
    
    sys.exit(app.exec_())