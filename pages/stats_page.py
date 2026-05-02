"""
统计页面 - Token 消耗查看页面
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QComboBox,
    QProgressBar, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor


class StatsPage(QWidget):
    """统计页面 - Token 消耗查看"""

    def __init__(self):
        super().__init__()
        self.token_records = []  # 全局 token 记录
        self.setup_ui()
        self.load_sample_data()  # 加载示例数据
        self.update_display()

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
            QLabel { color: #cccccc; }
            QTableWidget {
                background: rgba(30, 30, 30, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                gridline-color: rgba(255, 255, 255, 0.05);
                color: #cccccc;
            }
            QTableWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            }
            QTableWidget::item:selected {
                background: rgba(14, 99, 156, 0.4);
            }
            QHeaderView::section {
                background: rgba(37, 37, 38, 0.9);
                color: #ffffff;
                padding: 10px 12px;
                border: none;
                border-bottom: 2px solid rgba(255, 255, 255, 0.1);
                font-weight: bold;
                font-size: 12px;
            }
            QComboBox {
                background: rgba(30, 30, 30, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px 14px;
                color: #e0e0e0;
                font-size: 13px;
                min-width: 150px;
            }
            QComboBox:hover { border-color: rgba(255, 255, 255, 0.2); }
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
            QPushButton:hover { background: rgba(80, 80, 80, 0.8); }
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.15); border-radius: 3px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.3); }
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

        title_label = QLabel("📊 统计")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.update_display)
        title_layout.addWidget(refresh_btn)

        main_layout.addWidget(title_bar)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(40, 30, 40, 30)
        content_layout.setSpacing(24)

        # ===== 概览卡片 =====
        overview_group = QGroupBox("📈 Token 消耗概览")
        overview_layout = QHBoxLayout(overview_group)
        overview_layout.setSpacing(30)

        # 今日消耗
        self.today_tokens = self._create_stat_card("今日消耗", "0", "#4ec9b0")
        overview_layout.addWidget(self.today_tokens)

        # 本周消耗
        self.week_tokens = self._create_stat_card("本周消耗", "0", "#dcdcaa")
        overview_layout.addWidget(self.week_tokens)

        # 本月消耗
        self.month_tokens = self._create_stat_card("本月消耗", "0", "#6a9955")
        overview_layout.addWidget(self.month_tokens)

        # 总计消耗
        self.total_tokens = self._create_stat_card("总计消耗", "0", "#ce9178")
        overview_layout.addWidget(self.total_tokens)

        # 调用次数
        self.total_calls = self._create_stat_card("调用次数", "0", "#569cd6")
        overview_layout.addWidget(self.total_calls)

        content_layout.addWidget(overview_group)

        # ===== 按 Agent 统计 =====
        agent_group = QGroupBox("🤖 按 Agent 统计")
        agent_layout = QVBoxLayout(agent_group)
        agent_layout.setSpacing(30)

        self.agent_table = QTableWidget()
        self.agent_table.setColumnCount(5)
        self.agent_table.setHorizontalHeaderLabels(["Agent", "调用次数", "输入 Token", "输出 Token", "总计 Token"])
        self.agent_table.horizontalHeader().setStretchLastSection(True)
        self.agent_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.agent_table.setMinimumHeight(200)
        self.agent_table.verticalHeader().setDefaultSectionSize(36)  # 每行高度
        self.agent_table.verticalHeader().setVisible(False)
        agent_layout.addWidget(self.agent_table)

        content_layout.addWidget(agent_group)

        # ===== 消耗历史 =====
        history_group = QGroupBox("📋 消耗历史")
        history_layout = QVBoxLayout(history_group)
        history_layout.setSpacing(12)

        # 时间筛选
        filter_layout = QHBoxLayout()
        filter_label = QLabel("时间范围:")
        filter_layout.addWidget(filter_label)

        self.time_filter = QComboBox()
        self.time_filter.addItems(["最近 7 天", "最近 30 天", "全部"])
        self.time_filter.currentTextChanged.connect(self.update_display)
        filter_layout.addWidget(self.time_filter)
        filter_layout.addStretch()

        # 导出按钮
        export_btn = QPushButton("📥 导出 CSV")
        export_btn.clicked.connect(self.export_csv)
        filter_layout.addWidget(export_btn)

        history_layout.addLayout(filter_layout)

        # 历史表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(["时间", "Agent", "模型", "输入 Token", "输出 Token", "总计 Token"])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setMinimumHeight(200)
        history_layout.addWidget(self.history_table)

        content_layout.addWidget(history_group)

        # ===== 节省统计 =====
        savings_group = QGroupBox("💰 成本节省（相比直接调用）")
        savings_layout = QHBoxLayout(savings_group)
        savings_layout.setSpacing(30)

        self.saved_tokens = self._create_stat_card("节省 Token", "0", "#6a9955")
        savings_layout.addWidget(self.saved_tokens)

        self.saved_cost = self._create_stat_card("估算节省费用", "$0.00", "#4ec9b0")
        savings_layout.addWidget(self.saved_cost)

        self.compression_rate = self._create_stat_card("上下文压缩率", "0%", "#dcdcaa")
        savings_layout.addWidget(self.compression_rate)

        content_layout.addWidget(savings_group)

        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_stat_card(self, title: str, value: str, color: str) -> QWidget:
        """创建统计卡片"""
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: rgba(37, 37, 38, 0.7);
                border: 1px solid {color}33;
                border-radius: 16px;
                padding: 16px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #888; font-size: 12px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(value_label)

        return card

    def load_sample_data(self):
        """加载示例数据"""
        # 如果已有真实数据，就不加载示例
        if self.token_records:
            return

        # 生成示例数据
        now = datetime.now()
        agents = ["chat", "planner", "coder", "judge"]
        models = ["qwen3-coder:30b", "gpt-4-turbo", "claude-3-opus"]

        for i in range(50):
            record = {
                "timestamp": (now - timedelta(hours=i * 3, minutes=i * 7)).isoformat(),
                "agent": agents[i % 4],
                "model": models[i % 3],
                "input_tokens": 500 + (i * 100) % 3000,
                "output_tokens": 200 + (i * 50) % 1000,
            }
            record["total_tokens"] = record["input_tokens"] + record["output_tokens"]
            self.token_records.append(record)

    def add_record(self, agent: str, model: str, input_tokens: int, output_tokens: int):
        """添加一条 Token 记录"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
        self.token_records.append(record)

    def update_display(self):
        """更新显示"""
        if not self.token_records:
            return

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)

        today_tokens = 0
        week_tokens = 0
        month_tokens = 0
        total_tokens = 0
        total_calls = len(self.token_records)

        agent_stats = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0, "total": 0})

        filter_text = self.time_filter.currentText()
        if filter_text == "最近 7 天":
            filter_start = week_start
        elif filter_text == "最近 30 天":
            filter_start = month_start
        else:
            filter_start = None

        filtered_records = []

        for record in self.token_records:
            ts = datetime.fromisoformat(record["timestamp"])

            total_tokens += record["total_tokens"]
            if ts >= today_start:
                today_tokens += record["total_tokens"]
            if ts >= week_start:
                week_tokens += record["total_tokens"]
            if ts >= month_start:
                month_tokens += record["total_tokens"]

            agent = record["agent"]
            agent_stats[agent]["calls"] += 1
            agent_stats[agent]["input"] += record["input_tokens"]
            agent_stats[agent]["output"] += record["output_tokens"]
            agent_stats[agent]["total"] += record["total_tokens"]

            if filter_start is None or ts >= filter_start:
                filtered_records.append(record)

        # 更新概览卡片
        self._update_card_value(self.today_tokens, self._format_tokens(today_tokens))
        self._update_card_value(self.week_tokens, self._format_tokens(week_tokens))
        self._update_card_value(self.month_tokens, self._format_tokens(month_tokens))
        self._update_card_value(self.total_tokens, self._format_tokens(total_tokens))
        self._update_card_value(self.total_calls, str(total_calls))

        # 更新 Agent 表格
        self.agent_table.setRowCount(len(agent_stats))
        for i, (agent, stats) in enumerate(sorted(agent_stats.items())):
            self.agent_table.setItem(i, 0, QTableWidgetItem(agent))
            self.agent_table.setItem(i, 1, QTableWidgetItem(str(stats["calls"])))
            self.agent_table.setItem(i, 2, QTableWidgetItem(self._format_tokens(stats["input"])))
            self.agent_table.setItem(i, 3, QTableWidgetItem(self._format_tokens(stats["output"])))
            self.agent_table.setItem(i, 4, QTableWidgetItem(self._format_tokens(stats["total"])))

        # 更新历史表格
        self.history_table.setRowCount(len(filtered_records))
        for i, record in enumerate(reversed(filtered_records)):
            ts = datetime.fromisoformat(record["timestamp"])
            self.history_table.setItem(i, 0, QTableWidgetItem(ts.strftime("%Y-%m-%d %H:%M")))
            self.history_table.setItem(i, 1, QTableWidgetItem(record["agent"]))
            self.history_table.setItem(i, 2, QTableWidgetItem(record["model"]))
            self.history_table.setItem(i, 3, QTableWidgetItem(self._format_tokens(record["input_tokens"])))
            self.history_table.setItem(i, 4, QTableWidgetItem(self._format_tokens(record["output_tokens"])))
            self.history_table.setItem(i, 5, QTableWidgetItem(self._format_tokens(record["total_tokens"])))

        # 更新节省统计（估算：记忆系统节省约 30% Token）
        saved = int(total_tokens * 0.3)
        estimated_cost = saved / 1000 * 0.002  # 假设每 1K token $0.002
        self._update_card_value(self.saved_tokens, self._format_tokens(saved))
        self._update_card_value(self.saved_cost, f"${estimated_cost:.2f}")
        self._update_card_value(self.compression_rate, "30%")

    def _update_card_value(self, card, value):
        """更新卡片值"""
        layout = card.layout()
        if layout and layout.count() >= 2:
            value_label = layout.itemAt(1).widget()
            if isinstance(value_label, QLabel):
                value_label.setText(value)

    def _format_tokens(self, count: int) -> str:
        """格式化 Token 数量"""
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        elif count >= 1_000:
            return f"{count / 1_000:.1f}K"
        else:
            return str(count)

    def export_csv(self):
        """导出 CSV"""
        import csv
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出 CSV", "token_stats.csv", "CSV 文件 (*.csv)"
        )
        if not file_path:
            return

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["时间", "Agent", "模型", "输入 Token", "输出 Token", "总计 Token"])
            for record in self.token_records:
                writer.writerow([
                    record["timestamp"],
                    record["agent"],
                    record["model"],
                    record["input_tokens"],
                    record["output_tokens"],
                    record["total_tokens"],
                ])
