"""
控制台页面 - 主工作区
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QListWidget, QListWidgetItem,
    QSplitter, QTextBrowser, QProgressBar, QFrame,
    QGroupBox, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor


class ConsolePage(QWidget):
    """控制台页面"""

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

    def setup_ui(self):
        """设置UI - 左侧代码和文件结构，右侧任务输入和对话"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        main_splitter = QSplitter(Qt.Horizontal)

        # ===== 左侧区域（代码展示 + 文件结构）=====
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_splitter = QSplitter(Qt.Vertical)

        # 文件结构树区域（上方）
        file_tree_group = QGroupBox("📁 项目文件结构")
        file_tree_layout = QVBoxLayout(file_tree_group)

        refresh_layout = QHBoxLayout()
        self.refresh_tree_btn = QPushButton("🔄 刷新")
        self.refresh_tree_btn.clicked.connect(self.refresh_file_tree)
        self.workspace_label = QLabel("工作区: 未选择")
        self.workspace_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        refresh_layout.addWidget(self.refresh_tree_btn)
        refresh_layout.addWidget(self.workspace_label)
        refresh_layout.addStretch()
        file_tree_layout.addLayout(refresh_layout)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("文件结构")
        self.file_tree.setMaximumHeight(250)
        self.file_tree.itemDoubleClicked.connect(self.on_file_double_clicked)
        file_tree_layout.addWidget(self.file_tree)

        left_splitter.addWidget(file_tree_group)

        # 代码展示区域（下方）
        code_group = QGroupBox("📄 代码预览")
        code_layout = QVBoxLayout(code_group)

        # 标签页按钮
        tab_layout = QHBoxLayout()
        self.code_tab_btn = QPushButton("代码")
        self.code_tab_btn.setCheckable(True)
        self.code_tab_btn.setChecked(True)
        self.code_tab_btn.clicked.connect(lambda: self.switch_tab("code"))
        self.diff_tab_btn = QPushButton("Diff")
        self.diff_tab_btn.setCheckable(True)
        self.diff_tab_btn.clicked.connect(lambda: self.switch_tab("diff"))
        self.test_tab_btn = QPushButton("测试")
        self.test_tab_btn.setCheckable(True)
        self.test_tab_btn.clicked.connect(lambda: self.switch_tab("test"))

        tab_layout.addWidget(self.code_tab_btn)
        tab_layout.addWidget(self.diff_tab_btn)
        tab_layout.addWidget(self.test_tab_btn)
        tab_layout.addStretch()

        self.current_file_label = QLabel("未选择文件")
        self.current_file_label.setStyleSheet("color: #4ec9b0; font-size: 11px;")
        tab_layout.addWidget(self.current_file_label)

        code_layout.addLayout(tab_layout)

        # 代码显示区
        self.code_display = QTextEdit()
        self.code_display.setReadOnly(True)
        self.code_display.setPlaceholderText("双击左侧文件树中的文件查看代码...")
        self.code_display.setFont(QFont("Courier New", 10))
        code_layout.addWidget(self.code_display)

        # Diff显示区（隐藏）
        self.diff_display = QTextEdit()
        self.diff_display.setReadOnly(True)
        self.diff_display.setPlaceholderText("代码差异将在这里显示...")
        self.diff_display.setVisible(False)
        code_layout.addWidget(self.diff_display)

        # 测试结果显示区（隐藏）
        self.test_display = QTextEdit()
        self.test_display.setReadOnly(True)
        self.test_display.setPlaceholderText("测试结果将在这里显示...")
        self.test_display.setVisible(False)
        code_layout.addWidget(self.test_display)

        left_splitter.addWidget(code_group)

        left_splitter.setSizes([250, 500])
        left_layout.addWidget(left_splitter)

        # ===== 右侧区域（任务输入 + 计划步骤 + 对话区）=====
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 任务输入区
        input_group = QGroupBox("📝 任务输入")
        input_layout = QVBoxLayout(input_group)

        self.task_input = QTextEdit()
        self.task_input.setPlaceholderText(
            "描述你想要创建的项目或功能...\n\n"
            "例如：\n"
            "- 创建一个用户管理系统的后端，包含注册、登录、JWT认证\n"
            "- 写一个数据处理脚本，读取CSV文件并生成统计报告\n"
            "- 帮我搭建一个Flask博客API"
        )
        self.task_input.setMinimumHeight(100)
        input_layout.addWidget(self.task_input)

        btn_layout = QHBoxLayout()
        self.execute_btn = QPushButton("▶ 开始执行")
        self.execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.execute_btn.clicked.connect(self.on_execute_clicked)

        self.pause_btn = QPushButton("⏸ 暂停")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.on_pause_clicked)

        self.resume_btn = QPushButton("▶ 恢复")
        self.resume_btn.setEnabled(False)
        self.resume_btn.clicked.connect(self.on_resume_clicked)

        self.cancel_btn = QPushButton("✖ 取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)

        self.clear_btn = QPushButton("⬚ 清空")
        self.clear_btn.clicked.connect(self.on_clear_clicked)

        btn_layout.addWidget(self.execute_btn)
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.resume_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        input_layout.addLayout(btn_layout)

        right_layout.addWidget(input_group)

        # 计划步骤区
        plan_group = QGroupBox("📋 当前计划")
        plan_layout = QVBoxLayout(plan_group)

        self.step_list = QListWidget()
        self.step_list.setMaximumHeight(200)
        plan_layout.addWidget(self.step_list)

        right_layout.addWidget(plan_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)

        # 对话/日志区
        log_group = QGroupBox("💬 对话区")
        log_layout = QVBoxLayout(log_group)

        self.log_browser = QTextBrowser()
        self.log_browser.setOpenExternalLinks(True)
        log_layout.addWidget(self.log_browser)

        # 输入框和选项按钮区域
        self.input_widget = QWidget()
        input_widget_layout = QVBoxLayout(self.input_widget)
        input_widget_layout.setContentsMargins(0, 0, 0, 0)

        self.options_widget = QWidget()
        self.options_layout = QHBoxLayout(self.options_widget)
        self.options_layout.setContentsMargins(0, 5, 0, 5)
        self.options_widget.setVisible(False)
        input_widget_layout.addWidget(self.options_widget)

        text_input_layout = QHBoxLayout()
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("输入消息...")
        self.message_input.setMaximumHeight(60)
        self.message_input.setAcceptRichText(False)

        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.send_user_message)

        text_input_layout.addWidget(self.message_input)
        text_input_layout.addWidget(self.send_btn)
        input_widget_layout.addLayout(text_input_layout)

        log_layout.addWidget(self.input_widget)

        right_layout.addWidget(log_group)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([600, 700])

        layout.addWidget(main_splitter)

    def set_project_path(self, path):
        if isinstance(path, str):
            self.project_path = Path(path)
        else:
            self.project_path = path
        self.workspace_label.setText(f"工作区: {self.project_path}")
        self.refresh_file_tree()

    def refresh_file_tree(self):
        self.file_tree.clear()
        if not self.project_path or not self.project_path.exists():
            return
        root_item = QTreeWidgetItem([self.project_path.name])
        self.file_tree.addTopLevelItem(root_item)
        self._add_directory_items(root_item, self.project_path)
        root_item.setExpanded(True)

    def _add_directory_items(self, parent_item, path: Path):
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
                self.current_file_label.setText(f"当前: {file_path.name}")
            except Exception as e:
                self.code_display.setPlainText(f"无法读取文件: {e}")

    def switch_tab(self, tab_name):
        self.code_display.setVisible(tab_name == "code")
        self.diff_display.setVisible(tab_name == "diff")
        self.test_display.setVisible(tab_name == "test")
        self.code_tab_btn.setChecked(tab_name == "code")
        self.diff_tab_btn.setChecked(tab_name == "diff")
        self.test_tab_btn.setChecked(tab_name == "test")

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
            self.worker.resume()
        self.pause_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)

    def on_cancel_clicked(self):
        if self.worker:
            self.worker.cancel()
        self.set_running(False)

    def on_clear_clicked(self):
        self.task_input.clear()
        self.log_browser.clear()
        self.step_list.clear()
        self.code_display.clear()
        self.current_file_label.setText("未选择文件")

    def clear_log(self):
        self.log_browser.clear()

    def set_worker(self, worker):
        self.worker = worker
        worker.log_signal.connect(self.add_log)
        worker.status_signal.connect(self.on_status_change)
        worker.plan_signal.connect(self.on_plan_received)
        worker.step_signal.connect(self.on_step_update)
        worker.ask_signal.connect(self.on_ask_user)
        worker.finished_signal.connect(self.on_finished)
        worker.error_signal.connect(lambda e: self.add_log(f"错误: {e}", "error"))
        worker.diff_signal.connect(self.show_diff)

    def show_diff(self, file_path, old_content, new_content):
        import difflib
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        diff = difflib.unified_diff(old_lines, new_lines, fromfile=f'原文件: {file_path}', tofile=f'新文件: {file_path}', lineterm='')
        diff_text = '\n'.join(diff)
        self.diff_display.setPlainText(diff_text)
        self.switch_tab("diff")
        self.add_log(f"显示文件 {file_path} 的修改差异", "info")

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
        self.add_log(f"{icon} 步骤 {step_id}: {message}", "success" if status == "success" else "error" if status == "failed" else "info")

    def on_ask_user(self, question, options, context):
        self.add_log(f"🤖 AI: {question}", "ai")
        self.show_options(options, context)

    def show_options(self, options, context):
        print(f"=== show_options 被调用 ===")
        print(f"options: {options}")
        print(f"context: {context}")
        for i in reversed(range(self.options_layout.count())):
            widget = self.options_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        if options:
            for option in options:
                btn = QPushButton(option)
                btn.clicked.connect(lambda checked, opt=option, ctx=context: self.on_option_selected(opt, ctx))
                btn.setStyleSheet("QPushButton { background-color: #3d3d3d; padding: 6px 12px; border-radius: 4px; } QPushButton:hover { background-color: #4d4d4d; }")
                self.options_layout.addWidget(btn)
            self.options_widget.setVisible(True)
        else:
            self.options_widget.setVisible(False)
        self.waiting_for_response = True
        self.pending_context = context
        self.pending_options = options

    def on_option_selected(self, option, context):
        print(f"=== on_option_selected 被调用 ===")
        print(f"option: {option}")
        print(f"context: {context}")
        self.options_widget.setVisible(False)
        self.waiting_for_response = False
        self.add_log(f"👤 用户选择: {option}", "user")
        if self.worker:
            self.worker.on_user_response(option, context)

    def send_user_message(self):
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

    def add_log(self, message, level="info"):
        colors = {"info": "#a0a0a0", "success": "#6a9955", "error": "#f14c4c", "warning": "#dcdcaa", "ai": "#4ec9b0", "user": "#ce9178"}
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

    def set_running(self, running):
        self.execute_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running)
        self.resume_btn.setEnabled(False)
        self.cancel_btn.setEnabled(running)
        if not running:
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setVisible(False)

    def update_progress(self, current, total):
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def display_code(self, code, file_path=""):
        self.code_display.setPlainText(code)
        if file_path:
            self.current_file_label.setText(f"当前: {file_path}")

    def on_finished(self, result):
        """任务完成 - 处理各种完成状态"""
        if result.get("success"):
            if result.get("refresh"):
                self.refresh_file_tree()
                self.add_log("📁 文件树已刷新", "success")
                current_file = self.current_file_label.text().replace("当前: ", "")
                if current_file and current_file != "未选择文件":
                    for item in self.file_tree.findItems(current_file, Qt.MatchExactly | Qt.MatchRecursive):
                        if item:
                            self.on_file_double_clicked(item, 0)
                            break
                return
            elif result.get("completed"):
                self.add_log("会话结束", "info")
                self.set_running(False)
                self.options_widget.setVisible(False)
                self.waiting_for_response = False
            else:
                msg = f"🎉 任务完成！"
                if result.get("steps_completed"):
                    msg += f" 完成步骤: {result['steps_completed']}/{result['total_steps']}"
                self.add_log(msg, "success")
                self.refresh_file_tree()
                self.set_running(False)
                self.options_widget.setVisible(False)
                self.waiting_for_response = False
        else:
            self.add_log(f"❌ 任务失败: {result.get('reason', '未知原因')}", "error")
            self.set_running(False)
            self.options_widget.setVisible(False)
            self.waiting_for_response = False