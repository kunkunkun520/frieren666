"""
配置管理 - 使用 QSettings 存储
"""

import os
import json
from pathlib import Path
from PySide6.QtCore import QSettings



DEFAULT_CONFIG = {
    "version": 1,
    "planner": {
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model_name": "",  # 空字符串，让用户自己选
        "api_key": "",
        "temperature": 0.7,
        "max_tokens": 4096
    },
    "coder": {
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model_name": "",
        "api_key": "",
        "temperature": 0.7,
        "max_tokens": 4096
    },
    "judge": {
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model_name": "",
        "api_key": "",
        "temperature": 0.3,
        "max_tokens": 2048
    },
    "advanced": {
        "retry_count": 3,
        "score_threshold": 80,
        "workspace_path": "~/archon_workspace"
    },
    "rag": {
            "embedding_provider": "ollama",
            "embedding_model": "nomic-embed-text",
            "embedding_base_url": "http://localhost:11434",
            "embedding_api_key": ""
        }
}


class Config:
    """配置管理器"""

    def __init__(self):
        self.settings = QSettings("Archon", "ArchonDesktop")

    def get(self, key: str, default=None):
        return self.settings.value(key, default)

    def set(self, key: str, value):
        self.settings.setValue(key, value)

    def get_planner_config(self) -> dict:
        config = self.get("planner", DEFAULT_CONFIG["planner"])
        # 确保返回的是字典
        if isinstance(config, str):
            import json
            config = json.loads(config)
        return config

    def get_coder_config(self) -> dict:
        config = self.get("coder", DEFAULT_CONFIG["coder"])
        if isinstance(config, str):
            import json
            config = json.loads(config)
        return config

    def get_judge_config(self) -> dict:
        config = self.get("judge", DEFAULT_CONFIG["judge"])
        if isinstance(config, str):
            import json
            config = json.loads(config)
        return config

    def save_planner_config(self, config: dict):
        self.set("planner", config)

    def save_coder_config(self, config: dict):
        self.set("coder", config)

    def save_judge_config(self, config: dict):
        self.set("judge", config)

    def get_workspace_path(self) -> Path:
        advanced = self.get("advanced", DEFAULT_CONFIG["advanced"])
        if isinstance(advanced, str):
            import json
            advanced = json.loads(advanced)
        path = advanced.get("workspace_path", "~/archon_workspace")
        return Path(os.path.expanduser(path))
    def get_rag_config(self) -> dict:

        config = self.get("rag", DEFAULT_CONFIG["rag"])
        if isinstance(config, str):
            config = json.loads(config)
        return config
    def save_rag_config(self, config: dict):
        self.set("rag", config)