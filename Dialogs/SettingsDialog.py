from PySide6.QtCore import QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout,
                               QPushButton, QDialog,
                               QFileDialog, QGroupBox, QLineEdit, QComboBox)

class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowIcon(QIcon(":/icons/settings.png"))
        self.setGeometry(200, 200, 500, 400)

        self.settings = QSettings("PythonFlashTools", "FlashTool")

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # ADB路径设置
        adb_group = QGroupBox("ADB设置")
        adb_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        adb_layout = QVBoxLayout()

        self.adb_path_edit = QLineEdit()
        self.adb_path_edit.setPlaceholderText("自动检测或自定义ADB路径")
        adb_browse_btn = QPushButton("浏览...")
        adb_browse_btn.setStyleSheet("padding: 5px;")
        adb_browse_btn.clicked.connect(self._browse_adb_path)

        adb_path_layout = QHBoxLayout()
        adb_path_layout.addWidget(self.adb_path_edit)
        adb_path_layout.addWidget(adb_browse_btn)

        adb_layout.addLayout(adb_path_layout)
        adb_group.setLayout(adb_layout)

        # Fastboot路径设置
        fastboot_group = QGroupBox("Fastboot设置")
        fastboot_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        fastboot_layout = QVBoxLayout()

        self.fastboot_path_edit = QLineEdit()
        self.fastboot_path_edit.setPlaceholderText("自动检测或自定义Fastboot路径")
        fastboot_browse_btn = QPushButton("浏览...")
        fastboot_browse_btn.setStyleSheet("padding: 5px;")
        fastboot_browse_btn.clicked.connect(self._browse_fastboot_path)

        fastboot_path_layout = QHBoxLayout()
        fastboot_path_layout.addWidget(self.fastboot_path_edit)
        fastboot_path_layout.addWidget(fastboot_browse_btn)

        fastboot_layout.addLayout(fastboot_path_layout)
        fastboot_group.setLayout(fastboot_layout)

        # MTKClient路径设置
        mtk_group = QGroupBox("MTKClient设置")
        mtk_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        mtk_layout = QVBoxLayout()

        self.mtk_path_edit = QLineEdit()
        self.mtk_path_edit.setPlaceholderText("自动检测或自定义MTKClient路径")
        mtk_browse_btn = QPushButton("浏览...")
        mtk_browse_btn.setStyleSheet("padding: 5px;")
        mtk_browse_btn.clicked.connect(self._browse_mtk_path)

        mtk_path_layout = QHBoxLayout()
        mtk_path_layout.addWidget(self.mtk_path_edit)
        mtk_path_layout.addWidget(mtk_browse_btn)

        mtk_layout.addLayout(mtk_path_layout)
        mtk_group.setLayout(mtk_layout)

        # 主题设置
        theme_group = QGroupBox("主题设置")
        theme_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        theme_layout = QVBoxLayout()

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["春 (绿白)", "夏 (蓝白)", "秋 (橙白)", "冬 (纯白)"])
        self.theme_combo.setStyleSheet("padding: 5px;")

        theme_layout.addWidget(self.theme_combo)
        theme_group.setLayout(theme_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        save_btn.clicked.connect(self._save_settings)
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("background-color: #f44336; color: white; padding: 8px;")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)

        # 加载当前设置
        self._load_settings()

        # 组装布局
        layout.addWidget(adb_group)
        layout.addWidget(fastboot_group)
        layout.addWidget(mtk_group)
        layout.addWidget(theme_group)
        layout.addStretch()
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

    def _browse_mtk_path(self):
        """浏览MTKClient路径"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择MTKClient可执行文件", "",
            "Python文件 (*.py);;所有文件 (*)")

        if file_path:
            self.mtk_path_edit.setText(file_path)

    def _load_settings(self):
        """加载设置"""
        self.adb_path_edit.setText(str(self.settings.value("adb_path", "")))
        self.fastboot_path_edit.setText(str(self.settings.value("fastboot_path", "")))
        self.mtk_path_edit.setText(str(self.settings.value("mtk_path", "")))
        theme = self.settings.value("theme", "夏 (蓝白)")
        index = self.theme_combo.findText(str(theme))
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

    def _save_settings(self):
        """保存设置"""
        self.settings.setValue("adb_path", self.adb_path_edit.text())
        self.settings.setValue("fastboot_path", self.fastboot_path_edit.text())
        self.settings.setValue("mtk_path", self.mtk_path_edit.text())
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.accept()