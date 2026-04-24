"""
模型配置页面 - 美化版
"""

import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QGroupBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QTabWidget,
    QMessageBox, QScrollArea
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
    """模型配置页面 - 美化版"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QWidget {
                background: #1e1e1e;
                color: #cccccc;
                font-size: 13px;
            }
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
            QLabel {
                color: #cccccc;
                font-size: 13px;
            }
            QLineEdit {
                background: rgba(30, 30, 30, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px 14px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #13a10e;
            }
            QLineEdit:disabled {
                background: rgba(20, 20, 20, 0.5);
                color: #666;
            }
            QComboBox {
                background: rgba(30, 30, 30, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px 14px;
                color: #e0e0e0;
                font-size: 13px;
                min-width: 200px;
            }
            QComboBox:hover {
                border-color: rgba(255, 255, 255, 0.2);
            }
            QComboBox:focus {
                border-color: #13a10e;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox QAbstractItemView {
                background: #252526;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 4px;
                color: #e0e0e0;
                outline: none;
                selection-background-color: rgba(14, 99, 156, 0.4);
                selection-color: #ffffff;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 30px;
            }
            QComboBox QAbstractItemView::item:hover {
                background: rgba(255, 255, 255, 0.05);
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
            QPushButton:hover {
                background: rgba(80, 80, 80, 0.8);
                border-color: rgba(255, 255, 255, 0.2);
            }
            QPushButton#primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #13a10e, stop:1 #16c60c);
                border: none;
                color: white;
                font-weight: bold;
            }
            QPushButton#primary:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16c60c, stop:1 #1ae610);
            }
            QCheckBox {
                color: #cccccc;
                font-size: 13px;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                background: rgba(30, 30, 30, 0.8);
            }
            QCheckBox::indicator:checked {
                background: #13a10e;
                border-color: #13a10e;
            }
            QSpinBox, QDoubleSpinBox {
                background: rgba(30, 30, 30, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px 14px;
                color: #e0e0e0;
                font-size: 13px;
                min-width: 120px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #13a10e;
            }
            QTabWidget::pane {
                background: transparent;
                border: none;
                padding-top: 10px;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 12px 24px;
                color: #a0a0a0;
                font-size: 14px;
                font-weight: 500;
            }
            QTabBar::tab:hover {
                color: #e0e0e0;
            }
            QTabBar::tab:selected {
                color: #13a10e;
                border-bottom-color: #13a10e;
            }
            QScrollArea {
                background: transparent;
                border: none;
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

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 标题栏
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

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(40, 30, 40, 30)
        content_layout.setSpacing(30)

        # 标签页
        tabs = QTabWidget()
        tabs.addTab(self._create_model_tab(), "🧠 模型配置")
        tabs.addTab(self._create_advanced_tab(), "⚡ 高级设置")
        tabs.addTab(self._create_about_tab(), "ℹ️ 关于")
        content_layout.addWidget(tabs)

        # 底部按钮
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

    def _create_section_label(self, text):
        """创建区块标签"""
        label = QLabel(text)
        label.setStyleSheet("color: #888; font-size: 12px; font-weight: bold; padding: 0 4px;")
        return label

    def _create_model_tab(self):
        """创建模型配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(24)

        # Planner 配置
        planner_group = QGroupBox("Planner 模型配置")
        planner_layout = QVBoxLayout(planner_group)
        planner_layout.setSpacing(16)

        # 提供商 + API地址
        row1 = QHBoxLayout()
        row1.setSpacing(20)

        prov_widget = QWidget()
        prov_layout = QVBoxLayout(prov_widget)
        prov_layout.setContentsMargins(0, 0, 0, 0)
        prov_layout.setSpacing(6)
        prov_layout.addWidget(self._create_section_label("提供商"))
        self.planner_provider = QComboBox()
        self.planner_provider.addItems(["ollama", "openai", "openai_compatible", "anthropic"])
        self.planner_provider.currentTextChanged.connect(lambda: self.on_provider_changed("planner"))
        prov_layout.addWidget(self.planner_provider)
        row1.addWidget(prov_widget)

        url_widget = QWidget()
        url_layout = QVBoxLayout(url_widget)
        url_layout.setContentsMargins(0, 0, 0, 0)
        url_layout.setSpacing(6)
        url_layout.addWidget(self._create_section_label("API 地址"))
        self.planner_url = QLineEdit("http://localhost:11434")
        url_layout.addWidget(self.planner_url)
        row1.addWidget(url_widget)

        planner_layout.addLayout(row1)

        # API 密钥 + 模型
        row2 = QHBoxLayout()
        row2.setSpacing(20)

        key_widget = QWidget()
        key_layout = QVBoxLayout(key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(6)
        key_layout.addWidget(self._create_section_label("API 密钥"))
        self.planner_api_key = QLineEdit()
        self.planner_api_key.setPlaceholderText("sk-...")
        self.planner_api_key.setEchoMode(QLineEdit.Password)
        key_layout.addWidget(self.planner_api_key)
        row2.addWidget(key_widget)

        model_widget = QWidget()
        model_layout = QVBoxLayout(model_widget)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(6)
        model_layout.addWidget(self._create_section_label("模型"))
        model_row = QHBoxLayout()
        self.planner_model = QComboBox()
        self.planner_model.setEditable(True)
        self.planner_model.setPlaceholderText("点击刷新获取模型列表")
        model_row.addWidget(self.planner_model, stretch=1)
        self.refresh_planner_btn = QPushButton("🔄 刷新")
        self.refresh_planner_btn.clicked.connect(lambda: self.refresh_model_list("planner"))
        model_row.addWidget(self.refresh_planner_btn)
        model_layout.addLayout(model_row)
        row2.addWidget(model_widget)

        planner_layout.addLayout(row2)

        # 状态
        self.planner_status = QLabel("⚪ 未测试")
        self.planner_status.setStyleSheet("color: #a0a0a0; font-size: 12px; padding-top: 4px;")
        planner_layout.addWidget(self.planner_status)

        layout.addWidget(planner_group)

        # Coder 配置
        coder_group = QGroupBox("Coder 模型配置")
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
        coder_independent_layout.setSpacing(16)

        row3 = QHBoxLayout()
        row3.setSpacing(20)

        c_prov_widget = QWidget()
        c_prov_layout = QVBoxLayout(c_prov_widget)
        c_prov_layout.setContentsMargins(0, 0, 0, 0)
        c_prov_layout.setSpacing(6)
        c_prov_layout.addWidget(self._create_section_label("提供商"))
        self.coder_provider = QComboBox()
        self.coder_provider.addItems(["ollama", "openai", "openai_compatible", "anthropic"])
        c_prov_layout.addWidget(self.coder_provider)
        row3.addWidget(c_prov_widget)

        c_url_widget = QWidget()
        c_url_layout = QVBoxLayout(c_url_widget)
        c_url_layout.setContentsMargins(0, 0, 0, 0)
        c_url_layout.setSpacing(6)
        c_url_layout.addWidget(self._create_section_label("API 地址"))
        self.coder_url = QLineEdit("http://localhost:11434")
        c_url_layout.addWidget(self.coder_url)
        row3.addWidget(c_url_widget)

        coder_independent_layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.setSpacing(20)

        c_key_widget = QWidget()
        c_key_layout = QVBoxLayout(c_key_widget)
        c_key_layout.setContentsMargins(0, 0, 0, 0)
        c_key_layout.setSpacing(6)
        c_key_layout.addWidget(self._create_section_label("API 密钥"))
        self.coder_api_key = QLineEdit()
        self.coder_api_key.setEchoMode(QLineEdit.Password)
        c_key_layout.addWidget(self.coder_api_key)
        row4.addWidget(c_key_widget)

        c_model_widget = QWidget()
        c_model_layout = QVBoxLayout(c_model_widget)
        c_model_layout.setContentsMargins(0, 0, 0, 0)
        c_model_layout.setSpacing(6)
        c_model_layout.addWidget(self._create_section_label("模型"))
        c_model_row = QHBoxLayout()
        self.coder_model = QComboBox()
        self.coder_model.setEditable(True)
        c_model_row.addWidget(self.coder_model, stretch=1)
        self.refresh_coder_btn = QPushButton("🔄 刷新")
        self.refresh_coder_btn.clicked.connect(lambda: self.refresh_model_list("coder"))
        c_model_row.addWidget(self.refresh_coder_btn)
        c_model_layout.addLayout(c_model_row)
        row4.addWidget(c_model_widget)

        coder_independent_layout.addLayout(row4)

        self.coder_status = QLabel("⚪ 未测试")
        self.coder_status.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        coder_independent_layout.addWidget(self.coder_status)

        coder_layout.addWidget(self.coder_independent)
        layout.addWidget(coder_group)

        # Judge 配置
        judge_group = QGroupBox("Judge 模型配置")
        judge_layout = QVBoxLayout(judge_group)
        judge_layout.setSpacing(16)

        row5 = QHBoxLayout()
        row5.setSpacing(20)

        j_prov_widget = QWidget()
        j_prov_layout = QVBoxLayout(j_prov_widget)
        j_prov_layout.setContentsMargins(0, 0, 0, 0)
        j_prov_layout.setSpacing(6)
        j_prov_layout.addWidget(self._create_section_label("提供商"))
        self.judge_provider = QComboBox()
        self.judge_provider.addItems(["ollama", "openai", "openai_compatible", "anthropic"])
        j_prov_layout.addWidget(self.judge_provider)
        row5.addWidget(j_prov_widget)

        j_url_widget = QWidget()
        j_url_layout = QVBoxLayout(j_url_widget)
        j_url_layout.setContentsMargins(0, 0, 0, 0)
        j_url_layout.setSpacing(6)
        j_url_layout.addWidget(self._create_section_label("API 地址"))
        self.judge_url = QLineEdit("http://localhost:11434")
        j_url_layout.addWidget(self.judge_url)
        row5.addWidget(j_url_widget)

        judge_layout.addLayout(row5)

        row6 = QHBoxLayout()
        row6.setSpacing(20)

        j_key_widget = QWidget()
        j_key_layout = QVBoxLayout(j_key_widget)
        j_key_layout.setContentsMargins(0, 0, 0, 0)
        j_key_layout.setSpacing(6)
        j_key_layout.addWidget(self._create_section_label("API 密钥"))
        self.judge_api_key = QLineEdit()
        self.judge_api_key.setEchoMode(QLineEdit.Password)
        j_key_layout.addWidget(self.judge_api_key)
        row6.addWidget(j_key_widget)

        j_model_widget = QWidget()
        j_model_layout = QVBoxLayout(j_model_widget)
        j_model_layout.setContentsMargins(0, 0, 0, 0)
        j_model_layout.setSpacing(6)
        j_model_layout.addWidget(self._create_section_label("模型"))
        j_model_row = QHBoxLayout()
        self.judge_model = QComboBox()
        self.judge_model.setEditable(True)
        j_model_row.addWidget(self.judge_model, stretch=1)
        self.refresh_judge_btn = QPushButton("🔄 刷新")
        self.refresh_judge_btn.clicked.connect(lambda: self.refresh_model_list("judge"))
        j_model_row.addWidget(self.refresh_judge_btn)
        j_model_layout.addLayout(j_model_row)
        row6.addWidget(j_model_widget)

        judge_layout.addLayout(row6)

        self.judge_status = QLabel("⚪ 未测试")
        self.judge_status.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        judge_layout.addWidget(self.judge_status)

        layout.addWidget(judge_group)
        layout.addStretch()

        return widget

    def _create_advanced_tab(self):
        """创建高级设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(24)

        exec_group = QGroupBox("执行参数")
        exec_layout = QVBoxLayout(exec_group)
        exec_layout.setSpacing(16)

        row1 = QHBoxLayout()
        row1.setSpacing(20)

        temp_widget = QWidget()
        temp_layout = QVBoxLayout(temp_widget)
        temp_layout.setContentsMargins(0, 0, 0, 0)
        temp_layout.setSpacing(6)
        temp_layout.addWidget(self._create_section_label("Temperature"))
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.setValue(0.7)
        temp_layout.addWidget(self.temperature)
        row1.addWidget(temp_widget)

        max_widget = QWidget()
        max_layout = QVBoxLayout(max_widget)
        max_layout.setContentsMargins(0, 0, 0, 0)
        max_layout.setSpacing(6)
        max_layout.addWidget(self._create_section_label("Max Tokens"))
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(512, 32768)
        self.max_tokens.setSingleStep(512)
        self.max_tokens.setValue(4096)
        max_layout.addWidget(self.max_tokens)
        row1.addWidget(max_widget)

        exec_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(20)

        retry_widget = QWidget()
        retry_layout = QVBoxLayout(retry_widget)
        retry_layout.setContentsMargins(0, 0, 0, 0)
        retry_layout.setSpacing(6)
        retry_layout.addWidget(self._create_section_label("重试次数"))
        self.retry_count = QSpinBox()
        self.retry_count.setRange(1, 10)
        self.retry_count.setValue(3)
        retry_layout.addWidget(self.retry_count)
        row2.addWidget(retry_widget)

        score_widget = QWidget()
        score_layout = QVBoxLayout(score_widget)
        score_layout.setContentsMargins(0, 0, 0, 0)
        score_layout.setSpacing(6)
        score_layout.addWidget(self._create_section_label("评分阈值"))
        self.score_threshold = QSpinBox()
        self.score_threshold.setRange(0, 100)
        self.score_threshold.setValue(80)
        score_layout.addWidget(self.score_threshold)
        row2.addWidget(score_widget)

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
        """创建关于标签页"""
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

        usage_title = QLabel("📖 使用说明")
        usage_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        usage_title.setStyleSheet("color: #ffffff;")
        about_layout.addWidget(usage_title)

        steps = [
            "1. 确保 Ollama / OpenAI 服务已启动",
            "2. 在「模型配置」中选择提供商和模型",
            "3. 点击「刷新」获取可用模型列表",
            "4. 返回控制台，通过对话开始使用",
        ]
        for step in steps:
            step_label = QLabel(step)
            step_label.setStyleSheet("color: #cccccc; font-size: 13px; padding: 4px 0;")
            about_layout.addWidget(step_label)

        layout.addWidget(about_group)
        layout.addStretch()

        return widget

    # ========== 事件处理 ==========

    def on_provider_changed(self, role):
        if role == "planner":
            provider = self.planner_provider.currentText()
            if provider == "ollama":
                self.planner_api_key.setVisible(False)
                self.planner_url.setVisible(True)
            elif provider in ["openai", "openai_compatible"]:
                self.planner_api_key.setVisible(True)
                self.planner_url.setVisible(True)
            elif provider == "anthropic":
                self.planner_api_key.setVisible(True)
                self.planner_url.setVisible(False)

    def on_same_as_planner_toggled(self, checked):
        self.coder_independent.setVisible(not checked)

    def refresh_model_list(self, role):
        if role == "planner":
            provider = self.planner_provider.currentText()
            base_url = self.planner_url.text()
            api_key = self.planner_api_key.text()
            combo = self.planner_model
            status_label = self.planner_status
        elif role == "coder":
            provider = self.coder_provider.currentText()
            base_url = self.coder_url.text()
            api_key = self.coder_api_key.text()
            combo = self.coder_model
            status_label = self.coder_status
        else:
            provider = self.judge_provider.currentText()
            base_url = self.judge_url.text()
            api_key = self.judge_api_key.text()
            combo = self.judge_model
            status_label = self.judge_status

        status_label.setText("⏳ 获取模型中...")
        status_label.setStyleSheet("color: #dcdcaa; font-size: 12px;")

        self.fetch_thread = FetchModelsThread(base_url, provider, api_key)
        self.fetch_thread.finished.connect(lambda models: self.on_models_fetched(combo, status_label, models))
        self.fetch_thread.error.connect(lambda e: self.on_models_error(status_label, e))
        self.fetch_thread.start()

    def on_models_fetched(self, combo, status_label, models):
        combo.clear()
        if models:
            combo.addItems(models)
            status_label.setText(f"✅ 找到 {len(models)} 个模型")
            status_label.setStyleSheet("color: #6a9955; font-size: 12px;")
        else:
            combo.addItem("未找到模型")
            status_label.setText("⚠️ 未找到任何模型")
            status_label.setStyleSheet("color: #dcdcaa; font-size: 12px;")

    def on_models_error(self, status_label, error):
        status_label.setText(f"❌ 连接失败: {error}")
        status_label.setStyleSheet("color: #f14c4c; font-size: 12px;")

    def reset_to_default(self):
        self.planner_provider.setCurrentText("ollama")
        self.planner_url.setText("http://localhost:11434")
        self.planner_api_key.clear()
        self.planner_model.clear()
        self.same_as_planner.setChecked(True)
        self.judge_provider.setCurrentText("ollama")
        self.judge_url.setText("http://localhost:11434")
        self.judge_api_key.clear()
        self.judge_model.clear()
        self.temperature.setValue(0.7)
        self.max_tokens.setValue(4096)
        self.retry_count.setValue(3)
        self.score_threshold.setValue(80)
        self.workspace_path.setText("~/archon_workspace")

    def save_config(self):
        from utils.config import Config
        config = Config()

        planner_config = {
            "provider": self.planner_provider.currentText(),
            "base_url": self.planner_url.text(),
            "model_name": self.planner_model.currentText(),
            "api_key": self.planner_api_key.text(),
            "temperature": self.temperature.value(),
            "max_tokens": self.max_tokens.value()
        }
        config.save_planner_config(planner_config)

        if self.same_as_planner.isChecked():
            coder_config = planner_config.copy()
        else:
            coder_config = {
                "provider": self.coder_provider.currentText(),
                "base_url": self.coder_url.text(),
                "model_name": self.coder_model.currentText(),
                "api_key": self.coder_api_key.text(),
                "temperature": self.temperature.value(),
                "max_tokens": self.max_tokens.value()
            }
        config.save_coder_config(coder_config)

        judge_config = {
            "provider": self.judge_provider.currentText(),
            "base_url": self.judge_url.text(),
            "model_name": self.judge_model.currentText(),
            "api_key": self.judge_api_key.text(),
            "temperature": 0.3,
            "max_tokens": 2048
        }
        config.save_judge_config(judge_config)

        advanced_config = {
            "retry_count": self.retry_count.value(),
            "score_threshold": self.score_threshold.value(),
            "workspace_path": self.workspace_path.text()
        }
        config.set("advanced", advanced_config)

        QMessageBox.information(self, "保存成功", "配置已保存，下次执行任务时将使用新配置。")