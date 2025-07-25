import os
import sys
import time
import threading
import subprocess
import usb.core
import socket
import struct
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QProgressBar, QTextEdit,
                             QFileDialog, QMessageBox, QGroupBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class ADB:
    """改进后的ADB客户端实现"""
    def __init__(self, host='127.0.0.1', port=5037):
        self.host = host
        self.port = port
        self.adb_path = self._find_adb()
        self.server_started = False
        self.last_error = ""
    
    def _find_adb(self):
        """查找ADB工具路径，支持更多平台和路径"""
        paths = [
            "adb",
            "/usr/bin/adb",
            "/usr/local/bin/adb",
            "platform-tools/adb",
            "platform-tools/adb.exe",
            os.path.join(os.environ.get("ANDROID_HOME", ""), "platform-tools", "adb"),
            os.path.join(os.environ.get("ANDROID_SDK_ROOT", ""), "platform-tools", "adb"),
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
        
        self.last_error = "未找到ADB，请检查是否安装在以下路径之一:\n" + "\n".join(paths)
        return None
    
    def _ensure_adb_server(self):
        """确保ADB服务器正在运行，提供更详细的错误信息"""
        if self.server_started:
            return True
            
        if not self.adb_path:
            self.last_error = "ADB工具未找到，请先安装Android平台工具"
            return False
            
        try:
            result = subprocess.run([self.adb_path, "start-server"], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE,
                                 timeout=5)
            if result.returncode != 0:
                self.last_error = f"启动ADB服务失败: {result.stderr.decode('utf-8', 'replace')}"
                return False
                
            time.sleep(1)
            self.server_started = True
            return True
        except Exception as e:
            self.last_error = f"ADB服务启动异常: {str(e)}"
            return False
    
    def _connect(self):
        """连接到ADB服务器，改进错误处理"""
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
        """发送ADB命令，改进错误处理"""
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
        """获取设备列表，改进错误处理"""
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
        """重启设备，支持多种模式"""
        cmd = "reboot:"
        if mode == "bootloader":
            cmd = "reboot:bootloader"
        elif mode == "recovery":
            cmd = "reboot:recovery"
        
        sock = self._send_command(f"host:{cmd}")
        sock.close()
        return True
    
    def fastboot_devices(self):
        """获取fastboot设备列表，改进错误处理"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return []
            
        try:
            fastboot_path = os.path.join(os.path.dirname(self.adb_path), "fastboot")
            if not os.path.exists(fastboot_path):
                fastboot_path = "fastboot"
                
            result = subprocess.run([fastboot_path, "devices"], 
                                  capture_output=True, 
                                  text=True,
                                  timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return [line.split('\t') for line in result.stdout.splitlines() if line]
            else:
                self.last_error = result.stderr
                return []
        except Exception as e:
            self.last_error = str(e)
            return []

class FlashTool(QMainWindow):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str, str)  # 状态类型, 状态消息
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python刷机工具 V0.7")
        self.setGeometry(100, 100, 800, 600)
        
        # 初始化变量
        self.current_mode = None
        self.flashing = False
        self.firmware_path = ""
        self.adb = ADB()
        self.debug_mode = True
        self.adb_available = False
        
        # 连接信号
        self.log_signal.connect(self._log_message)
        self.progress_signal.connect(self._update_progress)
        self.status_signal.connect(self._update_status)
        
        self._init_ui()
        self._start_device_check()
    
    def _init_ui(self):
        # 主窗口
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        # 设备状态组
        status_group = QGroupBox("设备状态")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("等待设备连接...")
        self.status_label.setStyleSheet("font-weight: bold;")
        
        self.mode_label = QLabel("当前模式: 未连接")
        self.device_info = QLabel("")
        
        # ADB状态指示
        self.adb_status = QLabel("ADB: 未检测到")
        self.adb_status.setStyleSheet("color: red;")
        status_layout.addWidget(self.adb_status)
        
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
        """启动设备检测线程，降低检测频率"""
        def check_loop():
            last_adb_state = False
            while True:
                # 先检查ADB状态
                current_adb_state = self.adb._find_adb() is not None
                if current_adb_state != last_adb_state:
                    self.adb_available = current_adb_state
                    self.status_signal.emit("adb", "已就绪" if current_adb_state else "未检测到")
                    last_adb_state = current_adb_state
                
                # 检查设备连接状态
                self._check_device()
                time.sleep(3)  # 降低检测频率
        
        threading.Thread(target=check_loop, daemon=True).start()
    
    def _update_status(self, status_type, message):
        """更新状态显示"""
        if status_type == "adb":
            self.adb_status.setText(f"ADB: {message}")
            self.adb_status.setStyleSheet("color: green;" if "就绪" in message else "color: red;")
    
    def _check_device(self):
        """检测当前连接的设备，改进错误处理"""
        # 检查9008设备
        bootrom_dev = self._check_bootrom_device()
        if bootrom_dev:
            self._set_mode('bootrom', bootrom_dev)
            return
        
        # 检查Fastboot设备
        fastboot_dev = self._check_fastboot_device()
        if fastboot_dev:
            self._set_mode('fastboot', fastboot_dev)
            return
        
        # 检查ADB设备
        adb_dev = self._check_adb_device()
        if adb_dev:
            self._set_mode('adb', adb_dev)
            return
        
        # 没有设备连接
        if self.current_mode is not None:
            self._set_mode(None, None)
    
    def _check_bootrom_device(self):
        """检查9008/Bootrom设备，改进错误处理"""
        try:
            # MediaTek设备
            mtk = usb.core.find(idVendor=0x0e8d, idProduct=0x0003)
            if mtk:
                return {"type": "mtk", "device": mtk}
            
            # 高通设备
            qc = usb.core.find(idVendor=0x05c6, idProduct=0x9008)
            if qc:
                return {"type": "qualcomm", "device": qc}
            
            return None
        except Exception as e:
            if self.debug_mode:
                self.log_signal.emit(f"检查9008设备错误: {str(e)}")
            return None
    
    def _check_fastboot_device(self):
        """检查Fastboot设备，改进错误处理"""
        try:
            devices = self.adb.fastboot_devices()
            if devices:
                return {"id": devices[0][0]}
            return None
        except Exception as e:
            if self.debug_mode:
                self.log_signal.emit(f"检查Fastboot设备错误: {str(e)}")
            return None
    
    def _check_adb_device(self):
        """检查ADB设备，改进错误处理"""
        if not self.adb_available:
            return None
            
        try:
            devices = self.adb.devices()
            if devices and devices[0][1] == 'device':
                return {"id": devices[0][0]}
            return None
        except Exception as e:
            if self.debug_mode:
                self.log_signal.emit(f"检查ADB设备错误: {str(e)}")
            return None
    
    def _set_mode(self, mode, device_info):
        """更新设备模式状态，改进状态显示"""
        if mode == self.current_mode:
            return
            
        self.current_mode = mode
        self.device = device_info
        
        if mode == 'bootrom':
            self.status_label.setText("设备已连接 (9008模式)")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.mode_label.setText("当前模式: 9008/Bootrom")
            dev_type = device_info["type"]
            self.device_info.setText("MediaTek设备" if dev_type == "mtk" else "高通9008设备")
            
            self.bootrom_btn.setEnabled(False)
            self.fastboot_btn.setEnabled(False)
            self.reboot_btn.setEnabled(True)
            self.flash_btn.setEnabled(bool(self.firmware_path))
            
        elif mode == 'fastboot':
            self.status_label.setText("设备已连接 (Fastboot模式)")
            self.status_label.setStyleSheet("color: blue; font-weight: bold;")
            self.mode_label.setText("当前模式: Fastboot")
            self.device_info.setText(f"设备ID: {device_info['id']}")
            
            self.bootrom_btn.setEnabled(True)
            self.fastboot_btn.setEnabled(False)
            self.reboot_btn.setEnabled(True)
            self.flash_btn.setEnabled(bool(self.firmware_path))
            
        elif mode == 'adb':
            self.status_label.setText("设备已连接 (ADB模式)")
            self.status_label.setStyleSheet("color: purple; font-weight: bold;")
            self.mode_label.setText("当前模式: ADB")
            self.device_info.setText(f"设备ID: {device_info['id']}")
            
            self.bootrom_btn.setEnabled(True)
            self.fastboot_btn.setEnabled(True)
            self.reboot_btn.setEnabled(True)
            self.flash_btn.setEnabled(False)
            
        else:  # 无设备连接
            self.status_label.setText("设备未连接")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.mode_label.setText("当前模式: 未连接")
            self.device_info.setText("")
            
            self.bootrom_btn.setEnabled(False)
            self.fastboot_btn.setEnabled(False)
            self.reboot_btn.setEnabled(False)
            self.flash_btn.setEnabled(False)
    
    def _show_adb_help(self):
        """显示ADB安装帮助"""
        help_text = """本工具需要ADB(Android调试桥)支持。
        
安装说明:
Windows:
1. 从 https://developer.android.com/studio/releases/platform-tools 下载平台工具
2. 解压后，将包含adb.exe的目录添加到系统PATH环境变量中

Linux (Debian/Ubuntu):
执行命令: sudo apt install android-tools-adb

Mac:
执行命令: brew install android-platform-tools

安装完成后请重启本程序"""
        
        QMessageBox.information(self, "ADB安装帮助", help_text)
    
    def _enter_bootrom(self):
        """进入9008模式，改进用户反馈"""
        self.log_signal.emit("尝试进入9008模式...")
        self._disable_buttons()
        
        threading.Thread(target=self._execute_enter_bootrom, daemon=True).start()
    
    def _execute_enter_bootrom(self):
        try:
            if self.current_mode == 'adb':
                self.adb.reboot("bootloader")
                time.sleep(5)
                self.log_signal.emit("设备已重启到bootloader，请手动进入9008模式")
            else:
                self.log_signal.emit("请手动操作设备进入9008模式(如短接测试点)")
            
        except Exception as e:
            self.log_signal.emit(f"进入9008模式失败: {str(e)}")
        finally:
            time.sleep(2)
            self._check_device()
    
    def _enter_fastboot(self):
        """进入Fastboot模式，改进用户反馈"""
        self.log_signal.emit("尝试进入Fastboot模式...")
        self._disable_buttons()
        
        threading.Thread(target=self._execute_enter_fastboot, daemon=True).start()
    
    def _execute_enter_fastboot(self):
        try:
            if self.current_mode == 'adb':
                self.adb.reboot("bootloader")
                self.log_signal.emit("已发送Fastboot命令")
            else:
                self.log_signal.emit("无法从当前模式进入Fastboot")
        except Exception as e:
            self.log_signal.emit(f"进入Fastboot失败: {str(e)}")
        finally:
            time.sleep(5)
            self._check_device()
    
    def _reboot_device(self):
        """重启设备，改进用户反馈"""
        self.log_signal.emit("正在重启设备...")
        self._disable_buttons()
        
        threading.Thread(target=self._execute_reboot, daemon=True).start()
    
    def _execute_reboot(self):
        try:
            if self.current_mode == 'fastboot':
                subprocess.run(["fastboot", "reboot"], timeout=10, check=True)
            elif self.current_mode == 'adb':
                self.adb.reboot()
            elif self.current_mode == 'bootrom':
                self.log_signal.emit("9008模式需要手动重启设备")
            else:
                self.log_signal.emit("未知设备模式")
        except Exception as e:
            self.log_signal.emit(f"重启失败: {str(e)}")
        finally:
            time.sleep(5)
            self._check_device()
    
    def _select_firmware(self):
        """选择固件文件，改进文件过滤"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择固件", "", 
            "固件文件 (*.img *.bin *.mbn *.zip);;所有文件 (*)"
        )
        
        if path:
            self.firmware_path = path
            self.file_label.setText(os.path.basename(path))
            self.log_signal.emit(f"已选择固件: {path}")
            if self.current_mode in ('fastboot', 'bootrom'):
                self.flash_btn.setEnabled(True)
    
    def _start_flashing(self):
        """开始刷机，改进确认对话框"""
        if not self.firmware_path:
            QMessageBox.warning(self, "警告", "请先选择固件文件")
            return
            
        reply = QMessageBox.question(
            self, "确认",
            f"确定要刷写 {self.partition_combo.currentText()} 分区吗?\n"
            f"固件文件: {os.path.basename(self.firmware_path)}",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        self.flashing = True
        self._disable_buttons()
        
        partition = self.partition_combo.currentText()
        self.log_signal.emit(f"开始刷机 - 模式: {self.current_mode}, 分区: {partition}")
        
        threading.Thread(target=self._execute_flash, args=(partition,), daemon=True).start()
    
    def _execute_flash(self, partition):
        try:
            if self.current_mode == 'bootrom':
                self._flash_bootrom(partition)
            elif self.current_mode == 'fastboot':
                self._flash_fastboot(partition)
            
            self.log_signal.emit("刷机完成!")
        except Exception as e:
            self.log_signal.emit(f"刷机失败: {str(e)}")
        finally:
            self.flashing = False
            self._check_device()
    
    def _flash_bootrom(self, partition):
        """9008模式刷机，模拟进度"""
        self.log_signal.emit("开始9008模式刷机...")
        for i in range(101):
            time.sleep(0.05)
            self.progress_signal.emit(i)
            if i % 10 == 0:
                self.log_signal.emit(f"9008刷机进度: {i}%")
    
    def _flash_fastboot(self, partition):
        """Fastboot模式刷机，模拟进度"""
        self.log_signal.emit("开始Fastboot模式刷机...")
        for i in range(101):
            time.sleep(0.03)
            self.progress_signal.emit(i)
            if i % 10 == 0:
                self.log_signal.emit(f"Fastboot刷机进度: {i}%")
    
    def _disable_buttons(self):
        """禁用所有操作按钮"""
        self.bootrom_btn.setEnabled(False)
        self.fastboot_btn.setEnabled(False)
        self.reboot_btn.setEnabled(False)
        self.flash_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.help_btn.setEnabled(False)
    
    def _enable_buttons(self):
        """根据当前模式启用按钮"""
        if self.current_mode == 'bootrom':
            self.bootrom_btn.setEnabled(False)
            self.fastboot_btn.setEnabled(False)
            self.reboot_btn.setEnabled(True)
            self.flash_btn.setEnabled(bool(self.firmware_path))
        elif self.current_mode == 'fastboot':
            self.bootrom_btn.setEnabled(True)
            self.fastboot_btn.setEnabled(False)
            self.reboot_btn.setEnabled(True)
            self.flash_btn.setEnabled(bool(self.firmware_path))
        elif self.current_mode == 'adb':
            self.bootrom_btn.setEnabled(True)
            self.fastboot_btn.setEnabled(True)
            self.reboot_btn.setEnabled(True)
            self.flash_btn.setEnabled(False)
        else:
            self.bootrom_btn.setEnabled(False)
            self.fastboot_btn.setEnabled(False)
            self.reboot_btn.setEnabled(False)
            self.flash_btn.setEnabled(False)
        
        self.select_btn.setEnabled(True)
        self.help_btn.setEnabled(True)
    
    def _log_message(self, message):
        """处理日志消息，添加时间戳"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
    
    def _update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
    
    def closeEvent(self, event):
        """关闭事件处理，防止刷机过程中关闭"""
        if self.flashing:
            QMessageBox.warning(self, "警告", "刷机正在进行中，请等待完成")
            event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    tool = FlashTool()
    tool.show()
    sys.exit(app.exec_())