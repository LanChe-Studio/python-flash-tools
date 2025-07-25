import os
import sys
import time
import threading
import subprocess
import usb.core
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QProgressBar, QTextEdit,
                             QFileDialog, QMessageBox, QGroupBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class FlashTool(QMainWindow):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Flash Tools V0.4")
        self.setGeometry(100, 100, 800, 600)
        
        # 初始化变量
        self.current_mode = None  # 'fastboot', 'bootrom', None
        self.flashing = False
        self.firmware_path = ""
        self.adb_path = self._find_adb()
        
        # 连接信号
        self.log_signal.connect(self._log_message)
        self.progress_signal.connect(self._update_progress)
        
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
    
    def _find_adb(self):
        """查找ADB工具路径"""
        paths = ["adb", "/usr/bin/adb", "platform-tools/adb.exe"]
        for path in paths:
            try:
                subprocess.run([path, "version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return path
            except:
                continue
        self.log_signal.emit("警告: 未找到ADB工具，部分功能受限")
        return None
    
    def _start_device_check(self):
        """启动设备检测线程"""
        def check_loop():
            while True:
                self._check_device()
                time.sleep(1)
        
        threading.Thread(target=check_loop, daemon=True).start()
    
    def _check_device(self):
        """检测当前连接的设备"""
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
        
        # 没有设备连接
        if self.current_mode is not None:
            self._set_mode(None, None)
    
    def _check_bootrom_device(self):
        """检查9008/Bootrom设备"""
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
            self.log_signal.emit(f"检查9008设备错误: {str(e)}")
            return None
    
    def _check_fastboot_device(self):
        """检查Fastboot设备"""
        if not self.adb_path:
            return None
            
        try:
            result = subprocess.run([self.adb_path, "fastboot", "devices"], 
                                  capture_output=True, text=True, timeout=5)
            if result.stdout.strip():
                device_id = result.stdout.split()[0]
                return {"id": device_id}
            return None
        except Exception as e:
            self.log_signal.emit(f"检查Fastboot设备错误: {str(e)}")
            return None
    
    def _set_mode(self, mode, device_info):
        """更新设备模式状态"""
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
            
        else:  # 无设备连接
            self.status_label.setText("设备未连接")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.mode_label.setText("当前模式: 未连接")
            self.device_info.setText("")
            
            self.bootrom_btn.setEnabled(False)
            self.fastboot_btn.setEnabled(False)
            self.reboot_btn.setEnabled(False)
            self.flash_btn.setEnabled(False)
    
    def _enter_bootrom(self):
        """进入9008模式"""
        if not self.adb_path:
            self.log_signal.emit("错误: 未找到ADB工具")
            return
            
        self.log_signal.emit("尝试进入9008模式...")
        self._disable_buttons()
        
        threading.Thread(target=self._execute_enter_bootrom, daemon=True).start()
    
    def _execute_enter_bootrom(self):
        try:
            # 先进入fastboot
            subprocess.run([self.adb_path, "reboot", "bootloader"], timeout=10, check=True)
            time.sleep(5)
            
            # 然后尝试触发9008模式 (需要设备特定方法)
            self.log_signal.emit("请手动操作设备进入9008模式(如短接测试点)")
            
        except Exception as e:
            self.log_signal.emit(f"进入9008模式失败: {str(e)}")
        finally:
            time.sleep(2)
            self._check_device()
    
    def _enter_fastboot(self):
        """进入Fastboot模式"""
        if not self.adb_path:
            self.log_signal.emit("错误: 未找到ADB工具")
            return
            
        self.log_signal.emit("尝试进入Fastboot模式...")
        self._disable_buttons()
        
        threading.Thread(target=self._execute_enter_fastboot, daemon=True).start()
    
    def _execute_enter_fastboot(self):
        try:
            subprocess.run([self.adb_path, "reboot", "bootloader"], timeout=10, check=True)
            self.log_signal.emit("已发送Fastboot命令")
        except Exception as e:
            self.log_signal.emit(f"进入Fastboot失败: {str(e)}")
        finally:
            time.sleep(5)
            self._check_device()
    
    def _reboot_device(self):
        """重启设备"""
        self.log_signal.emit("正在重启设备...")
        self._disable_buttons()
        
        threading.Thread(target=self._execute_reboot, daemon=True).start()
    
    def _execute_reboot(self):
        try:
            if self.current_mode == 'fastboot' and self.adb_path:
                subprocess.run([self.adb_path, "fastboot", "reboot"], timeout=10, check=True)
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
        """选择固件文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择固件", "", 
            "固件文件 (*.img *.bin *.mbn);;所有文件 (*)"
        )
        
        if path:
            self.firmware_path = path
            self.file_label.setText(os.path.basename(path))
            self.log_signal.emit(f"已选择固件: {path}")
            if self.current_mode:
                self.flash_btn.setEnabled(True)
    
    def _start_flashing(self):
        """开始刷机"""
        if not self.firmware_path:
            QMessageBox.warning(self, "警告", "请先选择固件文件")
            return
            
        reply = QMessageBox.question(
            self, "确认",
            f"确定要刷写 {self.partition_combo.currentText()} 分区吗?",
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
        """9008模式刷机"""
        # 这里应该实现实际的9008协议通信
        # 以下是模拟过程
        for i in range(101):
            time.sleep(0.05)
            self.progress_signal.emit(i)
            if i % 10 == 0:
                self.log_signal.emit(f"9008刷机进度: {i}%")
    
    def _flash_fastboot(self, partition):
        """Fastboot模式刷机"""
        if not self.adb_path:
            raise Exception("ADB工具未找到")
            
        # 这里应该调用实际的fastboot命令
        # 以下是模拟过程
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
    
    def _log_message(self, message):
        """处理日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
    
    def _update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
    
    def closeEvent(self, event):
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