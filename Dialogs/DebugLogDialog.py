from PySide6.QtCore import QThread, QMetaObject, Q_ARG, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout,
                               QPushButton, QDialog,
                               QTextEdit, QFileDialog, QMessageBox, QApplication)


class DebugLogDialog(QDialog):
    """Debug日志对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("调试日志")
        self.setWindowIcon(QIcon(":/icons/debug.png"))
        self.setGeometry(400, 400, 800, 600)

        layout = QVBoxLayout()

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            font-family: monospace; 
            font-size: 10pt; 
            background-color: #2c2c2c; 
            color: #e0e0e0;
            border-radius: 5px;
            padding: 5px;
        """)

        # 添加按钮
        btn_layout = QHBoxLayout()
        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.setStyleSheet("padding: 6px; border-radius: 5px;")
        self.clear_btn.clicked.connect(self.clear_log)
        self.save_btn = QPushButton("保存日志")
        self.save_btn.setStyleSheet("padding: 6px; border-radius: 5px;")
        self.save_btn.clicked.connect(self.save_log)
        self.close_btn = QPushButton("关闭")
        self.close_btn.setStyleSheet("""
            background-color: #f44336; 
            color: white; 
            padding: 6px;
            border-radius: 5px;
        """)
        self.close_btn.clicked.connect(self.close)

        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)

        layout.addWidget(self.log_output)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def append_log(self, message):
        """安全添加日志 - 修复版本"""
        # 确保在主线程执行
        if not QThread.currentThread() is QApplication.instance().thread():
            QMetaObject.invokeMethod(self, b"append_log", Qt.ConnectionType.QueuedConnection,
                                     Q_ARG("QString", message))
            return

        # 使用文本追加而不是操作光标
        self.log_output.append(message)

    def clear_log(self):
        """清空日志"""
        self.log_output.clear()

    def save_log(self):
        """保存日志到文件"""
        file_path, _ = QFileDialog.getSaveFileName(self, "保存日志", "", "文本文件 (*.txt);;所有文件 (*)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_output.toPlainText())
                QMessageBox.information(self, "成功", "日志已保存成功!")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存日志失败: {str(e)}")