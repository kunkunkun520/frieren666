"""
模型配置页面 - 完整版
包含 Chat/Planner/Coder/Judge 模型独立配置
每个模型下含 MCP 服务配置 + Skill 技能配置"""

import requests
import json
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QGroupBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QTabWidget,
    QMessageBox, QScrollArea, QTextEdit, QFileDialog,
    QListWidget, QListWidgetItem, QInputDialog
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont


class FetchModelsThread(QThread):
    """获取模型列表的线程"""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, base_url, provider, api_key=""):
        super().__init__()
        self.base_url = base_url
        self.provider = provider
        self.api_key = api_key

    def run(self):
        try:
            if self.provider == "ollama":
                self._fetch_ollama()
            elif self.provider in ["openai", "openai_compatible"]:
                self._fetch_openai()
            elif self.provider == "anthropic":
                self._fetch_anthropic()
            else:
                self.error.emit(f"不支持的提供商: {self.provider}")
        except Exception as e:
            self.error.emit(str(e))

    def _fetch_ollama(self):
        url = self.base_url.rstrip('/') + "/api/tags"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            models = [m["name"] for m in response.json().get("models", [])]
            self.finished.emit(models)
        else:
            self.error.emit(f"HTTP {response.status_code}")

    def _fetch_openai(self):
        url = self.base_url.rstrip('/') + "/models"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = [m["id"] for m in data.get("data", [])]
            models = [m for m in models if not m.startswith("whisper") and not m.startswith("tts")]
            self.finished.emit(models)
        else:
            self.error.emit(f"HTTP {response.status_code}")

    def _fetch_anthropic(self):
        models = [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-3-5-sonnet-20240620",
            "claude-3-5-haiku-20241022",
        ]
        self.finished.emit(models)


