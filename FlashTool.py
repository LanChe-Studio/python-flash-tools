import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile

from PySide6.QtCore import Qt, Signal, QSettings, QTimer, QThread
from PySide6.QtGui import QIcon, QTextCursor, QFont, QColor, QPalette
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QComboBox, QProgressBar,
                               QFileDialog, QMessageBox, QGroupBox, QDialog,
                               QTabWidget, QTextEdit, QLineEdit, QPlainTextEdit, QCheckBox,
                               QGridLayout, QListWidget,
                               QStackedWidget, QSplitter, QListWidgetItem)

from Dialogs import DebugLogDialog, DownloadDialog
from Dialogs import SettingsDialog
from FlashingToolbox import FlashingToolbox
from Tool import PlatformTools, MTKClientTool


class FlashTool(QMainWindow):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    status_signal = Signal(str, str)
    mode_signal = Signal(str, str)
    mtk_device_signal = Signal(str)
    mtk_command_output = Signal(str)  # 使用str而不是QTextCursor
    splash_message = Signal(str)

    def __init__(self, splash=None):
        super().__init__()
        self.splash = splash

        self.setWindowTitle("Python Flash Tools V1.9")  # 更新版本号到1.9
        self.setGeometry(100, 100, 900, 600)

        # 初始化变量
        self.current_mode = None
        self.device_id = None
        self.flashing_toolbox = FlashingToolbox(PlatformTools(), MTKClientTool())
        self.debug_log_dialog = None
        self.firmware_path = ""
        self.backup_path = ""
        self.operation_in_progress = False
        self.settings_dialog = None
        self.settings = QSettings("PythonFlashTools", "FlashTool")
        self.running = True  # 设备检测线程运行标志
        self.mtk_detecting = False  # MTK设备检测标志

        # 添加缺失的属性
        self.xiaomi_flash_path = ""
        self.bootrom_flash_path = ""
        self.partition_img_path = ""
        self.mtk_process = None  # 存储当前运行的MTKClient进程
        self._last_update_time = time.time()

        # 连接信号
        self.log_signal.connect(self._log_message)
        self.progress_signal.connect(self._update_progress)
        self.status_signal.connect(self._update_status)
        self.mode_signal.connect(self._handle_mode_change)
        self.mtk_device_signal.connect(self._handle_mtk_device)
        self.mtk_command_output.connect(self._update_mtk_log)
        self.splash_message.connect(self._update_splash_message)

        # 初始化UI
        self._init_ui()

        # 启动设备检测线程
        self._start_device_check()

        # 应用主题
        self._apply_theme()

        # 检查工具依赖
        self._check_tools()

    def _update_splash_message(self, message):
        """更新启动画面消息"""
        if self.splash:
            self.splash.showMessage(message, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
            QApplication.processEvents()

    def _check_tools(self):
        """检查工具依赖"""

        missing_tools = []
        if not self.flashing_toolbox.platform_tools:
            missing_tools.append(PlatformTools())
        if not self.flashing_toolbox.mtk_client:
            missing_tools.append(MTKClientTool())

        if missing_tools:
            dialog = DownloadDialog(missing_tools)
            result = dialog.exec()

            if dialog.download_success:
                print("所有工具下载成功！")
            else:
                print("用户取消或部分工具下载失败")
            self.flashing_toolbox = FlashingToolbox(PlatformTools(), MTKClientTool())


    def _init_ui(self):
        """初始化用户界面 - 使用侧边栏布局"""
        # 设置全局字体
        font = QFont("Microsoft YaHei", 9)
        QApplication.setFont(font)

        # 创建主窗口布局
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 创建侧边栏
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("""
            QListWidget {
                background-color: #2c2c2c;
                border: none;
                font-size: 10pt;
                border-radius: 0;
            }
            QListWidget::item {
                height: 50px;
                padding: 5px 15px;
                border-bottom: 1px solid #3a3a3a;
                color: #e0e0e0;
            }
            QListWidget::item:selected {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
        """)

        # 创建堆叠窗口
        self.stacked_widget = QStackedWidget()

        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.stacked_widget)
        splitter.setSizes([200, 700])
        splitter.setHandleWidth(1)

        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 初始化侧边栏菜单
        self._init_sidebar()

        # 初始化页面
        self._init_pages()

        # 初始化Debug日志对话框
        self.debug_log_dialog = DebugLogDialog(self)
        self.settings_dialog = SettingsDialog(self)

    def _init_sidebar(self):
        """初始化侧边栏菜单"""
        # 添加菜单项
        menu_items = [
            ("设备信息", ":/icons/device.png", "device_info"),
            ("系统模式 (ADB)", ":/icons/adb.png", "adb_mode"),
            ("引导模式 (Fastboot)", ":/icons/fastboot.png", "fastboot_mode"),
            ("恢复模式 (Recovery)", ":/icons/recovery.png", "recovery_mode"),
            ("救砖模式 (Bootrom)", ":/icons/bootrom.png", "bootrom_mode"),
            ("设置", ":/icons/settings.png", "settings"),
            ("调试日志", ":/icons/debug.png", "debug_log"),
            ("关于", ":/icons/about.png", "about")
        ]

        for text, icon, tag in menu_items:
            item = QListWidgetItem(QIcon(icon), text)
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self.sidebar.addItem(item)

        # 连接选择信号
        self.sidebar.currentItemChanged.connect(self._on_sidebar_item_changed)

    def _init_pages(self):
        """初始化功能页面"""
        # 设备信息页面
        self.device_info_page = QWidget()
        self._init_device_info_page()
        self.stacked_widget.addWidget(self.device_info_page)

        # 系统模式 (ADB) 页面
        self.adb_mode_page = QWidget()
        self._init_adb_mode_page()
        self.stacked_widget.addWidget(self.adb_mode_page)

        # 引导模式 (Fastboot) 页面
        self.fastboot_mode_page = QWidget()
        self._init_fastboot_mode_page()
        self.stacked_widget.addWidget(self.fastboot_mode_page)

        # 恢复模式 (Recovery) 页面
        self.recovery_mode_page = QWidget()
        self._init_recovery_mode_page()
        self.stacked_widget.addWidget(self.recovery_mode_page)

        # 救砖模式 (Bootrom) 页面
        self.bootrom_mode_page = QWidget()
        self._init_bootrom_mode_page()
        self.stacked_widget.addWidget(self.bootrom_mode_page)

        # 设置页面 (使用设备信息页面作为占位符)
        self.stacked_widget.addWidget(QLabel("设置页面"))

        # 调试日志页面 (使用设备信息页面作为占位符)
        self.stacked_widget.addWidget(QLabel("调试日志页面"))

        # 关于页面 (使用设备信息页面作为占位符)
        self.stacked_widget.addWidget(QLabel("关于页面"))

    def _init_device_info_page(self):
        """初始化设备信息页面"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # 设备状态
        status_group = QGroupBox("设备状态")
        status_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        status_layout = QVBoxLayout()

        self.device_status = QLabel("等待设备连接...")
        self.device_status.setStyleSheet("font-size: 14pt; font-weight: bold; color: #666666;")

        # 设备信息
        self.device_info = QLabel()
        self.device_info.setStyleSheet("font-size: 11pt;")

        status_layout.addWidget(self.device_status)
        status_layout.addWidget(self.device_info)
        status_group.setLayout(status_layout)

        # 设备详细信息
        details_group = QGroupBox("设备信息")
        details_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        details_layout = QVBoxLayout()

        self.device_details = QLabel("设备详细信息将在此显示")
        self.device_details.setStyleSheet("font-size: 10pt;")
        self.device_details.setWordWrap(True)

        details_layout.addWidget(self.device_details)
        details_group.setLayout(details_layout)

        # 操作按钮
        btn_group = QGroupBox("设备操作")
        btn_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        btn_layout = QGridLayout()

        self.bootloader_btn = QPushButton("进入Bootloader")
        self.bootloader_btn.setIcon(QIcon(":/icons/bootloader.png"))
        self.bootloader_btn.setStyleSheet("padding: 8px; min-width: 160px; border-radius: 5px;")
        self.bootloader_btn.clicked.connect(self._enter_bootloader)

        self.recovery_btn = QPushButton("进入Recovery")
        self.recovery_btn.setIcon(QIcon(":/icons/recovery.png"))
        self.recovery_btn.setStyleSheet("padding: 8px; min-width: 160px; border-radius: 5px;")
        self.recovery_btn.clicked.connect(self._enter_recovery)

        self.reboot_btn = QPushButton("重启设备")
        self.reboot_btn.setIcon(QIcon(":/icons/reboot.png"))
        self.reboot_btn.setStyleSheet("padding: 8px; min-width: 160px; border-radius: 5px;")
        self.reboot_btn.clicked.connect(self._reboot_device)

        self.detect_mtk_btn = QPushButton("检测MTK设备")
        self.detect_mtk_btn.setIcon(QIcon(":/icons/detect.png"))
        self.detect_mtk_btn.setStyleSheet("padding: 8px; min-width: 160px; border-radius: 5px;")
        self.detect_mtk_btn.clicked.connect(self._detect_mtk_devices)

        btn_layout.addWidget(self.bootloader_btn, 0, 0)
        btn_layout.addWidget(self.recovery_btn, 0, 1)
        btn_layout.addWidget(self.reboot_btn, 1, 0)
        btn_layout.addWidget(self.detect_mtk_btn, 1, 1)
        btn_group.setLayout(btn_layout)

        # 工具状态
        tools_group = QGroupBox("工具状态")
        tools_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        tools_layout = QVBoxLayout()

        self.adb_status = QLabel("ADB: 检测中...")
        self.fastboot_status = QLabel("Fastboot: 检测中...")
        self.mtk_status = QLabel(f"MTKClient: {'可用' if self.flashing_toolbox.mtk_client else '不可用'}")

        tools_layout.addWidget(self.adb_status)
        tools_layout.addWidget(self.fastboot_status)
        tools_layout.addWidget(self.mtk_status)
        tools_group.setLayout(tools_layout)

        # 组装布局
        layout.addWidget(status_group)
        layout.addWidget(details_group)
        layout.addWidget(btn_group)
        layout.addWidget(tools_group)
        layout.addStretch()

        self.device_info_page.setLayout(layout)

    def _init_adb_mode_page(self):
        """初始化系统模式 (ADB) 页面"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # 创建标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 8px 15px;
                min-width: 80px;
                background: #2c2c2c;
                border: 1px solid #3a3a3a;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 10pt;
                color: #e0e0e0;
            }
            QTabBar::tab:selected {
                background: #3a3a3a;
                border-bottom: 2px solid #4a6fa5;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                padding: 10px;
                background: #2c2c2c;
                border-radius: 8px;
            }
        """)

        # ADB命令标签页
        adb_tab = QWidget()
        self._init_adb_tab(adb_tab)
        tabs.addTab(adb_tab, "ADB命令")

        # 应用管理标签页
        app_tab = QWidget()
        self._init_app_tab(app_tab)
        tabs.addTab(app_tab, "应用管理")

        # 系统界面管理标签页
        ui_tab = QWidget()
        self._init_ui_tab(ui_tab)
        tabs.addTab(ui_tab, "系统界面管理")

        layout.addWidget(tabs)
        self.adb_mode_page.setLayout(layout)

    def _init_fastboot_mode_page(self):
        """初始化引导模式 (Fastboot) 页面"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # 创建标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 8px 15px;
                min-width: 80px;
                background: #2c2c2c;
                border: 1px solid #3a3a3a;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 10pt;
                color: #e0e0e0;
            }
            QTabBar::tab:selected {
                background: #3a3a3a;
                border-bottom: 2px solid #4a6fa5;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                padding: 10px;
                background: #2c2c2c;
                border-radius: 8px;
            }
        """)

        # 刷机标签页
        flash_tab = QWidget()
        self._init_flash_tab(flash_tab)
        tabs.addTab(flash_tab, "刷机")

        # Fastboot命令标签页
        fastboot_cmd_tab = QWidget()
        self._init_fastboot_cmd_tab(fastboot_cmd_tab)
        tabs.addTab(fastboot_cmd_tab, "Fastboot命令")

        # BL解锁标签页
        unlock_tab = QWidget()
        self._init_unlock_tab(unlock_tab)
        tabs.addTab(unlock_tab, "BL解锁")

        # 小米线刷标签页
        xiaomi_tab = QWidget()
        self._init_xiaomi_tab(xiaomi_tab)
        tabs.addTab(xiaomi_tab, "小米线刷")

        layout.addWidget(tabs)
        self.fastboot_mode_page.setLayout(layout)

    def _init_recovery_mode_page(self):
        """初始化恢复模式 (Recovery) 页面"""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Recovery卡刷")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #e0e0e0;")

        # 固件选择
        file_group = QGroupBox("选择卡刷包")
        file_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        file_layout = QVBoxLayout()

        file_select_layout = QHBoxLayout()
        self.recovery_file_label = QLabel("未选择卡刷包")
        self.recovery_file_label.setStyleSheet("font-size: 11pt; color: #e0e0e0;")
        select_btn = QPushButton("选择卡刷包")
        select_btn.setIcon(QIcon(":/icons/folder.png"))
        select_btn.setStyleSheet("padding: 8px; min-width: 120px; border-radius: 5px;")
        select_btn.clicked.connect(self._select_recovery_file)

        file_select_layout.addWidget(self.recovery_file_label)
        file_select_layout.addWidget(select_btn)

        file_layout.addLayout(file_select_layout)
        file_group.setLayout(file_layout)

        # 进度条
        self.recovery_progress_bar = QProgressBar()
        self.recovery_progress_bar.setStyleSheet("""
            QProgressBar { 
                height: 25px; 
                font-size: 10pt; 
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: #4a6fa5;
                border-radius: 5px;
            }
        """)

        # 刷机按钮
        self.recovery_flash_btn = QPushButton("开始卡刷")
        self.recovery_flash_btn.setIcon(QIcon(":/icons/flash.png"))
        self.recovery_flash_btn.setStyleSheet("""
            background-color: #4CAF50; 
            color: white; 
            font-weight: bold; 
            padding: 10px; 
            font-size: 12pt; 
            min-width: 120px;
            border-radius: 5px;
        """)
        self.recovery_flash_btn.clicked.connect(self._start_recovery_flash)

        # 添加支持格式说明
        format_label = QLabel("支持格式: zip")
        format_label.setStyleSheet("color: #888888; font-size: 9pt;")

        # 添加USB连接提示
        usb_label = QLabel("提示: 确保设备已进入Recovery模式并开启ADB")
        usb_label.setStyleSheet("color: #ff6600; font-size: 9pt;")

        # 组装布局
        layout.addWidget(title)
        layout.addWidget(file_group)
        layout.addWidget(self.recovery_progress_bar)
        layout.addWidget(self.recovery_flash_btn)
        layout.addWidget(format_label)
        layout.addWidget(usb_label)
        layout.addStretch()

        self.recovery_mode_page.setLayout(layout)

    def _init_bootrom_mode_page(self):
        """初始化救砖模式 (Bootrom) 页面"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # 创建标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 8px 15px;
                min-width: 80px;
                background: #2c2c2c;
                border: 1px solid #3a3a3a;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 10pt;
                color: #e0e0e0;
            }
            QTabBar::tab:selected {
                background: #3a3a3a;
                border-bottom: 2px solid #4a6fa5;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                padding: 10px;
                background: #2c2c2c;
                border-radius: 8px;
            }
        """)

        # MTK工具标签页
        mtk_tab = QWidget()
        self._init_mtk_tab(mtk_tab)
        tabs.addTab(mtk_tab, "MTK工具")

        layout.addWidget(tabs)
        self.bootrom_mode_page.setLayout(layout)

    def _init_adb_tab(self, tab):
        """初始化ADB命令标签页 - 优化布局"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # 命令输入
        input_group = QGroupBox("ADB命令")
        input_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        input_layout = QVBoxLayout()

        self.adb_command_input = QLineEdit()
        self.adb_command_input.setPlaceholderText("输入ADB命令，例如: shell ls /sdcard")
        self.adb_command_input.setStyleSheet("border-radius: 5px; padding: 8px; font-size: 10pt;")

        # 执行按钮
        execute_btn = QPushButton("执行ADB命令")
        execute_btn.setIcon(QIcon(":/icons/run.png"))
        execute_btn.setStyleSheet("""
            background-color: #4CAF50; 
            color: white; 
            padding: 8px; 
            min-width: 120px;
            border-radius: 5px;
        """)
        execute_btn.clicked.connect(self._execute_adb_command)

        input_layout.addWidget(self.adb_command_input)
        input_layout.addWidget(execute_btn)
        input_group.setLayout(input_layout)

        # 输出显示
        output_group = QGroupBox("输出结果")
        output_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        output_layout = QVBoxLayout()

        self.adb_output = QPlainTextEdit()
        self.adb_output.setReadOnly(True)
        self.adb_output.setStyleSheet("""
            font-family: monospace; 
            font-size: 9pt; 
            background-color: #2c2c2c; 
            color: #e0e0e0;
            border-radius: 5px;
            padding: 5px;
        """)

        output_layout.addWidget(self.adb_output)
        output_group.setLayout(output_layout)

        # 常用命令按钮
        common_group = QGroupBox("常用命令")
        common_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        common_layout = QGridLayout()

        common_commands = [
            ("设备信息", "shell getprop", ":/icons/info.png"),
            ("文件列表", "shell ls /sdcard", ":/icons/list.png"),
            ("截图", "shell screencap -p /sdcard/screenshot.png", ":/icons/camera.png"),
            ("拉取文件", "pull /sdcard/screenshot.png", ":/icons/download.png"),
            ("推送文件", "push local.txt /sdcard/", ":/icons/upload.png"),
            ("安装应用", "install app.apk", ":/icons/install.png")
        ]

        row, col = 0, 0
        for text, cmd, icon in common_commands:
            btn = QPushButton(text)
            btn.setIcon(QIcon(icon))
            btn.setStyleSheet("padding: 6px; text-align: left; min-width: 120px; border-radius: 5px;")
            btn.setProperty("command", cmd)
            btn.clicked.connect(lambda _, cmd=cmd: self._set_adb_command(cmd))
            common_layout.addWidget(btn, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

        common_group.setLayout(common_layout)

        # 组装布局
        layout.addWidget(input_group)
        layout.addWidget(common_group)
        layout.addWidget(output_group)

        tab.setLayout(layout)

    def _init_app_tab(self, tab):
        """初始化应用管理标签页"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("应用管理")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #e0e0e0;")

        # 应用操作
        app_group = QGroupBox("应用操作")
        app_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        app_layout = QVBoxLayout()

        # 安装应用
        install_layout = QHBoxLayout()
        self.app_path_label = QLabel("未选择应用")
        self.app_path_label.setStyleSheet("font-size: 10pt; color: #e0e0e0;")
        select_app_btn = QPushButton("选择应用")
        select_app_btn.setIcon(QIcon(":/icons/folder.png"))
        select_app_btn.setStyleSheet("padding: 6px; min-width: 100px; border-radius: 5px;")
        select_app_btn.clicked.connect(self._select_app)

        install_btn = QPushButton("安装应用")
        install_btn.setIcon(QIcon(":/icons/install.png"))
        install_btn.setStyleSheet("""
            background-color: #4CAF50; 
            color: white; 
            padding: 8px; 
            min-width: 120px;
            border-radius: 5px;
        """)
        install_btn.clicked.connect(self._install_app)

        install_layout.addWidget(self.app_path_label)
        install_layout.addWidget(select_app_btn)
        install_layout.addWidget(install_btn)

        # 卸载应用
        uninstall_layout = QHBoxLayout()
        self.package_name_input = QLineEdit()
        self.package_name_input.setPlaceholderText("输入包名，例如: com.example.app")
        self.package_name_input.setStyleSheet("border-radius: 5px; padding: 8px; font-size: 10pt;")

        uninstall_btn = QPushButton("卸载应用")
        uninstall_btn.setIcon(QIcon(":/icons/uninstall.png"))
        uninstall_btn.setStyleSheet("""
            background-color: #f44336; 
            color: white; 
            padding: 8px; 
            min-width: 120px;
            border-radius: 5px;
        """)
        uninstall_btn.clicked.connect(self._uninstall_app)

        uninstall_layout.addWidget(self.package_name_input)
        uninstall_layout.addWidget(uninstall_btn)

        app_layout.addLayout(install_layout)
        app_layout.addLayout(uninstall_layout)
        app_group.setLayout(app_layout)

        # 应用列表
        list_group = QGroupBox("应用列表")
        list_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        list_layout = QVBoxLayout()

        self.app_list = QListWidget()
        self.app_list.setStyleSheet("font-size: 10pt; color: #e0e0e0; border-radius: 5px;")

        refresh_btn = QPushButton("刷新应用列表")
        refresh_btn.setIcon(QIcon(":/icons/refresh.png"))
        refresh_btn.setStyleSheet("padding: 6px; min-width: 120px; border-radius: 5px;")
        refresh_btn.clicked.connect(self._refresh_app_list)

        list_layout.addWidget(self.app_list)
        list_layout.addWidget(refresh_btn)
        list_group.setLayout(list_layout)

        # 组装布局
        layout.addWidget(title)
        layout.addWidget(app_group)
        layout.addWidget(list_group)

        tab.setLayout(layout)

    def _init_ui_tab(self, tab):
        """初始化系统界面管理标签页"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("系统界面管理")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #e0e0e0;")

        # 界面组件
        ui_group = QGroupBox("界面组件")
        ui_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        ui_layout = QGridLayout()

        ui_components = [
            ("状态栏", ":/icons/statusbar.png", "statusbar"),
            ("导航栏", ":/icons/navbar.png", "navbar"),
            ("锁屏", ":/icons/lockscreen.png", "lockscreen"),
            ("启动器", ":/icons/launcher.png", "launcher"),
            ("设置", ":/icons/settings.png", "settings"),
            ("通知中心", ":/icons/notification.png", "notification")
        ]

        row, col = 0, 0
        for text, icon, tag in ui_components:
            btn = QPushButton(text)
            btn.setIcon(QIcon(icon))
            btn.setStyleSheet("""
                padding: 10px; 
                min-width: 120px; 
                min-height: 100px;
                border-radius: 8px;
                text-align: bottom;
            """)
            btn.setProperty("component", tag)
            btn.clicked.connect(self._manage_ui_component)
            ui_layout.addWidget(btn, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

        ui_group.setLayout(ui_layout)

        # 操作日志
        log_group = QGroupBox("操作日志")
        log_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        log_layout = QVBoxLayout()

        self.ui_log = QPlainTextEdit()
        self.ui_log.setReadOnly(True)
        self.ui_log.setStyleSheet("""
            font-family: monospace; 
            font-size: 9pt; 
            background-color: #2c2c2c; 
            color: #e0e0e0;
            border-radius: 5px;
            padding: 5px;
        """)

        log_layout.addWidget(self.ui_log)
        log_group.setLayout(log_layout)

        # 组装布局
        layout.addWidget(title)
        layout.addWidget(ui_group)
        layout.addWidget(log_group)

        tab.setLayout(layout)

    def _init_flash_tab(self, tab):
        """初始化刷机标签页 - 优化布局"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # 固件选择
        file_group = QGroupBox("固件选择")
        file_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        file_layout = QVBoxLayout()

        file_select_layout = QHBoxLayout()
        self.file_label = QLabel("未选择固件")
        self.file_label.setStyleSheet("font-size: 10pt; color: #e0e0e0;")
        select_btn = QPushButton("选择固件")
        select_btn.setIcon(QIcon(":/icons/folder.png"))
        select_btn.setStyleSheet("padding: 6px; min-width: 100px; border-radius: 5px;")
        select_btn.clicked.connect(self._select_firmware)

        file_select_layout.addWidget(self.file_label)
        file_select_layout.addWidget(select_btn)

        file_layout.addLayout(file_select_layout)
        file_group.setLayout(file_layout)

        # 分区选择
        partition_group = QGroupBox("分区选择")
        partition_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        partition_layout = QVBoxLayout()

        self.partition_combo = QComboBox()
        self.partition_combo.setStyleSheet("padding: 6px; font-size: 10pt; border-radius: 5px;")
        self.partition_combo.addItems(["全部", "boot", "recovery", "system", "vendor", "userdata", "cache", "vbmeta"])

        partition_layout.addWidget(self.partition_combo)
        partition_group.setLayout(partition_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar { 
                height: 25px; 
                font-size: 10pt; 
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: #4a6fa5;
                border-radius: 5px;
            }
        """)

        # 刷机按钮
        self.flash_btn = QPushButton("开始刷机")
        self.flash_btn.setIcon(QIcon(":/icons/flash.png"))
        self.flash_btn.setStyleSheet("""
            background-color: #4CAF50; 
            color: white; 
            font-weight: bold; 
            padding: 10px; 
            font-size: 12pt; 
            min-width: 120px;
            border-radius: 5px;
        """)
        self.flash_btn.clicked.connect(self._start_flashing)

        # 添加支持格式说明
        format_label = QLabel("支持格式: zip, img, bin, tgz, tar.gz")
        format_label.setStyleSheet("color: #888888; font-size: 9pt;")

        # 添加USB连接提示
        usb_label = QLabel("提示: 确保使用高质量USB数据线并连接到USB 2.0端口")
        usb_label.setStyleSheet("color: #ff6600; font-size: 9pt;")

        # 组装布局
        layout.addWidget(file_group)
        layout.addWidget(partition_group)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.flash_btn)
        layout.addWidget(format_label)
        layout.addWidget(usb_label)
        layout.addStretch()

        tab.setLayout(layout)

    def _init_fastboot_cmd_tab(self, tab):
        """初始化Fastboot命令标签页 - 优化布局"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # 命令输入
        input_group = QGroupBox("Fastboot命令")
        input_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        input_layout = QVBoxLayout()

        self.fastboot_command_input = QLineEdit()
        self.fastboot_command_input.setPlaceholderText("输入Fastboot命令，例如: devices")
        self.fastboot_command_input.setStyleSheet("border-radius: 5px; padding: 8px; font-size: 10pt;")

        # 执行按钮
        execute_btn = QPushButton("执行Fastboot命令")
        execute_btn.setIcon(QIcon(":/icons/run.png"))
        execute_btn.setStyleSheet("""
            background-color: #4CAF50; 
            color: white; 
            padding: 8px; 
            min-width: 120px;
            border-radius: 5px;
        """)
        execute_btn.clicked.connect(self._execute_fastboot_command)

        input_layout.addWidget(self.fastboot_command_input)
        input_layout.addWidget(execute_btn)
        input_group.setLayout(input_layout)

        # 输出显示
        output_group = QGroupBox("输出结果")
        output_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        output_layout = QVBoxLayout()

        self.fastboot_output = QPlainTextEdit()
        self.fastboot_output.setReadOnly(True)
        self.fastboot_output.setStyleSheet("""
            font-family: monospace; 
            font-size: 9pt; 
            background-color: #2c2c2c; 
            color: #e0e0e0;
            border-radius: 5px;
            padding: 5px;
        """)

        output_layout.addWidget(self.fastboot_output)
        output_group.setLayout(output_layout)

        # 常用命令按钮
        common_group = QGroupBox("常用命令")
        common_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        common_layout = QGridLayout()

        common_commands = [
            ("设备列表", "devices", ":/icons/list.png"),
            ("重启", "reboot", ":/icons/reboot.png"),
            ("进入Recovery", "reboot recovery", ":/icons/recovery.png"),
            ("刷入boot", "flash boot boot.img", ":/icons/flash.png"),
            ("解锁BL", "flashing unlock", ":/icons/unlock.png"),
            ("锁定BL", "flashing lock", ":/icons/lock.png")
        ]

        row, col = 0, 0
        for text, cmd, icon in common_commands:
            btn = QPushButton(text)
            btn.setIcon(QIcon(icon))
            btn.setStyleSheet("padding: 6px; text-align: left; min-width: 120px; border-radius: 5px;")
            btn.setProperty("command", cmd)
            btn.clicked.connect(lambda _, cmd=cmd: self._set_fastboot_command(cmd))
            common_layout.addWidget(btn, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

        common_group.setLayout(common_layout)

        # 组装布局
        layout.addWidget(input_group)
        layout.addWidget(common_group)
        layout.addWidget(output_group)

        tab.setLayout(layout)

    def _init_unlock_tab(self, tab):
        """初始化BL解锁标签页 - 优化布局"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # 警告信息
        warning_group = QGroupBox("重要警告")
        warning_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        warning_layout = QVBoxLayout()

        warning_label = QLabel(
            "警告: 解锁Bootloader会清除设备上的所有数据!\n\n"
            "请在操作前备份重要数据。某些设备可能需要先申请解锁许可。"
        )
        warning_label.setStyleSheet("color: red; font-weight: bold; font-size: 10pt;")
        warning_label.setWordWrap(True)

        warning_layout.addWidget(warning_label)
        warning_group.setLayout(warning_layout)

        # 解锁按钮
        unlock_btn = QPushButton("解锁Bootloader")
        unlock_btn.setIcon(QIcon(":/icons/unlock.png"))
        unlock_btn.setStyleSheet("""
            background-color: #ff4444; 
            color: white; 
            font-weight: bold; 
            padding: 10px; 
            font-size: 12pt; 
            min-width: 150px;
            border-radius: 5px;
        """)
        unlock_btn.clicked.connect(self._unlock_bootloader)

        # 锁定按钮
        lock_btn = QPushButton("锁定Bootloader")
        lock_btn.setIcon(QIcon(":/icons/lock.png"))
        lock_btn.setStyleSheet("""
            background-color: #4444ff; 
            color: white; 
            font-weight: bold; 
            padding: 10px; 
            font-size: 12pt; 
            min-width: 150px;
            border-radius: 5px;
        """)
        lock_btn.clicked.connect(self._lock_bootloader)

        # 状态显示
        status_group = QGroupBox("操作状态")
        status_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        status_layout = QVBoxLayout()

        self.unlock_status = QLabel("设备状态: 未知")
        self.unlock_status.setStyleSheet("font-size: 10pt; color: #e0e0e0;")

        status_layout.addWidget(self.unlock_status)
        status_group.setLayout(status_layout)

        # 解锁说明
        instructions_group = QGroupBox("操作说明")
        instructions_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        instructions_layout = QVBoxLayout()

        instructions = QLabel(
            "解锁步骤:\n"
            "1. 确保设备已进入Fastboot模式\n"
            "2. 连接设备到电脑\n"
            "3. 点击解锁按钮\n"
            "4. 按照设备屏幕上的提示操作"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-size: 9pt; color: #e0e0e0;")

        instructions_layout.addWidget(instructions)
        instructions_group.setLayout(instructions_layout)

        # 组装布局
        layout.addWidget(warning_group)
        layout.addWidget(unlock_btn)
        layout.addWidget(lock_btn)
        layout.addWidget(status_group)
        layout.addWidget(instructions_group)
        layout.addStretch()

        tab.setLayout(layout)

    def _init_xiaomi_tab(self, tab):
        """初始化小米线刷标签页 - 优化布局"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # 固件选择
        file_group = QGroupBox("小米线刷包")
        file_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        file_layout = QVBoxLayout()

        file_select_layout = QHBoxLayout()
        self.xiaomi_file_label = QLabel("未选择小米线刷包")
        self.xiaomi_file_label.setStyleSheet("font-size: 10pt; color: #e0e0e0;")
        select_btn = QPushButton("选择线刷包")
        select_btn.setIcon(QIcon(":/icons/folder.png"))
        select_btn.setStyleSheet("padding: 6px; min-width: 100px; border-radius: 5px;")
        select_btn.clicked.connect(self._select_xiaomi_firmware)

        file_select_layout.addWidget(self.xiaomi_file_label)
        file_select_layout.addWidget(select_btn)

        file_layout.addLayout(file_select_layout)
        file_group.setLayout(file_layout)

        # 刷机选项
        options_group = QGroupBox("刷机选项")
        options_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        options_layout = QVBoxLayout()

        self.clean_all_check = QCheckBox("清除所有数据")
        self.clean_all_check.setChecked(True)
        self.clean_all_check.setStyleSheet("font-size: 10pt; color: #e0e0e0;")
        self.lock_bootloader_check = QCheckBox("锁定Bootloader")
        self.lock_bootloader_check.setStyleSheet("font-size: 10pt; color: #e0e0e0;")

        options_layout.addWidget(self.clean_all_check)
        options_layout.addWidget(self.lock_bootloader_check)
        options_group.setLayout(options_layout)

        # 进度条
        self.xiaomi_progress_bar = QProgressBar()
        self.xiaomi_progress_bar.setStyleSheet("""
            QProgressBar { 
                height: 25px; 
                font-size: 10pt; 
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: #FF9800;
                border-radius: 5px;
            }
        """)

        # 刷机按钮
        self.xiaomi_flash_btn = QPushButton("开始小米线刷")
        self.xiaomi_flash_btn.setIcon(QIcon(":/icons/flash.png"))
        self.xiaomi_flash_btn.setStyleSheet("""
            background-color: #FF9800; 
            color: white; 
            font-weight: bold; 
            padding: 10px; 
            font-size: 12pt; 
            min-width: 120px;
            border-radius: 5px;
        """)
        self.xiaomi_flash_btn.clicked.connect(self._start_xiaomi_flashing)

        # 组装布局
        layout.addWidget(file_group)
        layout.addWidget(options_group)
        layout.addWidget(self.xiaomi_progress_bar)
        layout.addWidget(self.xiaomi_flash_btn)
        layout.addStretch()

        tab.setLayout(layout)

    def _init_mtk_tab(self, tab):
        """初始化MTK命令行标签页 (原Bootrom刷机标签页)"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # 说明
        info_group = QGroupBox("使用说明")
        info_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        info_layout = QVBoxLayout()

        info_label = QLabel(
            "MTK命令行模式允许直接执行MTKClient命令")
        info_label.setStyleSheet("font-size: 10pt; color: #e0e0e0;")
        info_label.setWordWrap(True)

        info_layout.addWidget(info_label)
        info_group.setLayout(info_layout)

        # 命令输入
        command_group = QGroupBox("MTK命令")
        command_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        command_layout = QVBoxLayout()

        command_input_layout = QHBoxLayout()
        self.mtk_command_input = QLineEdit()
        self.mtk_command_input.setPlaceholderText("输入MTKClient命令，例如: printgpt")
        self.mtk_command_input.setStyleSheet("border-radius: 5px; padding: 8px; font-size: 10pt;")
        self.mtk_command_input.returnPressed.connect(self._execute_mtk_command)

        execute_btn = QPushButton("执行")
        execute_btn.setIcon(QIcon(":/icons/run.png"))
        execute_btn.setStyleSheet("""
            background-color: #4CAF50; 
            color: white; 
            padding: 8px; 
            min-width: 80px;
            border-radius: 5px;
        """)
        execute_btn.clicked.connect(self._execute_mtk_command)

        stop_btn = QPushButton("停止")
        stop_btn.setIcon(QIcon(":/icons/stop.png"))
        stop_btn.setStyleSheet("""
            background-color: #f44336; 
            color: white; 
            padding: 8px; 
            min-width: 80px;
            border-radius: 5px;
        """)
        stop_btn.clicked.connect(self._stop_mtk_command)

        command_input_layout.addWidget(self.mtk_command_input)
        command_input_layout.addWidget(execute_btn)
        command_input_layout.addWidget(stop_btn)

        command_layout.addLayout(command_input_layout)
        command_group.setLayout(command_layout)

        # 常用命令按钮
        common_group = QGroupBox("常用命令")
        common_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        common_layout = QGridLayout()

        common_commands = [
            ("检测设备", "detect", ":/icons/detect.png"),
            ("分区表", "printgpt", ":/icons/partition.png"),
            ("读取boot", "rf boot", ":/icons/read.png"),
            ("写入boot", "wf boot", ":/icons/write.png"),
            ("解锁设备", "da seccfg unlock", ":/icons/unlock.png"),
            ("读取分区", "rl", ":/icons/read.png"),
            ("写入分区", "wl", ":/icons/write.png"),
            ("备份分区", "dump", ":/icons/backup.png")
        ]

        row, col = 0, 0
        for text, cmd, icon in common_commands:
            btn = QPushButton(text)
            btn.setIcon(QIcon(icon))
            btn.setStyleSheet("padding: 6px; text-align: left; min-width: 120px; border-radius: 5px;")
            btn.setProperty("command", cmd)
            btn.clicked.connect(lambda _, cmd=cmd: self._set_mtk_command(cmd))
            common_layout.addWidget(btn, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1

        common_group.setLayout(common_layout)

        # 设备检测
        detect_group = QGroupBox("设备检测")
        detect_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        detect_layout = QVBoxLayout()

        detect_btn_layout = QHBoxLayout()
        self.start_detect_btn = QPushButton("持续检测设备")
        self.start_detect_btn.setIcon(QIcon(":/icons/scan.png"))
        self.start_detect_btn.setStyleSheet("padding: 6px; min-width: 120px; border-radius: 5px;")
        self.stop_detect_btn = QPushButton("停止检测")
        self.stop_detect_btn.setIcon(QIcon(":/icons/stop.png"))
        self.stop_detect_btn.setStyleSheet("padding: 6px; min-width: 120px; border-radius: 5px;")
        self.stop_detect_btn.setEnabled(False)

        self.start_detect_btn.clicked.connect(self._start_detect_mtk)
        self.stop_detect_btn.clicked.connect(self._stop_detect_mtk)

        # 设备连接状态
        self.mtk_status_label = QLabel("设备状态: 未连接")
        self.mtk_status_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #e0e0e0;")

        detect_btn_layout.addWidget(self.start_detect_btn)
        detect_btn_layout.addWidget(self.stop_detect_btn)

        detect_layout.addLayout(detect_btn_layout)
        detect_layout.addWidget(self.mtk_status_label)
        detect_group.setLayout(detect_layout)

        # 输出显示
        output_group = QGroupBox("命令输出")
        output_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        output_layout = QVBoxLayout()

        self.mtk_output = QTextEdit()
        self.mtk_output.setReadOnly(True)
        self.mtk_output.setStyleSheet("""
            font-family: monospace; 
            font-size: 9pt; 
            background-color: #2c2c2c; 
            color: #e0e0e0;
            border-radius: 5px;
            padding: 5px;
        """)

        output_layout.addWidget(self.mtk_output)
        output_group.setLayout(output_layout)

        # 组装布局
        layout.addWidget(info_group)
        layout.addWidget(command_group)
        layout.addWidget(common_group)
        layout.addWidget(detect_group)
        layout.addWidget(output_group)
        layout.addStretch()

        tab.setLayout(layout)

    def _apply_theme(self):
        """应用主题设置"""
        theme = self.settings.value("theme", "夏 (蓝白)")

        # 创建深色主题
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(35, 35, 35))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(40, 40, 40))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(50, 50, 50))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(74, 111, 165))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(74, 111, 165))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        QApplication.setPalette(dark_palette)

        # 设置全局样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {
                background-color: #2c2c2c;
                border: 1px solid #3a3a3a;
                padding: 3px;
                border-radius: 5px;
                color: #e0e0e0;
            }
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                text-align: center;
                background-color: #2c2c2c;
            }
            QProgressBar::chunk {
                background-color: #4a6fa5;
                border-radius: 5px;
            }
            QLabel {
                color: #e0e0e0;
            }
            QTabBar::tab {
                background-color: #2c2c2c;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-bottom: none;
                padding: 8px 15px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background-color: #3a3a3a;
                border-bottom: 2px solid #4a6fa5;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                background-color: #2c2c2c;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                border: none;
                background: #2c2c2c;
                width: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #4a6fa5;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical {
                border: none;
                background: none;
                height: 0px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
            }
            QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
                subcontrol-position: top;
                subcontrol-origin: margin;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

    def _on_sidebar_item_changed(self, current, previous):
        """侧边栏菜单项选择变化"""
        if current is None:
            return

        tag = current.data(Qt.ItemDataRole.UserRole)

        # 根据标签切换到相应页面
        if tag == "device_info":
            self.stacked_widget.setCurrentIndex(0)
        elif tag == "adb_mode":
            self.stacked_widget.setCurrentIndex(1)
        elif tag == "fastboot_mode":
            self.stacked_widget.setCurrentIndex(2)
        elif tag == "recovery_mode":
            self.stacked_widget.setCurrentIndex(3)
        elif tag == "bootrom_mode":
            self.stacked_widget.setCurrentIndex(4)
        elif tag == "settings":
            self._show_settings()
        elif tag == "debug_log":
            self._show_debug_log()
        elif tag == "about":
            self._show_about()

    def _start_device_check(self):
        """启动设备检测线程"""
        self.running = True

        def check_loop():
            while self.running:
                try:
                    # 检查ADB设备
                    adb_devices = self.flashing_toolbox.platform_tools.get_adb_devices()
                    if adb_devices:
                        self.mode_signal.emit("adb", adb_devices[0][0])
                        self._update_device_details(adb_devices[0][0])
                        time.sleep(3)
                        continue
                except Exception as e:
                    self.log_signal.emit(f"ADB设备检测错误: {str(e)}")

                # 检查Fastboot设备
                try:
                    fastboot_devices = self.flashing_toolbox.platform_tools.get_fastboot_devices()
                    if fastboot_devices:
                        self.mode_signal.emit("fastboot", fastboot_devices[0][0])
                        self._update_device_details(fastboot_devices[0][0])
                        time.sleep(3)
                        continue
                except Exception as e:
                    self.log_signal.emit(f"Fastboot设备检测错误: {str(e)}")

                # 检查MTK设备
                if self.mtk_detecting:  # 只有开始识别时才检测
                    try:
                        mtk_devices = self.flashing_toolbox.mtk_client.detect_devices()
                        if mtk_devices:
                            self.mtk_device_signal.emit(mtk_devices[0][0])
                            self.mtk_detecting = False  # 检测到设备后停止检测
                            self.stop_detect_btn.setEnabled(False)
                            self.start_detect_btn.setEnabled(True)
                            self.mtk_status_label.setText(f"设备状态: 已连接 (端口: {mtk_devices[0][0]})")
                            time.sleep(3)
                            continue
                    except Exception as e:
                        self.log_signal.emit(f"MTK设备检测错误: {str(e)}")
                        self.mtk_status_label.setText(f"设备状态: 检测错误 - {str(e)}")
                        time.sleep(1)

                # 没有检测到设备
                self.mode_signal.emit(None, None)
                self.device_details.setText("设备详细信息将在此显示")
                self.mtk_status_label.setText("设备状态: 未连接")
                time.sleep(3)

        self.check_thread = threading.Thread(target=check_loop, daemon=True)
        self.check_thread.start()

    def _update_device_details(self, device_id):
        """更新设备详细信息"""
        try:
            if self.current_mode == "adb":
                # 获取设备信息
                result = self.flashing_toolbox.platform_tools.execute_adb_command(f"-s {device_id} shell getprop")
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
                result = self.flashing_toolbox.platform_tools.execute_fastboot_command(f"-s {device_id} getvar all")
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
            self.device_status.setStyleSheet("color: #4CAF50;")
            self._update_button_states()
        elif mode == "fastboot":
            self.device_status.setText("Fastboot模式")
            self.device_info.setText(f"设备ID: {device_id}")
            self.device_status.setStyleSheet("color: #2196F3;")
            self._update_button_states()
        else:
            self.device_status.setText("未连接设备")
            self.device_info.setText("")
            self.device_status.setStyleSheet("color: #666666;")
            self._update_button_states()

    def _handle_mtk_device(self, device_id):
        """处理MTK设备检测结果"""
        self.current_mode = "mtk"
        self.device_id = device_id
        self.device_status.setText("MTK Bootrom模式")
        self.device_info.setText(f"设备端口: {device_id}")
        self.device_status.setStyleSheet("color: #FF9800;")
        self._update_button_states()
        self.mtk_status_label.setText(f"设备状态: 已连接 (端口: {device_id})")

    def _update_button_states(self):
        """更新按钮状态"""
        has_device = self.current_mode is not None

        self.bootloader_btn.setEnabled(has_device and self.current_mode == "adb")
        self.recovery_btn.setEnabled(has_device and self.current_mode == "adb")
        self.reboot_btn.setEnabled(has_device)
        self.detect_mtk_btn.setEnabled(True)
        self.flash_btn.setEnabled(has_device and bool(self.firmware_path) and self.current_mode == "fastboot")
        self.xiaomi_flash_btn.setEnabled(bool(self.xiaomi_flash_path))

    def _update_status(self, status_type, message):
        """更新状态显示"""
        if status_type == "adb":
            self.adb_status.setText(f"ADB: {message}")
        elif status_type == "fastboot":
            self.fastboot_status.setText(f"Fastboot: {message}")

    def _log_message(self, message):
        """记录日志消息"""
        self.statusBar().showMessage(message)
        if self.debug_log_dialog:
            self.debug_log_dialog.append_log(message)

    def _update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
        self.xiaomi_progress_bar.setValue(value)
        self.recovery_progress_bar.setValue(value)

    def _update_mtk_log(self, message):
        """更新MTK日志输出 - 修复线程安全问题"""
        # 确保在主线程中执行UI更新
        if not QThread.currentThread() is QApplication.instance().thread():
            # 使用信号而不是直接调用
            self.mtk_command_output.emit(message)
            return

        # 直接追加消息
        if hasattr(self, 'mtk_output') and self.mtk_output:
            self.mtk_output.append(message)

            # 滚动到底部
            self.mtk_output.moveCursor(QTextCursor.MoveOperation.End)
            self.mtk_output.ensureCursorVisible()

        current_time = time.time()
        if current_time - self._last_update_time > 0.1:  # 每100ms更新一次
            self.mtk_output.append(message)
            self._last_update_time = current_time
        else:
            # 缓存消息，稍后一起更新
            if not hasattr(self, '_mtk_message_buffer'):
                self._mtk_message_buffer = []
            self._mtk_message_buffer.append(message)

            # 如果没有定时器，创建一个
            if not hasattr(self, '_mtk_update_timer'):
                self._mtk_update_timer = QTimer(self)
                self._mtk_update_timer.timeout.connect(self._flush_mtk_buffer)
                self._mtk_update_timer.start(100)  # 100ms后刷新

    def _flush_mtk_buffer(self):
        """刷新MTK消息缓冲区"""
        if hasattr(self, '_mtk_message_buffer') and self._mtk_message_buffer:
            # 批量更新消息
            message = "\n".join(self._mtk_message_buffer)
            if hasattr(self, 'mtk_output') and self.mtk_output:
                self.mtk_output.append(message)
                self.mtk_output.moveCursor(QTextCursor.MoveOperation.End)
                self.mtk_output.ensureCursorVisible()

            # 清空缓冲区
            self._mtk_message_buffer.clear()

        # 停止定时器
        if hasattr(self, '_mtk_update_timer'):
            self._mtk_update_timer.stop()

    def _show_settings(self):
        """显示设置对话框"""
        if self.settings_dialog.exec() == QDialog.DialogCode.Accepted:
            # 重新初始化ADB以应用新的路径设置
            self._apply_theme()
            self.log_signal.emit("设置已保存并应用")

    def _show_debug_log(self):
        """显示调试日志"""
        self.debug_log_dialog.show()

    def _show_about(self):
        """显示关于信息"""
        about_text = (
            "<h2>Python Flash Tools V1.9</h2>"
            "<p>Powered by LanChe-Studio</p>"
            "<p>开源项目: <a href='https://github.com/LanChe-Studio/python-flash-tools'>https://github.com/LanChe-Studio/python-flash-tools</a></p>"
            "<p>开源协议: GPL 3.0</p>"
            "<h3>使用的组件:</h3>"
            "<ul>"
            "<li>MTKClient: <a href='https://github.com/bkerler/mtkclient'>https://github.com/bkerler/mtkclient</a> (GPL 3.0)</li>"
            "<li>Android SDK: <a href='https://github.com/aosp-mirror'>https://github.com/aosp-mirror</a></li>"
            "</ul>"
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("关于")
        msg.setWindowIcon(QIcon(":/icons/about.png"))
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(about_text)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()

    def _enter_bootloader(self):
        """进入Bootloader模式"""
        if self.operation_in_progress:
            return

        self.operation_in_progress = True
        self.log_signal.emit("尝试进入Bootloader模式...")

        try:
            success, error = self.flashing_toolbox.platform_tools.adb_reboot("bootloader")
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
            success, error = self.flashing_toolbox.platform_tools.adb_reboot("recovery")
            if success:
                self.log_signal.emit("设备正在重启到Recovery...")
            else:
                self.log_signal.emit(f"操作失败: {error}")
        except Exception as e:
            self.log_signal.emit(f"操作异常: {str(e)}")
        finally:
            self.operation_in_progress = False

    def _detect_mtk_devices(self):
        """检测MTK设备"""
        if self.operation_in_progress:
            return

        self.operation_in_progress = True
        self.log_signal.emit("开始检测MTK设备...")
        self.mtk_output.clear()

        try:
            # 启动MTKClient命令
            cmd = [sys.executable, self.flashing_toolbox.mtk_client.get_main_program(), "detect"]
            self.mtk_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # 启动线程读取输出
            threading.Thread(target=self._read_mtk_output, daemon=True).start()
        except Exception as e:
            self.log_signal.emit(f"检测MTK设备失败: {str(e)}")
            self.operation_in_progress = False

    def _start_detect_mtk(self):
        """开始持续检测MTK设备"""
        self.log_signal.emit("开始持续检测MTK设备...")
        self.mtk_detecting = True
        self.start_detect_btn.setEnabled(False)
        self.stop_detect_btn.setEnabled(True)
        self.mtk_status_label.setText("设备状态: 检测中...")

        # 启动新的检测线程
        threading.Thread(target=self._detect_mtk_continuous, daemon=True).start()

    def _detect_mtk_continuous(self):
        """持续检测MTK设备"""
        while self.mtk_detecting:
            try:
                # 执行检测命令
                cmd = [sys.executable, self.flashing_toolbox.mtk_client.get_main_program(), "detect"]
                self.mtk_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )

                # 读取输出
                while self.mtk_detecting:
                    output = self.mtk_process.stdout.readline()
                    if output == '' and self.mtk_process.poll() is not None:
                        break
                    if output:
                        self.mtk_command_output.emit(output.strip())

                # 检查是否检测到设备
                if self.mtk_detecting and self.mtk_process.poll() == 0:
                    # 尝试解析输出以获取设备信息
                    mtk_devices = self.flashing_toolbox.mtk_client.detect_mtk_devices()
                    if mtk_devices:
                        self.mtk_device_signal.emit(mtk_devices[0][0])
                        self.mtk_detecting = False  # 检测到设备后停止检测
                        self.stop_detect_btn.setEnabled(False)
                        self.start_detect_btn.setEnabled(True)
                        self.mtk_status_label.setText(f"设备状态: 已连接 (端口: {mtk_devices[0][0]})")
                        break

                time.sleep(1)
            except Exception as e:
                self.mtk_command_output.emit(f"检测错误: {str(e)}")
                self.mtk_status_label.setText(f"设备状态: 检测错误 - {str(e)}")
                time.sleep(1)

    def _stop_detect_mtk(self):
        """停止检测MTK设备"""
        self.log_signal.emit("已停止检测MTK设备")
        self.mtk_detecting = False
        self.start_detect_btn.setEnabled(True)
        self.stop_detect_btn.setEnabled(False)
        self.mtk_status_label.setText("设备状态: 检测已停止")

        # 如果检测进程仍在运行，终止它
        if self.mtk_process and self.mtk_process.poll() is None:
            try:
                self.mtk_process.terminate()
            except:
                pass

    def _reboot_device(self):
        """重启设备"""
        if self.operation_in_progress:
            return

        self.operation_in_progress = True
        self.log_signal.emit("正在重启设备...")

        try:
            if self.current_mode == "adb":
                success, error = self.flashing_toolbox.platform_tools.adb_reboot()
                if not success:
                    self.log_signal.emit(f"重启失败: {error}")
            elif self.current_mode == "fastboot":
                success, error = self.flashing_toolbox.platform_tools.fastboot_reboot()
                if not success:
                    self.log_signal.emit(f"重启失败: {error}")
            elif self.current_mode == "mtk":
                self.log_signal.emit("MTK设备重启需要手动操作")
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

    def _select_recovery_file(self):
        """选择Recovery卡刷包"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Recovery卡刷包", "",
            "卡刷包 (*.zip);;所有文件 (*)")

        if file_path:
            self.recovery_file_path = file_path
            self.recovery_file_label.setText(os.path.basename(file_path))
            self.log_signal.emit(f"已选择卡刷包: {file_path}")

    def _select_app(self):
        """选择应用文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择应用文件", "",
            "应用文件 (*.apk);;所有文件 (*)")

        if file_path:
            self.app_path = file_path
            self.app_path_label.setText(os.path.basename(file_path))
            self.log_signal.emit(f"已选择应用: {file_path}")

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
            result = self.flashing_toolbox.platform_tools.execute_adb_command(command)
            if result is None:
                self.adb_output.setPlainText(f"执行失败: {self.flashing_toolbox.platform_tools.last_error}")
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
            result = self.flashing_toolbox.platform_tools.execute_fastboot_command(command)
            if result is None:
                self.fastboot_output.setPlainText(f"执行失败: {self.flashing_toolbox.platform_tools.last_error}")
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

    def _set_mtk_command(self, command):
        """设置MTK命令"""
        self.mtk_command_input.setText(command)

    def _execute_mtk_command(self):
        """执行MTK命令"""
        if self.operation_in_progress:
            return

        command = self.mtk_command_input.text().strip()
        if not command:
            self.log_signal.emit("请输入MTK命令")
            return

        self.operation_in_progress = True
        self.log_signal.emit(f"执行MTK命令: {command}")
        self.mtk_output.clear()
        self.mtk_output.append(f">>> {command}")

        try:
            # 分割命令为参数列表
            args = command.split()

            # 启动MTKClient命令
            if self.flashing_toolbox.mtk_client:
                cmd = [sys.executable, self.flashing_toolbox.mtk_client.get_main_program()] + args

                # 启动子进程
                self.mtk_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )

                # 启动线程读取输出
                threading.Thread(target=self._read_mtk_output, daemon=True).start()
            else:
                self.log_signal.emit("未找到MTKClient工具")
                self.operation_in_progress = False
        except Exception as e:
            self.mtk_output.append(f"执行异常: {str(e)}")
            self.log_signal.emit(f"MTK命令执行异常: {str(e)}")
            self.operation_in_progress = False

    def _read_mtk_output(self):
        """读取MTK命令输出"""
        try:
            while True:
                output = self.mtk_process.stdout.readline()
                if output == '' and self.mtk_process.poll() is not None:
                    break
                if output:
                    self.mtk_command_output.emit(output.strip())

            # 命令执行完成
            return_code = self.mtk_process.poll()
            if return_code == 0:
                self.mtk_command_output.emit("命令执行成功")
            else:
                self.mtk_command_output.emit(f"命令执行失败，返回码: {return_code}")
        except Exception as e:
            self.mtk_command_output.emit(f"读取输出错误: {str(e)}")
        finally:
            self.mtk_process = None
            self.operation_in_progress = False

    def _stop_mtk_command(self):
        """停止当前MTK命令"""
        if self.mtk_process and self.mtk_process.poll() is None:
            try:
                self.mtk_process.terminate()
                self.mtk_command_output.emit("命令已终止")
            except Exception as e:
                self.mtk_command_output.emit(f"终止命令失败: {str(e)}")
        else:
            self.mtk_command_output.emit("没有正在执行的命令")

    def _unlock_bootloader(self):
        """解锁Bootloader"""
        if self.operation_in_progress:
            return

        reply = QMessageBox.warning(
            self, "警告",
            "解锁Bootloader会清除设备上的所有数据!\n\n确定要继续吗?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        self.operation_in_progress = True
        self.log_signal.emit("正在尝试解锁Bootloader...")

        try:
            success, error = self.flashing_toolbox.platform_tools.unlock_bootloader()
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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        self.operation_in_progress = True
        self.log_signal.emit("正在尝试锁定Bootloader...")

        try:
            success, error = self.flashing_toolbox.platform_tools.lock_bootloader()
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

        # 检查Bootloader锁定状态
        if self.current_mode == "fastboot":
            result = self.flashing_toolbox.platform_tools.execute_fastboot_command("oem device-info")
            if result and "Device unlocked: false" in result['output']:
                reply = QMessageBox.question(
                    self, "Bootloader已锁定",
                    "设备Bootloader已锁定，刷机前需要解锁。是否现在解锁?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._unlock_bootloader()
                    return

        reply = QMessageBox.question(
            self, "确认",
            "确定要刷机吗? 此操作有风险!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        self.operation_in_progress = True
        threading.Thread(target=self._execute_xiaomi_flash, daemon=True).start()

    def _execute_xiaomi_flash(self):
        pass

    def _start_recovery_flash(self):
        """开始Recovery卡刷"""
        if self.operation_in_progress or not self.recovery_file_path:
            return

        # 检查设备状态
        if self.current_mode != "adb":
            QMessageBox.warning(self, "警告", "设备未处于ADB模式，无法进行卡刷")
            return

        reply = QMessageBox.question(
            self, "确认",
            "确定要进行Recovery卡刷吗?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        self.operation_in_progress = True
        threading.Thread(target=self._execute_recovery_flash, daemon=True).start()

    def _install_app(self):
        """安装应用"""
        if self.operation_in_progress or not hasattr(self, 'app_path'):
            return

        self.operation_in_progress = True
        self.log_signal.emit(f"正在安装应用: {self.app_path}")

        try:
            result = self.flashing_toolbox.platform_tools.execute_adb_command(f"install -r \"{self.app_path}\"")
            if result and result['success']:
                self.log_signal.emit("应用安装成功")
            else:
                error = result['error'] if result else "未知错误"
                self.log_signal.emit(f"应用安装失败: {error}")
        except Exception as e:
            self.log_signal.emit(f"应用安装异常: {str(e)}")
        finally:
            self.operation_in_progress = False

    def _uninstall_app(self):
        """卸载应用"""
        if self.operation_in_progress:
            return

        package_name = self.package_name_input.text().strip()
        if not package_name:
            self.log_signal.emit("请输入包名")
            return

        self.operation_in_progress = True
        self.log_signal.emit(f"正在卸载应用: {package_name}")

        try:
            result = self.flashing_toolbox.platform_tools.execute_adb_command(f"uninstall {package_name}")
            if result and result['success']:
                self.log_signal.emit("应用卸载成功")
            else:
                error = result['error'] if result else "未知错误"
                self.log_signal.emit(f"应用卸载失败: {error}")
        except Exception as e:
            self.log_signal.emit(f"应用卸载异常: {str(e)}")
        finally:
            self.operation_in_progress = False

    def _refresh_app_list(self):
        """刷新应用列表"""
        if self.operation_in_progress:
            return

        self.operation_in_progress = True
        self.log_signal.emit("正在获取应用列表...")

        try:
            result = self.flashing_toolbox.platform_tools.execute_adb_command("shell pm list packages")
            if result and result['success']:
                self.app_list.clear()
                packages = result['output'].splitlines()
                for package in packages:
                    if package.startswith("package:"):
                        self.app_list.addItem(package[8:])
                self.log_signal.emit(f"已加载 {len(packages)} 个应用")
            else:
                self.log_signal.emit("获取应用列表失败")
        except Exception as e:
            self.log_signal.emit(f"获取应用列表异常: {str(e)}")
        finally:
            self.operation_in_progress = False

    def _manage_ui_component(self):
        """管理系统界面组件"""
        sender = self.sender()
        component = sender.property("component")
        self.log_signal.emit(f"正在管理组件: {component}")
        self.ui_log.appendPlainText(f"已选择组件: {component}")

        # 根据组件执行相应的操作
        if component == "statusbar":
            self._toggle_statusbar()
        elif component == "navbar":
            self._toggle_navbar()
        elif component == "lockscreen":
            self._toggle_lockscreen()
        elif component == "launcher":
            self._toggle_launcher()
        elif component == "settings":
            self._toggle_settings()
        elif component == "notification":
            self._toggle_notification()

    def _toggle_statusbar(self):
        """切换状态栏可见性"""
        self.log_signal.emit("切换状态栏可见性...")
        result = self.flashing_toolbox.platform_tools.execute_adb_command("shell settings put global policy_control immersive.status=*")
        if result and result['success']:
            self.ui_log.appendPlainText("状态栏已隐藏")
            self.log_signal.emit("状态栏已隐藏")
        else:
            self.ui_log.appendPlainText("操作失败")
            self.log_signal.emit("切换状态栏失败")

    def _toggle_navbar(self):
        """切换导航栏可见性"""
        self.log_signal.emit("切换导航栏可见性...")
        result = self.flashing_toolbox.platform_tools.execute_adb_command("shell settings put global policy_control immersive.navigation=*")
        if result and result['success']:
            self.ui_log.appendPlainText("导航栏已隐藏")
            self.log_signal.emit("导航栏已隐藏")
        else:
            self.ui_log.appendPlainText("操作失败")
            self.log_signal.emit("切换导航栏失败")

    def _toggle_lockscreen(self):
        """切换锁屏样式"""
        self.log_signal.emit("切换锁屏样式...")
        self.ui_log.appendPlainText("锁屏样式已切换")
        self.log_signal.emit("锁屏样式已切换")

    def _toggle_launcher(self):
        """切换启动器"""
        self.log_signal.emit("切换启动器...")
        self.ui_log.appendPlainText("启动器已切换")
        self.log_signal.emit("启动器已切换")

    def _toggle_settings(self):
        """重置设置应用"""
        self.log_signal.emit("重置设置应用...")
        result = self.flashing_toolbox.platform_tools.execute_adb_command("shell pm clear com.android.settings")
        if result and result['success']:
            self.ui_log.appendPlainText("设置应用已重置")
            self.log_signal.emit("设置应用已重置")
        else:
            self.ui_log.appendPlainText("操作失败")
            self.log_signal.emit("重置设置应用失败")

    def _toggle_notification(self):
        """切换通知中心样式"""
        self.log_signal.emit("切换通知中心样式...")
        self.ui_log.appendPlainText("通知中心样式已切换")
        self.log_signal.emit("通知中心样式已切换")

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

                # 检查文件大小
                file_size = os.path.getsize(self.firmware_path)
                if file_size > 100 * 1024 * 1024:  # 大于100MB
                    self.log_signal.emit(f"大文件刷写 ({file_size // 1024 // 1024}MB)，请保持USB连接稳定...")

                if self.flashing_toolbox.platform_tools.flash_partition(partition, self.firmware_path):
                    self.log_signal.emit(f"{partition} 分区刷入成功!")
                    self.progress_signal.emit(100)
                else:
                    self.log_signal.emit(f"刷入失败: {self.flashing_toolbox.platform_tools.last_error}")
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

                            # 检查文件大小
                            file_size = os.path.getsize(img_file)
                            if file_size > 100 * 1024 * 1024:  # 大于100MB
                                self.log_signal.emit(f"大文件刷写 ({file_size // 1024 // 1024}MB)，请保持USB连接稳定...")

                            if self.flashing_toolbox.platform_tools.flash_partition(partition_name, img_file):
                                self.log_signal.emit(f"{partition_name} 刷写成功")
                            else:
                                self.log_signal.emit(f"{partition_name} 刷写失败: {self.flashing_toolbox.platform_tools.last_error}")

                            # 更新进度
                            progress = int((i + 1) / total * 100)
                            self.progress_signal.emit(progress)

                        self.log_signal.emit("所有分区刷写完成")
                    else:
                        # 查找特定分区镜像
                        img_file = None
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file.lower().endswith(f"{partition}.img") or file.lower().endswith(
                                        f"{partition}.bin"):
                                    img_file = os.path.join(root, file)
                                    break
                            if img_file:
                                break

                        if img_file:
                            self.log_signal.emit(f"找到分区镜像: {os.path.basename(img_file)}")
                            self.progress_signal.emit(50)

                            # 检查文件大小
                            file_size = os.path.getsize(img_file)
                            if file_size > 100 * 1024 * 1024:  # 大于100MB
                                self.log_signal.emit(f"大文件刷写 ({file_size // 1024 // 1024}MB)，请保持USB连接稳定...")

                            if self.flashing_toolbox.platform_tools.flash_partition(partition, img_file):
                                self.log_signal.emit(f"{partition} 分区刷入成功!")
                                self.progress_signal.emit(100)
                            else:
                                self.log_signal.emit(f"{partition} 分区刷入失败: {self.flashing_toolbox.platform_tools.last_error}")
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

    def _execute_xiaomi_flashing(self):
        """执行小米线刷"""
        try:
            self.log_signal.emit("开始小米线刷...")
            self.xiaomi_progress_bar.setValue(0)

            # 解压线刷包
            temp_dir = tempfile.mkdtemp(prefix="xiaomi_flash_")
            try:
                if self.xiaomi_flash_path.endswith('.tgz') or self.xiaomi_flash_path.endswith('.tar.gz'):
                    with tarfile.open(self.xiaomi_flash_path, 'r:gz') as tar_ref:
                        tar_ref.extractall(temp_dir)
                else:
                    self.log_signal.emit("不支持的小米线刷包格式")
                    return

                # 查找flash_all脚本
                flash_script = None
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.startswith("flash_all") and (file.endswith(".bat") or file.endswith(".sh")):
                            flash_script = os.path.join(root, file)
                            break

                if flash_script:
                    self.log_signal.emit(f"正在执行刷机脚本: {os.path.basename(flash_script)}")

                    # 根据操作系统选择执行方式
                    if platform.system().lower() == "windows" and flash_script.endswith(".bat"):
                        cmd = ["cmd", "/c", flash_script]
                    elif flash_script.endswith(".sh"):
                        cmd = ["bash", flash_script]
                    else:
                        cmd = [sys.executable, flash_script]

                    # 执行刷机命令
                    process = subprocess.Popen(cmd, cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               text=True, encoding='utf-8', errors='ignore')

                    # 读取输出并更新日志
                    while True:
                        output = process.stdout.readline()
                        if output == '' and process.poll() is not None:
                            break
                        if output:
                            self.log_signal.emit(output.strip())

                    # 检查结果
                    if process.returncode == 0:
                        self.log_signal.emit("小米线刷完成!")
                        self.xiaomi_progress_bar.setValue(100)
                    else:
                        self.log_signal.emit(f"小米线刷失败，返回码: {process.returncode}")
                        self.xiaomi_progress_bar.setValue(0)
                else:
                    self.log_signal.emit("在刷机包中未找到flash_all脚本")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            self.log_signal.emit(f"小米线刷失败: {str(e)}")
            self.xiaomi_progress_bar.setValue(0)
        finally:
            self.operation_in_progress = False

    def _execute_recovery_flash(self):
        """执行Recovery卡刷"""
        try:
            self.log_signal.emit("开始Recovery卡刷...")
            self.recovery_progress_bar.setValue(0)

            # 推送卡刷包到设备
            self.log_signal.emit("推送卡刷包到设备...")
            remote_path = "/sdcard/recovery_flash.zip"
            result = self.flashing_toolbox.platform_tools.execute_adb_command(f"push \"{self.recovery_file_path}\" {remote_path}")

            if result and result['success']:
                self.recovery_progress_bar.setValue(30)
                self.log_signal.emit("卡刷包推送成功")

                # 进入Recovery模式
                self.log_signal.emit("重启设备到Recovery模式...")
                success, error = self.flashing_toolbox.platform_tools.adb_reboot("recovery")
                if success:
                    self.recovery_progress_bar.setValue(50)
                    self.log_signal.emit("设备已重启到Recovery模式")

                    # 等待设备进入Recovery
                    time.sleep(10)

                    # 执行刷机命令
                    self.log_signal.emit("开始刷入卡刷包...")
                    result = self.flashing_toolbox.platform_tools.execute_adb_command("recovery --update_package=/sdcard/recovery_flash.zip")
                    if result and result['success']:
                        self.recovery_progress_bar.setValue(100)
                        self.log_signal.emit("卡刷包刷入成功! 设备将自动重启")
                    else:
                        self.log_signal.emit("卡刷包刷入失败")
                else:
                    self.log_signal.emit(f"重启到Recovery失败: {error}")
            else:
                self.log_signal.emit("卡刷包推送失败")
        except Exception as e:
            self.log_signal.emit(f"Recovery卡刷失败: {str(e)}")
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

            # 终止正在运行的MTK命令
            if self.mtk_process and self.mtk_process.poll() is None:
                try:
                    self.mtk_process.terminate()
                except:
                    pass
            event.accept()
