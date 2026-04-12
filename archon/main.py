"""
Archon Desktop - AI编程助手
主程序入口
"""

import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from archon.main_window import MainWindow


def main():
    """程序入口"""
    # 启用高DPI支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Archon")
    app.setOrganizationName("Archon")

    # 设置全局样式
    app.setStyle("Fusion")

    # 创建主窗口
    window = MainWindow()
    window.show()

    # 优雅退出处理
    def signal_handler():
        window.close()
        app.quit()

    signal.signal(signal.SIGINT, lambda s, f: signal_handler())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()