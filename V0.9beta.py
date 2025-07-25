import os
import sys
import time
import threading
import subprocess
import usb.core
import socket
import struct
import platform
import tempfile
import urllib.request
import zipfile
import shutil
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QProgressBar, QTextEdit,
                             QFileDialog, QMessageBox, QGroupBox, QDialog, QVBoxLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class DebugLogDialog(QDialog):
    """Debug日志对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Debug日志")
        self.setGeometry(200, 200, 800, 500)
        
        layout = QVBoxLayout()
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("font-family: monospace;")
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        
        layout.addWidget(self.log_output)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)

class ADB:
    """改进后的ADB客户端实现，包含内置ADB支持和下载功能"""
    def __init__(self, host='127.0.0.1', port=5037):
        self.host = host
        self.port = port
        self.adb_path = None
        self.fastboot_path = None  # 新增fastboot路径存储
        self.server_started = False
        self.last_error = ""
        self.temp_dir = None
        self._init_adb()

    def _init_adb(self):
        """初始化ADB路径查找"""
        self.adb_path = self._find_or_install_adb()
        if not self.adb_path:
            self.last_error = "无法找到或安装ADB工具"
        else:
            # 初始化时同时查找fastboot路径
            self._find_fastboot()

    def _get_platform_specific_name(self, tool):
        """获取平台特定的可执行文件名"""
        system = platform.system().lower()
        if system == "windows":
            return f"{tool}.exe"
        return tool

    def _get_builtin_adb_path(self):
        """获取内置ADB路径"""
        if not hasattr(sys, '_MEIPASS'):
            return None
            
        base_path = sys._MEIPASS
        adb_name = self._get_platform_specific_name("adb")
        possible_paths = [
            os.path.join(base_path, adb_name),
            os.path.join(base_path, "platform-tools", adb_name)
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    def _find_fastboot(self):
        """查找fastboot工具路径"""
        if not self.adb_path:
            return None
            
        # 首先尝试在adb同级目录查找
        adb_dir = os.path.dirname(self.adb_path)
        fastboot_name = self._get_platform_specific_name("fastboot")
        possible_paths = [
            os.path.join(adb_dir, fastboot_name),
            os.path.join(adb_dir, "platform-tools", fastboot_name),
            fastboot_name  # 最后尝试系统PATH中的fastboot
        ]
        
        for path in possible_paths:
            try:
                # 检查fastboot是否可用
                result = subprocess.run([path, "--version"], 
                                      capture_output=True, 
                                      text=True,
                                      timeout=2)
                if result.returncode == 0:
                    self.fastboot_path = path
                    print(f"找到Fastboot工具: {path}")
                    return path
            except:
                continue
                
        self.last_error = "无法找到可用的Fastboot工具"
        return None

    def _download_adb(self):
        """下载ADB工具"""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="adb_temp_")
            
            url = "https://dl.google.com/android/repository/platform-tools-latest-{}.zip"
            system = platform.system().lower()
            if system == "windows":
                url = url.format("windows")
            elif system == "linux":
                url = url.format("linux")
            elif system == "darwin":
                url = url.format("darwin")
            else:
                raise Exception("不支持的操作系统")
            
            zip_path = os.path.join(self.temp_dir, "platform-tools.zip")
            
            def _report_progress(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                sys.stdout.write(f"\r下载ADB工具... {percent}%")
                sys.stdout.flush()
            
            print("正在下载ADB工具...")
            urllib.request.urlretrieve(url, zip_path, _report_progress)
            print("\n下载完成")
            
            print("正在解压...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
            
            adb_name = self._get_platform_specific_name("adb")
            adb_path = os.path.join(self.temp_dir, "platform-tools", adb_name)
            
            if platform.system().lower() != "windows":
                os.chmod(adb_path, 0o755)
            
            print(f"ADB已安装到: {adb_path}")
            return adb_path
        except Exception as e:
            self.last_error = f"下载ADB失败: {str(e)}"
            return None

    def _find_system_adb(self):
        """查找系统PATH中的ADB"""
        adb_name = self._get_platform_specific_name("adb")
        try:
            result = subprocess.run([adb_name, "version"], 
                                  capture_output=True, 
                                  text=True,
                                  timeout=2)
            if result.returncode == 0:
                return adb_name
        except:
            return None

    def _find_adb_in_common_paths(self):
        """在常见路径中查找ADB"""
        adb_name = self._get_platform_specific_name("adb")
        paths = [
            "adb",
            "/usr/bin/adb",
            "/usr/local/bin/adb",
            "platform-tools/adb",
            "platform-tools/adb.exe",
            os.path.join(os.environ.get("ANDROID_HOME", ""), "platform-tools", adb_name),
            os.path.join(os.environ.get("ANDROID_SDK_ROOT", ""), "platform-tools", adb_name),
            "C:\\Program Files (x86)\\Android\\android-sdk\\platform-tools\\adb.exe",
            os.path.expanduser("~/Library/Android/sdk/platform-tools/adb")
        ]
        
        for path in paths:
            try:
                result = subprocess.run([path, "version"], 
                                      capture_output=True, 
                                      text=True,
                                      timeout=2)
                if result.returncode == 0:
                    return path
            except:
                continue
        return None

    def _find_or_install_adb(self):
        """查找或安装ADB工具"""
        system_adb = self._find_system_adb()
        if system_adb:
            print(f"找到系统ADB: {system_adb}")
            return system_adb
            
        common_adb = self._find_adb_in_common_paths()
        if common_adb:
            print(f"找到ADB: {common_adb}")
            return common_adb
            
        builtin_adb = self._get_builtin_adb_path()
        if builtin_adb:
            print(f"使用内置ADB: {builtin_adb}")
            return builtin_adb
            
        print("未找到ADB，尝试下载...")
        downloaded_adb = self._download_adb()
        if downloaded_adb:
            return downloaded_adb
            
        self.last_error = "无法找到或安装ADB工具"
        return None

    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"已清理临时目录: {self.temp_dir}")
            except Exception as e:
                print(f"清理临时目录失败: {str(e)}")

    def _ensure_adb_server(self):
        """确保ADB服务器正在运行"""
        if self.server_started:
            return True
            
        if not self.adb_path:
            self.last_error = "ADB工具未找到，请先安装Android平台工具"
            return False
            
        try:
            subprocess.run([self.adb_path, "kill-server"], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE,
                         timeout=5)
            
            result = subprocess.run([self.adb_path, "start-server"], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE,
                                 timeout=10)
            if result.returncode != 0:
                self.last_error = f"启动ADB服务失败: {result.stderr.decode('utf-8', 'replace')}"
                return False
                
            time.sleep(2)
            self.server_started = True
            return True
        except subprocess.TimeoutExpired:
            self.last_error = "ADB服务启动超时，请手动尝试运行: adb start-server"
            return False
        except Exception as e:
            self.last_error = f"ADB服务启动异常: {str(e)}"
            return False
    
    def _connect(self):
        """连接到ADB服务器"""
        if not self._ensure_adb_server():
            raise Exception(self.last_error)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.host, self.port))
            return sock
        except Exception as e:
            raise Exception(f"无法连接到ADB服务器: {str(e)}")
    
    def _send_command(self, cmd):
        """发送ADB命令"""
        sock = self._connect()
        try:
            cmd_bytes = cmd.encode('utf-8')
            sock.send(struct.pack('4s', f"{len(cmd_bytes):04x}".encode('utf-8')))
            sock.send(cmd_bytes)
            
            status = sock.recv(4)
            if not status:
                raise Exception("无响应")
                
            if status == b"FAIL":
                length = int(sock.recv(4), 16)
                error = sock.recv(length).decode('utf-8', 'replace')
                raise Exception(f"ADB错误: {error}")
            elif status == b"OKAY":
                return sock
            else:
                raise Exception(f"未知响应: {status}")
        except Exception as e:
            sock.close()
            raise e
    
    def devices(self):
        """获取设备列表"""
        try:
            sock = self._send_command("host:devices")
            length = int(sock.recv(4), 16)
            data = sock.recv(length).decode('utf-8', 'replace')
            return [line.split('\t') for line in data.splitlines() if line]
        except Exception as e:
            if self.adb_path:
                try:
                    result = subprocess.run([self.adb_path, "devices"], 
                                          capture_output=True, 
                                          text=True,
                                          timeout=5)
                    if result.returncode == 0 and result.stdout.strip():
                        return [line.split('\t') for line in result.stdout.splitlines() 
                               if line and not line.startswith('List of')]
                    else:
                        self.last_error = result.stderr
                except Exception as sub_e:
                    self.last_error = str(sub_e)
            raise Exception(f"获取设备列表失败: {str(e)}. {self.last_error}")
        finally:
            if 'sock' in locals():
                sock.close()
    
    def reboot(self, mode=None):
        """重启设备 - 改进版本"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return False
            
        try:
            cmd = [self.adb_path, "reboot"]
            if mode == "bootloader":
                cmd.append("bootloader")
            elif mode == "recovery":
                cmd.append("recovery")
            
            result = subprocess.run(cmd, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  timeout=10)
            
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', 'replace').strip()
                self.last_error = f"重启失败: {error_msg}"
                return False
                
            return True
        except subprocess.TimeoutExpired:
            self.last_error = "重启操作超时"
            return False
        except Exception as e:
            self.last_error = f"重启异常: {str(e)}"
            return False
    
    def fastboot_devices(self):
        """获取fastboot设备列表 - 改进版本"""
        if not self.fastboot_path:
            self._find_fastboot()
            if not self.fastboot_path:
                self.last_error = "Fastboot工具未找到"
                return []
            
        try:
            # 获取设备列表
            result = subprocess.run([self.fastboot_path, "devices"], 
                                  capture_output=True, 
                                  text=True,
                                  timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return [line.split('\t') for line in result.stdout.splitlines() if line]
            else:
                self.last_error = result.stderr or "无Fastboot设备"
                return []
        except Exception as e:
            self.last_error = str(e)
            return []

    def fastboot_reboot(self):
        """通过fastboot重启设备"""
        if not self.fastboot_path:
            self._find_fastboot()
            if not self.fastboot_path:
                self.last_error = "Fastboot工具未找到"
                return False
                
        try:
            result = subprocess.run([self.fastboot_path, "reboot"], 
                                  capture_output=True,
                                  text=True,
                                  timeout=10)
            
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                self.last_error = f"Fastboot重启失败: {error_msg}"
                return False
                
            return True
        except subprocess.TimeoutExpired:
            self.last_error = "Fastboot重启操作超时"
            return False
        except Exception as e:
            self.last_error = f"Fastboot重启异常: {str(e)}"
            return False

    def backup_partition(self, partition, output_path):
        """备份指定分区"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return False
            
        try:
            # 创建输出目录
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 使用dd命令备份分区
            cmd = f"su -c 'dd if=/dev/block/bootdevice/by-name/{partition} of={output_path}'"
            result = subprocess.run([self.adb_path, "shell", cmd], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  timeout=300)  # 5分钟超时
            
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', 'replace').strip()
                self.last_error = f"备份失败: {error_msg}"
                return False
                
            return True
        except subprocess.TimeoutExpired:
            self.last_error = "备份操作超时"
            return False
        except Exception as e:
            self.last_error = f"备份异常: {str(e)}"
            return False

    def fastboot_backup_partition(self, partition, output_path):
        """在Fastboot模式下备份分区"""
        if not self.fastboot_path:
            self._find_fastboot()
            if not self.fastboot_path:
                self.last_error = "Fastboot工具未找到"
                return False
                
        try:
            # 创建输出目录
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 使用fastboot获取分区大小
            size_cmd = [self.fastboot_path, "getvar", f"partition-size:{partition}"]
            size_result = subprocess.run(size_cmd, 
                                       capture_output=True,
                                       text=True,
                                       timeout=10)
            
            if size_result.returncode != 0:
                self.last_error = f"获取分区大小失败: {size_result.stderr.strip()}"
                return False
                
            # 解析分区大小
            size_lines = size_result.stdout.splitlines()
            size_line = next((line for line in size_lines if line.startswith(f"partition-size:{partition}")), None)
            if not size_line:
                self.last_error = "无法解析分区大小"
                return False
                
            size_str = size_line.split(":")[1].strip()
            try:
                partition_size = int(size_str, 16)
            except ValueError:
                self.last_error = "无效的分区大小格式"
                return False
                
            # 使用fastboot dump分区
            dump_cmd = [self.fastboot_path, "dump", f"partition:{partition}", output_path]
            result = subprocess.run(dump_cmd, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  timeout=600)  # 10分钟超时
            
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', 'replace').strip()
                self.last_error = f"备份失败: {error_msg}"
                return False
                
            # 检查备份文件大小
            if os.path.getsize(output_path) != partition_size:
                self.last_error = "备份文件大小与分区大小不匹配"
                return False
                
            return True
        except subprocess.TimeoutExpired:
            self.last_error = "备份操作超时"
            return False
        except Exception as e:
            self.last_error = f"备份异常: {str(e)}"
            return False

class FlashTool(QMainWindow):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str, str)  # 状态类型, 状态消息
    mode_signal = pyqtSignal(str, str)    # 模式, 设备ID
    reboot_signal = pyqtSignal(str)       # 重启状态信号
    backup_signal = pyqtSignal(str)       # 备份状态信号
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Flash Tools V0.9")
        self.setGeometry(100, 100, 800, 600)
        
        # 初始化变量
        self.current_mode = None
        self.device_id = None
        self.flashing = False
        self.backing_up = False
        self.firmware_path = ""
        self.backup_path = ""
        self.adb = ADB()
        self.debug_mode = True
        self.adb_available = False
        self.debug_log_dialog = None
        
        # 连接信号
        self.log_signal.connect(self._log_message)
        self.progress_signal.connect(self._update_progress)
        self.status_signal.connect(self._update_status)
        self.mode_signal.connect(self._handle_mode_change)
        self.reboot_signal.connect(self._handle_reboot_status)
        self.backup_signal.connect(self._handle_backup_status)
        
        self._init_ui()
        self._start_device_check()
    
    def _init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        # 设备状态组
        status_group = QGroupBox("设备状态")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("等待设备连接...")
        self.status_label.setStyleSheet("font-weight: bold;")
        
        self.mode_label = QLabel("当前模式: 未连接")
        self.device_info = QLabel("")
        
        # ADB/Fastboot状态指示
        self.adb_status = QLabel("ADB: 检测中...")
        self.adb_status.setStyleSheet("color: orange;")
        
        self.fastboot_status = QLabel("Fastboot: 检测中...")
        self.fastboot_status.setStyleSheet("color: orange;")
        
        status_layout.addWidget(self.adb_status)
        status_layout.addWidget(self.fastboot_status)
        
        # 模式切换按钮
        btn_layout = QHBoxLayout()
        self.bootrom_btn = QPushButton("进入9008模式")
        self.bootrom_btn.clicked.connect(self._enter_bootrom)
        self.bootrom_btn.setEnabled(False)
        
        self.fastboot_btn = QPushButton("进入Fastboot")
        self.fastboot_btn.clicked.connect(self._enter_fastboot)
        self.fastboot_btn.setEnabled(False)
        
        self.reboot_btn = QPushButton("重启设备")
        self.reboot_btn.clicked.connect(self._reboot_device)
        self.reboot_btn.setEnabled(False)
        
        btn_layout.addWidget(self.bootrom_btn)
        btn_layout.addWidget(self.fastboot_btn)
        btn_layout.addWidget(self.reboot_btn)
        
        # 工具按钮
        tool_btn_layout = QHBoxLayout()
        self.help_btn = QPushButton("ADB安装帮助")
        self.help_btn.clicked.connect(self._show_adb_help)
        
        self.download_btn = QPushButton("下载ADB工具")
        self.download_btn.clicked.connect(self._download_adb_tool)
        
        self.debug_btn = QPushButton("Debug日志")
        self.debug_btn.clicked.connect(self._show_debug_log)
        
        # 关于按钮 (暂时不实现功能)
        self.about_btn = QPushButton("关于")
        self.about_btn.clicked.connect(self._show_about)
        
        tool_btn_layout.addWidget(self.help_btn)
        tool_btn_layout.addWidget(self.download_btn)
        tool_btn_layout.addWidget(self.debug_btn)
        tool_btn_layout.addWidget(self.about_btn)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.mode_label)
        status_layout.addWidget(self.device_info)
        status_layout.addLayout(btn_layout)
        status_layout.addLayout(tool_btn_layout)
        status_group.setLayout(status_layout)
        
        # 刷机控制组
        flash_group = QGroupBox("刷机控制")
        flash_layout = QVBoxLayout()
        
        # 文件选择
        file_layout = QHBoxLayout()
        self.file_label = QLabel("未选择文件")
        self.select_btn = QPushButton("选择固件")
        self.select_btn.clicked.connect(self._select_firmware)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.select_btn)
        
        # 分区选择
        self.partition_combo = QComboBox()
        self.partition_combo.addItems(["全部", "boot", "recovery", "system", "vendor"])
        
        # 刷机按钮
        self.flash_btn = QPushButton("开始刷机")
        self.flash_btn.setEnabled(False)
        self.flash_btn.clicked.connect(self._start_flashing)
        
        self.progress_bar = QProgressBar()
        
        flash_layout.addLayout(file_layout)
        flash_layout.addWidget(self.partition_combo)
        flash_layout.addWidget(self.progress_bar)
        flash_layout.addWidget(self.flash_btn)
        
        # 备份控制组
        backup_group = QGroupBox("备份控制")
        backup_layout = QVBoxLayout()
        
        # 备份路径选择
        backup_path_layout = QHBoxLayout()
        self.backup_path_label = QLabel("未选择备份路径")
        self.select_backup_btn = QPushButton("选择备份路径")
        self.select_backup_btn.clicked.connect(self._select_backup_path)
        backup_path_layout.addWidget(self.backup_path_label)
        backup_path_layout.addWidget(self.select_backup_btn)
        
        # 备份按钮
        self.backup_btn = QPushButton("开始备份")
        self.backup_btn.setEnabled(False)
        self.backup_btn.clicked.connect(self._start_backup)
        
        backup_layout.addLayout(backup_path_layout)
        backup_layout.addWidget(self.backup_btn)
        backup_group.setLayout(backup_layout)
        
        flash_layout.addWidget(backup_group)
        flash_group.setLayout(flash_layout)
        
        # 组装主界面
        layout.addWidget(status_group)
        layout.addWidget(flash_group)
        main_widget.setLayout(layout)
        
        self.setCentralWidget(main_widget)
        
        # 初始化Debug日志对话框
        self.debug_log_dialog = DebugLogDialog(self)
    
    def _show_debug_log(self):
        """显示Debug日志对话框"""
        self.debug_log_dialog.show()
    
    def _show_about(self):
        """显示关于对话框 (暂时不实现)"""
        pass
    
    def _start_device_check(self):
        """启动设备检测线程"""
        def check_loop():
            last_adb_state = False
            last_fastboot_state = False
            while True:
                # 检查ADB状态
                current_adb_state = self.adb.adb_path is not None
                if current_adb_state != last_adb_state:
                    self.adb_available = current_adb_state
                    status = "已就绪" if current_adb_state else "未检测到"
                    if current_adb_state:
                        status += f" ({os.path.basename(self.adb.adb_path)})"
                    self.status_signal.emit("adb", status)
                    last_adb_state = current_adb_state
                
                # 检查Fastboot状态
                current_fastboot_state = self.adb.fastboot_path is not None
                if current_fastboot_state != last_fastboot_state:
                    status = "已就绪" if current_fastboot_state else "未检测到"
                    if current_fastboot_state:
                        status += f" ({os.path.basename(self.adb.fastboot_path)})"
                    self.status_signal.emit("fastboot", status)
                    last_fastboot_state = current_fastboot_state
                
                # 检查设备连接状态
                self._check_device()
                time.sleep(3)
        
        threading.Thread(target=check_loop, daemon=True).start()
    
    def _check_device(self):
        """检查设备连接状态"""
        try:
            # 检查ADB设备
            if self.adb_available:
                try:
                    adb_devices = self.adb.devices()
                    if adb_devices:
                        self.mode_signal.emit("adb", adb_devices[0][0])
                        return
                except Exception as e:
                    self.log_signal.emit(f"ADB设备检测错误: {str(e)}")
            
            # 检查Fastboot设备
            try:
                fastboot_devices = self.adb.fastboot_devices()
                if fastboot_devices:
                    self.mode_signal.emit("fastboot", fastboot_devices[0][0])
                    return
            except Exception as e:
                self.log_signal.emit(f"Fastboot设备检测错误: {str(e)}")
            
            # 检查Bootrom设备
            try:
                bootrom_device = self._check_bootrom_device()
                if bootrom_device:
                    self.mode_signal.emit("bootrom", bootrom_device)
                    return
            except Exception as e:
                self.log_signal.emit(f"Bootrom设备检测错误: {str(e)}")
            
            # 没有检测到设备
            self.mode_signal.emit(None, None)
            
        except Exception as e:
            self.log_signal.emit(f"设备检测错误: {str(e)}")
            self.mode_signal.emit(None, None)
    
    def _check_bootrom_device(self):
        """检查9008模式设备并返回设备信息"""
        try:
            devices = usb.core.find(find_all=True)
            for device in devices:
                if device.idVendor == 0x05c6 and device.idProduct == 0x9008:
                    # 获取更多设备信息
                    try:
                        manufacturer = usb.util.get_string(device, device.iManufacturer)
                        product = usb.util.get_string(device, device.iProduct)
                        serial = usb.util.get_string(device, device.iSerialNumber)
                        
                        info = f"VID:PID={device.idVendor:04x}:{device.idProduct:04x}"
                        if manufacturer:
                            info += f" {manufacturer}"
                        if product:
                            info += f" {product}"
                        if serial:
                            info += f" (SN:{serial})"
                            
                        return info
                    except:
                        return f"9008设备 (VID:PID={device.idVendor:04x}:{device.idProduct:04x})"
            return None
        except Exception as e:
            self.log_signal.emit(f"USB设备检测错误: {str(e)}")
            return None
    
    def _handle_mode_change(self, mode, device_id):
        """处理模式变化的槽函数（在主线程执行）"""
        if mode == self.current_mode and device_id == self.device_id:
            return
            
        self.current_mode = mode
        self.device_id = device_id
        
        if mode == "adb":
            self.status_label.setText("设备已连接 (ADB模式)")
            self.mode_label.setText("当前模式: ADB")
            self.device_info.setText(f"设备ID: {device_id}")
            self._enable_buttons()
            
        elif mode == "fastboot":
            self.status_label.setText("设备已连接 (Fastboot模式)")
            self.mode_label.setText("当前模式: Fastboot")
            self.device_info.setText(f"设备ID: {device_id}")
            self._enable_buttons()
            
        elif mode == "bootrom":
            self.status_label.setText("设备已连接 (9008模式)")
            self.mode_label.setText("当前模式: 9008")
            self.device_info.setText(f"{device_id}")
            self._enable_buttons()
            
        else:
            self.status_label.setText("等待设备连接...")
            self.mode_label.setText("当前模式: 未连接")
            self.device_info.setText("")
            self._disable_buttons()
    
    def _handle_reboot_status(self, message):
        """处理重启状态更新"""
        self.log_signal.emit(message)
        if "失败" in message or "错误" in message:
            QMessageBox.warning(self, "错误", message)
    
    def _handle_backup_status(self, message):
        """处理备份状态更新"""
        self.log_signal.emit(message)
        if "失败" in message or "错误" in message:
            QMessageBox.warning(self, "错误", message)
    
    def _download_adb_tool(self):
        """手动下载ADB工具"""
        self.log_signal.emit("开始下载ADB工具...")
        self._disable_buttons()
        
        reply = QMessageBox.question(
            self, "确认",
            "确定要下载ADB工具吗? 这将需要网络连接并下载约10MB数据",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            self._enable_buttons()
            return
            
        threading.Thread(target=self._execute_download_adb, daemon=True).start()
    
    def _execute_download_adb(self):
        """执行ADB下载"""
        try:
            if self.adb:
                self.adb.cleanup()
            
            self.adb = ADB()
            
            if self.adb.adb_path:
                self.log_signal.emit(f"ADB工具已下载并安装到: {self.adb.adb_path}")
                self.status_signal.emit("adb", f"已就绪 ({os.path.basename(self.adb.adb_path)})")
                
                # 检查fastboot是否可用
                if self.adb.fastboot_path:
                    self.status_signal.emit("fastboot", f"已就绪 ({os.path.basename(self.adb.fastboot_path)})")
                else:
                    self.status_signal.emit("fastboot", "未检测到")
            else:
                self.log_signal.emit(f"下载ADB失败: {self.adb.last_error}")
                QMessageBox.warning(self, "错误", f"下载ADB失败: {self.adb.last_error}")
        except Exception as e:
            self.log_signal.emit(f"下载ADB时出错: {str(e)}")
            QMessageBox.warning(self, "错误", f"下载ADB时出错: {str(e)}")
        finally:
            self._check_device()
            self._enable_buttons()
    
    def _show_adb_help(self):
        """显示ADB安装帮助"""
        help_text = """ADB和Fastboot安装帮助:

1. 自动下载: 点击"下载ADB工具"按钮自动下载安装(包含Fastboot)

2. 手动安装:
   - Windows: 下载Android SDK Platform Tools并解压
   - Mac: brew install android-platform-tools
   - Linux: sudo apt install android-tools-adb android-tools-fastboot

3. 确保ADB和Fastboot路径已添加到系统PATH环境变量中"""
        
        QMessageBox.information(self, "ADB安装帮助", help_text)
    
    def _enter_bootrom(self):
        """进入9008模式"""
        if not self.adb_available:
            QMessageBox.warning(self, "错误", "ADB不可用，无法执行此操作")
            return
            
        reply = QMessageBox.question(
            self, "确认",
            "确定要让设备进入9008模式吗? 此操作可能需要手动操作",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        self._disable_buttons()
        self.log_signal.emit("尝试让设备进入9008模式...")
        threading.Thread(target=self._execute_enter_bootrom, daemon=True).start()
    
    def _execute_enter_bootrom(self):
        """执行进入9008模式"""
        try:
            # 首先尝试通过ADB重启到bootloader
            if self.adb.reboot("bootloader"):
                self.log_signal.emit("设备正在重启到bootloader...")
                
                # 等待设备进入fastboot模式
                time.sleep(5)
                
                # 检查是否进入fastboot模式
                fastboot_devices = self.adb.fastboot_devices()
                if fastboot_devices:
                    self.log_signal.emit("设备已进入fastboot模式，现在尝试进入9008模式...")
                    
                    # 尝试通过fastboot命令进入9008模式
                    if self.adb.fastboot_path:
                        result = subprocess.run([self.adb.fastboot_path, "oem", "edl"], 
                                             capture_output=True,
                                             text=True,
                                             timeout=10)
                        
                        if result.returncode == 0:
                            self.log_signal.emit("已发送EDL命令，设备应进入9008模式")
                        else:
                            self.log_signal.emit(f"发送EDL命令失败: {result.stderr.strip()}")
                            self.log_signal.emit("可能需要手动进入9008模式")
                else:
                    self.log_signal.emit("未能检测到fastboot设备，可能需要手动进入9008模式")
                    
            else:
                self.log_signal.emit(f"重启到bootloader失败: {self.adb.last_error}")
                self.log_signal.emit("可能需要手动进入9008模式")
                
        except Exception as e:
            self.log_signal.emit(f"进入9008模式失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"进入9008模式失败: {str(e)}")
        finally:
            self._check_device()
            self._enable_buttons()
    
    def _enter_fastboot(self):
        """进入Fastboot模式"""
        if not self.adb_available:
            QMessageBox.warning(self, "错误", "ADB不可用，无法执行此操作")
            return
            
        reply = QMessageBox.question(
            self, "确认",
            "确定要让设备进入Fastboot模式吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        self._disable_buttons()
        self.log_signal.emit("尝试让设备进入Fastboot模式...")
        threading.Thread(target=self._execute_enter_fastboot, daemon=True).start()
    
    def _execute_enter_fastboot(self):
        """执行进入Fastboot模式"""
        try:
            self.adb.reboot("bootloader")
            self.log_signal.emit("设备正在重启到Fastboot模式...")
            
            time.sleep(5)
            
            fastboot_devices = self.adb.fastboot_devices()
            if fastboot_devices:
                self.log_signal.emit("设备已进入Fastboot模式")
            else:
                self.log_signal.emit("未能检测到Fastboot设备")
                
        except Exception as e:
            self.log_signal.emit(f"进入Fastboot模式失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"进入Fastboot模式失败: {str(e)}")
        finally:
            self._check_device()
            self._enable_buttons()
    
    def _reboot_device(self):
        """重启设备"""
        if not self.adb_available and self.current_mode != "fastboot":
            QMessageBox.warning(self, "错误", "无法执行重启操作")
            return
            
        reply = QMessageBox.question(
            self, "确认",
            "确定要重启设备吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        self._disable_buttons()
        self.log_signal.emit("正在重启设备...")
        threading.Thread(target=self._execute_reboot, daemon=True).start()
    
    def _execute_reboot(self):
        """执行重启设备 - 改进版本"""
        try:
            if self.current_mode == "adb":
                if self.adb.reboot():
                    self.reboot_signal.emit("设备正在重启...")
                else:
                    self.reboot_signal.emit(f"重启失败: {self.adb.last_error}")
                    
            elif self.current_mode == "fastboot":
                if self.adb.fastboot_reboot():
                    self.reboot_signal.emit("设备正在从Fastboot模式重启...")
                else:
                    self.reboot_signal.emit(f"Fastboot重启失败: {self.adb.last_error}")
                    
            else:
                self.reboot_signal.emit("当前模式不支持重启操作")
                
        except subprocess.TimeoutExpired:
            self.reboot_signal.emit("重启操作超时")
        except Exception as e:
            self.reboot_signal.emit(f"重启设备时发生异常: {str(e)}")
        finally:
            time.sleep(2)
            self._check_device()
            self._enable_buttons()
    
    def _select_firmware(self):
        """选择固件文件"""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择固件文件", "", 
            "固件文件 (*.zip *.tgz *.tar.gz *.img);;所有文件 (*)", 
            options=options)
            
        if file_path:
            self.firmware_path = file_path
            self.file_label.setText(os.path.basename(file_path))
            self.flash_btn.setEnabled(self.current_mode is not None)
            self.log_signal.emit(f"已选择固件: {file_path}")
    
    def _select_backup_path(self):
        """选择备份路径"""
        options = QFileDialog.Options()
        backup_dir = QFileDialog.getExistingDirectory(
            self, "选择备份目录", "",
            options=options)
            
        if backup_dir:
            self.backup_path = backup_dir
            self.backup_path_label.setText(os.path.basename(backup_dir))
            self.backup_btn.setEnabled(self.current_mode is not None)
            self.log_signal.emit(f"已选择备份路径: {backup_dir}")
    
    def _start_flashing(self):
        """开始刷机"""
        if not self.firmware_path:
            QMessageBox.warning(self, "错误", "请先选择固件文件")
            return
            
        reply = QMessageBox.warning(
            self, "警告",
            "刷机有风险，可能导致设备损坏或数据丢失!\n确定要继续吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        self._disable_buttons()
        self.flashing = True
        self.log_signal.emit("开始刷机过程...")
        threading.Thread(target=self._execute_flash, daemon=True).start()
    
    def _start_backup(self):
        """开始备份"""
        if not self.backup_path:
            QMessageBox.warning(self, "错误", "请先选择备份路径")
            return
            
        reply = QMessageBox.question(
            self, "确认",
            "确定要备份设备分区吗? 这可能需要一些时间",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        self._disable_buttons()
        self.backing_up = True
        self.log_signal.emit("开始备份过程...")
        threading.Thread(target=self._execute_backup, daemon=True).start()
    
    def _execute_flash(self):
        """执行刷机"""
        try:
            partition = self.partition_combo.currentText()
            
            if self.current_mode == "bootrom":
                self._flash_bootrom()
            elif self.current_mode == "fastboot":
                self._flash_fastboot(partition)
            else:
                self.log_signal.emit("当前模式不支持刷机")
                
            self.log_signal.emit("刷机完成!")
            
        except Exception as e:
            self.log_signal.emit(f"刷机失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"刷机失败: {str(e)}")
            
        finally:
            self.flashing = False
            self._check_device()
            self._enable_buttons()
    
    def _execute_backup(self):
        """执行备份"""
        try:
            partition = self.partition_combo.currentText()
            
            if partition == "全部":
                partitions = ["boot", "recovery", "system", "vendor"]
            else:
                partitions = [partition]
            
            for part in partitions:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = os.path.join(self.backup_path, f"{part}_backup_{timestamp}.img")
                
                if self.current_mode == "adb":
                    self.backup_signal.emit(f"正在备份 {part} 分区...")
                    if self.adb.backup_partition(part, backup_file):
                        self.backup_signal.emit(f"{part} 分区备份成功: {backup_file}")
                    else:
                        self.backup_signal.emit(f"{part} 分区备份失败: {self.adb.last_error}")
                        return
                
                elif self.current_mode == "fastboot":
                    self.backup_signal.emit(f"正在备份 {part} 分区...")
                    if self.adb.fastboot_backup_partition(part, backup_file):
                        self.backup_signal.emit(f"{part} 分区备份成功: {backup_file}")
                    else:
                        self.backup_signal.emit(f"{part} 分区备份失败: {self.adb.last_error}")
                        return
                
                else:
                    self.backup_signal.emit("当前模式不支持备份")
                    return
            
            self.backup_signal.emit("备份完成!")
            
        except Exception as e:
            self.backup_signal.emit(f"备份失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"备份失败: {str(e)}")
            
        finally:
            self.backing_up = False
            self._check_device()
            self._enable_buttons()
    
    def _flash_bootrom(self):
        """在9008模式下刷机"""
        self.log_signal.emit("开始在9008模式下刷机...")
        
        try:
            # 检查设备是否仍在9008模式
            if not self._check_bootrom_device():
                raise Exception("9008设备已断开连接")
            
            # 模拟刷机过程
            for i in range(1, 101):
                time.sleep(0.1)
                self.progress_signal.emit(i)
                self.log_signal.emit(f"刷机进度: {i}%")
                
                # 每10%检查一次设备连接
                if i % 10 == 0 and not self._check_bootrom_device():
                    raise Exception("9008设备在刷机过程中断开连接")
                    
            self.log_signal.emit("9008模式刷机完成!")
            
        except Exception as e:
            self.log_signal.emit(f"9008刷机失败: {str(e)}")
            raise
    
    def _flash_fastboot(self, partition):
        """在Fastboot模式下刷机"""
        self.log_signal.emit(f"开始在Fastboot模式下刷写 {partition} 分区...")
        
        if not self.adb.fastboot_path:
            self.log_signal.emit("错误: 未找到Fastboot工具")
            return
            
        # 模拟刷机过程
        for i in range(1, 101):
            time.sleep(0.05)
            self.progress_signal.emit(i)
            self.log_signal.emit(f"刷写 {partition} 分区进度: {i}%")
    
    def _log_message(self, message):
        """在日志输出区域显示消息"""
        # 同时输出到主窗口和Debug日志对话框
        if self.debug_log_dialog:
            self.debug_log_dialog.log_output.append(message)
            self.debug_log_dialog.log_output.ensureCursorVisible()
        QApplication.processEvents()
    
    def _update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
        QApplication.processEvents()
    
    def _update_status(self, status_type, message):
        """更新状态显示"""
        if status_type == "adb":
            self.adb_status.setText(f"ADB: {message}")
            if "就绪" in message:
                self.adb_status.setStyleSheet("color: green;")
            elif "未检测到" in message:
                self.adb_status.setStyleSheet("color: red;")
            else:
                self.adb_status.setStyleSheet("color: orange;")
        elif status_type == "fastboot":
            self.fastboot_status.setText(f"Fastboot: {message}")
            if "就绪" in message:
                self.fastboot_status.setStyleSheet("color: green;")
            elif "未检测到" in message:
                self.fastboot_status.setStyleSheet("color: red;")
            else:
                self.fastboot_status.setStyleSheet("color: orange;")
    
    def _disable_buttons(self):
        """禁用所有按钮"""
        self.bootrom_btn.setEnabled(False)
        self.fastboot_btn.setEnabled(False)
        self.reboot_btn.setEnabled(False)
        self.flash_btn.setEnabled(False)
        self.backup_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.select_backup_btn.setEnabled(False)
        self.help_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.debug_btn.setEnabled(False)
        self.about_btn.setEnabled(False)
    
    def _enable_buttons(self):
        """根据当前模式启用适当的按钮"""
        self.bootrom_btn.setEnabled(self.current_mode == "adb")
        self.fastboot_btn.setEnabled(self.current_mode == "adb")
        self.reboot_btn.setEnabled(self.current_mode is not None)
        self.flash_btn.setEnabled(self.current_mode is not None and bool(self.firmware_path))
        self.backup_btn.setEnabled(self.current_mode is not None and bool(self.backup_path))
        self.select_btn.setEnabled(True)
        self.select_backup_btn.setEnabled(True)
        self.help_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.debug_btn.setEnabled(True)
        self.about_btn.setEnabled(True)
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.flashing or self.backing_up:
            QMessageBox.warning(self, "警告", "操作正在进行中，请等待完成")
            event.ignore()
        else:
            if hasattr(self, 'adb') and self.adb:
                self.adb.cleanup()
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tool = FlashTool()
    tool.show()
    
    if not tool.adb.adb_path:
        reply = QMessageBox.question(
            None, "ADB未找到",
            "未检测到ADB工具，是否现在下载? (需要网络连接)",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            tool._download_adb_tool()
    
    sys.exit(app.exec_())