class SettingsPage(QWidget):
    """模型配置页面 - 完整版"""

    def __init__(self):
        super().__init__()
        self.mcp_editors = {}
        self.skill_editors = {}
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QWidget { background: #1e1e1e; color: #cccccc; font-size: 13px; }
            QGroupBox {
                background: rgba(37, 37, 38, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                margin-top: 12px;
                padding: 24px;
                padding-top: 32px;
                font-weight: 500;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
            }
            QLabel { color: #cccccc; font-size: 13px; }
            QLineEdit {
                background: rgba(30, 30, 30, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px 14px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #13a10e; }
            QComboBox {
                background: rgba(30, 30, 30, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px 14px;
                color: #e0e0e0;
                font-size: 13px;
                min-width: 200px;
            }
            QComboBox:hover { border-color: rgba(255, 255, 255, 0.2); }
            QComboBox:focus { border-color: #13a10e; }
            QComboBox::drop-down { border: none; padding-right: 10px; }
            QComboBox QAbstractItemView {
                background: #252526;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 4px;
                color: #e0e0e0;
                selection-background-color: rgba(14, 99, 156, 0.4);
            }
            QPushButton {
                background: rgba(61, 61, 61, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                padding: 10px 20px;
                color: #e0e0e0;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: rgba(80, 80, 80, 0.8); border-color: rgba(255, 255, 255, 0.2); }
            QPushButton#primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #13a10e, stop:1 #16c60c);
                border: none;
                color: white;
                font-weight: bold;
            }
            QPushButton#primary:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16c60c, stop:1 #1ae610);
            }
            QCheckBox { color: #cccccc; font-size: 13px; spacing: 10px; }
            QCheckBox::indicator {
                width: 20px; height: 20px;
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                background: rgba(30, 30, 30, 0.8);
            }
            QCheckBox::indicator:checked { background: #13a10e; border-color: #13a10e; }
            QSpinBox, QDoubleSpinBox {
                background: rgba(30, 30, 30, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px 14px;
                color: #e0e0e0;
                font-size: 13px;
                min-width: 120px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus { border-color: #13a10e; }
            QTabWidget::pane { background: transparent; border: none; padding-top: 10px; }
            QTabWidget::tab-bar { alignment: left; }
            QTabBar::tab {
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 12px 24px;
                color: #a0a0a0;
                font-size: 14px;
                font-weight: 500;
            }
            QTabBar::tab:hover { color: #e0e0e0; }
            QTabBar::tab:selected { color: #13a10e; border-bottom-color: #13a10e; }
            QTextEdit {
                background: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
                padding: 12px;
                color: #d4d4d4;
                font-size: 13px;
            }
            QListWidget {
                background: rgba(30, 30, 30, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 4px;
                color: #e0e0e0;
            }
            QListWidget::item { padding: 8px 12px; border-radius: 6px; }
            QListWidget::item:hover { background: rgba(255, 255, 255, 0.05); }
            QListWidget::item:selected { background: rgba(14, 99, 156, 0.4); }
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.15); border-radius: 3px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.3); }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        title_bar = QWidget()
        title_bar.setFixedHeight(60)
        title_bar.setStyleSheet("""
            QWidget {
                background: rgba(37, 37, 38, 0.95);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(24, 0, 24, 0)

        title_label = QLabel("⚙️ 设置")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addWidget(title_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(40, 30, 40, 30)
        content_layout.setSpacing(30)

        tabs = QTabWidget()
        tabs.addTab(self._create_agent_tab("chat", "💬 对话模型"), "💬 对话模型")
        tabs.addTab(self._create_agent_tab("planner", "🧠 Planner 模型"), "🧠 Planner")
        tabs.addTab(self._create_coder_tab(), "⌨️ Coder 模型")
        tabs.addTab(self._create_agent_tab("judge", "⚖️ Judge 模型"), "⚖️ Judge")
        tabs.addTab(self._create_embedding_tab(), "🔍 Embedding")
        tabs.addTab(self._create_advanced_tab(), "⚡ 高级设置")
        tabs.addTab(self._create_about_tab(), "ℹ️ 关于")
        content_layout.addWidget(tabs)

        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 10, 0, 0)

        self.default_btn = QPushButton("↺ 恢复默认")
        self.default_btn.clicked.connect(self.reset_to_default)

        self.apply_btn = QPushButton("✓ 应用配置")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.clicked.connect(self.save_config)

        btn_layout.addStretch()
        btn_layout.addWidget(self.default_btn)
        btn_layout.addSpacing(12)
        btn_layout.addWidget(self.apply_btn)
        content_layout.addWidget(btn_widget)

        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    # ========== 通用 Agent 标签页 ==========

    def _create_agent_tab(self, agent_name: str, title: str) -> QWidget:
        """创建通用 Agent 标签页（模型配置 + MCP + Skill）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(24)

        # 模型配置
        model_group = QGroupBox(f"{title} 配置")
        model_layout = QVBoxLayout(model_group)
        model_layout.setSpacing(8)
        model_layout.addWidget(self._create_model_row(agent_name))
        layout.addWidget(model_group)

        # MCP 配置
        layout.addWidget(self._create_mcp_section(agent_name))

        # Skill 配置
        layout.addWidget(self._create_skill_section(agent_name))

        layout.addStretch()
        return widget

    def _create_coder_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(24)

        coder_group = QGroupBox("⌨️ Coder 模型配置")
        coder_layout = QVBoxLayout(coder_group)
        coder_layout.setSpacing(16)

        self.same_as_planner = QCheckBox("使用与 Planner 相同的配置")
        self.same_as_planner.setChecked(True)
        self.same_as_planner.toggled.connect(self.on_same_as_planner_toggled)
        coder_layout.addWidget(self.same_as_planner)

        self.coder_independent = QWidget()
        self.coder_independent.setVisible(False)
        coder_independent_layout = QVBoxLayout(self.coder_independent)
        coder_independent_layout.setContentsMargins(0, 0, 0, 0)
        coder_independent_layout.addWidget(self._create_model_row("coder"))
        coder_layout.addWidget(self.coder_independent)

        layout.addWidget(coder_group)
        layout.addWidget(self._create_mcp_section("coder"))
        layout.addWidget(self._create_skill_section("coder"))
        layout.addStretch()
        return widget

    def _create_embedding_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(24)

        embed_group = QGroupBox("🔍 RAG Embedding 模型配置")
        embed_layout = QVBoxLayout(embed_group)
        embed_layout.setSpacing(8)
        embed_layout.addWidget(self._create_model_row("embedding"))

        hint = QLabel("💡 Embedding 模型用于 RAG 记忆检索，推荐使用 nomic-embed-text")
        hint.setStyleSheet("color: #888; font-size: 12px; padding: 8px 0;")
        hint.setWordWrap(True)
        embed_layout.addWidget(hint)

        layout.addWidget(embed_group)
        layout.addStretch()
        return widget

    def _create_advanced_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(24)

        exec_group = QGroupBox("执行参数")
        exec_layout = QVBoxLayout(exec_group)
        exec_layout.setSpacing(16)

        row1 = QHBoxLayout()
        row1.setSpacing(20)
        row1.addWidget(self._make_param_widget("Temperature", "temperature", QDoubleSpinBox, 0.0, 2.0, 0.1, 0.7))
        row1.addWidget(self._make_param_widget("Max Tokens", "max_tokens", QSpinBox, 512, 32768, 512, 4096))
        exec_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(20)
        row2.addWidget(self._make_param_widget("重试次数", "retry_count", QSpinBox, 1, 10, 1, 3))
        row2.addWidget(self._make_param_widget("评分阈值", "score_threshold", QSpinBox, 0, 100, 1, 80))
        exec_layout.addLayout(row2)
        layout.addWidget(exec_group)

        workspace_group = QGroupBox("工作区")
        workspace_layout = QVBoxLayout(workspace_group)
        workspace_layout.setSpacing(6)
        workspace_layout.addWidget(self._create_section_label("工作区路径"))
        self.workspace_path = QLineEdit("~/archon_workspace")
        workspace_layout.addWidget(self.workspace_path)
        layout.addWidget(workspace_group)

        layout.addStretch()
        return widget

    def _create_about_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(24)

        about_group = QGroupBox("关于 Archon")
        about_layout = QVBoxLayout(about_group)
        about_layout.setSpacing(16)

        logo = QLabel("✨ Archon Desktop")
        logo.setFont(QFont("Segoe UI", 24, QFont.Bold))
        logo.setStyleSheet("color: #13a10e;")
        logo.setAlignment(Qt.AlignCenter)
        about_layout.addWidget(logo)

        version = QLabel("版本 1.0.0")
        version.setStyleSheet("color: #888; font-size: 14px;")
        version.setAlignment(Qt.AlignCenter)
        about_layout.addWidget(version)

        desc = QLabel("AI 编程助手 - 让 AI 像资深工程师一样工作")
        desc.setStyleSheet("color: #cccccc; font-size: 14px;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        about_layout.addWidget(desc)

        about_layout.addSpacing(20)

        usage = QLabel("📖 配置指南")
        usage.setFont(QFont("Segoe UI", 16, QFont.Bold))
        usage.setStyleSheet("color: #ffffff;")
        about_layout.addWidget(usage)

        steps = [
            "1. 在各模型标签页中配置对应的模型",
            "2. 在 MCP 配置中添加外部工具服务",
            "3. 在 Skill 配置中创建自定义工作流",
            "4. 返回控制台，通过对话开始使用",
        ]
        for step in steps:
            l = QLabel(step)
            l.setStyleSheet("color: #cccccc; font-size: 13px; padding: 4px 0;")
            about_layout.addWidget(l)

        layout.addWidget(about_group)
        layout.addStretch()
        return widget

    # ========== 模型配置行 ==========

    def _create_model_row(self, prefix: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        row1 = QHBoxLayout()
        row1.setSpacing(20)
        row1.addWidget(self._make_combo_widget(prefix, "provider", "提供商", ["ollama", "openai", "openai_compatible", "anthropic"]))
        row1.addWidget(self._make_input_widget(prefix, "url", "API 地址", "http://localhost:11434"))
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(20)
        row2.addWidget(self._make_input_widget(prefix, "api_key", "API 密钥", "", True))
        row2.addWidget(self._make_model_widget(prefix))
        layout.addLayout(row2)

        status = QLabel("⚪ 未测试")
        status.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(status)
        setattr(self, f"{prefix}_status", status)

        return widget

    def _create_section_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("color: #888; font-size: 12px; font-weight: bold; padding: 0 4px;")
        return label

    def _make_input_widget(self, prefix, field, label, default="", password=False):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(6)
        l.addWidget(self._create_section_label(label))
        inp = QLineEdit(default)
        if password:
            inp.setEchoMode(QLineEdit.Password)
            inp.setPlaceholderText("sk-...")
        l.addWidget(inp)
        setattr(self, f"{prefix}_{field}", inp)
        return w

    def _make_combo_widget(self, prefix, field, label, items):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(6)
        l.addWidget(self._create_section_label(label))
        combo = QComboBox()
        combo.addItems(items)
        l.addWidget(combo)
        setattr(self, f"{prefix}_{field}", combo)
        return w

    def _make_model_widget(self, prefix):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(6)
        l.addWidget(self._create_section_label("模型"))
        row = QHBoxLayout()
        combo = QComboBox()
        combo.setEditable(True)
        combo.setPlaceholderText("点击刷新获取模型列表")
        row.addWidget(combo, stretch=1)
        btn = QPushButton("🔄 刷新")
        btn.clicked.connect(lambda: self.refresh_model_list(prefix))
        row.addWidget(btn)
        l.addLayout(row)
        setattr(self, f"{prefix}_model", combo)
        setattr(self, f"refresh_{prefix}_btn", btn)
        return w

    def _make_param_widget(self, label, attr, cls, min_v, max_v, step, default):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(6)
        l.addWidget(self._create_section_label(label))
        spin = cls()
        spin.setRange(min_v, max_v)
        if hasattr(spin, 'setSingleStep'):
            spin.setSingleStep(step)
        spin.setValue(default)
        l.addWidget(spin)
        setattr(self, attr, spin)
        return w

    # ========== MCP 配置 ==========

    def _create_mcp_section(self, agent_name: str) -> QGroupBox:
        agent_names = {"chat": "对话模型", "planner": "Planner", "coder": "Coder", "judge": "Judge"}
        display = agent_names.get(agent_name, agent_name)

        group = QGroupBox("🔌 MCP 服务配置")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        desc = QLabel(f"为 {display} 配置外部 MCP 工具服务\n格式: {{\"mcpServers\": {{\"服务名\": {{\"type\": \"streamable_http\", \"url\": \"...\"}}}}}}")
        desc.setStyleSheet("color: #888; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(10)

        help_btn = QPushButton("📖 如何获取 MCP 链接？")
        help_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #4ec9b0; font-size: 12px; } QPushButton:hover { color: #ffffff; }")
        help_btn.clicked.connect(self._show_mcp_help)
        quick_row.addWidget(help_btn)
        quick_row.addStretch()

        local_btn = QPushButton("➕ 添加本地 MCP 服务")
        local_btn.setStyleSheet("QPushButton { background: rgba(61,61,61,0.7); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 6px 14px; font-size: 12px; } QPushButton:hover { background: rgba(80,80,80,0.8); }")
        local_btn.clicked.connect(lambda: self._add_local_mcp_service(agent_name))
        quick_row.addWidget(local_btn)
        layout.addLayout(quick_row)

        editor = QTextEdit()
        editor.setPlaceholderText('{\n    "mcpServers": {\n        "fetch": {\n            "type": "streamable_http",\n            "url": "https://mcp.api-inference.modelscope.net/你的key/mcp"\n        }\n    }\n}')
        editor.setMinimumHeight(100)
        editor.setMaximumHeight(160)
        editor.setFont(QFont("Consolas", 11))
        layout.addWidget(editor)
        self.mcp_editors[agent_name] = editor

        test_layout = QHBoxLayout()
        test_layout.setSpacing(10)
        test_btn = QPushButton("🔌 测试 MCP 连接")
        test_btn.clicked.connect(lambda: self.test_mcp_connection(agent_name))
        test_layout.addWidget(test_btn)
        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #888; font-size: 12px; } QPushButton:hover { color: #f14c4c; }")
        clear_btn.clicked.connect(lambda: editor.clear())
        test_layout.addWidget(clear_btn)
        delete_btn = QPushButton("❌ 删除服务")
        delete_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #888; font-size: 12px; } QPushButton:hover { color: #f14c4c; }")
        delete_btn.clicked.connect(lambda: self._delete_mcp_service(agent_name))
        test_layout.addWidget(delete_btn)

        test_layout.addStretch()
        layout.addLayout(test_layout)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        status = QLabel("")
        status.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        status.setWordWrap(True)
        layout.addWidget(status)
        setattr(self, f"mcp_{agent_name}_status", status)

        return group

    # ========== Skill 配置 ==========
    def _delete_mcp_service(self, agent_name: str):
        """删除 MCP 配置中的某个服务"""
        editor = self.mcp_editors.get(agent_name)
        if not editor:
            return

        config_text = editor.toPlainText().strip()
        if not config_text:
            QMessageBox.warning(self, "提示", "没有可删除的配置")
            return

        try:
            config = json.loads(config_text)
            servers = config.get("mcpServers", {})
            if not servers:
                QMessageBox.warning(self, "提示", "没有可删除的服务")
                return

            # 弹出选择对话框
            from PySide6.QtWidgets import QInputDialog
            server_names = list(servers.keys())
            name, ok = QInputDialog.getItem(
                self, "删除 MCP 服务",
                "选择要删除的服务:",
                server_names, 0, False
            )

            if ok and name:
                reply = QMessageBox.question(
                    self, "确认删除",
                    f"确定要删除 MCP 服务「{name}」吗？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    del servers[name]
                    if servers:
                        editor.setPlainText(json.dumps(config, ensure_ascii=False, indent=2))
                    else:
                        editor.clear()

                    status_label = getattr(self, f"mcp_{agent_name}_status")
                    if status_label:
                        status_label.setText(f"✅ 已删除服务: {name}")
                        status_label.setStyleSheet("color: #6a9955; font-size: 12px;")

        except json.JSONDecodeError:
            QMessageBox.warning(self, "错误", "JSON 格式错误，请检查配置")
    def _create_skill_section(self, agent_name: str) -> QGroupBox:
        agent_names = {"chat": "对话模型", "planner": "Planner", "coder": "Coder", "judge": "Judge"}
        display = agent_names.get(agent_name, agent_name)

        group = QGroupBox("🧩 Skill 技能配置")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        desc = QLabel(f"为 {display} 配置自定义 Skill 工作流\nSkill 文件存放在 extensions/skills/ 目录，使用 Markdown 格式")
        desc.setStyleSheet("color: #888; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        skill_list = QListWidget()
        skill_list.setMaximumHeight(100)
        layout.addWidget(skill_list)
        setattr(self, f"skill_list_{agent_name}", skill_list)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        reload_btn = QPushButton("🔄 刷新列表")
        reload_btn.clicked.connect(lambda: self._load_skill_list(agent_name))
        btn_layout.addWidget(reload_btn)

        add_btn = QPushButton("➕ 新建 Skill")
        add_btn.clicked.connect(lambda: self._create_new_skill(agent_name))
        btn_layout.addWidget(add_btn)

        open_dir_btn = QPushButton("📂 打开目录")
        open_dir_btn.clicked.connect(self._open_skill_dir)
        btn_layout.addWidget(open_dir_btn)
        delete_btn = QPushButton("🗑️ 删除选中")
        delete_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #888; font-size: 12px; } QPushButton:hover { color: #f14c4c; }")
        delete_btn.clicked.connect(lambda: self._delete_skill(agent_name))
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._load_skill_list(agent_name)
        return group

    def _delete_skill(self, agent_name: str):
        """删除选中的 Skill"""
        skill_list = getattr(self, f"skill_list_{agent_name}", None)
        if not skill_list:
            return

        current = skill_list.currentItem()
        if not current:
            QMessageBox.warning(self, "提示", "请先选择要删除的 Skill")
            return

        # 兼容 📁 文件夹和 📄 文件两种格式
        skill_name = current.text()
        for prefix in ["📁 ", "📄 "]:
            skill_name = skill_name.replace(prefix, "")

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 Skill「{skill_name}」吗？\n\n"
            f"这将永久删除 extensions/skills/{skill_name}/ 文件夹及其所有内容。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            import shutil
            # 尝试删除文件夹
            skill_dir = Path("extensions/skills") / skill_name
            if skill_dir.is_dir():
                shutil.rmtree(skill_dir)
            # 尝试删除 .md 文件（兼容旧格式）
            skill_file = Path("extensions/skills") / f"{skill_name}.md"
            if skill_file.exists():
                skill_file.unlink()
            self._load_skill_list(agent_name)

    def _load_skill_list(self, agent_name):
        skill_list = getattr(self, f"skill_list_{agent_name}", None)
        if not skill_list:
            return
        skill_list.clear()
        skills_dir = Path("extensions/skills")
        if skills_dir.exists():
            for folder in skills_dir.iterdir():
                if folder.is_dir() and not folder.name.startswith("."):
                    skill_md = folder / "SKILL.md"
                    if skill_md.exists():
                        item = QListWidgetItem(f"📁 {folder.name}")
                        item.setData(Qt.UserRole, str(folder))
                        skill_list.addItem(item)
                        item.setToolTip(f"双击打开文件夹: {folder.name}")

            # 兼容旧格式：单独的 .md 文件
            for f in skills_dir.glob("*.md"):
                item = QListWidgetItem(f"📄 {f.stem}")
                item.setData(Qt.UserRole, str(f))
                skill_list.addItem(item)
                item.setToolTip(f"双击编辑: {f.name}")

    def _create_new_skill(self, agent_name):
        name, ok = QInputDialog.getText(self, "新建 Skill", "Skill 名称:")
        if not ok or not name:
            return

        # 创建 Skill 文件夹
        skill_dir = Path("extensions/skills") / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # 创建 SKILL.md
        skill_md_content = f"""---
    name: {name}
    description: 在这里写 Skill 的描述
    triggers:
      - 触发词1
      - 触发词2
    requires_tools:
      - list_files
      - read_file
    ---

    # {name}

    ## 工作流

    ### 步骤 1
    描述第一步做什么。

    ### 步骤 2
    描述第二步做什么。

    ## 约束
    - 约束1
    """
        (skill_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

        # 创建 tools.py 模板
        tools_py_content = f'''"""
    {name} - 自定义工具
    """

    def example_tool(params):
        """示例工具函数"""
        return {{"success": True, "result": "Hello from {name}"}}

    TOOLS = {{
        "example_tool": {{
            "function": example_tool,
            "description": "示例工具",
            "parameters": {{}}
        }}
    }}
    '''
        (skill_dir / "tools.py").write_text(tools_py_content, encoding="utf-8")

        self._load_skill_list(agent_name)
        os.startfile(str(skill_dir / "SKILL.md"))
    def _open_skill_dir(self):
        skills_dir = Path("extensions/skills")
        skills_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(skills_dir))

    # ========== MCP 操作 ==========

    def _show_mcp_help(self):
        QMessageBox.information(self, "📖 MCP 链接获取",
            "1. ModelScope MCP: https://modelscope.cn/mcp\n"
            "2. 自建 MCP: http://localhost:端口/mcp\n"
            "3. 第三方服务商提供的 MCP URL\n\n"
            "配置格式:\n"
            '{"mcpServers": {"服务名": {"url": "链接"}}}')

    def _add_local_mcp_service(self, agent_name):
        name, ok = QInputDialog.getText(self, "添加本地 MCP", "服务名称:")
        if not ok or not name:
            return
        url, ok = QInputDialog.getText(self, "添加本地 MCP", "URL:", text="http://localhost:8001/mcp")
        if not ok or not url:
            return

        editor = self.mcp_editors.get(agent_name)
        if not editor:
            return
        current = editor.toPlainText().strip()
        try:
            config = json.loads(current) if current else {"mcpServers": {}}
        except:
            config = {"mcpServers": {}}
        config["mcpServers"][name] = {"type": "streamable_http", "url": url}
        editor.setPlainText(json.dumps(config, ensure_ascii=False, indent=2))

    def test_mcp_connection(self, agent_name):
        editor = self.mcp_editors.get(agent_name)
        status_label = getattr(self, f"mcp_{agent_name}_status")
        if not editor:
            return

        config_text = editor.toPlainText().strip()
        if not config_text:
            status_label.setText("⚠️ 请输入配置")
            return

        try:
            config = json.loads(config_text)
            servers = config.get("mcpServers", {})
            if not servers:
                status_label.setText("⚠️ 没有配置服务")
                return

            status_label.setText("⏳ 测试中...")
            messages = []
            success = 0

            from core.mcp.connectors.streamable_http import StreamableHttpConnector
            for name, sc in servers.items():
                url = sc.get("url", "") if isinstance(sc, dict) else sc
                if not url:
                    messages.append(f"⚠️ {name}: URL 为空")
                    continue
                try:
                    connector = StreamableHttpConnector()
                    if connector.connect({"url": url, "headers": {}}):
                        tools = connector.list_tools()
                        success += 1
                        messages.append(f"✅ {name}: {len(tools)} 个工具")
                        connector.disconnect()
                    else:
                        messages.append(f"❌ {name}: 连接失败")
                except Exception as e:
                    messages.append(f"❌ {name}: {str(e)[:50]}")

            status_label.setText(f"{success}/{len(servers)} 成功\n" + "\n".join(messages))
            status_label.setStyleSheet(f"color: {'#6a9955' if success == len(servers) else '#dcdcaa' if success > 0 else '#f14c4c'}; font-size: 12px;")
        except json.JSONDecodeError:
            status_label.setText("❌ JSON 格式错误")
        except Exception as e:
            status_label.setText(f"❌ 测试失败: {e}")

    # ========== 模型刷新 ==========

    def refresh_model_list(self, prefix):
        prov = getattr(self, f"{prefix}_provider").currentText()
        url = getattr(self, f"{prefix}_url").text()
        key = getattr(self, f"{prefix}_api_key").text()
        combo = getattr(self, f"{prefix}_model")
        status = getattr(self, f"{prefix}_status")

        status.setText("⏳ 获取中...")
        status.setStyleSheet("color: #dcdcaa; font-size: 12px;")

        self.fetch_thread = FetchModelsThread(url, prov, key)
        self.fetch_thread.finished.connect(lambda models: self._on_models_fetched(combo, status, models))
        self.fetch_thread.error.connect(lambda e: self._on_models_error(status, e))
        self.fetch_thread.start()

    def _on_models_fetched(self, combo, status, models):
        combo.clear()
        if models:
            combo.addItems(models)
            status.setText(f"✅ {len(models)} 个模型")
            status.setStyleSheet("color: #6a9955; font-size: 12px;")
        else:
            combo.addItem("未找到模型")
            status.setText("⚠️ 无模型")
            status.setStyleSheet("color: #dcdcaa; font-size: 12px;")

    def _on_models_error(self, status, error):
        status.setText(f"❌ {error}")
        status.setStyleSheet("color: #f14c4c; font-size: 12px;")

    # ========== 保存/重置 ==========

    def on_same_as_planner_toggled(self, checked):
        self.coder_independent.setVisible(not checked)

    def reset_to_default(self):
        for prefix in ["chat", "planner", "coder", "judge", "embedding"]:
            prov = getattr(self, f"{prefix}_provider", None)
            url = getattr(self, f"{prefix}_url", None)
            key = getattr(self, f"{prefix}_api_key", None)
            model = getattr(self, f"{prefix}_model", None)
            if prov:
                prov.setCurrentText("ollama")
            if url:
                url.setText("http://localhost:11434")
            if key:
                key.clear()
            if model:
                model.clear()
        self.same_as_planner.setChecked(True)
        self.temperature.setValue(0.7)
        self.max_tokens.setValue(4096)
        self.retry_count.setValue(3)
        self.score_threshold.setValue(80)
        self.workspace_path.setText("~/archon_workspace")

    def save_config(self):
        from utils.config import Config
        config = Config()

        def save_model(prefix):
            return {
                "provider": getattr(self, f"{prefix}_provider").currentText(),
                "base_url": getattr(self, f"{prefix}_url").text(),
                "model_name": getattr(self, f"{prefix}_model").currentText(),
                "api_key": getattr(self, f"{prefix}_api_key").text(),
                "temperature": self.temperature.value(),
                "max_tokens": self.max_tokens.value()
            }

        config.save_chat_config(save_model("chat"))
        config.save_planner_config(save_model("planner"))
        config.save_coder_config(save_model("coder") if not self.same_as_planner.isChecked() else save_model("planner"))
        config.save_judge_config(save_model("judge"))
        config.save_rag_config(save_model("embedding"))

        for agent_name in ["chat", "planner", "coder", "judge"]:
            editor = self.mcp_editors.get(agent_name)
            if editor and editor.toPlainText().strip():
                try:
                    mcp_config = json.loads(editor.toPlainText())
                    config.set(f"mcp_{agent_name}", mcp_config)
                except:
                    pass

        config.set("advanced", {
            "retry_count": self.retry_count.value(),
            "score_threshold": self.score_threshold.value(),
            "workspace_path": self.workspace_path.text()
        })

        QMessageBox.information(self, "保存成功", "配置已保存，下次执行任务时将使用新配置。")

    def load_mcp_configs(self):
        from utils.config import Config
        config = Config()
        for agent_name, editor in self.mcp_editors.items():
            saved = config.get(f"mcp_{agent_name}", {})
            if isinstance(saved, str):
                try:
                    saved = json.loads(saved)
                except:
                    saved = {}
            if saved:
                editor.setPlainText(json.dumps(saved, ensure_ascii=False, indent=2))