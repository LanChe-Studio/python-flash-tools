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
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QProgressBar, QTextEdit,
                             QFileDialog, QMessageBox, QGroupBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

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

class FlashTool(QMainWindow):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str, str)  # 状态类型, 状态消息
    mode_signal = pyqtSignal(str, str)    # 模式, 设备ID
    reboot_signal = pyqtSignal(str)       # 重启状态信号
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Flash Tools V0.8")
        self.setGeometry(100, 100, 800, 600)
        
        # 初始化变量
        self.current_mode = None
        self.device_id = None
        self.flashing = False
        self.firmware_path = ""
        self.adb = ADB()
        self.debug_mode = True
        self.adb_available = False
        
        # 连接信号
        self.log_signal.connect(self._log_message)
        self.progress_signal.connect(self._update_progress)
        self.status_signal.connect(self._update_status)
        self.mode_signal.connect(self._handle_mode_change)
        self.reboot_signal.connect(self._handle_reboot_status)
        
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
        
        # ADB帮助按钮
        self.help_btn = QPushButton("ADB安装帮助")
        self.help_btn.clicked.connect(self._show_adb_help)
        btn_layout.addWidget(self.help_btn)
        
        # 下载ADB按钮
        self.download_btn = QPushButton("下载ADB工具")
        self.download_btn.clicked.connect(self._download_adb_tool)
        btn_layout.addWidget(self.download_btn)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.mode_label)
        status_layout.addWidget(self.device_info)
        status_layout.addLayout(btn_layout)
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
        flash_group.setLayout(flash_layout)
        
        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("font-family: monospace;")
        
        # 组装主界面
        layout.addWidget(status_group)
        layout.addWidget(flash_group)
        layout.addWidget(self.log_output)
        main_widget.setLayout(layout)
        
        self.setCentralWidget(main_widget)
    
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
                if self._check_bootrom_device():
                    self.mode_signal.emit("bootrom", "9008设备")
                    return
            except Exception as e:
                self.log_signal.emit(f"Bootrom设备检测错误: {str(e)}")
            
            # 没有检测到设备
            self.mode_signal.emit(None, None)
            
        except Exception as e:
            self.log_signal.emit(f"设备检测错误: {str(e)}")
            self.mode_signal.emit(None, None)
    
    def _check_bootrom_device(self):
        """检查9008模式设备"""
        try:
            devices = usb.core.find(find_all=True)
            for device in devices:
                if device.idVendor == 0x05c6 and device.idProduct == 0x9008:
                    return True
            return False
        except Exception as e:
            self.log_signal.emit(f"USB设备检测错误: {str(e)}")
            return False
    
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
            self.device_info.setText("设备已进入EDL模式")
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
            self.adb.reboot("bootloader")
            self.log_signal.emit("设备正在重启到bootloader...")
            
            time.sleep(5)
            
            fastboot_devices = self.adb.fastboot_devices()
            if fastboot_devices:
                self.log_signal.emit("设备已进入fastboot模式")
            else:
                self.log_signal.emit("未能检测到fastboot设备")
                
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
    
    def _flash_bootrom(self):
        """在9008模式下刷机"""
        self.log_signal.emit("开始在9008模式下刷机...")
        
        for i in range(1, 101):
            time.sleep(0.1)
            self.progress_signal.emit(i)
            self.log_signal.emit(f"刷机进度: {i}%")
    
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
        self.log_output.append(message)
        self.log_output.ensureCursorVisible()
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
        self.select_btn.setEnabled(False)
        self.help_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
    
    def _enable_buttons(self):
        """根据当前模式启用适当的按钮"""
        self.bootrom_btn.setEnabled(self.current_mode == "adb")
        self.fastboot_btn.setEnabled(self.current_mode == "adb")
        self.reboot_btn.setEnabled(self.current_mode is not None)
        self.flash_btn.setEnabled(self.current_mode is not None and bool(self.firmware_path))
        self.select_btn.setEnabled(True)
        self.help_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.flashing:
            QMessageBox.warning(self, "警告", "刷机正在进行中，请等待完成")
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