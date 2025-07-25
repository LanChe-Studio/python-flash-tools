import os
import sys
import time
import threading
import subprocess
from enum import Enum
import usb.core
import usb.util
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QProgressBar, QTextEdit,
                             QFileDialog, QMessageBox, QGroupBox, QTabWidget, QGridLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class DeviceMode(Enum):
    DISCONNECTED = 0
    BOOTROM = 1     # 9008模式
    FASTBOOT = 2
    RECOVERY = 3
    ADB = 4

class FlashTool(QMainWindow):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    mode_changed_signal = pyqtSignal(DeviceMode)
    connection_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Flash Tools V0.3")
        self.setGeometry(100, 100, 950, 700)
        
        # 初始化变量
        self.current_mode = DeviceMode.DISCONNECTED
        self.flashing = False
        self.firmware_path = ""
        self.port = ""
        self.device = None
        self.adb_path = self.find_adb()
        
        # 连接信号
        self.log_signal.connect(self.handle_log)
        self.progress_signal.connect(self.update_progress)
        self.mode_changed_signal.connect(self.handle_mode_change)
        self.connection_signal.connect(self.handle_connection_change)
        
        self.init_ui()
        
    def init_ui(self):
        # 主布局
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 顶部状态栏
        status_group = QGroupBox("设备状态与控制")
        status_layout = QGridLayout()
        
        # 第一行: 连接控制
        self.connection_status = QLabel("设备未连接")
        self.connection_status.setStyleSheet("font-weight: bold;")
        
        self.device_info_label = QLabel("无设备信息")
        
        # 第二行: 模式控制和信息
        self.mode_label = QLabel("当前模式: 未连接")
        
        self.bootrom_btn = QPushButton("进入9008模式")
        self.bootrom_btn.clicked.connect(self.enter_bootrom)
        self.bootrom_btn.setEnabled(False)
        self.bootrom_btn.setToolTip("使设备进入MediaTek Bootrom/高通9008下载模式")
        
        self.fastboot_btn = QPushButton("进入Fastboot")
        self.fastboot_btn.clicked.connect(self.enter_fastboot)
        self.fastboot_btn.setEnabled(False)
        self.fastboot_btn.setToolTip("使设备进入Fastboot模式")
        
        self.recovery_btn = QPushButton("进入Recovery")
        self.recovery_btn.clicked.connect(self.enter_recovery)
        self.recovery_btn.setEnabled(False)
        self.recovery_btn.setToolTip("使设备进入Recovery模式")
        
        self.reboot_btn = QPushButton("重启设备")
        self.reboot_btn.clicked.connect(self.reboot_device)
        self.reboot_btn.setEnabled(False)
        self.reboot_btn.setToolTip("重启设备到当前模式")
        
        # 布局安排
        status_layout.addWidget(QLabel("状态:"), 0, 0)
        status_layout.addWidget(self.connection_status, 0, 1, 1, 2)
        status_layout.addWidget(self.device_info_label, 0, 3, 1, 3)
        
        status_layout.addWidget(self.mode_label, 1, 0)
        status_layout.addWidget(self.bootrom_btn, 1, 1)
        status_layout.addWidget(self.fastboot_btn, 1, 2)
        status_layout.addWidget(self.recovery_btn, 1, 3)
        status_layout.addWidget(self.reboot_btn, 1, 4)
        
        status_group.setLayout(status_layout)
        
        # 主选项卡
        self.tabs = QTabWidget()
        
        # 刷机选项卡
        flash_tab = QWidget()
        flash_layout = QVBoxLayout()
        
        # 固件选择
        firmware_group = QGroupBox("固件文件")
        firmware_layout = QHBoxLayout()
        
        self.firmware_path_label = QLabel("未选择文件")
        self.firmware_path_label.setWordWrap(True)
        
        self.select_firmware_btn = QPushButton("选择固件")
        self.select_firmware_btn.clicked.connect(self.select_firmware)
        
        firmware_layout.addWidget(self.firmware_path_label)
        firmware_layout.addWidget(self.select_firmware_btn)
        firmware_group.setLayout(firmware_layout)
        
        # 分区选择
        partition_group = QGroupBox("分区选项")
        partition_layout = QVBoxLayout()
        
        self.partition_combo = QComboBox()
        self.partition_combo.addItems(["全部", "boot", "recovery", "system", "vendor", "userdata", "cache", "vbmeta"])
        
        partition_layout.addWidget(self.partition_combo)
        partition_group.setLayout(partition_layout)
        
        # 刷机控制
        control_group = QGroupBox("刷机控制")
        control_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        self.flash_btn = QPushButton("开始刷机")
        self.flash_btn.setEnabled(False)
        self.flash_btn.clicked.connect(self.start_flashing)
        
        control_layout.addWidget(self.progress_bar)
        control_layout.addWidget(self.flash_btn)
        control_group.setLayout(control_layout)
        
        # 组装刷机选项卡
        flash_layout.addWidget(firmware_group)
        flash_layout.addWidget(partition_group)
        flash_layout.addWidget(control_group)
        flash_layout.addStretch()
        flash_tab.setLayout(flash_layout)
        
        # 日志选项卡
        log_tab = QWidget()
        log_layout = QVBoxLayout()
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("font-family: monospace;")
        
        # 添加清除日志按钮
        log_control_layout = QHBoxLayout()
        self.clear_log_btn = QPushButton("清除日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        log_control_layout.addStretch()
        log_control_layout.addWidget(self.clear_log_btn)
        
        log_layout.addWidget(self.log_output)
        log_layout.addLayout(log_control_layout)
        log_tab.setLayout(log_layout)
        
        # 添加选项卡
        self.tabs.addTab(flash_tab, "刷机")
        self.tabs.addTab(log_tab, "日志")
        
        # 组装主布局
        main_layout.addWidget(status_group)
        main_layout.addWidget(self.tabs)
        main_widget.setLayout(main_layout)
        
        self.setCentralWidget(main_widget)
        
        # 启动设备检测线程
        self.device_check_thread = threading.Thread(target=self.device_check_loop, daemon=True)
        self.device_check_thread.start()
        
        # 更新UI状态
        self.update_ui_state()
    
    def find_adb(self):
        """尝试查找ADB可执行文件路径"""
        possible_paths = [
            "adb",
            "/usr/bin/adb",
            "/usr/local/bin/adb",
            "platform-tools/adb",
            os.path.join(os.getenv("ANDROID_HOME", ""), "platform-tools/adb")
        ]
        
        for path in possible_paths:
            try:
                subprocess.run([path, "version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return path
            except:
                continue
        
        self.log_signal.emit("警告: 未找到ADB可执行文件，ADB功能将不可用")
        return None
    
    def device_check_loop(self):
        """持续检测设备状态的线程"""
        while True:
            try:
                self.check_device_state()
                time.sleep(1)
            except Exception as e:
                self.log_signal.emit(f"设备检测错误: {str(e)}")
                time.sleep(3)
    
    def check_device_state(self):
        """检测当前设备连接状态和模式"""
        # 先检查9008模式
        bootrom_dev = self.check_bootrom_device()
        if bootrom_dev:
            self.device = bootrom_dev
            self.mode_changed_signal.emit(DeviceMode.BOOTROM)
            self.connection_signal.emit(True)
            return
        
        # 检查ADB设备
        adb_dev = self.check_adb_device()
        if adb_dev:
            self.device = adb_dev
            # 检查是ADB模式还是Recovery模式
            if self.is_recovery_mode():
                self.mode_changed_signal.emit(DeviceMode.RECOVERY)
            else:
                self.mode_changed_signal.emit(DeviceMode.ADB)
            self.connection_signal.emit(True)
            return
        
        # 检查Fastboot设备
        fastboot_dev = self.check_fastboot_device()
        if fastboot_dev:
            self.device = fastboot_dev
            self.mode_changed_signal.emit(DeviceMode.FASTBOOT)
            self.connection_signal.emit(True)
            return
        
        # 没有检测到设备
        if self.current_mode != DeviceMode.DISCONNECTED:
            self.mode_changed_signal.emit(DeviceMode.DISCONNECTED)
            self.connection_signal.emit(False)
    
    def check_bootrom_device(self):
        """检查是否连接了9008/Bootrom设备"""
        try:
            # 查找MediaTek Bootrom设备
            mtk_dev = usb.core.find(idVendor=0x0e8d, idProduct=0x0003)
            if mtk_dev:
                return {"type": "mtk", "device": mtk_dev}
            
            # 查找高通9008设备
            qualcomm_dev = usb.core.find(idVendor=0x05c6, idProduct=0x9008)
            if qualcomm_dev:
                return {"type": "qualcomm", "device": qualcomm_dev}
            
            return None
        except Exception as e:
            self.log_signal.emit(f"检查9008设备错误: {str(e)}")
            return None
    
    def check_adb_device(self):
        """检查是否连接了ADB设备"""
        if not self.adb_path:
            return None
            
        try:
            result = subprocess.run([self.adb_path, "devices"], capture_output=True, text=True)
            lines = result.stdout.splitlines()
            if len(lines) > 1 and "device" in lines[1]:
                device_id = lines[1].split("\t")[0]
                return {"type": "adb", "id": device_id}
            return None
        except Exception as e:
            self.log_signal.emit(f"检查ADB设备错误: {str(e)}")
            return None
    
    def check_fastboot_device(self):
        """检查是否连接了Fastboot设备"""
        if not self.adb_path:
            return None
            
        try:
            result = subprocess.run([self.adb_path, "fastboot", "devices"], capture_output=True, text=True)
            lines = result.stdout.splitlines()
            if lines and len(lines[0]) > 0:
                device_id = lines[0].split("\t")[0]
                return {"type": "fastboot", "id": device_id}
            return None
        except Exception as e:
            self.log_signal.emit(f"检查Fastboot设备错误: {str(e)}")
            return None
    
    def is_recovery_mode(self):
        """检查设备是否处于Recovery模式"""
        if not self.adb_path or not self.device or self.device["type"] != "adb":
            return False
            
        try:
            result = subprocess.run([self.adb_path, "-s", self.device["id"], "shell", "getprop", "ro.bootmode"], 
                                  capture_output=True, text=True)
            return "recovery" in result.stdout.lower()
        except:
            return False
    
    def update_ui_state(self):
        # 根据当前模式更新UI状态
        if self.current_mode == DeviceMode.DISCONNECTED:
            self.connection_status.setText("设备未连接")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
            self.mode_label.setText("当前模式: 未连接")
            self.bootrom_btn.setEnabled(False)
            self.fastboot_btn.setEnabled(False)
            self.recovery_btn.setEnabled(False)
            self.reboot_btn.setEnabled(False)
            self.flash_btn.setEnabled(False)
            self.device_info_label.setText("无设备信息")
        else:
            self.connection_status.setText("设备已连接")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
            self.bootrom_btn.setEnabled(self.current_mode != DeviceMode.BOOTROM)
            self.fastboot_btn.setEnabled(self.current_mode not in [DeviceMode.FASTBOOT, DeviceMode.BOOTROM] and self.adb_path is not None)
            self.recovery_btn.setEnabled(self.current_mode not in [DeviceMode.RECOVERY, DeviceMode.BOOTROM] and self.adb_path is not None)
            self.reboot_btn.setEnabled(True)
            self.flash_btn.setEnabled(bool(self.firmware_path))
            
            if self.current_mode == DeviceMode.BOOTROM:
                self.mode_label.setText("当前模式: Bootrom/9008")
                self.mode_label.setStyleSheet("color: purple; font-weight: bold;")
                dev_type = self.device["type"]
                if dev_type == "mtk":
                    self.device_info_label.setText("MediaTek Bootrom设备")
                else:
                    self.device_info_label.setText("高通9008设备")
            elif self.current_mode == DeviceMode.FASTBOOT:
                self.mode_label.setText("当前模式: Fastboot")
                self.mode_label.setStyleSheet("color: blue; font-weight: bold;")
                self.device_info_label.setText(f"设备ID: {self.device['id']}")
            elif self.current_mode == DeviceMode.RECOVERY:
                self.mode_label.setText("当前模式: Recovery")
                self.mode_label.setStyleSheet("color: orange; font-weight: bold;")
                self.device_info_label.setText(f"设备ID: {self.device['id']}")
            elif self.current_mode == DeviceMode.ADB:
                self.mode_label.setText("当前模式: ADB")
                self.mode_label.setStyleSheet("color: green; font-weight: bold;")
                self.device_info_label.setText(f"设备ID: {self.device['id']}")
    
    def enter_bootrom(self):
        """使设备进入9008/Bootrom模式"""
        if self.current_mode == DeviceMode.BOOTROM:
            self.log_signal.emit("设备已经在9008/Bootrom模式")
            return
            
        self.log_signal.emit("尝试使设备进入9008/Bootrom模式...")
        
        # 禁用按钮防止重复操作
        self.bootrom_btn.setEnabled(False)
        self.fastboot_btn.setEnabled(False)
        self.recovery_btn.setEnabled(False)
        self.reboot_btn.setEnabled(False)
        
        # 启动线程执行操作
        threading.Thread(target=self._execute_enter_bootrom, daemon=True).start()
    
    def _execute_enter_bootrom(self):
        try:
            if self.current_mode == DeviceMode.ADB or self.current_mode == DeviceMode.RECOVERY:
                # 通过ADB重启到Bootrom
                if self.adb_path:
                    subprocess.run([self.adb_path, "-s", self.device["id"], "reboot", "bootloader"], 
                                 timeout=10, check=True)
                    time.sleep(2)
                    # 然后尝试触发Bootrom模式
                    # 这里需要设备特定的方法，如短接或特殊命令
                    self.log_signal.emit("请手动操作设备进入9008模式(如短接测试点)")
            elif self.current_mode == DeviceMode.FASTBOOT:
                # Fastboot模式下可以直接尝试触发Bootrom
                self.log_signal.emit("请手动操作设备进入9008模式(如短接测试点)")
            
            time.sleep(5)  # 等待设备进入模式
            
        except Exception as e:
            self.log_signal.emit(f"进入9008模式失败: {str(e)}")
        finally:
            self.check_device_state()
    
    def enter_fastboot(self):
        """使设备进入Fastboot模式"""
        if self.current_mode == DeviceMode.FASTBOOT:
            self.log_signal.emit("设备已经在Fastboot模式")
            return
        if self.current_mode == DeviceMode.BOOTROM:
            self.log_signal.emit("无法从9008模式直接进入Fastboot")
            return
            
        self.log_signal.emit("尝试使设备进入Fastboot模式...")
        
        # 禁用按钮防止重复操作
        self.bootrom_btn.setEnabled(False)
        self.fastboot_btn.setEnabled(False)
        self.recovery_btn.setEnabled(False)
        self.reboot_btn.setEnabled(False)
        
        # 启动线程执行操作
        threading.Thread(target=self._execute_enter_fastboot, daemon=True).start()
    
    def _execute_enter_fastboot(self):
        try:
            if self.current_mode == DeviceMode.ADB or self.current_mode == DeviceMode.RECOVERY:
                if self.adb_path:
                    subprocess.run([self.adb_path, "-s", self.device["id"], "reboot", "bootloader"], 
                                 timeout=10, check=True)
                    self.log_signal.emit("已发送Fastboot启动命令")
            
            time.sleep(5)  # 等待设备进入模式
            
        except Exception as e:
            self.log_signal.emit(f"进入Fastboot模式失败: {str(e)}")
        finally:
            self.check_device_state()
    
    def enter_recovery(self):
        """使设备进入Recovery模式"""
        if self.current_mode == DeviceMode.RECOVERY:
            self.log_signal.emit("设备已经在Recovery模式")
            return
        if self.current_mode == DeviceMode.BOOTROM:
            self.log_signal.emit("无法从9008模式直接进入Recovery")
            return
            
        self.log_signal.emit("尝试使设备进入Recovery模式...")
        
        # 禁用按钮防止重复操作
        self.bootrom_btn.setEnabled(False)
        self.fastboot_btn.setEnabled(False)
        self.recovery_btn.setEnabled(False)
        self.reboot_btn.setEnabled(False)
        
        # 启动线程执行操作
        threading.Thread(target=self._execute_enter_recovery, daemon=True).start()
    
    def _execute_enter_recovery(self):
        try:
            if self.current_mode == DeviceMode.ADB:
                if self.adb_path:
                    subprocess.run([self.adb_path, "-s", self.device["id"], "reboot", "recovery"], 
                                 timeout=10, check=True)
                    self.log_signal.emit("已发送Recovery启动命令")
            elif self.current_mode == DeviceMode.FASTBOOT:
                if self.adb_path:
                    subprocess.run([self.adb_path, "-s", self.device["id"], "fastboot", "reboot-recovery"], 
                                 timeout=10, check=True)
                    self.log_signal.emit("已发送Recovery启动命令")
            
            time.sleep(5)  # 等待设备进入模式
            
        except Exception as e:
            self.log_signal.emit(f"进入Recovery模式失败: {str(e)}")
        finally:
            self.check_device_state()
    
    def reboot_device(self):
        """重启设备"""
        self.log_signal.emit("正在重启设备...")
        
        # 禁用按钮防止重复操作
        self.bootrom_btn.setEnabled(False)
        self.fastboot_btn.setEnabled(False)
        self.recovery_btn.setEnabled(False)
        self.reboot_btn.setEnabled(False)
        
        # 启动线程执行操作
        threading.Thread(target=self._execute_reboot, daemon=True).start()
    
    def _execute_reboot(self):
        try:
            if self.current_mode == DeviceMode.ADB:
                if self.adb_path:
                    subprocess.run([self.adb_path, "-s", self.device["id"], "reboot"], 
                                 timeout=10, check=True)
            elif self.current_mode == DeviceMode.FASTBOOT:
                if self.adb_path:
                    subprocess.run([self.adb_path, "-s", self.device["id"], "fastboot", "reboot"], 
                                 timeout=10, check=True)
            elif self.current_mode == DeviceMode.RECOVERY:
                if self.adb_path:
                    subprocess.run([self.adb_path, "-s", self.device["id"], "reboot"], 
                                 timeout=10, check=True)
            elif self.current_mode == DeviceMode.BOOTROM:
                self.log_signal.emit("9008模式需要手动重启设备")
            
            time.sleep(5)  # 等待设备重启
            
        except Exception as e:
            self.log_signal.emit(f"重启设备失败: {str(e)}")
        finally:
            self.check_device_state()
    
    def select_firmware(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择固件文件", "", 
            "固件文件 (*.bin *.img *.zip *.mbn);;所有文件 (*)", 
            options=options
        )
        
        if file_path:
            self.firmware_path = file_path
            self.firmware_path_label.setText(os.path.basename(file_path))
            self.log_signal.emit(f"已选择固件: {file_path}")
            if self.current_mode != DeviceMode.DISCONNECTED:
                self.flash_btn.setEnabled(True)
    
    def start_flashing(self):
        if not self.firmware_path:
            QMessageBox.warning(self, "警告", "请先选择固件文件")
            return
            
        if self.current_mode == DeviceMode.DISCONNECTED:
            QMessageBox.warning(self, "警告", "请先连接设备")
            return
            
        # 确认对话框
        reply = QMessageBox.question(
            self, '确认',
            f"确定要刷写 {self.partition_combo.currentText()} 分区吗?\n文件: {os.path.basename(self.firmware_path)}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        self.flashing = True
        self.flash_btn.setEnabled(False)
        self.bootrom_btn.setEnabled(False)
        self.fastboot_btn.setEnabled(False)
        self.recovery_btn.setEnabled(False)
        self.reboot_btn.setEnabled(False)
        
        partition = self.partition_combo.currentText()
        self.log_signal.emit(f"开始刷机 - 模式: {self.current_mode.name}, 分区: {partition}, 文件: {self.firmware_path}")
        
        # 启动刷机线程
        threading.Thread(target=self._execute_flash, args=(partition,), daemon=True).start()
    
    def _execute_flash(self, partition):
        try:
            if self.current_mode == DeviceMode.BOOTROM:
                self._flash_in_bootrom(partition)
            elif self.current_mode == DeviceMode.FASTBOOT:
                self._flash_in_fastboot(partition)
            elif self.current_mode in [DeviceMode.ADB, DeviceMode.RECOVERY]:
                self._flash_in_adb(partition)
            
            self.log_signal.emit(f"刷机完成 - 分区: {partition}")
        except Exception as e:
            self.log_signal.emit(f"刷机失败: {str(e)}")
        finally:
            self.flashing = False
            self.check_device_state()
    
    def _flash_in_bootrom(self, partition):
        """在9008模式下刷机"""
        total_steps = 100
        for i in range(total_steps + 1):
            time.sleep(0.05)  # 模拟刷机耗时
            progress = int((i / total_steps) * 100)
            self.progress_signal.emit(progress)
            
            if i % 10 == 0:
                self.log_signal.emit(f"9008刷机进度: {progress}%")
                
        # 实际实现中这里应该调用9008协议刷机代码
        # 例如使用libusb与设备通信
    
    def _flash_in_fastboot(self, partition):
        """在Fastboot模式下刷机"""
        if not self.adb_path:
            raise Exception("ADB工具未找到")
            
        total_steps = 100
        for i in range(total_steps + 1):
            time.sleep(0.03)  # 模拟刷机耗时
            progress = int((i / total_steps) * 100)
            self.progress_signal.emit(progress)
            
            if i % 10 == 0:
                self.log_signal.emit(f"Fastboot刷机进度: {progress}%")
                
        # 实际实现中这里应该调用fastboot命令
        # 例如: subprocess.run([self.adb_path, "fastboot", "flash", partition, self.firmware_path])
    
    def _flash_in_adb(self, partition):
        """在ADB/Recovery模式下刷机"""
        if not self.adb_path:
            raise Exception("ADB工具未找到")
            
        total_steps = 100
        for i in range(total_steps + 1):
            time.sleep(0.04)  # 模拟刷机耗时
            progress = int((i / total_steps) * 100)
            self.progress_signal.emit(progress)
            
            if i % 10 == 0:
                self.log_signal.emit(f"ADB刷机进度: {progress}%")
                
        # 实际实现中这里应该调用adb命令
        # 例如: subprocess.run([self.adb_path, "push", self.firmware_path, f"/sdcard/{partition}.img"])
    
    def clear_log(self):
        self.log_output.clear()
    
    def handle_log(self, message):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_message = f"[{timestamp}] {message}"
        self.log_output.append(log_message)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def handle_mode_change(self, new_mode):
        self.current_mode = new_mode
        self.update_ui_state()
    
    def handle_connection_change(self, connected):
        if not connected:
            self.current_mode = DeviceMode.DISCONNECTED
            self.device = None
        self.update_ui_state()
    
    def closeEvent(self, event):
        if self.flashing:
            reply = QMessageBox.question(
                self, '警告',
                "刷机正在进行中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
                
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    tool = FlashTool()
    tool.show()
    sys.exit(app.exec_())