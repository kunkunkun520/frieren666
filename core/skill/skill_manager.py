"""
Skill 管理器
"""

from pathlib import Path
from typing import Dict, List, Optional
from core.skill.skill_loader import Skill


class SkillManager:
    """Skill 管理器"""

    def __init__(self, skills_dir: Path = None):
        self.skills_dir = skills_dir or Path("extensions/skills")
        self.skills: Dict[str, Skill] = {}

    def load_all(self) -> int:
        """加载所有 Skill"""
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            self._create_example_skill()
            return 0

        count = 0
        for folder in self.skills_dir.iterdir():
            if folder.is_dir() and not folder.name.startswith("."):
                skill = Skill.from_folder(folder)
                if skill:
                    self.skills[skill.name] = skill
                    count += 1

        return count

    def get_skill(self, name: str) -> Optional[Skill]:
        return self.skills.get(name)

    def get_skills_prompt(self) -> str:
        """生成 Skill 列表 Prompt"""
        if not self.skills:
            return ""

        lines = ["\n## 可用技能 (Skills)"]
        for skill in self.skills.values():
            lines.append(f"\n### {skill.name}")
            lines.append(f"描述: {skill.description}")
            lines.append(f"触发词: {', '.join(skill.triggers)}")
            if skill.custom_tools:
                lines.append(f"自定义工具: {', '.join(skill.custom_tools.keys())}")
            lines.append("使用 read_skill 工具读取完整工作流")

        return "\n".join(lines)

    def find_matching_skills(self, user_message: str) -> List[Skill]:
        """查找匹配的 Skill"""
        matching = []
        message_lower = user_message.lower()
        for skill in self.skills.values():
            for trigger in skill.triggers:
                if trigger.lower() in message_lower:
                    matching.append(skill)
                    break
        return matching

    def register_all_tools(self, registry, agent_name: str):
        """将匹配的 Skill 工具注册到指定的 ToolRegistry"""
        for skill in self.skills.values():
            for tool_config in skill.get_tools_list():
                from core.skill.skill_tool_adapter import SkillToolAdapter
                adapter = SkillToolAdapter(
                    tool_config["name"],
                    tool_config["description"],
                    tool_config["parameters"],
                    tool_config["handler"]
                )
                registry.register(adapter)

    def _create_example_skill(self):
        """创建示例 Skill 文件夹"""
        example_dir = self.skills_dir / "前端开发文档生成器"
        example_dir.mkdir(parents=True, exist_ok=True)

        skill_md = example_dir / "SKILL.md"
        if not skill_md.exists():
            skill_md.write_text("""---
name: 前端开发文档生成器
description: 根据前端代码自动生成组件文档
triggers:
  - 生成文档
  - 写开发文档
  - 生成组件说明
requires_tools:
  - list_files
  - read_file
  - create_file
---

# 前端开发文档生成器

## 工作流

### 步骤 1：扫描组件目录
使用 list_files 扫描 src/components/ 目录。

### 步骤 2：分析组件
使用 read_file 读取每个组件代码。

### 步骤 3：生成文档
为每个组件生成 Markdown 文档。

### 步骤 4：写入文件
使用 create_file 写入 docs/components/ 目录。
""", encoding="utf-8")

        tools_py = example_dir / "tools.py"
        if not tools_py.exists():
            tools_py.write_text("""\"\"\"
前端开发文档生成器 - 自定义工具
\"\"\"

def parse_props(params):
    file_content = params.get("file_content", "")
    return {"success": True, "result": "Props 解析结果"}

TOOLS = {
    "parse_props": {
        "function": parse_props,
        "description": "解析组件 Props",
        "parameters": {
            "file_content": {"type": "string", "description": "文件内容"}
        }
    }
}
""", encoding="utf-8")