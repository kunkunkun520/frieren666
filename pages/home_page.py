"""
首页 - 欢迎页 / 项目启动器 (最简测试版)
"""

from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFrame,
    QGridLayout, QDialog, QLineEdit, QFormLayout,
    QMessageBox, QFileDialog, QGroupBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from utils.session_manager import SessionManager


class NewSessionDialog(QDialog):
    """新建会话对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建会话")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setStyleSheet("""
            QDialog {
                background: #252526;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
            }
            QLineEdit, QTextEdit {
                background: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
                padding: 10px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #13a10e;
            }
            QPushButton {
                background: #0e639c;
                border: none;
                border-radius: 20px;
                padding: 10px 20px;
                color: white;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #1177bb;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        title = QLabel("✨ 创建新项目")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #ffffff; padding: 10px 0;")
        layout.addWidget(title)

        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如: 电商网站项目")
        form_layout.addRow("项目名称:", self.name_input)

        self.task_input = QTextEdit()
        self.task_input.setPlaceholderText(
            "描述你想要创建的项目...\n\n"
            "例如：\n"
            "• 创建一个用户管理系统，包含注册、登录、JWT认证\n"
            "• 写一个电商网站后端，包括商品管理、购物车、订单\n"
            "• 帮我搭建一个Flask博客API"
        )
        self.task_input.setMinimumHeight(180)
        form_layout.addRow("任务描述:", self.task_input)

        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d;
            }
            QPushButton:hover {
                background: #4d4d4d;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)

        self.create_btn = QPushButton("创建并开始")
        self.create_btn.setStyleSheet("""
            QPushButton {
                background: #13a10e;
            }
            QPushButton:hover {
                background: #16c60c;
            }
        """)
        self.create_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.create_btn)
        layout.addLayout(btn_layout)

    def get_session_data(self):
        return self.name_input.text().strip(), self.task_input.toPlainText().strip()


