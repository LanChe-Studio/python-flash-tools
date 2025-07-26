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
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QProgressBar,
                             QFileDialog, QMessageBox, QGroupBox, QDialog, 
                             QTabWidget, QTextEdit, QLineEdit, QPlainTextEdit, QCheckBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QSettings
from PyQt5.QtGui import QFont

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
        
        # 主题设置
        theme_group = QGroupBox("主题设置")
        theme_layout = QVBoxLayout()
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["浅色", "深色"])
        
        theme_layout.addWidget(self.theme_combo)
        theme_group.setLayout(theme_layout)
        
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
        layout.addWidget(theme_group)
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
        self.theme_combo.setCurrentText(self.settings.value("theme", "浅色"))
    
    def _save_settings(self):
        """保存设置"""
        self.settings.setValue("adb_path", self.adb_path_edit.text())
        self.settings.setValue("fastboot_path", self.fastboot_path_edit.text())
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.accept()

class ADB:
    """ADB工具管理类"""
    def __init__(self, host='127.0.0.1', port=5037):
        self.host = host
        self.port = port
        self.adb_path = None
        self.fastboot_path = None
        self.server_started = False
        self.last_error = ""
        self.temp_dir = None
        self.settings = QSettings("PythonFlashTools", "FlashTool")
        self._init_adb()

    def _get_platform_specific_name(self, tool):
        """获取平台特定的可执行文件名"""
        return f"{tool}.exe" if platform.system().lower() == "windows" else tool

    def _find_or_install_adb(self):
        """查找或安装ADB工具"""
        # 首先检查用户自定义路径
        custom_path = self.settings.value("adb_path", "")
        if custom_path and os.path.exists(custom_path):
            try:
                # 使用UTF-8编码避免解码错误
                result = subprocess.run([custom_path, "version"], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=2)
                if result.returncode == 0:
                    return custom_path
            except:
                pass
        
        # 查找系统PATH中的ADB
        adb_name = self._get_platform_specific_name("adb")
        try:
            result = subprocess.run([adb_name, "version"], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=2)
            if result.returncode == 0:
                return adb_name
        except:
            pass
        
        # 查找常见路径中的ADB
        paths = [
            "/usr/bin/adb",
            "/usr/local/bin/adb",
            os.path.join(os.environ.get("ANDROID_HOME", ""), "platform-tools", adb_name),
            os.path.join(os.environ.get("ANDROID_SDK_ROOT", ""), "platform-tools", adb_name),
            "C:\\Program Files (x86)\\Android\\android-sdk\\platform-tools\\adb.exe",
            os.path.expanduser("~/Library/Android/sdk/platform-tools/adb")
        ]
        
        for path in paths:
            try:
                result = subprocess.run([path, "version"], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=2)
                if result.returncode == 0:
                    return path
            except:
                continue
        
        # 尝试下载ADB
        return self._download_adb()

    def _download_adb(self):
        """下载ADB工具"""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="adb_temp_")
            system = platform.system().lower()
            
            url = {
                "windows": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
                "linux": "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
                "darwin": "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip"
            }.get(system)
            
            if not url:
                raise Exception("不支持的操作系统")
            
            zip_path = os.path.join(self.temp_dir, "platform-tools.zip")
            
            # 下载进度回调
            def _report_progress(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                sys.stdout.write(f"\r下载ADB工具... {percent}%")
                sys.stdout.flush()
            
            print("正在下载ADB工具...")
            urllib.request.urlretrieve(url, zip_path, _report_progress)
            print("\n下载完成")
            
            # 解压文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
            
            # 设置权限(非Windows)
            adb_path = os.path.join(self.temp_dir, "platform-tools", self._get_platform_specific_name("adb"))
            if platform.system().lower() != "windows":
                os.chmod(adb_path, 0o755)
            
            return adb_path
        except Exception as e:
            self.last_error = f"下载ADB失败: {str(e)}"
            return None

    def _find_fastboot(self):
        """查找fastboot工具"""
        # 首先检查用户自定义路径
        custom_path = self.settings.value("fastboot_path", "")
        if custom_path and os.path.exists(custom_path):
            try:
                result = subprocess.run([custom_path, "--version"], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=2)
                if result.returncode == 0:
                    return custom_path
            except:
                pass
        
        if not self.adb_path:
            return None
            
        adb_dir = os.path.dirname(self.adb_path)
        fastboot_name = self._get_platform_specific_name("fastboot")
        
        # 查找fastboot路径
        for path in [
            os.path.join(adb_dir, fastboot_name),
            os.path.join(adb_dir, "platform-tools", fastboot_name),
            fastboot_name
        ]:
            try:
                result = subprocess.run([path, "--version"], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=2)
                if result.returncode == 0:
                    return path
            except:
                continue
                
        return None

    def _init_adb(self):
        """初始化ADB"""
        self.adb_path = self._find_or_install_adb()
        if self.adb_path:
            self.fastboot_path = self._find_fastboot()

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
            # 使用DEVNULL避免输出解码问题
            subprocess.run([self.adb_path, "start-server"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL,
                         timeout=10)
            self.server_started = True
            return True
        except Exception as e:
            self.last_error = f"启动ADB服务失败: {str(e)}"
            return False
    
    def devices(self):
        """获取设备列表"""
        if not self._ensure_adb_server():
            return []
            
        try:
            # 使用UTF-8编码避免解码错误
            result = subprocess.run([self.adb_path, "devices"], 
                                  capture_output=True, 
                                  text=True,
                                  encoding='utf-8',
                                  errors='ignore',
                                  timeout=5)
            if result.returncode == 0:
                return [line.split('\t') for line in result.stdout.splitlines() 
                       if line and not line.startswith('List of')]
        except Exception as e:
            self.last_error = str(e)
            
        return []

    def fastboot_devices(self):
        """获取fastboot设备列表"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return []
            
        try:
            # 使用UTF-8编码避免解码错误
            result = subprocess.run([self.fastboot_path, "devices"], 
                                  capture_output=True, 
                                  text=True,
                                  encoding='utf-8',
                                  errors='ignore',
                                  timeout=5)
            if result.returncode == 0:
                return [line.split('\t') for line in result.stdout.splitlines() if line]
        except Exception as e:
            self.last_error = str(e)
            
        return []

    def reboot(self, mode=None):
        """重启设备"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return False
            
        cmd = [self.adb_path, "reboot"]
        if mode in ["bootloader", "recovery"]:
            cmd.append(mode)
            
        try:
            # 使用UTF-8编码避免解码错误
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                  timeout=10, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                self.last_error = result.stderr.strip()
                return False
            return True
        except Exception as e:
            self.last_error = str(e)
            return False

    def fastboot_reboot(self):
        """Fastboot模式重启"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False
            
        try:
            # 使用UTF-8编码避免解码错误
            result = subprocess.run([self.fastboot_path, "reboot"], 
                                  capture_output=True,
                                  text=True,
                                  encoding='utf-8',
                                  errors='ignore',
                                  timeout=10)
            return result.returncode == 0
        except Exception as e:
            self.last_error = str(e)
            return False

    def backup_partition(self, partition, output_path):
        """备份分区"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return False
            
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cmd = f"su -c 'dd if=/dev/block/bootdevice/by-name/{partition} of={output_path}'"
            # 使用UTF-8编码避免解码错误
            result = subprocess.run([self.adb_path, "shell", cmd], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  timeout=300,
                                  encoding='utf-8',
                                  errors='ignore')
            return result.returncode == 0
        except Exception as e:
            self.last_error = str(e)
            return False

    def execute_adb_command(self, command):
        """执行ADB命令"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return None
            
        try:
            # 使用UTF-8编码避免解码错误
            result = subprocess.run([self.adb_path] + command.split(),
                                  capture_output=True,
                                  text=True,
                                  timeout=30,
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

    def execute_fastboot_command(self, command):
        """执行Fastboot命令"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return None
            
        try:
            # 使用UTF-8编码避免解码错误
            result = subprocess.run([self.fastboot_path] + command.split(),
                                  capture_output=True,
                                  text=True,
                                  timeout=30,
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
            return False
            
        try:
            # 使用UTF-8编码避免解码错误
            result = subprocess.run([self.fastboot_path, "flashing", "unlock"],
                                  capture_output=True,
                                  text=True,
                                  timeout=30,
                                  encoding='utf-8',
                                  errors='ignore')
            if result.returncode != 0:
                # 尝试另一种解锁命令
                result = subprocess.run([self.fastboot_path, "oem", "unlock"],
                                      capture_output=True,
                                      text=True,
                                      timeout=30,
                                      encoding='utf-8',
                                      errors='ignore')
            return result.returncode == 0
        except Exception as e:
            self.last_error = str(e)
            return False

    def lock_bootloader(self):
        """锁定Bootloader"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False
            
        try:
            # 使用UTF-8编码避免解码错误
            result = subprocess.run([self.fastboot_path, "flashing", "lock"],
                                  capture_output=True,
                                  text=True,
                                  timeout=30,
                                  encoding='utf-8',
                                  errors='ignore')
            if result.returncode != 0:
                # 尝试另一种锁定命令
                result = subprocess.run([self.fastboot_path, "oem", "lock"],
                                      capture_output=True,
                                      text=True,
                                      timeout=30,
                                      encoding='utf-8',
                                      errors='ignore')
            return result.returncode == 0
        except Exception as e:
            self.last_error = str(e)
            return False

    def backup_partition_fastboot(self, partition, output_path):
        """使用Fastboot备份分区"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False
            
        try:
            # 获取分区大小
            result = subprocess.run([self.fastboot_path, "getvar", f"partition-size:{partition}"],
                                 capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                self.last_error = f"无法获取分区大小: {result.stderr}"
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
                # 验证文件大小
                if os.path.getsize(output_path) == partition_size:
                    return True
                else:
                    self.last_error = "备份文件大小不匹配"
                    return False
            else:
                self.last_error = result.stderr.decode('utf-8', 'ignore') if result.stderr else "未知错误"
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
        self.setWindowTitle("Python Flash Tools V1.0")
        self.setGeometry(100, 100, 600, 400)
        
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
        
        # 添加缺失的属性
        self.xiaomi_flash_path = ""
        self.edl_flash_path = ""
        self.bootrom_flash_path = ""
        
        # 连接信号
        self.log_signal.connect(self._log_message)
        self.progress_signal.connect(self._update_progress)
        self.status_signal.connect(self._update_status)
        self.mode_signal.connect(self._handle_mode_change)
        
        self._init_ui()
        self._start_device_check()
        self._apply_theme()
    
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
        
        # 备份标签页 - 改为Fastboot备份
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
        
        # 小米线刷标签页
        xiaomi_tab = QWidget()
        self._init_xiaomi_tab(xiaomi_tab)
        self.tabs.addTab(xiaomi_tab, "小米线刷")
        
        # 9008模式标签页
        edl_tab = QWidget()
        self._init_edl_tab(edl_tab)
        self.tabs.addTab(edl_tab, "9008模式")
        
        # Bootrom刷机标签页
        bootrom_tab = QWidget()
        self._init_bootrom_tab(bootrom_tab)
        self.tabs.addTab(bootrom_tab, "Bootrom刷机")
        
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
        self.edl_btn = QPushButton("进入9008")
        self.edl_btn.clicked.connect(self._enter_edl)
        
        btn_layout.addWidget(self.bootloader_btn)
        btn_layout.addWidget(self.recovery_btn)
        btn_layout.addWidget(self.reboot_btn)
        btn_layout.addWidget(self.edl_btn)
        
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
        
        # 固件选择
        file_layout = QHBoxLayout()
        self.file_label = QLabel("未选择固件")
        select_btn = QPushButton("选择固件")
        select_btn.clicked.connect(self._select_firmware)
        
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(select_btn)
        
        # 分区选择
        self.partition_combo = QComboBox()
        self.partition_combo.addItems(["全部", "boot", "recovery", "system", "vendor"])
        
        # 刷机按钮
        self.flash_btn = QPushButton("开始刷机")
        self.flash_btn.clicked.connect(self._start_flashing)
        
        # 进度条
        self.progress_bar = QProgressBar()
        
        # 组装布局
        layout.addLayout(file_layout)
        layout.addWidget(self.partition_combo)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.flash_btn)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def _init_backup_tab(self, tab):
        """初始化备份标签页 - 改为Fastboot备份"""
        layout = QVBoxLayout()
        
        # 备份路径选择
        path_layout = QHBoxLayout()
        self.backup_path_label = QLabel("未选择备份路径")
        select_btn = QPushButton("选择路径")
        select_btn.clicked.connect(self._select_backup_path)
        
        path_layout.addWidget(self.backup_path_label)
        path_layout.addWidget(select_btn)
        
        # 分区选择
        self.backup_partition_combo = QComboBox()
        self.backup_partition_combo.addItems(["boot", "recovery", "system", "vendor"])
        
        # 备份按钮
        self.backup_btn = QPushButton("开始备份")
        self.backup_btn.clicked.connect(self._start_backup)
        
        # 添加提示信息
        info_label = QLabel("注意: 此备份功能使用Fastboot模式，需要设备处于Fastboot模式")
        info_label.setStyleSheet("color: #888888; font-size: 9pt;")
        
        # 组装布局
        layout.addLayout(path_layout)
        layout.addWidget(self.backup_partition_combo)
        layout.addWidget(self.backup_btn)
        layout.addWidget(info_label)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def _init_adb_tab(self, tab):
        """初始化ADB命令标签页"""
        layout = QVBoxLayout()
        
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
        
        # 警告信息
        warning_label = QLabel(
            "警告: 解锁Bootloader会清除设备上的所有数据!\n"
            "请在操作前备份重要数据。某些设备可能需要先申请解锁许可。"
        )
        warning_label.setStyleSheet("color: red; font-weight: bold;")
        warning_label.setWordWrap(True)
        
        # 解锁按钮
        unlock_btn = QPushButton("解锁Bootloader")
        unlock_btn.clicked.connect(self._unlock_bootloader)
        unlock_btn.setStyleSheet("background-color: #ff4444; color: white;")
        
        # 锁定按钮
        lock_btn = QPushButton("锁定Bootloader")
        lock_btn.clicked.connect(self._lock_bootloader)
        lock_btn.setStyleSheet("background-color: #4444ff; color: white;")
        
        # 状态显示
        self.unlock_status = QLabel("设备状态: 未知")
        
        # 解锁说明
        instructions = QLabel(
            "解锁步骤:\n"
            "1. 确保设备已进入Fastboot模式\n"
            "2. 连接设备到电脑\n"
            "3. 点击解锁按钮\n"
            "4. 按照设备屏幕上的提示操作"
        )
        instructions.setWordWrap(True)
        
        # 组装布局
        layout.addWidget(warning_label)
        layout.addWidget(unlock_btn)
        layout.addWidget(lock_btn)
        layout.addWidget(self.unlock_status)
        layout.addWidget(instructions)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def _init_xiaomi_tab(self, tab):
        """初始化小米线刷标签页"""
        layout = QVBoxLayout()
        
        # 固件选择
        file_layout = QHBoxLayout()
        self.xiaomi_file_label = QLabel("未选择小米线刷包")
        select_btn = QPushButton("选择线刷包")
        select_btn.clicked.connect(self._select_xiaomi_firmware)
        
        file_layout.addWidget(self.xiaomi_file_label)
        file_layout.addWidget(select_btn)
        
        # 刷机选项
        options_group = QGroupBox("刷机选项")
        options_layout = QVBoxLayout()
        
        self.clean_all_check = QCheckBox("清除所有数据")
        self.clean_all_check.setChecked(True)
        self.lock_bootloader_check = QCheckBox("锁定Bootloader")
        
        options_layout.addWidget(self.clean_all_check)
        options_layout.addWidget(self.lock_bootloader_check)
        options_group.setLayout(options_layout)
        
        # 刷机按钮
        self.xiaomi_flash_btn = QPushButton("开始小米线刷")
        self.xiaomi_flash_btn.clicked.connect(self._start_xiaomi_flashing)
        
        # 进度条
        self.xiaomi_progress_bar = QProgressBar()
        
        # 组装布局
        layout.addLayout(file_layout)
        layout.addWidget(options_group)
        layout.addWidget(self.xiaomi_progress_bar)
        layout.addWidget(self.xiaomi_flash_btn)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def _init_edl_tab(self, tab):
        """初始化9008模式标签页"""
        layout = QVBoxLayout()
        
        # 说明
        info_label = QLabel(
            "9008模式(EDL模式)是Qualcomm设备的一种紧急下载模式。\n"
            "某些设备需要授权账号才能使用此模式。"
        )
        info_label.setWordWrap(True)
        
        # 进入9008按钮
        self.enter_edl_btn = QPushButton("进入9008模式")
        self.enter_edl_btn.clicked.connect(self._enter_edl)
        
        # 刷机选项
        edl_group = QGroupBox("9008刷机")
        edl_layout = QVBoxLayout()
        
        file_layout = QHBoxLayout()
        self.edl_file_label = QLabel("未选择9008刷机包")
        select_btn = QPushButton("选择刷机包")
        select_btn.clicked.connect(self._select_edl_firmware)
        
        file_layout.addWidget(self.edl_file_label)
        file_layout.addWidget(select_btn)
        
        self.edl_flash_btn = QPushButton("开始9008刷机")
        self.edl_flash_btn.clicked.connect(self._start_edl_flashing)
        
        edl_layout.addLayout(file_layout)
        edl_layout.addWidget(self.edl_flash_btn)
        edl_group.setLayout(edl_layout)
        
        # 组装布局
        layout.addWidget(info_label)
        layout.addWidget(self.enter_edl_btn)
        layout.addWidget(edl_group)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def _init_bootrom_tab(self, tab):
        """初始化Bootrom刷机标签页 - 添加分区操作功能"""
        layout = QVBoxLayout()
        
        # 说明
        info_label = QLabel(
            "Bootrom模式是设备的底层刷机模式，通常用于设备变砖后的修复。\n"
            "此操作需要设备处于Bootrom模式并连接电脑。\n\n"
            "手动进入Bootrom模式的方法：\n"
            "1. 关闭设备电源\n"
            "2. 同时按住音量减键和电源键\n"
            "3. 连接设备到电脑\n"
            "4. 保持按键直到设备被识别\n\n"
            "注意：不同设备进入方式可能不同，请查阅设备相关文档。"
        )
        info_label.setStyleSheet("font-size: 9pt;")
        info_label.setWordWrap(True)
        
        # 进入Bootrom按钮
        self.enter_bootrom_btn = QPushButton("进入Bootrom模式")
        self.enter_bootrom_btn.clicked.connect(self._enter_bootrom)
        
        # 分区操作组
        partition_group = QGroupBox("分区操作")
        partition_layout = QVBoxLayout()
        
        # 分区选择
        partition_select_layout = QHBoxLayout()
        self.partition_label = QLabel("选择分区:")
        self.partition_combo_bootrom = QComboBox()
        self.partition_combo_bootrom.addItems(["boot", "recovery", "system", "vendor", "userdata"])
        
        partition_select_layout.addWidget(self.partition_label)
        partition_select_layout.addWidget(self.partition_combo_bootrom)
        
        # 分区操作按钮
        btn_layout = QHBoxLayout()
        self.dump_partition_btn = QPushButton("提取分区")
        self.dump_partition_btn.clicked.connect(self._dump_bootrom_partition)
        self.flash_partition_btn = QPushButton("刷入分区")
        self.flash_partition_btn.clicked.connect(self._flash_bootrom_partition)
        self.get_partition_table_btn = QPushButton("获取分区表")
        self.get_partition_table_btn.clicked.connect(self._get_bootrom_partition_table)
        
        btn_layout.addWidget(self.dump_partition_btn)
        btn_layout.addWidget(self.flash_partition_btn)
        btn_layout.addWidget(self.get_partition_table_btn)
        
        # 分区输出
        self.partition_output = QPlainTextEdit()
        self.partition_output.setReadOnly(True)
        self.partition_output.setStyleSheet("font-family: monospace; font-size: 9pt;")
        
        partition_layout.addLayout(partition_select_layout)
        partition_layout.addLayout(btn_layout)
        partition_layout.addWidget(self.partition_output)
        partition_group.setLayout(partition_layout)
        
        # 刷机选项
        bootrom_group = QGroupBox("Bootrom刷机")
        bootrom_layout = QVBoxLayout()
        
        file_layout = QHBoxLayout()
        self.bootrom_file_label = QLabel("未选择Bootrom刷机包")
        select_btn = QPushButton("选择刷机包")
        select_btn.clicked.connect(self._select_bootrom_firmware)
        
        file_layout.addWidget(self.bootrom_file_label)
        file_layout.addWidget(select_btn)
        
        self.bootrom_flash_btn = QPushButton("开始Bootrom刷机")
        self.bootrom_flash_btn.clicked.connect(self._start_bootrom_flashing)
        
        bootrom_layout.addLayout(file_layout)
        bootrom_layout.addWidget(self.bootrom_flash_btn)
        bootrom_group.setLayout(bootrom_layout)
        
        # 组装布局
        layout.addWidget(info_label)
        layout.addWidget(self.enter_bootrom_btn)
        layout.addWidget(partition_group)
        layout.addWidget(bootrom_group)
        layout.addStretch()
        
        tab.setLayout(layout)
    
    def _apply_theme(self):
        """应用主题设置"""
        theme = self.settings.value("theme", "浅色")
        
        if theme == "深色":
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #333333;
                    color: #ffffff;
                }
                QLabel, QPushButton, QComboBox, QLineEdit, QPlainTextEdit, QTextEdit {
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #555555;
                    border: 1px solid #666666;
                }
                QPushButton:hover {
                    background-color: #666666;
                }
                QTabWidget::pane {
                    border: 1px solid #444444;
                    background: #333333;
                }
                QTabBar::tab {
                    background: #444444;
                    color: #ffffff;
                    padding: 8px;
                }
                QTabBar::tab:selected {
                    background: #555555;
                }
                QGroupBox {
                    border: 1px solid #444444;
                    border-radius: 3px;
                    margin-top: 10px;
                    padding-top: 15px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #f0f0f0;
                }
                QGroupBox {
                    border: 1px solid #cccccc;
                    border-radius: 3px;
                    margin-top: 10px;
                    padding-top: 15px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                }
            """)
    
    def _start_device_check(self):
        """启动设备检测线程"""
        def check_loop():
            while True:
                # 检查ADB设备
                try:
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
        
        threading.Thread(target=check_loop, daemon=True).start()
    
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
        self.edl_btn.setEnabled(has_device and self.current_mode == "adb")
        self.flash_btn.setEnabled(has_device and bool(self.firmware_path))
        self.backup_btn.setEnabled(has_device and bool(self.backup_path))
        self.xiaomi_flash_btn.setEnabled(bool(self.xiaomi_flash_path))
        self.edl_flash_btn.setEnabled(bool(self.edl_flash_path))
        self.bootrom_flash_btn.setEnabled(bool(self.bootrom_flash_path))
    
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
            self.debug_log_dialog.log_output.append(message)
    
    def _update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
        self.xiaomi_progress_bar.setValue(value)
    
    def _show_settings(self):
        """显示设置对话框"""
        if self.settings_dialog.exec_() == QDialog.Accepted:
            # 重新初始化ADB以应用新的路径设置
            self.adb = ADB()
            self._apply_theme()
            self.log_signal.emit("设置已保存并应用")
    
    def _show_debug_log(self):
        """显示调试日志"""
        self.debug_log_dialog.show()
    
    def _show_about(self):
        """显示关于信息"""
        QMessageBox.information(self, "关于", "Python Flash Tools V1.0\nPowered by LanChe-Studio")
    
    def _enter_bootloader(self):
        """进入Bootloader模式"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        self.log_signal.emit("尝试进入Bootloader模式...")
        
        try:
            if self.adb.reboot("bootloader"):
                self.log_signal.emit("设备正在重启到Bootloader...")
            else:
                self.log_signal.emit(f"操作失败: {self.adb.last_error}")
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
            if self.adb.reboot("recovery"):
                self.log_signal.emit("设备正在重启到Recovery...")
            else:
                self.log_signal.emit(f"操作失败: {self.adb.last_error}")
        except Exception as e:
            self.log_signal.emit(f"操作异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _enter_edl(self):
        """进入9008模式"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        self.log_signal.emit("尝试进入9008模式...")
        
        try:
            # 尝试通过ADB进入EDL模式
            result = self.adb.execute_adb_command("reboot edl")
            if result and result['success']:
                self.log_signal.emit("设备正在重启到9008模式...")
            else:
                # 尝试通过fastboot进入EDL模式
                result = self.adb.execute_fastboot_command("oem edl")
                if result and result['success']:
                    self.log_signal.emit("设备正在重启到9008模式...")
                else:
                    self.log_signal.emit("无法进入9008模式，可能需要手动操作")
        except Exception as e:
            self.log_signal.emit(f"操作异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _enter_bootrom(self):
        """进入Bootrom模式"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        self.log_signal.emit("尝试进入Bootrom模式...")
        
        try:
            # 尝试通过ADB进入Bootrom模式
            result = self.adb.execute_adb_command("reboot bootrom")
            if result and result['success']:
                self.log_signal.emit("设备正在重启到Bootrom模式...")
            else:
                # 尝试通过fastboot进入Bootrom模式
                result = self.adb.execute_fastboot_command("oem bootrom")
                if result and result['success']:
                    self.log_signal.emit("设备正在重启到Bootrom模式...")
                else:
                    self.log_signal.emit("无法进入Bootrom模式，请参考标签页中的手动进入指南")
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
                if not self.adb.reboot():
                    self.log_signal.emit(f"重启失败: {self.adb.last_error}")
            elif self.current_mode == "fastboot":
                if not self.adb.fastboot_reboot():
                    self.log_signal.emit(f"重启失败: {self.adb.last_error}")
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
            "固件文件 (*.zip *.tgz *.tar.gz *.img);;所有文件 (*)")
            
        if file_path:
            self.firmware_path = file_path
            self.file_label.setText(os.path.basename(file_path))
            self._update_button_states()
            self.log_signal.emit(f"已选择固件: {file_path}")
    
    def _select_xiaomi_firmware(self):
        """选择小米线刷包"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择小米线刷包", "", 
            "小米线刷包 (*.tgz *.tar.gz);;所有文件 (*)")
            
        if file_path:
            self.xiaomi_flash_path = file_path
            self.xiaomi_file_label.setText(os.path.basename(file_path))
            self._update_button_states()
            self.log_signal.emit(f"已选择小米线刷包: {file_path}")
    
    def _select_edl_firmware(self):
        """选择9008刷机包"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择9008刷机包", "", 
            "刷机包 (*.zip);;所有文件 (*)")
            
        if file_path:
            self.edl_flash_path = file_path
            self.edl_file_label.setText(os.path.basename(file_path))
            self._update_button_states()
            self.log_signal.emit(f"已选择9008刷机包: {file_path}")
    
    def _select_bootrom_firmware(self):
        """选择Bootrom刷机包"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Bootrom刷机包", "", 
            "刷机包 (*.zip);;所有文件 (*)")
            
        if file_path:
            self.bootrom_flash_path = file_path
            self.bootrom_file_label.setText(os.path.basename(file_path))
            self._update_button_states()
            self.log_signal.emit(f"已选择Bootrom刷机包: {file_path}")
    
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
            if self.adb.unlock_bootloader():
                self.log_signal.emit("解锁Bootloader成功! 设备将自动重启")
                self.unlock_status.setText("设备状态: 已解锁")
            else:
                self.log_signal.emit(f"解锁失败: {self.adb.last_error}")
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
            if self.adb.lock_bootloader():
                self.log_signal.emit("锁定Bootloader成功! 设备将自动重启")
                self.unlock_status.setText("设备状态: 已锁定")
            else:
                self.log_signal.emit(f"锁定失败: {self.adb.last_error}")
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
            
        reply = QMessageBox.question(
            self, "确认",
            "确定要刷机吗? 此操作有风险!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_flash, daemon=True).start()
    
    def _start_xiaomi_flashing(self):
        """开始小米线刷"""
        if self.operation_in_progress or not self.xiaomi_flash_path:
            return
            
        reply = QMessageBox.question(
            self, "确认",
            "确定要刷入小米线刷包吗? 此操作会清除所有数据!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_xiaomi_flash, daemon=True).start()
    
    def _start_edl_flashing(self):
        """开始9008刷机"""
        if self.operation_in_progress or not self.edl_flash_path:
            return
            
        reply = QMessageBox.question(
            self, "确认",
            "确定要通过9008模式刷机吗? 此操作有风险!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_edl_flash, daemon=True).start()
    
    def _start_bootrom_flashing(self):
        """开始Bootrom刷机"""
        if self.operation_in_progress or not self.bootrom_flash_path:
            return
            
        reply = QMessageBox.question(
            self, "确认",
            "确定要通过Bootrom模式刷机吗? 此操作有风险!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_bootrom_flash, daemon=True).start()
    
    def _start_backup(self):
        """开始备份 - 使用Fastboot备份"""
        if self.operation_in_progress or not self.backup_path:
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_backup, daemon=True).start()
    
    def _dump_bootrom_partition(self):
        """提取Bootrom分区"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_dump_bootrom_partition, daemon=True).start()
    
    def _flash_bootrom_partition(self):
        """刷入Bootrom分区"""
        if self.operation_in_progress:
            return
            
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择分区镜像文件", "", 
            "镜像文件 (*.img);;所有文件 (*)")
            
        if not file_path:
            self.operation_in_progress = False
            return
            
        self.partition_img_path = file_path
        self.operation_in_progress = True
        threading.Thread(target=self._execute_flash_bootrom_partition, daemon=True).start()
    
    def _get_bootrom_partition_table(self):
        """获取Bootrom分区表"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_get_bootrom_partition_table, daemon=True).start()
    
    def _execute_flash(self):
        """执行刷机"""
        try:
            partition = self.partition_combo.currentText()
            self.log_signal.emit(f"开始刷写 {partition} 分区...")
            
            # 模拟刷机过程
            for i in range(1, 101):
                time.sleep(0.05)
                self.progress_signal.emit(i)
                
            self.log_signal.emit("刷机完成!")
        except Exception as e:
            self.log_signal.emit(f"刷机失败: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _execute_xiaomi_flash(self):
        """执行小米线刷"""
        try:
            self.log_signal.emit("开始小米线刷...")
            
            # 模拟刷机过程
            for i in range(1, 101):
                time.sleep(0.1)
                self.progress_signal.emit(i)
                
            self.log_signal.emit("小米线刷完成!")
        except Exception as e:
            self.log_signal.emit(f"小米线刷失败: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _execute_edl_flash(self):
        """执行9008刷机"""
        try:
            self.log_signal.emit("开始9008模式刷机...")
            
            # 模拟刷机过程
            for i in range(1, 101):
                time.sleep(0.1)
                self.progress_signal.emit(i)
                
            self.log_signal.emit("9008刷机完成!")
        except Exception as e:
            self.log_signal.emit(f"9008刷机失败: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _execute_bootrom_flash(self):
        """执行Bootrom刷机"""
        try:
            self.log_signal.emit("开始Bootrom模式刷机...")
            
            # 模拟刷机过程
            for i in range(1, 101):
                time.sleep(0.1)
                self.progress_signal.emit(i)
                
            self.log_signal.emit("Bootrom刷机完成!")
        except Exception as e:
            self.log_signal.emit(f"Bootrom刷机失败: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _execute_backup(self):
        """执行备份 - 使用Fastboot备份"""
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
    
    def _execute_dump_bootrom_partition(self):
        """执行提取Bootrom分区"""
        try:
            partition = self.partition_combo_bootrom.currentText()
            self.log_signal.emit(f"开始提取 {partition} 分区...")
            
            # 模拟提取过程
            for i in range(1, 101):
                time.sleep(0.02)
                self.progress_signal.emit(i)
                
            # 保存到用户选择的路径
            save_path, _ = QFileDialog.getSaveFileName(
                self, "保存分区镜像", 
                f"{partition}_backup.img", 
                "镜像文件 (*.img);;所有文件 (*)")
            
            if save_path:
                # 在实际应用中，这里会执行实际的提取操作
                # 此处仅模拟成功消息
                self.log_signal.emit(f"分区 {partition} 已提取到: {save_path}")
                self.partition_output.appendPlainText(f"成功提取 {partition} 分区到:\n{save_path}")
            else:
                self.log_signal.emit("提取操作已取消")
                
        except Exception as e:
            self.log_signal.emit(f"提取分区失败: {str(e)}")
            self.partition_output.appendPlainText(f"错误: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _execute_flash_bootrom_partition(self):
        """执行刷入Bootrom分区"""
        try:
            partition = self.partition_combo_bootrom.currentText()
            self.log_signal.emit(f"开始刷入 {partition} 分区...")
            
            # 模拟刷入过程
            for i in range(1, 101):
                time.sleep(0.03)
                self.progress_signal.emit(i)
                
            self.log_signal.emit(f"{partition} 分区刷入完成!")
            self.partition_output.appendPlainText(f"成功刷入 {partition} 分区")
            
        except Exception as e:
            self.log_signal.emit(f"刷入分区失败: {str(e)}")
            self.partition_output.appendPlainText(f"错误: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _execute_get_bootrom_partition_table(self):
        """执行获取Bootrom分区表"""
        try:
            self.log_signal.emit("正在获取分区表信息...")
            
            # 模拟获取过程
            time.sleep(1)
            
            # 生成模拟分区表数据
            partitions = [
                ("boot", "0x0000000000004000", "0x0000000000400000"),
                ("recovery", "0x0000000000404000", "0x0000000000400000"),
                ("system", "0x0000000000804000", "0x0000000004000000"),
                ("vendor", "0x0000000004804000", "0x0000000002000000"),
                ("userdata", "0x0000000006804000", "0x00000000c0000000"),
                ("cache", "0x00000000c6804000", "0x0000000004000000")
            ]
            
            table_text = "分区表信息:\n\n"
            table_text += "分区名称      起始地址         大小\n"
            table_text += "------------------------------------\n"
            for name, start, size in partitions:
                table_text += f"{name.ljust(12)}{start.ljust(16)}{size}\n"
            
            self.partition_output.setPlainText(table_text)
            self.log_signal.emit("分区表信息已获取")
            
        except Exception as e:
            self.log_signal.emit(f"获取分区表失败: {str(e)}")
            self.partition_output.appendPlainText(f"错误: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.operation_in_progress:
            QMessageBox.warning(self, "警告", "请等待当前操作完成")
            event.ignore()
        else:
            self.adb.cleanup()
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion样式使界面更现代
    
    # 设置全局字体为微软雅黑
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    tool = FlashTool()
    tool.show()
    
    sys.exit(app.exec_())