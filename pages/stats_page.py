"""
统计监控页面
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QFrame, QTabWidget
)
from PySide6.QtCore import Qt


class StatsPage(QWidget):
    """统计监控页面"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 顶部统计卡片
        cards_layout = QHBoxLayout()

        cards = [
            ("🔢 Token消耗", "12,345", "+23%"),
            ("📊 请求次数", "47", "+5%"),
            ("📦 Git提交", "12", "持平"),
            ("⏱️ 运行时长", "3h 24m", "+12%"),
        ]

        for title, value, change in cards:
            card = self._create_stat_card(title, value, change)
            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)

        # 图表区域（占位）
        tabs = QTabWidget()

        # Token趋势图（占位）
        token_tab = QWidget()
        token_layout = QVBoxLayout(token_tab)
        token_layout.addWidget(QLabel("📈 Token消耗趋势图"))
        token_layout.addWidget(QLabel("[图表区域 - 待实现]"))
        token_tab.setLayout(token_layout)
        tabs.addTab(token_tab, "Token趋势")

        # 模型调用分布
        model_tab = QWidget()
        model_layout = QVBoxLayout(model_tab)
        model_layout.addWidget(QLabel("🥧 模型调用分布"))
        model_layout.addWidget(QLabel("Qwen-Coder: ████████████████████ 80%"))
        model_layout.addWidget(QLabel("Gemma:      ████ 20%"))
        model_tab.setLayout(model_layout)
        tabs.addTab(model_tab, "模型分布")

        # 每日统计
        daily_tab = QWidget()
        daily_layout = QVBoxLayout(daily_tab)
        daily_layout.addWidget(QLabel("📅 每日使用统计"))
        daily_layout.addWidget(QLabel("[表格区域 - 待实现]"))
        daily_tab.setLayout(daily_layout)
        tabs.addTab(daily_tab, "每日统计")

        layout.addWidget(tabs)

    def _create_stat_card(self, title, value, change):
        """创建统计卡片"""
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 12px;
            }
        """)

        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(value_label)

        change_label = QLabel(change)
        change_color = "#6a9955" if "+" in change else "#f14c4c"
        change_label.setStyleSheet(f"color: {change_color}; font-size: 11px;")
        layout.addWidget(change_label)

        return card