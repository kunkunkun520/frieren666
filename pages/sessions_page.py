"""
会话历史页面
"""
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QTextBrowser, QLineEdit, QGroupBox, QDialog,
    QFormLayout, QMessageBox, QInputDialog, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from utils.session_manager import SessionManager, Session


class NewSessionDialog(QDialog):
    """新建会话对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建会话")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如: 电商网站项目")
        form_layout.addRow("会话名称:", self.name_input)

        self.task_input = QTextEdit()
        self.task_input.setPlaceholderText(
            "描述你想要创建的项目...\n\n"
            "例如：\n"
            "- 帮我写一个电商网站包括vip用户专属价格\n"
            "- 创建一个用户管理系统的后端API"
        )
        self.task_input.setMinimumHeight(150)
        form_layout.addRow("任务描述:", self.task_input)

        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        self.create_btn = QPushButton("创建并开始")
        self.create_btn.setStyleSheet("background-color: #0078d4; color: white;")
        self.cancel_btn = QPushButton("取消")

        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.create_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def get_session_data(self):
        return self.name_input.text().strip(), self.task_input.toPlainText().strip()


class SessionsPage(QWidget):
    """会话历史页面"""

    new_session_signal = Signal(str, str)  # session_name, user_task
    load_session_signal = Signal(object)    # Session object

    def __init__(self, session_manager: SessionManager):
        super().__init__()
        self.session_manager = session_manager
        self.setup_ui()
        self.refresh_session_list()

    def setup_ui(self):
        layout = QHBoxLayout(self)

        # 左侧：会话列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 新建会话按钮
        self.new_btn = QPushButton("➕ 新建会话")
        self.new_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 10px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.new_btn.clicked.connect(self.on_new_session)
        left_layout.addWidget(self.new_btn)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索会话...")
        self.search_input.textChanged.connect(self.on_search)
        left_layout.addWidget(self.search_input)

        # 会话列表
        self.session_list = QListWidget()
        self.session_list.itemDoubleClicked.connect(self.on_session_double_clicked)
        left_layout.addWidget(self.session_list)

        # 删除按钮
        self.delete_btn = QPushButton("🗑️ 删除选中会话")
        self.delete_btn.clicked.connect(self.on_delete_session)
        left_layout.addWidget(self.delete_btn)

        layout.addWidget(left_widget, stretch=1)

        # 右侧：详情
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        detail_group = QGroupBox("会话详情")
        detail_layout = QVBoxLayout(detail_group)

        self.detail_browser = QTextBrowser()
        self.detail_browser.setPlaceholderText("点击左侧会话查看详情")
        detail_layout.addWidget(self.detail_browser)

        right_layout.addWidget(detail_group)

        # 加载按钮
        self.load_btn = QPushButton("📂 加载此会话")
        self.load_btn.setStyleSheet("background-color: #0078d4; color: white;")
        self.load_btn.clicked.connect(self.on_load_selected)
        right_layout.addWidget(self.load_btn)

        layout.addWidget(right_widget, stretch=1)

        self.current_sessions = []
        self.selected_session = None

    def refresh_session_list(self, filter_text=""):
        """刷新会话列表"""
        self.session_list.clear()
        sessions = self.session_manager.list_sessions()
        self.current_sessions = []

        for session in sessions:
            if filter_text and filter_text.lower() not in session.name.lower() and filter_text.lower() not in session.user_task.lower():
                continue

            self.current_sessions.append(session)

            # 状态图标
            status_icon = {
                "pending": "⏳",
                "running": "🔄",
                "completed": "✅",
                "failed": "❌"
            }.get(session.status, "📁")

            created_time = datetime.fromisoformat(session.created_at).strftime("%Y-%m-%d %H:%M")
            item_text = f"{status_icon} {session.name}\n   📅 {created_time} | 📁 {session.steps_completed}/{session.total_steps}步"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, session.session_id)
            self.session_list.addItem(item)

    def on_search(self, text):
        """搜索会话"""
        self.refresh_session_list(text)

    def on_new_session(self):
        """新建会话"""
        dialog = NewSessionDialog(self)
        if dialog.exec() == QDialog.Accepted:
            name, task = dialog.get_session_data()
            if not name:
                QMessageBox.warning(self, "警告", "请输入会话名称")
                return
            if not task:
                QMessageBox.warning(self, "警告", "请输入任务描述")
                return
            self.new_session_signal.emit(name, task)

    def on_session_double_clicked(self, item):
        """双击会话加载"""
        session_id = item.data(Qt.UserRole)
        session = self.session_manager.load_session(session_id)
        if session:
            self.selected_session = session
            self.show_session_detail(session)

    def on_load_selected(self):
        """加载选中的会话"""
        current_item = self.session_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个会话")
            return
        session_id = current_item.data(Qt.UserRole)
        session = self.session_manager.load_session(session_id)
        if session:
            self.load_session_signal.emit(session)

    def show_session_detail(self, session: Session):
        """显示会话详情"""
        detail = f"""
<h3>{session.name}</h3>
<hr>
<p><b>会话ID:</b> {session.session_id}</p>
<p><b>创建时间:</b> {session.created_at}</p>
<p><b>最后更新:</b> {session.updated_at}</p>
<p><b>状态:</b> {session.status}</p>
<p><b>进度:</b> {session.steps_completed}/{session.total_steps} 步骤</p>
<p><b>任务描述:</b></p>
<p style="background-color: #2d2d2d; padding: 10px; border-radius: 4px;">{session.user_task}</p>
<p><b>工作区路径:</b><br><code>{session.workspace_path}</code></p>
        """
        self.detail_browser.setHtml(detail)

    def on_delete_session(self):
        """删除会话"""
        current_item = self.session_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个会话")
            return

        reply = QMessageBox.question(self, "确认删除", "确定要删除这个会话吗？所有文件将被永久删除。",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            session_id = current_item.data(Qt.UserRole)
            self.session_manager.delete_session(session_id)
            self.refresh_session_list()
            self.detail_browser.clear()