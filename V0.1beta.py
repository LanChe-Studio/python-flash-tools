import os
import sys
import time
import threading
from enum import Enum
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QProgressBar, QTextEdit,
                             QFileDialog, QMessageBox, QGroupBox, QTabWidget)
from PyQt5.QtCore import Qt, pyqtSignal, QObject


class FlashTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Flash Tools V0.1")
        self.setGeometry(100, 100, 800, 600)
        
        # 初始化变量
        self.connected = False
        self.flashing = False
        self.firmware_path = ""
        self.port = ""
        
        self.init_ui()
        
    def init_ui(self):
        # 主布局
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 顶部状态栏
        status_group = QGroupBox("状态")
        status_layout = QHBoxLayout()
        
        self.connection_status = QLabel("设备未连接")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)
        
        self.refresh_btn = QPushButton("刷新端口")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        
        self.connect_btn = QPushButton("连接设备")
        self.connect_btn.clicked.connect(self.toggle_connection)
        
        status_layout.addWidget(QLabel("端口:"))
        status_layout.addWidget(self.port_combo)
        status_layout.addWidget(self.refresh_btn)
        status_layout.addWidget(self.connect_btn)
        status_layout.addStretch()
        status_layout.addWidget(self.connection_status)
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
        self.partition_combo.addItems(["全部", "boot", "recovery", "system", "userdata", "cache"])
        
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
        
        log_layout.addWidget(self.log_output)
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
        
    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)
        
    def toggle_connection(self):
        if not self.connected:
            self.connect_device()
        else:
            self.disconnect_device()
    
    def connect_device(self):
        if self.port_combo.count() == 0:
            self.log("没有可用的端口")
            return
            
        self.port = self.port_combo.currentText()
        
        # 模拟连接过程
        self.log(f"尝试连接设备: {self.port}")
        self.connect_btn.setEnabled(False)
        
        # 模拟连接耗时操作
        threading.Thread(target=self._simulate_connect, daemon=True).start()
    
    def _simulate_connect(self):
        time.sleep(2)  # 模拟连接耗时
        
        # 模拟连接成功
        self.connected = True
        self.connect_btn.setText("断开连接")
        self.connect_btn.setEnabled(True)
        self.connection_status.setText("设备已连接")
        self.connection_status.setStyleSheet("color: green; font-weight: bold;")
        self.flash_btn.setEnabled(True)
        self.log("设备连接成功")
        
    def disconnect_device(self):
        self.connected = False
        self.connect_btn.setText("连接设备")
        self.connection_status.setText("设备未连接")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        self.flash_btn.setEnabled(False)
        self.log("设备已断开")
    
    def select_firmware(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择固件文件", "", 
            "固件文件 (*.bin *.img);;所有文件 (*)", 
            options=options
        )
        
        if file_path:
            self.firmware_path = file_path
            self.firmware_path_label.setText(file_path)
            self.log(f"已选择固件: {file_path}")
    
    def start_flashing(self):
        if not self.firmware_path:
            QMessageBox.warning(self, "警告", "请先选择固件文件")
            return
            
        if not self.connected:
            QMessageBox.warning(self, "警告", "请先连接设备")
            return
            
        self.flashing = True
        self.flash_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        
        partition = self.partition_combo.currentText()
        self.log(f"开始刷机 - 分区: {partition}, 文件: {self.firmware_path}")
        
        # 模拟刷机过程
        threading.Thread(target=self._simulate_flash, args=(partition,), daemon=True).start()
    
    def _simulate_flash(self, partition):
        total_steps = 100
        for i in range(total_steps + 1):
            time.sleep(0.05)  # 模拟刷机耗时
            progress = int((i / total_steps) * 100)
            self.progress_bar.setValue(progress)
            
            if i % 10 == 0:
                self.log(f"刷机进度: {progress}%")
                
        self.log(f"刷机完成 - 分区: {partition}")
        self.flashing = False
        self.flash_btn.setEnabled(True)
        self.connect_btn.setEnabled(True)
    
    def log(self, message):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_message = f"[{timestamp}] {message}"
        self.log_output.append(log_message)
    
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
                
        if self.connected:
            self.disconnect_device()
            
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    tool = FlashTool()
    tool.show()
    sys.exit(app.exec_())