class ProjectCard(QFrame):
    """项目卡片"""

    clicked = Signal(dict)

    def __init__(self, session_data, parent=None):
        super().__init__(parent)
        self.session_data = session_data
        self.setup_ui()
        self.setCursor(Qt.PointingHandCursor)

    def setup_ui(self):
        self.setFixedSize(200, 140)
        self.setStyleSheet("""
            ProjectCard {
                background: #3d3d3d;
                border: 1px solid #4d4d4d;
                border-radius: 16px;
            }
            ProjectCard:hover {
                background: #4d4d4d;
                border-color: #13a10e;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QHBoxLayout()
        icon = QLabel("📁")
        icon.setStyleSheet("font-size: 24px;")
        header.addWidget(icon)

        name = QLabel(self.session_data.get("name", "未命名")[:15])
        name.setStyleSheet("color: #e0e0e0; font-size: 14px; font-weight: 500;")
        name.setWordWrap(True)
        header.addWidget(name, stretch=1)
        layout.addLayout(header)

        date_str = self.session_data.get("created_at", "")
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                date_str = dt.strftime("%Y-%m-%d")
            except:
                pass
        date = QLabel(f"📅 {date_str}")
        date.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(date)

        completed = self.session_data.get("steps_completed", 0)
        total = self.session_data.get("total_steps", 0)
        progress = QLabel(f"📊 {completed}/{total} 步骤")
        progress.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(progress)

        layout.addStretch()

    def mousePressEvent(self, event):
        self.clicked.emit(self.session_data)
        super().mousePressEvent(event)


class HomePage(QWidget):
    """首页 - 欢迎页 / 项目启动器"""

    new_session_signal = Signal(str, str)
    load_session_signal = Signal(object)
    open_folder_signal = Signal(str)

    def __init__(self, session_manager: SessionManager):
        super().__init__()
        self.session_manager = session_manager
        self.setup_ui()
        self.load_recent_projects()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(60, 40, 60, 40)
        main_layout.setSpacing(20)

        # 标题
        logo = QLabel("✨ Archon")
        logo.setFont(QFont("Segoe UI", 36, QFont.Bold))
        logo.setStyleSheet("color: #13a10e;")
        logo.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(logo)

        subtitle = QLabel("AI 编程助手 - 让 AI 像资深工程师一样工作")
        subtitle.setFont(QFont("Segoe UI", 14))
        subtitle.setStyleSheet("color: #a0a0a0;")
        subtitle.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(subtitle)

        main_layout.addSpacing(20)

        # 快速开始区域
        quick_group = QGroupBox("🚀 快速开始")
        quick_group.setStyleSheet("""
            QGroupBox {
                background: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 16px;
                padding: 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QGroupBox::title {
                color: #cccccc;
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
            }
        """)
        quick_layout = QVBoxLayout(quick_group)
        quick_layout.setSpacing(15)

        self.task_input = QTextEdit()
        self.task_input.setPlaceholderText("📝 输入任务描述...\n\n例如：创建一个用户管理系统，包含登录、注册、JWT认证")
        self.task_input.setMaximumHeight(80)
        self.task_input.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 12px;
                padding: 12px;
                color: #e0e0e0;
            }
            QTextEdit:focus {
                border-color: #13a10e;
            }
        """)
        quick_layout.addWidget(self.task_input)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        self.new_btn = QPushButton("✨ 开始新任务")
        self.new_btn.setCursor(Qt.PointingHandCursor)
        self.new_btn.setFixedHeight(45)
        self.new_btn.setStyleSheet("""
            QPushButton {
                background: #13a10e;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #1177bb;
            }
        """)
        self.new_btn.clicked.connect(self.on_new_task)

        self.open_btn = QPushButton("📂 打开已有项目")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.setFixedHeight(45)
        self.open_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d;
                border: 1px solid #4d4d4d;
                border-radius: 8px;
                padding: 10px 24px;
                color: #e0e0e0;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #1177bb;
                color: white;
            }
        """)
        self.open_btn.clicked.connect(self.on_open_folder)

        btn_layout.addWidget(self.new_btn)
        btn_layout.addWidget(self.open_btn)
        btn_layout.addStretch()
        quick_layout.addLayout(btn_layout)

        main_layout.addWidget(quick_group)

        # 最近项目区域
        recent_group = QGroupBox("📁 最近项目")
        recent_group.setStyleSheet("""
            QGroupBox {
                background: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 16px;
                padding: 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QGroupBox::title {
                color: #cccccc;
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
            }
        """)
        recent_layout = QVBoxLayout(recent_group)
        recent_layout.setSpacing(15)

        self.projects_container = QWidget()
        self.projects_grid = QGridLayout(self.projects_container)
        self.projects_grid.setContentsMargins(0, 0, 0, 0)
        self.projects_grid.setSpacing(15)
        recent_layout.addWidget(self.projects_container)

        self.no_projects_label = QLabel("暂无项目，点击「开始新任务」创建第一个项目")
        self.no_projects_label.setStyleSheet("color: #808080; font-size: 14px; padding: 20px;")
        self.no_projects_label.setAlignment(Qt.AlignCenter)
        self.no_projects_label.setVisible(False)
        recent_layout.addWidget(self.no_projects_label)

        self.browse_btn = QPushButton("📂 浏览所有项目...")
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #4ec9b0;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #ffffff;
                text-decoration: underline;
            }
        """)
        self.browse_btn.clicked.connect(self.on_browse_all)
        recent_layout.addWidget(self.browse_btn, alignment=Qt.AlignRight)

        main_layout.addWidget(recent_group)
        main_layout.addStretch()

    def load_recent_projects(self):
        for i in reversed(range(self.projects_grid.count())):
            widget = self.projects_grid.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        sessions = self.session_manager.list_sessions()[:4]

        if not sessions:
            self.no_projects_label.setVisible(True)
            return

        self.no_projects_label.setVisible(False)

        for i, session in enumerate(sessions):
            session_data = {
                "session_id": session.session_id,
                "name": session.name,
                "created_at": session.created_at,
                "steps_completed": session.steps_completed,
                "total_steps": session.total_steps,
                "workspace_path": session.workspace_path,
                "user_task": session.user_task,
            }
            card = ProjectCard(session_data)
            card.clicked.connect(self.on_project_clicked)
            row = i // 4
            col = i % 4
            self.projects_grid.addWidget(card, row, col)

    def on_new_task(self):
        task = self.task_input.toPlainText().strip()
        if not task:
            QMessageBox.warning(self, "提示", "请输入任务描述")
            return

        dialog = NewSessionDialog(self)
        dialog.task_input.setPlainText(task)
        if dialog.exec() == QDialog.Accepted:
            name, task = dialog.get_session_data()
            if not name:
                QMessageBox.warning(self, "提示", "请输入项目名称")
                return
            self.new_session_signal.emit(name, task)

    def on_open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择项目文件夹", str(Path.home()))
        if folder:
            self.open_folder_signal.emit(folder)

    def on_project_clicked(self, session_data):
        session_id = session_data["session_id"]
        session = self.session_manager.load_session(session_id)
        if session:
            self.load_session_signal.emit(session)

    def on_browse_all(self):
        from pages.sessions_page import SessionsPage
        dialog = QDialog(self)
        dialog.setWindowTitle("所有项目")
        dialog.setMinimumSize(700, 500)
        dialog.setStyleSheet("QDialog { background: #252526; }")
        layout = QVBoxLayout(dialog)
        sessions_page = SessionsPage(self.session_manager)
        sessions_page.new_session_signal.connect(self.new_session_signal)
        sessions_page.load_session_signal.connect(self.load_session_signal)
        sessions_page.load_session_signal.connect(lambda: dialog.accept())
        layout.addWidget(sessions_page)
        dialog.exec()
        self.load_recent_projects()