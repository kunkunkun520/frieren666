"""
模型配置页面 - 用户自己选择模型
"""

import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QGroupBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QTabWidget,
    QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal


class FetchModelsThread(QThread):
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
        # OpenAI 兼容 API 的模型列表
        url = self.base_url.rstrip('/') + "/models"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = [m["id"] for m in data.get("data", [])]
            # 过滤掉一些不常用的模型
            models = [m for m in models if not m.startswith("whisper") and not m.startswith("tts")]
            self.finished.emit(models)
        else:
            self.error.emit(f"HTTP {response.status_code}")

    def _fetch_anthropic(self):
        # Anthropic 的模型列表是固定的
        models = [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-3-5-sonnet-20240620",
            "claude-3-5-haiku-20241022",
        ]
        self.finished.emit(models)


class SettingsPage(QWidget):
    """模型配置页面"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 标签页
        tabs = QTabWidget()

        # 模型配置标签页
        model_tab = self._create_model_tab()
        tabs.addTab(model_tab, "模型配置")

        # 高级设置标签页
        advanced_tab = self._create_advanced_tab()
        tabs.addTab(advanced_tab, "高级设置")

        # 关于标签页
        about_tab = self._create_about_tab()
        tabs.addTab(about_tab, "关于")

        layout.addWidget(tabs)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.default_btn = QPushButton("恢复默认")
        self.default_btn.clicked.connect(self.reset_to_default)
        self.apply_btn = QPushButton("应用配置")
        self.apply_btn.setStyleSheet("background-color: #0078d4; color: white;")
        self.apply_btn.clicked.connect(self.save_config)

        btn_layout.addStretch()
        btn_layout.addWidget(self.default_btn)
        btn_layout.addWidget(self.apply_btn)
        layout.addLayout(btn_layout)

    def _create_model_tab(self):
        """创建模型配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)

        # ===== Planner 配置 =====
        planner_group = QGroupBox("Planner 模型配置")
        planner_layout = QVBoxLayout(planner_group)

        # 提供商
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("提供商:"))
        self.planner_provider = QComboBox()
        self.planner_provider.addItems(["ollama", "openai", "openai_compatible", "anthropic"])
        self.planner_provider.currentTextChanged.connect(lambda: self.on_provider_changed("planner"))
        provider_layout.addWidget(self.planner_provider)
        provider_layout.addStretch()
        planner_layout.addLayout(provider_layout)

        # API 地址
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("API地址:"))
        self.planner_url = QLineEdit("http://localhost:11434")
        url_layout.addWidget(self.planner_url)
        planner_layout.addLayout(url_layout)

        # API 密钥（OpenAI/Anthropic 需要）
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("API密钥:"))
        self.planner_api_key = QLineEdit()
        self.planner_api_key.setPlaceholderText("sk-... (OpenAI/Anthropic需要)")
        self.planner_api_key.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(self.planner_api_key)
        planner_layout.addLayout(api_layout)

        # 模型选择
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型:"))
        self.planner_model = QComboBox()
        self.planner_model.setEditable(True)
        self.planner_model.setPlaceholderText("点击「刷新模型列表」获取")
        model_layout.addWidget(self.planner_model, stretch=1)

        self.refresh_planner_btn = QPushButton("🔄 刷新模型列表")
        self.refresh_planner_btn.clicked.connect(lambda: self.refresh_model_list("planner"))
        model_layout.addWidget(self.refresh_planner_btn)
        planner_layout.addLayout(model_layout)

        # 连接状态
        self.planner_status = QLabel("⚪ 未测试")
        self.planner_status.setStyleSheet("color: #a0a0a0;")
        planner_layout.addWidget(self.planner_status)

        layout.addWidget(planner_group)

        # ===== Coder 配置（复用 Planner）=====
        coder_group = QGroupBox("Coder 模型配置")
        coder_layout = QVBoxLayout(coder_group)

        self.same_as_planner = QCheckBox("使用与 Planner 相同的配置")
        self.same_as_planner.setChecked(True)
        self.same_as_planner.toggled.connect(self.on_same_as_planner_toggled)
        coder_layout.addWidget(self.same_as_planner)

        # Coder 独立配置（默认隐藏）
        self.coder_independent = QWidget()
        coder_independent_layout = QVBoxLayout(self.coder_independent)
        coder_independent_layout.setContentsMargins(0, 0, 0, 0)

        # 提供商
        provider_layout2 = QHBoxLayout()
        provider_layout2.addWidget(QLabel("提供商:"))
        self.coder_provider = QComboBox()
        self.coder_provider.addItems(["ollama", "openai", "openai_compatible", "anthropic"])
        provider_layout2.addWidget(self.coder_provider)
        provider_layout2.addStretch()
        coder_independent_layout.addLayout(provider_layout2)

        # API 地址
        url_layout2 = QHBoxLayout()
        url_layout2.addWidget(QLabel("API地址:"))
        self.coder_url = QLineEdit("http://localhost:11434")
        coder_independent_layout.addLayout(url_layout2)

        # API 密钥
        api_layout2 = QHBoxLayout()
        api_layout2.addWidget(QLabel("API密钥:"))
        self.coder_api_key = QLineEdit()
        self.coder_api_key.setEchoMode(QLineEdit.Password)
        api_layout2.addWidget(self.coder_api_key)
        coder_independent_layout.addLayout(api_layout2)

        # 模型
        model_layout2 = QHBoxLayout()
        model_layout2.addWidget(QLabel("模型:"))
        self.coder_model = QComboBox()
        self.coder_model.setEditable(True)
        model_layout2.addWidget(self.coder_model, stretch=1)
        self.refresh_coder_btn = QPushButton("🔄 刷新模型列表")
        self.refresh_coder_btn.clicked.connect(lambda: self.refresh_model_list("coder"))
        model_layout2.addWidget(self.refresh_coder_btn)
        coder_independent_layout.addLayout(model_layout2)

        self.coder_status = QLabel("⚪ 未测试")
        coder_independent_layout.addWidget(self.coder_status)

        coder_layout.addWidget(self.coder_independent)
        self.coder_independent.setVisible(False)

        layout.addWidget(coder_group)

        # ===== Judge 配置 =====
        judge_group = QGroupBox("Judge 模型配置 (Gemma)")
        judge_layout = QVBoxLayout(judge_group)

        # 提供商
        provider_layout3 = QHBoxLayout()
        provider_layout3.addWidget(QLabel("提供商:"))
        self.judge_provider = QComboBox()
        self.judge_provider.addItems(["ollama", "openai", "openai_compatible", "anthropic"])
        provider_layout3.addWidget(self.judge_provider)
        provider_layout3.addStretch()
        judge_layout.addLayout(provider_layout3)

        # API 地址
        url_layout3 = QHBoxLayout()
        url_layout3.addWidget(QLabel("API地址:"))
        self.judge_url = QLineEdit("http://localhost:11434")
        judge_layout.addLayout(url_layout3)

        # API 密钥
        api_layout3 = QHBoxLayout()
        api_layout3.addWidget(QLabel("API密钥:"))
        self.judge_api_key = QLineEdit()
        self.judge_api_key.setEchoMode(QLineEdit.Password)
        api_layout3.addWidget(self.judge_api_key)
        judge_layout.addLayout(api_layout3)

        # 模型
        model_layout3 = QHBoxLayout()
        model_layout3.addWidget(QLabel("模型:"))
        self.judge_model = QComboBox()
        self.judge_model.setEditable(True)
        model_layout3.addWidget(self.judge_model, stretch=1)
        self.refresh_judge_btn = QPushButton("🔄 刷新模型列表")
        self.refresh_judge_btn.clicked.connect(lambda: self.refresh_model_list("judge"))
        model_layout3.addWidget(self.refresh_judge_btn)
        judge_layout.addLayout(model_layout3)

        self.judge_status = QLabel("⚪ 未测试")
        judge_layout.addWidget(self.judge_status)

        layout.addWidget(judge_group)
        layout.addStretch()

        return widget

    def _create_advanced_tab(self):
        """创建高级设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        exec_group = QGroupBox("执行参数")
        exec_layout = QVBoxLayout(exec_group)

        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Temperature:"))
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.setValue(0.7)
        temp_layout.addWidget(self.temperature)
        temp_layout.addStretch()
        exec_layout.addLayout(temp_layout)

        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max Tokens:"))
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(512, 32768)
        self.max_tokens.setSingleStep(512)
        self.max_tokens.setValue(4096)
        max_layout.addWidget(self.max_tokens)
        max_layout.addStretch()
        exec_layout.addLayout(max_layout)

        retry_layout = QHBoxLayout()
        retry_layout.addWidget(QLabel("重试次数:"))
        self.retry_count = QSpinBox()
        self.retry_count.setRange(1, 10)
        self.retry_count.setValue(3)
        retry_layout.addWidget(self.retry_count)
        retry_layout.addStretch()
        exec_layout.addLayout(retry_layout)

        score_layout = QHBoxLayout()
        score_layout.addWidget(QLabel("评分阈值:"))
        self.score_threshold = QSpinBox()
        self.score_threshold.setRange(0, 100)
        self.score_threshold.setValue(80)
        score_layout.addWidget(self.score_threshold)
        score_layout.addStretch()
        exec_layout.addLayout(score_layout)

        layout.addWidget(exec_group)

        workspace_group = QGroupBox("工作区")
        workspace_layout = QHBoxLayout(workspace_group)
        self.workspace_path = QLineEdit("~/archon_workspace")
        workspace_layout.addWidget(self.workspace_path)
        layout.addWidget(workspace_group)

        layout.addStretch()
        return widget

    def _create_about_tab(self):
        """创建关于标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        about_text = QLabel(
            "<h1>Archon Desktop</h1>"
            "<p>版本: 1.0.0</p>"
            "<p>AI编程助手 - 让AI像资深工程师一样工作</p>"
            "<br>"
            "<p><b>使用说明:</b></p>"
            "<ul>"
            "<li>1. 确保 Ollama/OpenAI 服务已启动</li>"
            "<li>2. 在「模型配置」中选择提供商和模型</li>"
            "<li>3. 点击「测试连接」确认配置正确</li>"
            "<li>4. 返回控制台输入任务开始使用</li>"
            "</ul>"
        )
        about_text.setWordWrap(True)
        about_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(about_text)

        layout.addStretch()
        return widget

    def on_provider_changed(self, role):
        """提供商改变时更新UI"""
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
                self.planner_url.setVisible(False)  # Anthropic 不需要 base_url

    def on_same_as_planner_toggled(self, checked):
        """Coder 是否复用 Planner 配置"""
        self.coder_independent.setVisible(not checked)

    def refresh_model_list(self, role):
        """刷新模型列表"""
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
        else:  # judge
            provider = self.judge_provider.currentText()
            base_url = self.judge_url.text()
            api_key = self.judge_api_key.text()
            combo = self.judge_model
            status_label = self.judge_status

        status_label.setText("⏳ 获取模型中...")
        status_label.setStyleSheet("color: #dcdcaa;")

        self.fetch_thread = FetchModelsThread(base_url, provider, api_key)
        self.fetch_thread.finished.connect(lambda models: self.on_models_fetched(combo, status_label, models))
        self.fetch_thread.error.connect(lambda e: self.on_models_error(status_label, e))
        self.fetch_thread.start()

    def on_models_fetched(self, combo, status_label, models):
        """模型列表获取成功"""
        combo.clear()
        if models:
            combo.addItems(models)
            status_label.setText(f"✅ 找到 {len(models)} 个模型")
            status_label.setStyleSheet("color: #6a9955;")
        else:
            combo.addItem("未找到模型，请先运行 ollama pull <模型名>")
            status_label.setText("⚠️ 未找到任何模型")
            status_label.setStyleSheet("color: #dcdcaa;")

    def on_models_error(self, status_label, error):
        """模型列表获取失败"""
        status_label.setText(f"❌ 连接失败: {error}")
        status_label.setStyleSheet("color: #f14c4c;")

    def reset_to_default(self):
        """恢复默认配置"""
        # 清空所有输入
        self.planner_provider.setCurrentText("ollama")
        self.planner_url.setText("http://localhost:11434")
        self.planner_api_key.clear()
        self.planner_model.clear()
        self.planner_model.setPlaceholderText("点击「刷新模型列表」获取")

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
        """保存配置"""
        from utils.config import Config
        config = Config()

        # 保存 Planner 配置
        planner_config = {
            "provider": self.planner_provider.currentText(),
            "base_url": self.planner_url.text(),
            "model_name": self.planner_model.currentText(),
            "api_key": self.planner_api_key.text(),
            "temperature": self.temperature.value(),
            "max_tokens": self.max_tokens.value()
        }
        config.save_planner_config(planner_config)

        # 保存 Coder 配置
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

        # 保存 Judge 配置
        judge_config = {
            "provider": self.judge_provider.currentText(),
            "base_url": self.judge_url.text(),
            "model_name": self.judge_model.currentText(),
            "api_key": self.judge_api_key.text(),
            "temperature": 0.3,
            "max_tokens": 2048
        }
        config.save_judge_config(judge_config)

        # 保存高级配置
        advanced_config = {
            "retry_count": self.retry_count.value(),
            "score_threshold": self.score_threshold.value(),
            "workspace_path": self.workspace_path.text()
        }
        config.set("advanced", advanced_config)

        QMessageBox.information(self, "保存成功", "配置已保存，下次执行任务时将使用新配置。")