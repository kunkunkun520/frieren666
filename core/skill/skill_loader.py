"""
Skill 加载器
从文件夹中加载 Skill（SKILL.md + tools.py）
"""

import re
import yaml
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional


class Skill:
    """技能定义"""

    def __init__(self):
        self.name: str = ""
        self.description: str = ""
        self.version: str = "1.0.0"
        self.triggers: List[str] = []
        self.requires_tools: List[str] = []
        self.workflow: str = ""
        self.custom_tools: Dict[str, Dict] = {}
        self.folder_path: str = ""

    @classmethod
    def from_folder(cls, folder_path: Path) -> Optional["Skill"]:
        """从文件夹加载 Skill"""
        skill_md = folder_path / "SKILL.md"
        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding="utf-8")

            # 提取 YAML 元数据
            yaml_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not yaml_match:
                return None

            metadata = yaml.safe_load(yaml_match.group(1))
            if not metadata:
                return None

            skill = cls()
            skill.name = metadata.get("name", folder_path.name)
            skill.description = metadata.get("description", "")
            skill.version = metadata.get("version", "1.0.0")
            skill.triggers = metadata.get("triggers", [])
            skill.requires_tools = metadata.get("requires_tools", [])
            skill.folder_path = str(folder_path)

            # 提取工作流
            workflow_match = re.search(
                r'^---\n.*?\n---\n(.*)', content, re.DOTALL
            )
            if workflow_match:
                skill.workflow = workflow_match.group(1).strip()

            # 加载自定义工具
            skill._load_custom_tools(folder_path)

            return skill
        except Exception as e:
            print(f"加载 Skill 失败: {folder_path} - {e}")
            return None

    def _load_custom_tools(self, folder_path: Path):
        """加载自定义工具"""
        tools_py = folder_path / "tools.py"
        if not tools_py.exists():
            return

        try:
            module_name = f"skill_{self.name.replace(' ', '_').replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(
                module_name, tools_py
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            if hasattr(module, "TOOLS"):
                for tool_name, tool_config in module.TOOLS.items():
                    prefixed_name = f"skill_{self.name}__{tool_name}"
                    self.custom_tools[prefixed_name] = {
                        "name": prefixed_name,
                        "description": tool_config.get("description", ""),
                        "function": tool_config.get("function"),
                        "parameters": tool_config.get("parameters", {})
                    }
        except Exception as e:
            print(f"加载自定义工具失败: {tools_py} - {e}")

    def get_tools_list(self) -> List[Dict]:
        """获取自定义工具列表（用于注册到 ToolRegistry）"""
        tools = []
        for tool_name, tool_config in self.custom_tools.items():
            tools.append({
                "name": tool_name,
                "description": tool_config["description"],
                "parameters": tool_config["parameters"],
                "handler": tool_config["function"]
            })
        return tools

    def to_dict(self) -> Dict:
        """转为摘要字典"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "triggers": self.triggers,
            "custom_tools_count": len(self.custom_tools),
            "workflow_preview": self.workflow[:200] + "..."
            if len(self.workflow) > 200
            else self.workflow,
        }