"""
Archon Desktop - 主窗口
"""

from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStatusBar, QFrame, QMessageBox
)
from PySide6.QtCore import Qt

from pages.home_page import HomePage
from pages.console_page import ConsolePage
from pages.settings_page import SettingsPage
from utils.session_manager import SessionManager
from workers.agent_worker import AgentWorker


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Archon - AI编程助手")
        self.setMinimumSize(1400, 900)
        self.resize(1600, 1000)
        self.worker = None

        self.session_manager = SessionManager()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("background-color: #1e1e1e;")

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.home_page = HomePage(self.session_manager)
        self.console_page = ConsolePage()
        self.settings_page = SettingsPage()

        main_layout.addWidget(self._create_top_nav())

        self.page_container = QWidget()
        self.page_container.setStyleSheet("background: #1e1e1e;")
        self.page_layout = QVBoxLayout(self.page_container)
        self.page_layout.setContentsMargins(0, 0, 0, 0)
        self.page_layout.setSpacing(0)
        main_layout.addWidget(self.page_container, stretch=1)

        self.current_page = None
        self._show_page(self.home_page)

        main_layout.addWidget(self._create_status_bar())

        self._connect_signals()
        self.nav_buttons[0][0].setChecked(True)

        print("MainWindow 初始化完成")

    def _create_top_nav(self):
        nav_frame = QFrame()
        nav_frame.setFixedHeight(50)
        nav_frame.setStyleSheet("""
            QFrame {
                background: rgba(37, 37, 38, 0.95);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)

        layout = QHBoxLayout(nav_frame)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(0)

        logo = QLabel("✨ Archon")
        logo.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #13a10e;
                padding-right: 30px;
            }
        """)
        layout.addWidget(logo)

        self.nav_buttons = []
        nav_items = [
            ("🏠 首页", self.home_page),
            ("🎮 控制台", self.console_page),
            ("⚙️ 设置", self.settings_page),
        ]

        for text, page in nav_items:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, p=page: self._switch_page(p))
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-bottom: 2px solid transparent;
                    padding: 12px 24px;
                    color: #a0a0a0;
                    font-size: 14px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    color: #e0e0e0;
                    border-bottom-color: rgba(255, 255, 255, 0.2);
                }
                QPushButton:checked {
                    color: #13a10e;
                    border-bottom-color: #13a10e;
                }
            """)
            layout.addWidget(btn)
            self.nav_buttons.append((btn, page))

        layout.addStretch()

        self.connection_status = QLabel("● 已连接")
        self.connection_status.setStyleSheet("color: #6a9955; padding: 0 15px;")
        layout.addWidget(self.connection_status)

        return nav_frame

    def _create_status_bar(self):
        status_bar = QStatusBar()
        status_bar.setStyleSheet("""
            QStatusBar {
                background: rgba(30, 30, 30, 0.95);
                border-top: 1px solid rgba(255, 255, 255, 0.05);
                color: #a0a0a0;
                min-height: 28px;
            }
        """)
        self.setStatusBar(status_bar)

        self.status_label = QLabel("● 就绪")
        self.status_label.setStyleSheet("color: #6a9955; padding: 0 12px;")
        status_bar.addWidget(self.status_label)

        status_bar.addWidget(self._create_separator())

        self.session_label = QLabel("📁 未选择会话")
        self.session_label.setStyleSheet("padding: 0 12px;")
        status_bar.addWidget(self.session_label)

        status_bar.addWidget(self._create_separator())

        self.model_label = QLabel("🧠 模型: Qwen3-Coder-30B")
        self.model_label.setStyleSheet("padding: 0 12px;")
        status_bar.addWidget(self.model_label)

        status_bar.addPermanentWidget(QLabel("Archon v1.0.0"))

        return status_bar

    def _create_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("background: rgba(255, 255, 255, 0.1);")
        sep.setFixedSize(1, 16)
        return sep

    def _show_page(self, page):
        if self.current_page == page:
            return
        if self.current_page:
            self.page_layout.removeWidget(self.current_page)
            self.current_page.setParent(None)
        self.page_layout.addWidget(page)
        self.current_page = page
        page.setVisible(True)

    def _switch_page(self, page):
        self._show_page(page)
        for btn, btn_page in self.nav_buttons:
            btn.setChecked(btn_page == page)

    def _connect_signals(self):
        self.home_page.new_session_signal.connect(self.on_new_session)
        self.home_page.load_session_signal.connect(self.on_load_session)
        self.home_page.open_folder_signal.connect(self.on_open_folder)

    def on_new_session(self, session_name, user_task, agents_md=""):
        print(f"创建新会话: {session_name}")
        session = self.session_manager.create_session(session_name, user_task)
        workspace_path = Path(session.workspace_path)

        if agents_md:
            agents_path = workspace_path / "AGENTS.md"
            agents_path.write_text(agents_md, encoding="utf-8")

        self.console_page.set_project_path(workspace_path)
        self.console_page.clear_log()
        self.console_page.update_plan([])

        self.session_label.setText(f"📁 {session_name}")

        self.worker = AgentWorker(
            user_task=user_task,
            workspace_path=workspace_path,
            is_load_mode=False
        )
        self.console_page.set_worker(self.worker)
        self.worker.start()

        self._switch_page(self.console_page)
        self.status_label.setText(f"● 创建新会话: {session_name}")

    def on_load_session(self, session):
        print(f"加载会话: {session.name}")
        workspace_path = Path(session.workspace_path)

        self.console_page.set_project_path(workspace_path)
        self.console_page.refresh_file_tree()
        self.console_page.clear_log()
        self.console_page.add_log(f"📁 已加载会话: {session.name}", "success")
        self.console_page.add_log(f"工作区: {workspace_path}", "info")

        self.session_label.setText(f"📁 {session.name}")

        self.worker = AgentWorker(
            user_task=session.user_task,
            workspace_path=workspace_path,
            is_load_mode=True,
            session_id=session.session_id
        )
        self.console_page.set_worker(self.worker)
        self.worker.start()

        self._switch_page(self.console_page)
        self.status_label.setText(f"● 已加载会话: {session.name}")

    def on_open_folder(self, folder_path):
        print(f"打开文件夹: {folder_path}")
        workspace_path = Path(folder_path)
        folder_name = workspace_path.name

        self.console_page.set_project_path(workspace_path)
        self.console_page.refresh_file_tree()
        self.console_page.clear_log()
        self.console_page.add_log(f"📂 已打开文件夹: {workspace_path}", "success")

        self.session_label.setText(f"📁 {folder_name}")

        self._switch_page(self.console_page)
        self.status_label.setText(f"● 打开文件夹: {folder_name}")

    def update_status(self, message):
        self.status_label.setText(f"● {message}")