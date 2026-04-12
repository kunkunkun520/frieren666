"""
文件浏览器页面
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget,
    QTreeWidgetItem, QTextEdit, QPushButton, QLabel,
    QSplitter, QFileDialog
)
from PySide6.QtCore import Qt


class FilesPage(QWidget):
    """文件浏览器页面"""

    def __init__(self):
        super().__init__()
        self.current_path = Path.home()
        self.setup_ui()
        self.refresh_file_tree()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.path_label = QLabel(str(self.current_path))
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh_file_tree)
        self.open_btn = QPushButton("📂 打开文件夹")
        self.open_btn.clicked.connect(self.open_folder)

        toolbar.addWidget(self.path_label)
        toolbar.addStretch()
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("文件浏览器")
        self.file_tree.itemClicked.connect(self.on_file_clicked)
        splitter.addWidget(self.file_tree)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        splitter.addWidget(self.preview)

        splitter.setSizes([300, 500])
        layout.addWidget(splitter)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 保存")
        self.save_btn.setEnabled(False)
        self.run_test_btn = QPushButton("🧪 运行测试")
        self.git_btn = QPushButton("📦 Git提交")

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.run_test_btn)
        btn_layout.addWidget(self.git_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def set_root_path(self, path):
        """设置根路径"""
        if isinstance(path, str):
            self.current_path = Path(path)
        else:
            self.current_path = path
        self.path_label.setText(str(self.current_path))
        self.refresh_file_tree()

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", str(self.current_path))
        if folder:
            self.current_path = Path(folder)
            self.path_label.setText(str(self.current_path))
            self.refresh_file_tree()

    def refresh_file_tree(self):
        self.file_tree.clear()
        if not self.current_path.exists():
            return
        root_item = QTreeWidgetItem([self.current_path.name])
        self.file_tree.addTopLevelItem(root_item)
        self._add_directory_items(root_item, self.current_path)
        root_item.setExpanded(True)

    def _add_directory_items(self, parent_item, path: Path):
        try:
            for item in sorted(path.iterdir()):
                if item.name.startswith('.'):
                    continue
                if item.is_dir():
                    child = QTreeWidgetItem([item.name])
                    parent_item.addChild(child)
                    self._add_directory_items(child, item)
                elif item.suffix in ['.py', '.html', '.css', '.js', '.json', '.txt', '.md']:
                    child = QTreeWidgetItem([item.name])
                    parent_item.addChild(child)
        except PermissionError:
            pass

    def on_file_clicked(self, item, column):
        path_parts = []
        current = item
        while current:
            path_parts.insert(0, current.text(0))
            current = current.parent()
        if not path_parts:
            return
        file_path = self.current_path
        for part in path_parts[1:]:
            file_path = file_path / part
        if file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8")
                self.preview.setPlainText(content)
                self.save_btn.setEnabled(True)
            except Exception as e:
                self.preview.setPlainText(f"无法读取文件: {e}")
                self.save_btn.setEnabled(False)