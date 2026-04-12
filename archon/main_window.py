"""
Archon Desktop - 主窗口
"""
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QPushButton, QLabel, QStatusBar,
    QFrame
)
from PySide6.QtCore import Qt
from pages.files_page import FilesPage
from pages.console_page import ConsolePage
from pages.sessions_page import SessionsPage

from pages.settings_page import SettingsPage
from pages.stats_page import StatsPage
from utils.session_manager import SessionManager
from workers.agent_worker import AgentWorker


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Archon - AI编程助手")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        self.worker = None

        # 初始化会话管理器
        self.session_manager = SessionManager()

        # 设置中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧边栏
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        # 右侧内容区域
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        # 创建页面
        self.pages = {
            "sessions": SessionsPage(self.session_manager),
            "console": ConsolePage(),
            "files": FilesPage(),
            "settings": SettingsPage(),
            "stats": StatsPage()
        }

        self.stack.addWidget(self.pages["sessions"])  # index 0
        self.stack.addWidget(self.pages["console"])   # index 1
        self.stack.addWidget(self.pages["files"])     # index 2
        self.stack.addWidget(self.pages["settings"])  # index 3
        self.stack.addWidget(self.pages["stats"])     # index 4

        # 默认显示会话页面
        self.stack.setCurrentIndex(0)

        # 连接会话页面信号
        sessions_page = self.pages["sessions"]
        sessions_page.new_session_signal.connect(self.on_new_session)
        sessions_page.load_session_signal.connect(self.on_load_session)

        # 连接控制台信号
        console_page = self.pages["console"]
        console_page.execute_signal.connect(self.on_execute_task)

        # 创建状态栏
        self._create_status_bar()

    def _create_sidebar(self):
        """创建左侧导航栏"""
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setFrameShape(QFrame.StyledPanel)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-right: 1px solid #3d3d3d;
            }
            QPushButton {
                text-align: left;
                padding: 12px 16px;
                font-size: 14px;
                border: none;
                background-color: transparent;
                color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QPushButton:checked {
                background-color: #4a4a4a;
                border-left: 3px solid #0078d4;
                color: white;
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 20, 0, 0)
        layout.setSpacing(0)

        logo_label = QLabel("Archon")
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #0078d4;
                padding: 16px;
            }
        """)
        layout.addWidget(logo_label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #3d3d3d;")
        layout.addWidget(line)

        nav_buttons = [
            ("💬 会话", 0),
            ("🎮 控制台", 1),
            ("📁 文件", 2),
            ("⚙️ 设置", 3),
            ("📊 统计", 4),
        ]

        self.nav_buttons = []
        for text, index in nav_buttons:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, i=index: self._switch_page(i))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)

        if self.nav_buttons:
            self.nav_buttons[0].setChecked(True)

        layout.addStretch()
        return sidebar

    def _switch_page(self, index):
        """切换页面"""
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def _create_status_bar(self):
        """创建状态栏"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self.status_label = QLabel("● 就绪")
        self.status_label.setStyleSheet("QLabel { padding: 0 8px; }")
        status_bar.addWidget(self.status_label)

        status_bar.addWidget(self._create_separator())

        self.session_label = QLabel("📁 未选择会话")
        status_bar.addWidget(self.session_label)

        status_bar.addWidget(self._create_separator())

        self.model_label = QLabel("🧠 模型: --")
        status_bar.addWidget(self.model_label)

        status_bar.addPermanentWidget(QLabel("Archon v1.0.0"))

    def _create_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #3d3d3d;")
        sep.setFixedSize(1, 20)
        return sep

    def on_new_session(self, session_name, user_task):
        """创建新会话"""
        session = self.session_manager.create_session(session_name, user_task)

        console = self.pages["console"]
        workspace_path = Path(session.workspace_path)
        console.set_project_path(workspace_path)
        console.task_input.setPlainText(user_task)
        console.clear_log()
        console.update_plan([])
        console.set_running(True)

        files_page = self.pages["files"]
        files_page.set_root_path(workspace_path)

        self.session_label.setText(f"📁 {session_name}")

        # 切换到控制台页面
        self._switch_page(1)

        # 创建 Worker 并生成计划（不自动执行）
        from workers.agent_worker import AgentWorker
        self.worker = AgentWorker(user_task, workspace_path)
        console.set_worker(self.worker)
        self.worker.start()

    def on_load_session(self, session):
        """加载已有会话"""
        from workers.agent_worker import AgentWorker

        console = self.pages["console"]
        workspace_path = Path(session.workspace_path)

        # 设置工作区路径
        console.set_project_path(workspace_path)
        console.task_input.setPlainText(session.user_task)
        console.refresh_file_tree()
        console.clear_log()
        console.add_log(f"📁 已加载会话: {session.name}", "success")
        console.add_log(f"工作区: {workspace_path}", "info")

        # 更新文件页面
        files_page = self.pages["files"]
        files_page.set_root_path(workspace_path)

        # 更新状态栏
        self.session_label.setText(f"📁 {session.name}")

        # 创建 Worker（加载模式，不生成新计划）
        self.worker = AgentWorker(session.user_task, workspace_path, is_load_mode=True)
        console.set_worker(self.worker)
        self.worker.start()

        # 切换到控制台页面
        self._switch_page(1)
        self.status_label.setText(f"● 已加载会话: {session.name}")

    def on_execute_task(self, task, workspace_path=None):
        """执行任务"""
        if not task.strip():
            return

        console = self.pages["console"]

        # 如果没有传入workspace_path，使用当前会话的工作区
        if workspace_path is None:
            # 从控制台获取当前工作区
            if console.project_path:
                workspace_path = console.project_path
            else:
                # 创建新会话
                session_name = f"任务_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                session = self.session_manager.create_session(session_name, task)
                workspace_path = Path(session.workspace_path)
                console.set_project_path(workspace_path)
                files_page = self.pages["files"]
                files_page.set_root_path(workspace_path)
                self.session_label.setText(f"📁 {session_name}")

        console.add_log(f"📝 新任务: {task}", "user")
        console.update_plan([])
        console.set_running(True)

        # 创建并启动 Worker
        self.worker = AgentWorker(task, workspace_path)
        console.set_worker(self.worker)
        self.worker.start()

    def update_status(self, message):
        self.status_label.setText(f"● {message}")