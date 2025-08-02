import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QColor
from PySide6.QtWidgets import (QApplication, QSplashScreen)

from FlashTool import FlashTool
from utils import install_python_dependencies

if __name__ == "__main__":
    # 检测并安装Python依赖
    install_python_dependencies()
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 设置全局字体为微软雅黑
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    # 创建启动画面
    splash_pix = QPixmap(800, 400)
    splash_pix.fill(QColor(45, 45, 45))
    splash = QSplashScreen(splash_pix)
    splash.setFont(font)
    splash.showMessage("正在初始化...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
    splash.show()
    app.processEvents()
    
    # 初始化主窗口
    tool = FlashTool(splash)
    
    # 关闭启动画面
    tool.show()
    splash.finish(tool)
    
    sys.exit(app.exec())