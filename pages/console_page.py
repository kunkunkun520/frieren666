"""
控制台页面 - 三栏布局
左侧：文件树 + 计划 + 任务输入
中间：代码预览区
右侧：对话区
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QListWidget, QListWidgetItem,
    QSplitter, QTextBrowser, QProgressBar,
    QGroupBox, QTreeWidget, QTreeWidgetItem, QStackedWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor


class ConsolePage(QWidget):
    """控制台页面 - 三栏布局"""

    execute_signal = Signal(str)
    pause_signal = Signal()
    clear_signal = Signal()

    def __init__(self):
        super().__init__()
        self.worker = None
        self.waiting_for_response = False
        self.pending_context = None
        self.pending_options = []
        self.project_path = None
        self.setup_ui()
        self.setup_style()

    def setup_style(self):
        """设置深色主题样式"""
        self.setStyleSheet("""
            QWidget {
                background: #1e1e1e;
                color: #cccccc;
                font-size: 13px;
            }
            QGroupBox {
                background: rgba(37, 37, 38, 0.7);
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 16px;
                margin-top: 8px;
                padding-top: 16px;
                font-weight: 500;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
                color: #cccccc;
            }
            QTreeWidget, QListWidget, QTextEdit, QTextBrowser {
                background: transparent;
                border: none;
                color: #cccccc;
            }
            QTreeWidget::item, QListWidget::item {
                padding: 4px 0;
                border-radius: 6px;
            }
            QTreeWidget::item:hover, QListWidget::item:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background: rgba(14, 99, 156, 0.3);
            }
            QPushButton {
                background: rgba(61, 61, 61, 0.5);
                border: 1px solid rgba(74, 74, 74, 0.5);
                border-radius: 20px;
                padding: 8px 16px;
                color: #cccccc;
            }
            QPushButton:hover {
                background: rgba(74, 74, 74, 0.7);
                border-color: rgba(106, 106, 106, 0.7);
            }
            QTextEdit {
                background: rgba(30, 30, 30, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 12px;
            }
            QTextEdit:focus {
                border-color: #13a10e;
            }
            QProgressBar {
                border: none;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 10px;
                height: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #13a10e, stop:1 #16c60c);
                border-radius: 10px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.3);
            }
        """)

    def setup_ui(self):
        """设置UI - 三栏布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 主分割器
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(1)
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background: rgba(255, 255, 255, 0.05);
                margin: 8px 0;
            }
        """)

        # ===== 左侧面板（文件树 + 计划 + 任务输入）=====
        left_panel = self._create_left_panel()
        main_splitter.addWidget(left_panel)

        # ===== 中间代码区 =====
        center_panel = self._create_code_panel()
        main_splitter.addWidget(center_panel)

        # ===== 右侧对话区 =====
        right_panel = self._create_chat_panel()
        main_splitter.addWidget(right_panel)

        main_splitter.setSizes([300, 700, 400])
        layout.addWidget(main_splitter)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def _create_left_panel(self):
        """创建左侧面板（文件树 + 计划 + 任务输入）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # 文件树
        file_group = QGroupBox("📁 文件结构")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(8)

        refresh_layout = QHBoxLayout()
        self.workspace_label = QLabel("工作区: 未选择")
        self.workspace_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        self.refresh_tree_btn = QPushButton("🔄 刷新")
        self.refresh_tree_btn.clicked.connect(self.refresh_file_tree)
        refresh_layout.addWidget(self.workspace_label)
        refresh_layout.addStretch()
        refresh_layout.addWidget(self.refresh_tree_btn)
        file_layout.addLayout(refresh_layout)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderHidden(True)
        self.file_tree.itemDoubleClicked.connect(self.on_file_double_clicked)
        file_layout.addWidget(self.file_tree)

        layout.addWidget(file_group, stretch=3)

        # 当前计划
        plan_group = QGroupBox("📋 当前计划")
        plan_layout = QVBoxLayout(plan_group)
        plan_layout.setSpacing(8)

        self.step_list = QListWidget()
        plan_layout.addWidget(self.step_list)

        layout.addWidget(plan_group, stretch=2)

        # 任务输入
        task_group = QGroupBox("📝 任务描述")
        task_layout = QVBoxLayout(task_group)
        task_layout.setSpacing(8)

        self.task_input = QTextEdit()
        self.task_input.setPlaceholderText("描述你想要创建的项目或功能...")
        self.task_input.setMinimumHeight(80)
        self.task_input.setMaximumHeight(120)
        task_layout.addWidget(self.task_input)

        # 按钮组
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.execute_btn = QPushButton("▶ 开始执行")
        self.execute_btn.setObjectName("ExecuteButton")
        self.execute_btn.setCursor(Qt.PointingHandCursor)
        self.execute_btn.clicked.connect(self.on_execute_clicked)
        self.execute_btn.setStyleSheet("""
            #ExecuteButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #13a10e, stop:1 #16c60c);
                border: none;
                border-radius: 24px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }
            #ExecuteButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #16c60c, stop:1 #1ae610);
                box-shadow: 0 0 15px rgba(19, 161, 14, 0.3);
            }
            #ExecuteButton:disabled {
                background: #4a4a4a;
                color: #808080;
            }
        """)

        self.pause_btn = QPushButton("⏸ 暂停")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.clicked.connect(self.on_pause_clicked)

        self.resume_btn = QPushButton("▶ 恢复")
        self.resume_btn.setEnabled(False)
        self.resume_btn.setCursor(Qt.PointingHandCursor)
        self.resume_btn.clicked.connect(self.on_resume_clicked)

        self.cancel_btn = QPushButton("✖ 取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)

        self.clear_btn = QPushButton("⬚ 清空")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.on_clear_clicked)

        btn_layout.addWidget(self.execute_btn)
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.resume_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.clear_btn)

        task_layout.addLayout(btn_layout)
        layout.addWidget(task_group, stretch=1)

        return panel

    def _create_code_panel(self):
        """创建中间代码展示区"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # 文件标签栏
        tab_bar = QWidget()
        tab_bar.setFixedHeight(40)
        tab_bar.setStyleSheet("""
            QWidget {
                background: rgba(37, 37, 38, 0.8);
                border-radius: 12px;
            }
        """)

        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(12, 0, 12, 0)
        tab_layout.setSpacing(0)

        self.current_file_label = QLabel("未打开文件")
        self.current_file_label.setStyleSheet("color: #cccccc; padding: 0 12px;")
        tab_layout.addWidget(self.current_file_label)
        tab_layout.addStretch()

        # 标签切换按钮
        self.code_tab_btn = self._create_tab_button("代码", True)
        self.diff_tab_btn = self._create_tab_button("Diff", False)
        self.test_tab_btn = self._create_tab_button("测试", False)

        self.code_tab_btn.clicked.connect(lambda: self.switch_tab("code"))
        self.diff_tab_btn.clicked.connect(lambda: self.switch_tab("diff"))
        self.test_tab_btn.clicked.connect(lambda: self.switch_tab("test"))

        tab_layout.addWidget(self.code_tab_btn)
        tab_layout.addWidget(self.diff_tab_btn)
        tab_layout.addWidget(self.test_tab_btn)

        layout.addWidget(tab_bar)

        # 代码显示栈
        self.code_stack = QStackedWidget()

        # 代码显示区
        self.code_display = QTextEdit()
        self.code_display.setReadOnly(True)
        self.code_display.setPlaceholderText("双击左侧文件树中的文件查看代码...")
        self.code_display.setFont(QFont("Consolas", 11))
        self.code_stack.addWidget(self.code_display)

        # Diff显示区
        self.diff_display = QTextEdit()
        self.diff_display.setReadOnly(True)
        self.diff_display.setPlaceholderText("代码差异将在这里显示...")
        self.diff_display.setFont(QFont("Consolas", 11))
        self.code_stack.addWidget(self.diff_display)

        # 测试结果显示区
        self.test_display = QTextEdit()
        self.test_display.setReadOnly(True)
        self.test_display.setPlaceholderText("测试结果将在这里显示...")
        self.test_display.setFont(QFont("Consolas", 11))
        self.code_stack.addWidget(self.test_display)

        layout.addWidget(self.code_stack)

        return panel

    def _create_chat_panel(self):
        """创建右侧对话区"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        chat_group = QGroupBox("💬 对话区")
        chat_layout = QVBoxLayout(chat_group)
        chat_layout.setSpacing(8)

        # 对话历史
        self.log_browser = QTextBrowser()
        self.log_browser.setOpenExternalLinks(True)
        chat_layout.addWidget(self.log_browser)

        # 选项按钮区域
        self.options_widget = QWidget()
        self.options_layout = QHBoxLayout(self.options_widget)
        self.options_layout.setContentsMargins(0, 4, 0, 4)
        self.options_widget.setVisible(False)
        chat_layout.addWidget(self.options_widget)

        # 输入框
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("输入消息... (输入「恢复执行」继续任务)")
        self.message_input.setMaximumHeight(80)
        self.message_input.setAcceptRichText(False)

        self.send_btn = QPushButton("发送")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self.send_user_message)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #0e639c, stop:1 #1177bb);
                border: none;
                border-radius: 20px;
                padding: 8px 20px;
                color: white;
                font-weight: 500;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #1177bb, stop:1 #1688d6);
            }
        """)

        input_layout.addWidget(self.message_input, stretch=1)
        input_layout.addWidget(self.send_btn)
        chat_layout.addWidget(input_widget)

        layout.addWidget(chat_group)

        return panel

    def _create_tab_button(self, text, checked=False):
        """创建标签切换按钮"""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 16px;
                color: #a0a0a0;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #e0e0e0;
            }
            QPushButton:checked {
                color: #13a10e;
                border-bottom-color: #13a10e;
            }
        """)
        return btn

    # ========== 公共方法 ==========

    def set_project_path(self, path):
        """设置项目路径"""
        if isinstance(path, str):
            self.project_path = Path(path)
        else:
            self.project_path = path
        self.workspace_label.setText(f"工作区: {self.project_path}")
        self.refresh_file_tree()

    def refresh_file_tree(self):
        """刷新文件树"""
        self.file_tree.clear()
        if not self.project_path or not self.project_path.exists():
            return
        root_item = QTreeWidgetItem([self.project_path.name])
        self.file_tree.addTopLevelItem(root_item)
        self._add_directory_items(root_item, self.project_path)
        root_item.setExpanded(True)

    def _add_directory_items(self, parent_item, path: Path):
        """递归添加目录项"""
        try:
            for item in sorted(path.iterdir()):
                if item.name.startswith('.') or item.name == '__pycache__':
                    continue
                if item.is_dir():
                    child = QTreeWidgetItem([item.name])
                    parent_item.addChild(child)
                    self._add_directory_items(child, item)
                elif item.suffix in ['.py', '.html', '.css', '.js', '.json', '.yaml', '.yml', '.md']:
                    child = QTreeWidgetItem([item.name])
                    parent_item.addChild(child)
        except PermissionError:
            pass

    def on_file_double_clicked(self, item, column):
        """双击文件预览"""
        path_parts = []
        current = item
        while current:
            path_parts.insert(0, current.text(0))
            current = current.parent()
        if not path_parts:
            return

        file_path = self.project_path
        for part in path_parts[1:]:
            file_path = file_path / part

        if file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8")
                self.code_display.setPlainText(content)
                self.current_file_label.setText(f"📄 {file_path.name}")
            except Exception as e:
                self.code_display.setPlainText(f"无法读取文件: {e}")

    def switch_tab(self, tab_name):
        """切换代码标签页"""
        tabs = {"code": 0, "diff": 1, "test": 2}
        self.code_stack.setCurrentIndex(tabs.get(tab_name, 0))
        self.code_tab_btn.setChecked(tab_name == "code")
        self.diff_tab_btn.setChecked(tab_name == "diff")
        self.test_tab_btn.setChecked(tab_name == "test")

    def show_diff(self, file_path, old_content, new_content):
        """显示代码差异"""
        import difflib
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f'原文件: {file_path}',
            tofile=f'新文件: {file_path}',
            lineterm=''
        )
        diff_text = '\n'.join(diff)
        self.diff_display.setPlainText(diff_text)
        self.switch_tab("diff")
        self.add_log(f"显示文件 {file_path} 的修改差异", "info")

    def set_worker(self, worker):
        """设置工作线程"""
        self.worker = worker
        worker.log_signal.connect(self.add_log)
        worker.status_signal.connect(self.on_status_change)
        worker.plan_signal.connect(self.on_plan_received)
        worker.step_signal.connect(self.on_step_update)
        worker.ask_signal.connect(self.on_ask_user)
        worker.finished_signal.connect(self.on_finished)
        worker.error_signal.connect(lambda e: self.add_log(f"错误: {e}", "error"))
        worker.diff_signal.connect(self.show_diff)

    # ========== 按钮事件 ==========

    def on_execute_clicked(self):
        task = self.task_input.toPlainText().strip()
        if not task:
            self.add_log("请先输入任务描述", "warning")
            return
        self.execute_signal.emit(task)

    def on_pause_clicked(self):
        if self.worker:
            self.worker.pause()
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(True)
        self.add_log("任务已暂停", "warning")

    def on_resume_clicked(self):
        if self.worker:
            if hasattr(self.worker, 'is_paused') and self.worker.is_paused:
                self.worker.resume()
                self.pause_btn.setEnabled(True)
                self.resume_btn.setEnabled(False)
            else:
                self.worker.handle_chat_message("恢复执行")
        self.add_log("恢复执行...", "info")

    def on_cancel_clicked(self):
        if self.worker:
            self.worker.cancel()
        self.set_running(False)

    def on_clear_clicked(self):
        self.task_input.clear()
        self.log_browser.clear()
        self.step_list.clear()
        self.code_display.clear()
        self.current_file_label.setText("未打开文件")

    def clear_log(self):
        self.log_browser.clear()

    def send_user_message(self):
        """发送用户消息"""
        message = self.message_input.toPlainText().strip()
        if not message:
            return
        self.add_log(f"👤 用户: {message}", "user")
        self.message_input.clear()

        if self.waiting_for_response:
            if hasattr(self, 'pending_context') and self.pending_context and self.pending_context.get("action") == "modify_plan":
                self.waiting_for_response = False
                if self.worker:
                    self.worker.on_modify_feedback(message)
            else:
                self.waiting_for_response = False
                self.options_widget.setVisible(False)
                if self.worker:
                    self.worker.on_user_response(message, getattr(self, 'pending_context', None))
        else:
            if self.worker and hasattr(self.worker, 'handle_chat_message'):
                self.worker.handle_chat_message(message)
            elif self.worker:
                self.worker.on_user_response(message, {})

    # ========== 信号处理 ==========

    def on_status_change(self, status):
        status_text = {
            "planning": "规划中", "executing": "执行中", "paused": "已暂停",
            "completed": "已完成", "cancelled": "已取消", "failed": "失败"
        }.get(status, status)
        self.add_log(f"状态: {status_text}", "info")
        self.set_running(status in ["planning", "executing"])

    def on_plan_received(self, steps):
        self.update_plan(steps)
        self.add_log(f"计划已生成，共 {len(steps)} 个步骤", "success")

    def on_step_update(self, step_id, status, message):
        self.update_step_status(step_id, status, message)
        icon = {"running": "🔄", "success": "✅", "failed": "❌", "skipped": "⏭️"}.get(status, "⏳")
        self.add_log(
            f"{icon} 步骤 {step_id}: {message}",
            "success" if status == "success" else "error" if status == "failed" else "info"
        )

    def on_ask_user(self, question, options, context):
        self.add_log(f"🤖 AI: {question}", "ai")
        self.show_options(options, context)

    def on_finished(self, result):
        if result.get("success"):
            if result.get("refresh"):
                self.refresh_file_tree()
                self.add_log("📁 文件树已刷新", "success")
            elif result.get("completed"):
                self.add_log("会话结束", "info")
                self.set_running(False)
            else:
                self.add_log("🎉 任务完成！", "success")
                self.refresh_file_tree()
                self.set_running(False)
        else:
            self.add_log(f"❌ 任务失败: {result.get('reason', '未知原因')}", "error")
            self.set_running(False)

        self.options_widget.setVisible(False)
        self.waiting_for_response = False

    # ========== UI 更新方法 ==========

    def add_log(self, message, level="info"):
        colors = {
            "info": "#a0a0a0", "success": "#6a9955", "error": "#f14c4c",
            "warning": "#dcdcaa", "ai": "#4ec9b0", "user": "#ce9178"
        }
        color = colors.get(level, "#a0a0a0")
        self.log_browser.append(f'<span style="color: {color};">{message}</span>')
        cursor = self.log_browser.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_browser.setTextCursor(cursor)

    def update_plan(self, steps):
        self.step_list.clear()
        for step in steps:
            item = QListWidgetItem(f"⏳ {step}")
            self.step_list.addItem(item)

    def update_step_status(self, step_id, status, message=""):
        index = step_id - 1
        if 0 <= index < self.step_list.count():
            item = self.step_list.item(index)
            icon = {"running": "🔄", "success": "✅", "failed": "❌", "skipped": "⏭️"}.get(status, "⏳")
            display_text = f"{icon} {message}" if message else f"{icon} 步骤{step_id}"
            item.setText(display_text)

    def show_options(self, options, context):
        for i in reversed(range(self.options_layout.count())):
            widget = self.options_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        if options:
            for option in options:
                btn = QPushButton(option)
                btn.clicked.connect(lambda checked, opt=option, ctx=context: self.on_option_selected(opt, ctx))
                btn.setStyleSheet("""
                    QPushButton {
                        background: #3d3d3d;
                        padding: 8px 16px;
                        border-radius: 16px;
                    }
                    QPushButton:hover {
                        background: #4d4d4d;
                    }
                """)
                self.options_layout.addWidget(btn)
            self.options_widget.setVisible(True)
        else:
            self.options_widget.setVisible(False)

        self.waiting_for_response = True
        self.pending_context = context
        self.pending_options = options

    def on_option_selected(self, option, context):
        self.options_widget.setVisible(False)
        self.waiting_for_response = False
        self.add_log(f"👤 用户选择: {option}", "user")
        if self.worker:
            self.worker.on_user_response(option, context)

    def set_running(self, running):
        self.execute_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running)
        self.resume_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.progress_bar.setVisible(running)

    def display_code(self, code, file_path=""):
        self.code_display.setPlainText(code)
        if file_path:
            self.current_file_label.setText(f"📄 {file_path}")