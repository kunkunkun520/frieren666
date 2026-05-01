"""
首页 - 欢迎页 / 项目启动器 (对话式初始化版)
"""

from pathlib import Path
from datetime import datetime
import json
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFrame,
    QDialog, QLineEdit, QFormLayout,
    QMessageBox, QFileDialog, QGroupBox, QTextBrowser, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QTextCursor

from utils.session_manager import SessionManager
from utils.llm_client import LLMClient
from utils.config import Config


class ProjectSetupDialog(QDialog):
    """项目初始化设置对话框 - 对话式"""

    def __init__(self, user_task: str, llm_client: LLMClient, parent=None):
        super().__init__(parent)
        self.user_task = user_task
        self.llm_client = llm_client
        self.conversation_history = []
        self.agents_md = None
        self.current_question = None

        self.setWindowTitle("项目初始化")
        self.setModal(True)
        self.setMinimumWidth(650)
        self.setMinimumHeight(750)
        self.setStyleSheet("""
            QDialog { background: #252526; }
            QLabel { color: #cccccc; }
            QTextEdit { background: #1e1e1e; border: 1px solid #3c3c3c; border-radius: 8px; padding: 12px; color: #e0e0e0; }
            QLineEdit { background: #1e1e1e; border: 1px solid #3c3c3c; border-radius: 20px; padding: 10px 16px; color: #e0e0e0; }
            QPushButton { background: #0e639c; border: none; border-radius: 20px; padding: 10px 20px; color: white; }
            QPushButton:hover { background: #1177bb; }
            QGroupBox { color: #cccccc; border: 1px solid #3c3c3c; border-radius: 8px; margin-top: 10px; padding-top: 16px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; }
        """)

        self.setup_ui()
        self.start_conversation()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        title = QLabel("🚀 项目初始化")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #ffffff;")
        layout.addWidget(title)

        task_label = QLabel("📋 你的任务:")
        task_label.setStyleSheet("color: #888; margin-top: 10px;")
        layout.addWidget(task_label)

        task_display = QTextEdit()
        task_display.setPlainText(self.user_task)
        task_display.setReadOnly(True)
        task_display.setMaximumHeight(80)
        layout.addWidget(task_display)

        chat_label = QLabel("💬 对话")
        chat_label.setStyleSheet("color: #888; margin-top: 10px;")
        layout.addWidget(chat_label)

        self.chat_browser = QTextBrowser()
        self.chat_browser.setOpenExternalLinks(True)
        self.chat_browser.setStyleSheet("QTextBrowser { background: #1e1e1e; border: 1px solid #3c3c3c; border-radius: 8px; padding: 12px; }")
        layout.addWidget(self.chat_browser, stretch=1)

        self.preview_group = QGroupBox("📄 AGENTS.md 预览")
        self.preview_group.setCheckable(True)
        self.preview_group.setChecked(False)
        preview_layout = QVBoxLayout(self.preview_group)
        self.preview_browser = QTextBrowser()
        self.preview_browser.setStyleSheet("QTextBrowser { background: #1e1e1e; border: none; font-family: Consolas, monospace; font-size: 12px; }")
        preview_layout.addWidget(self.preview_browser)
        layout.addWidget(self.preview_group)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("输入你的回答，或直接按回车跳过...")
        self.message_input.returnPressed.connect(self.send_message)
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.send_message)
        self.skip_btn = QPushButton("跳过")
        self.skip_btn.setStyleSheet("background: #3d3d3d;")
        self.skip_btn.setToolTip("让 AI 自行决定")
        self.skip_btn.clicked.connect(self.skip_question)
        input_layout.addWidget(self.message_input, stretch=1)
        input_layout.addWidget(self.send_btn)
        input_layout.addWidget(self.skip_btn)
        layout.addLayout(input_layout)

        hint = QLabel("💡 提示: 你可以回答问题，也可以点击「跳过」让 AI 自行决定")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        self.confirm_btn = QPushButton("✅ 确认并创建项目")
        self.confirm_btn.setStyleSheet("QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #13a10e, stop:1 #16c60c); padding: 14px; font-weight: bold; font-size: 14px; } QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16c60c, stop:1 #1ae610); } QPushButton:disabled { background: #3d3d3d; color: #888; }")
        self.confirm_btn.clicked.connect(self.accept)
        self.confirm_btn.setEnabled(False)
        layout.addWidget(self.confirm_btn)

    def start_conversation(self):
        self.add_message("🤖 AI", "正在分析你的任务...", "ai")
        analysis_prompt = f"""用户任务：{self.user_task}

请分析这个任务，推断可能需要的技术栈，然后提出 1-2 个关键问题来确认项目约定。
注意：不要预设选项，根据任务内容灵活提问。问题要简洁友好。
直接输出你的问题，不要其他内容。"""
        try:
            question = self.llm_client.chat([
                {"role": "system", "content": "你是项目初始化助手，通过对话帮助用户确定项目约定。"},
                {"role": "user", "content": analysis_prompt}
            ])
        except Exception:
            question = "请问这个项目你希望使用什么技术栈？比如编程语言、框架等。"

        self.add_message("🤖 AI", question, "ai")
        self.conversation_history.append({"role": "assistant", "content": question})

    def send_message(self):
        message = self.message_input.text().strip()
        if not message:
            return
        self.add_message("👤 用户", message, "user")
        self.conversation_history.append({"role": "user", "content": message})
        self.message_input.clear()
        self.continue_conversation()

    def skip_question(self):
        self.add_message("👤 用户", "（让 AI 自行决定）", "user")
        self.conversation_history.append({"role": "user", "content": "你可以自行决定，不用再问我。请根据任务直接生成最合适的约定。"})
        self.continue_conversation(finalize=True)

    def continue_conversation(self, finalize=False):
        self.add_message("🤖 AI", "正在思考...", "ai")

        # 决定是继续问还是直接生成
        if finalize or len(self.conversation_history) >= 6:
            action = "generate"
            parsed_data = {}
        else:
            check_prompt = f"""用户任务：{self.user_task}
对话历史：
{self._format_history()}

请判断：
1. 是否已经有足够信息生成 AGENTS.md？
2. 如果不够，还需要问什么关键问题？（最多再问1个）
3. 如果够了，直接生成 AGENTS.md。

输出 JSON 格式：
如果还需要问：{{"action": "ask", "question": "你的问题"}}
如果够了：{{"action": "generate", "agents_md": "完整的 AGENTS.md 内容"}}

只输出 JSON，不要用 markdown 代码块包裹。"""

            try:
                response = self.llm_client.chat([
                    {"role": "system", "content": "你是项目初始化助手，只输出合法 JSON，不要用 markdown 包裹。"},
                    {"role": "user", "content": check_prompt}
                ])
                parsed_data = self._extract_json(response)
                if parsed_data is None:
                    parsed_data = {}
                action = parsed_data.get("action", "generate")
            except Exception:
                action = "generate"
                parsed_data = {}

        if action == "ask":
            question = parsed_data.get("question", "还有什么需要补充的吗？")
            self.add_message("🤖 AI", question, "ai")
            self.conversation_history.append({"role": "assistant", "content": question})
        else:
            # 尝试从 parsed_data 获取 agents_md
            agents_md = parsed_data.get("agents_md") if parsed_data else None

            if not agents_md:
                # 单独生成 AGENTS.md
                generate_prompt = f"""用户任务：{self.user_task}
对话历史：
{self._format_history()}

请根据以上信息生成完整的 AGENTS.md。

必须包含以下章节：
# 项目约定
## 技术栈
## 可用依赖（请勿使用清单外的库）
## 目录结构
## 编码规范
## 禁止事项
1. 不要导入「可用依赖」清单之外的第三方库
2. 不要自己创建不存在的工具文件
3. 如需新依赖，先在对话中说明
4. （根据项目特点补充其他禁止项）

直接输出完整的 Markdown 内容。"""
                try:
                    agents_md = self.llm_client.chat([
                        {"role": "system", "content": "你是项目架构专家，生成项目约定文档。"},
                        {"role": "user", "content": generate_prompt}
                    ])
                except Exception:
                    agents_md = f"""# 项目约定
## 技术栈
- 根据任务推断: {self.user_task[:50]}...
## 可用依赖
- 待补充
## 目录结构
- 待规划
## 禁止事项
1. 不要导入不存在的模块
2. 不要自创工具文件"""

            self.agents_md = agents_md
            self.preview_browser.setPlainText(self.agents_md)
            self.preview_group.setChecked(True)
            self.add_message("🤖 AI", "✅ 我已经根据对话生成了项目约定，请查看上方预览。如果确认无误，点击「确认并创建项目」开始！", "ai")
            self.confirm_btn.setEnabled(True)

    def _extract_json(self, text: str) -> dict:
        """从文本中提取 JSON，兼容多种格式"""
        if not text:
            return None

        # 1. 尝试直接解析
        try:
            return json.loads(text.strip())
        except:
            pass

        # 2. 尝试提取 markdown 代码块中的 JSON
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except:
                pass

        # 3. 尝试提取花括号包裹的 JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass

        return None

    def _format_history(self):
        return "\n".join([f"{m['role']}: {m['content']}" for m in self.conversation_history])

    def add_message(self, sender, message, level):
        colors = {"ai": "#4ec9b0", "user": "#ce9178", "system": "#888"}
        color = colors.get(level, "#ccc")
        if "正在思考" in self.chat_browser.toPlainText():
            cursor = self.chat_browser.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
        self.chat_browser.append(f'<p><b style="color: {color};">{sender}:</b> {message}</p>')
        cursor = self.chat_browser.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_browser.setTextCursor(cursor)

    def get_agents_md(self):
        return self.agents_md

    def get_session_name(self):
        if self.agents_md:
            prompt = f"""从以下 AGENTS.md 中提取项目名称，如果找不到，根据任务生成一个简短的名称（2-4个字）。
{self.agents_md[:500]}
用户原始任务：{self.user_task[:100]}
只输出项目名称，不要其他内容。"""
            try:
                name = self.llm_client.chat([
                    {"role": "system", "content": "只输出项目名称。"},
                    {"role": "user", "content": prompt}
                ]).strip()
                if name and len(name) <= 20:
                    return name
            except:
                pass
        return f"项目_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


class ProjectCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, session_data, parent=None):
        super().__init__(parent)
        self.session_data = session_data
        self.setup_ui()
        self.setCursor(Qt.PointingHandCursor)

    def setup_ui(self):
        self.setFixedSize(220, 140)
        self.setStyleSheet("ProjectCard { background: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 16px; } ProjectCard:hover { background: #3d3d3d; border-color: #13a10e; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        header = QHBoxLayout()
        icon = QLabel("📁")
        icon.setStyleSheet("font-size: 20px;")
        header.addWidget(icon)
        name = QLabel(self.session_data.get("name", "未命名")[:15])
        name.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")
        header.addWidget(name, stretch=1)
        layout.addLayout(header)
        date_str = self.session_data.get("created_at", "")[:10]
        layout.addWidget(QLabel(f"📅 {date_str}", styleSheet="color: #a0a0a0; font-size: 11px;"))
        completed = self.session_data.get("steps_completed", 0)
        total = self.session_data.get("total_steps", 0)
        layout.addWidget(QLabel(f"📊 {completed}/{total} 步骤", styleSheet="color: #a0a0a0; font-size: 11px;"))
        layout.addStretch()

    def mousePressEvent(self, event):
        self.clicked.emit(self.session_data)
        super().mousePressEvent(event)


class HomePage(QWidget):
    new_session_signal = Signal(str, str, str)
    load_session_signal = Signal(object)
    open_folder_signal = Signal(str)

    def __init__(self, session_manager: SessionManager):
        super().__init__()
        self.session_manager = session_manager
        config = Config()
        planner_config = config.get_planner_config()
        self.llm_client = LLMClient(planner_config)
        self.setup_ui()
        self.load_recent_projects()

    def setup_ui(self):
        self.setStyleSheet("background: #1e1e1e;")
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        left_panel = QFrame()
        left_panel.setFixedWidth(400)
        left_panel.setStyleSheet("QFrame { background: #252526; border: none; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(30, 40, 30, 40)
        left_layout.setSpacing(20)

        logo = QLabel("✨ Archon")
        logo.setFont(QFont("Segoe UI", 28, QFont.Bold))
        logo.setStyleSheet("color: #2d8cff;")
        left_layout.addWidget(logo)

        subtitle = QLabel("AI 编程助手")
        subtitle.setFont(QFont("Segoe UI", 14))
        subtitle.setStyleSheet("color: #888888; margin-bottom: 20px;")
        left_layout.addWidget(subtitle)

        quick_card = QFrame()
        quick_card.setStyleSheet("QFrame { background: #2d2d2d; border: none; border-radius: 12px; padding: 24px; }")
        quick_layout = QVBoxLayout(quick_card)
        quick_layout.setSpacing(16)
        quick_title = QLabel("🚀 快速开始")
        quick_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        quick_title.setStyleSheet("color: #ffffff;")
        quick_layout.addWidget(quick_title)

        self.task_input = QTextEdit()
        self.task_input.setPlaceholderText("输入任务描述...\n\n例如：\n- 写一个 Pygame 2D 游戏\n- 创建一个数据分析脚本\n- 搭建一个 FastAPI 后端")
        self.task_input.setMaximumHeight(120)
        self.task_input.setStyleSheet("QTextEdit { background: #1e1e1e; border: none; border-radius: 8px; padding: 14px; color: #cccccc; } QTextEdit:focus { background: #252525; }")
        quick_layout.addWidget(self.task_input)

        self.new_btn = QPushButton("✨ 开始新任务")
        self.new_btn.setCursor(Qt.PointingHandCursor)
        self.new_btn.setFixedHeight(44)
        self.new_btn.setStyleSheet("QPushButton { background: #2d8cff; border: none; border-radius: 8px; color: white; font-weight: bold; font-size: 14px; } QPushButton:hover { background: #1a75e8; }")
        self.new_btn.clicked.connect(self.on_new_task)
        quick_layout.addWidget(self.new_btn)
        left_layout.addWidget(quick_card)

        self.open_btn = QPushButton("📂 打开已有项目")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.setFixedHeight(44)
        self.open_btn.setStyleSheet("QPushButton { background: #2d2d2d; border: none; border-radius: 8px; color: #cccccc; font-size: 14px; } QPushButton:hover { background: #3c3c3c; color: white; }")
        self.open_btn.clicked.connect(self.on_open_folder)
        left_layout.addWidget(self.open_btn)
        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        right_panel = QFrame()
        right_panel.setStyleSheet("QFrame { background: #1e1e1e; border: none; }")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(40, 40, 60, 40)
        right_layout.setSpacing(20)

        title_layout = QHBoxLayout()
        recent_title = QLabel("📁 最近项目")
        recent_title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        recent_title.setStyleSheet("color: #ffffff;")
        title_layout.addWidget(recent_title)
        title_layout.addStretch()
        right_layout.addLayout(title_layout)

        self.project_list = QListWidget()
        self.project_list.setStyleSheet("QListWidget { background: transparent; border: none; } QListWidget::item { background: transparent; border: none; border-radius: 8px; margin: 4px 0; padding: 0; } QListWidget::item:hover { background: #2d2d2d; }")
        self.project_list.setSpacing(2)
        right_layout.addWidget(self.project_list)

        self.no_projects_label = QLabel("暂无项目\n\n点击左侧「开始新任务」创建第一个项目")
        self.no_projects_label.setStyleSheet("color: #666666; font-size: 14px;")
        self.no_projects_label.setAlignment(Qt.AlignCenter)
        self.no_projects_label.setVisible(False)
        right_layout.addWidget(self.no_projects_label)
        right_layout.addStretch()
        main_layout.addWidget(right_panel, stretch=1)

    def load_recent_projects(self):
        self.project_list.clear()
        sessions = self.session_manager.list_sessions()[:10]
        if not sessions:
            self.no_projects_label.setVisible(True)
            return
        self.no_projects_label.setVisible(False)
        for session in sessions:
            session_data = {
                "session_id": session.session_id, "name": session.name,
                "created_at": session.created_at, "steps_completed": session.steps_completed,
                "total_steps": session.total_steps, "workspace_path": session.workspace_path,
                "user_task": session.user_task,
            }
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 60))
            self.project_list.addItem(item)
            widget = ProjectItemWidget(session_data)
            widget.clicked.connect(self.on_project_clicked)
            widget.deleted.connect(self.on_project_delete)
            self.project_list.setItemWidget(item, widget)

    def on_project_delete(self, session_id: str):
        if not session_id:
            return
        session = self.session_manager.load_session(session_id)
        project_name = session.name if session else "未知项目"
        reply = QMessageBox.question(self, "确认删除", f"确定要删除项目「{project_name}」吗？\n\n这将永久删除该项目的工作区和所有文件。\n此操作不可撤销！", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.session_manager.delete_session(session_id)
                self.load_recent_projects()
            except Exception as e:
                QMessageBox.critical(self, "删除失败", f"删除项目失败: {e}")

    def on_new_task(self):
        task = self.task_input.toPlainText().strip()
        if not task:
            QMessageBox.warning(self, "提示", "请输入任务描述")
            return
        dialog = ProjectSetupDialog(task, self.llm_client, self)
        if dialog.exec() == QDialog.Accepted:
            agents_md = dialog.get_agents_md()
            session_name = dialog.get_session_name()
            if not agents_md:
                QMessageBox.warning(self, "提示", "生成项目约定失败")
                return
            self.new_session_signal.emit(session_name, task, agents_md)

    def on_open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择项目文件夹", str(Path.home()))
        if folder:
            self.open_folder_signal.emit(folder)

    def on_project_clicked(self, session_data):
        session = self.session_manager.load_session(session_data["session_id"])
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
        sessions_page.new_session_signal.connect(lambda name, task: self.new_session_signal.emit(name, task, ""))
        sessions_page.load_session_signal.connect(self.load_session_signal)
        sessions_page.load_session_signal.connect(lambda: dialog.accept())
        layout.addWidget(sessions_page)
        dialog.exec()
        self.load_recent_projects()


class ProjectItemWidget(QWidget):
    clicked = Signal(dict)
    deleted = Signal(str)

    def __init__(self, session_data, parent=None):
        super().__init__(parent)
        self.session_data = session_data
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        name = QLabel(self.session_data.get("name", "未命名"))
        name.setFont(QFont("Segoe UI", 13))
        name.setStyleSheet("color: #ffffff;")
        layout.addWidget(name)
        date_str = self.session_data.get("created_at", "")
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                date_str = dt.strftime("%Y-%m-%d")
            except:
                pass
        layout.addWidget(QLabel(date_str, styleSheet="color: #888888; font-size: 12px;"))
        layout.addStretch()
        completed = self.session_data.get("steps_completed", 0)
        total = self.session_data.get("total_steps", 0)
        if total > 0:
            layout.addWidget(QLabel(f"{completed}/{total} 步骤", styleSheet="color: #888888; font-size: 12px;"))
        open_btn = QPushButton("打开")
        open_btn.setFixedWidth(80)
        open_btn.setStyleSheet("QPushButton { background: #3c3c3c; border: 1px solid #555; border-radius: 4px; padding: 6px 12px; color: #ffffff; } QPushButton:hover { background: #2d8cff; border-color: #2d8cff; }")
        open_btn.clicked.connect(self.on_click)
        layout.addWidget(open_btn)
        delete_btn = QPushButton("🗑️")
        delete_btn.setFixedWidth(40)
        delete_btn.setToolTip("删除此项目")
        delete_btn.setStyleSheet("QPushButton { background: transparent; border: 1px solid #555; border-radius: 4px; padding: 6px 8px; color: #888; } QPushButton:hover { background: #f14c4c; border-color: #f14c4c; color: white; }")
        delete_btn.clicked.connect(self.on_delete)
        layout.addWidget(delete_btn)

    def on_click(self):
        self.clicked.emit(self.session_data)

    def on_delete(self):
        self.deleted.emit(self.session_data.get("session_id", ""))

    def mouseDoubleClickEvent(self, event):
        self.clicked.emit(self.session_data)
        super().mouseDoubleClickEvent(event)
