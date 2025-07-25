import os
import sys
import time
import threading
from enum import Enum
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QProgressBar, QTextEdit,
                             QFileDialog, QMessageBox, QGroupBox, QTabWidget, QGridLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class DeviceMode(Enum):
    DISCONNECTED = 0
    BOOTROM = 1     # 9008模式
    FASTBOOT = 2
    TWRP = 3
    ADB = 4

class FlashTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Flash Tools V0.2")
        self.setGeometry(100, 100, 900, 650)
        
        # 初始化变量
        self.current_mode = DeviceMode.DISCONNECTED
        self.flashing = False
        self.firmware_path = ""
        self.port = ""
        
        self.init_ui()
        
    def init_ui(self):
        # 主布局
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 顶部状态栏
        status_group = QGroupBox("设备状态")
        status_layout = QGridLayout()
        
        # 第一行: 连接控制
        self.connection_status = QLabel("设备未连接")
        self.connection_status.setStyleSheet("font-weight: bold;")
        
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)
        
        self.refresh_btn = QPushButton("刷新端口")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        
        self.connect_btn = QPushButton("连接设备")
        self.connect_btn.clicked.connect(self.toggle_connection)
        
        status_layout.addWidget(QLabel("端口:"), 0, 0)
        status_layout.addWidget(self.port_combo, 0, 1)
        status_layout.addWidget(self.refresh_btn, 0, 2)
        status_layout.addWidget(self.connect_btn, 0, 3)
        status_layout.addWidget(self.connection_status, 0, 4, 1, 2)
        
        # 第二行: 模式切换按钮
        self.mode_label = QLabel("当前模式: 未连接")
        
        self.bootrom_btn = QPushButton("进入Bootrom/9008")
        self.bootrom_btn.clicked.connect(lambda: self.switch_mode(DeviceMode.BOOTROM))
        self.bootrom_btn.setEnabled(False)
        
        self.fastboot_btn = QPushButton("进入Fastboot")
        self.fastboot_btn.clicked.connect(lambda: self.switch_mode(DeviceMode.FASTBOOT))
        self.fastboot_btn.setEnabled(False)
        
        self.twrp_btn = QPushButton("进入TWRP")
        self.twrp_btn.clicked.connect(lambda: self.switch_mode(DeviceMode.TWRP))
        self.twrp_btn.setEnabled(False)
        
        self.reboot_btn = QPushButton("重启设备")
        self.reboot_btn.clicked.connect(self.reboot_device)
        self.reboot_btn.setEnabled(False)
        
        status_layout.addWidget(self.mode_label, 1, 0)
        status_layout.addWidget(self.bootrom_btn, 1, 1)
        status_layout.addWidget(self.fastboot_btn, 1, 2)
        status_layout.addWidget(self.twrp_btn, 1, 3)
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
        self.partition_combo.addItems(["全部", "boot", "recovery", "system", "vendor", "userdata", "cache"])
        
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
        
        # 初始化端口
        self.refresh_ports()
        
        # 更新UI状态
        self.update_ui_state()
    
    def update_ui_state(self):
        # 根据当前模式更新UI状态
        if self.current_mode == DeviceMode.DISCONNECTED:
            self.connection_status.setText("设备未连接")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
            self.mode_label.setText("当前模式: 未连接")
            self.bootrom_btn.setEnabled(False)
            self.fastboot_btn.setEnabled(False)
            self.twrp_btn.setEnabled(False)
            self.reboot_btn.setEnabled(False)
            self.flash_btn.setEnabled(False)
        else:
            self.connection_status.setText("设备已连接")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
            self.bootrom_btn.setEnabled(True)
            self.fastboot_btn.setEnabled(True)
            self.twrp_btn.setEnabled(True)
            self.reboot_btn.setEnabled(True)
            self.flash_btn.setEnabled(bool(self.firmware_path))
            
            if self.current_mode == DeviceMode.BOOTROM:
                self.mode_label.setText("当前模式: Bootrom/9008")
                self.mode_label.setStyleSheet("color: purple; font-weight: bold;")
            elif self.current_mode == DeviceMode.FASTBOOT:
                self.mode_label.setText("当前模式: Fastboot")
                self.mode_label.setStyleSheet("color: blue; font-weight: bold;")
            elif self.current_mode == DeviceMode.TWRP:
                self.mode_label.setText("当前模式: TWRP")
                self.mode_label.setStyleSheet("color: orange; font-weight: bold;")
            elif self.current_mode == DeviceMode.ADB:
                self.mode_label.setText("当前模式: ADB")
                self.mode_label.setStyleSheet("color: green; font-weight: bold;")
    
    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)
        
        if not ports:
            self.log("没有检测到可用端口")
        else:
            self.log(f"检测到 {len(ports)} 个可用端口")
    
    def toggle_connection(self):
        if self.current_mode == DeviceMode.DISCONNECTED:
            self.connect_device()
        else:
            self.disconnect_device()
    
    def connect_device(self):
        if self.port_combo.count() == 0:
            self.log("错误: 没有可用的端口")
            return
            
        self.port = self.port_combo.currentText()
        self.log(f"尝试连接设备: {self.port}")
        self.connect_btn.setEnabled(False)
        
        # 模拟连接过程
        threading.Thread(target=self._simulate_connect, daemon=True).start()
    
    def _simulate_connect(self):
        time.sleep(2)  # 模拟连接耗时
        
        # 随机选择一种模式模拟连接
        import random
        modes = [DeviceMode.BOOTROM, DeviceMode.FASTBOOT, DeviceMode.TWRP, DeviceMode.ADB]
        self.current_mode = random.choice(modes)
        
        self.connect_btn.setText("断开连接")
        self.connect_btn.setEnabled(True)
        self.log(f"设备连接成功 - 当前模式: {self.current_mode.name}")
        self.update_ui_state()
        
    def disconnect_device(self):
        self.current_mode = DeviceMode.DISCONNECTED
        self.connect_btn.setText("连接设备")
        self.log("设备已断开")
        self.update_ui_state()
    
    def switch_mode(self, target_mode):
        if self.current_mode == target_mode:
            self.log(f"设备已经在 {target_mode.name} 模式")
            return
            
        self.log(f"尝试切换到 {target_mode.name} 模式...")
        
        # 禁用所有按钮防止重复操作
        self.bootrom_btn.setEnabled(False)
        self.fastboot_btn.setEnabled(False)
        self.twrp_btn.setEnabled(False)
        self.reboot_btn.setEnabled(False)
        
        # 模拟模式切换
        threading.Thread(target=self._simulate_mode_switch, args=(target_mode,), daemon=True).start()
    
    def _simulate_mode_switch(self, target_mode):
        time.sleep(1.5)  # 模拟模式切换耗时
        
        self.current_mode = target_mode
        self.log(f"已成功切换到 {target_mode.name} 模式")
        self.update_ui_state()
    
    def reboot_device(self):
        self.log("正在重启设备...")
        
        # 禁用按钮防止重复操作
        self.bootrom_btn.setEnabled(False)
        self.fastboot_btn.setEnabled(False)
        self.twrp_btn.setEnabled(False)
        self.reboot_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        
        # 模拟重启过程
        threading.Thread(target=self._simulate_reboot, daemon=True).start()
    
    def _simulate_reboot(self):
        time.sleep(2)  # 模拟重启耗时
        
        # 随机决定重启后进入什么模式
        import random
        modes = [DeviceMode.BOOTROM, DeviceMode.FASTBOOT, DeviceMode.TWRP, DeviceMode.ADB]
        self.current_mode = random.choice(modes)
        
        self.log(f"设备重启完成 - 当前模式: {self.current_mode.name}")
        self.update_ui_state()
    
    def select_firmware(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择固件文件", "", 
            "固件文件 (*.bin *.img *.zip);;所有文件 (*)", 
            options=options
        )
        
        if file_path:
            self.firmware_path = file_path
            self.firmware_path_label.setText(os.path.basename(file_path))
            self.log(f"已选择固件: {file_path}")
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
        self.connect_btn.setEnabled(False)
        self.bootrom_btn.setEnabled(False)
        self.fastboot_btn.setEnabled(False)
        self.twrp_btn.setEnabled(False)
        self.reboot_btn.setEnabled(False)
        
        partition = self.partition_combo.currentText()
        self.log(f"开始刷机 - 模式: {self.current_mode.name}, 分区: {partition}, 文件: {self.firmware_path}")
        
        # 模拟刷机过程
        threading.Thread(target=self._simulate_flash, args=(partition,), daemon=True).start()
    
    def _simulate_flash(self, partition):
        total_steps = 100
        for i in range(total_steps + 1):
            time.sleep(0.03)  # 模拟刷机耗时
            progress = int((i / total_steps) * 100)
            self.progress_bar.setValue(progress)
            
            if i % 10 == 0:
                self.log(f"刷机进度: {progress}%")
                
        self.log(f"刷机完成 - 分区: {partition}")
        self.flashing = False
        self.update_ui_state()
    
    def clear_log(self):
        self.log_output.clear()
    
    def log(self, message):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_message = f"[{timestamp}] {message}"
        self.log_output.append(log_message)
        # 自动滚动到底部
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
    
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
                
        if self.current_mode != DeviceMode.DISCONNECTED:
            self.disconnect_device()
            
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    tool = FlashTool()
    tool.show()
    sys.exit(app.exec_())