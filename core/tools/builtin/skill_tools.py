
"""
Skill 工具
"""

from typing import Dict, Any
from core.tools.base import BaseTool


class ListSkillsTool(BaseTool):
    """列出可用技能"""

    @property
    def name(self) -> str:
        return "list_skills"

    @property
    def description(self) -> str:
        return "列出所有可用的技能（Skills）。当用户问「有什么技能」「可以做什么」时使用。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        skill_manager = context.get("skill_manager")
        if not skill_manager:
            return {"success": False, "error": "Skill 管理器未初始化"}

        skills = skill_manager.list_skills()
        return {
            "success": True,
            "result": skills,
            "count": len(skills)
        }


class ReadSkillTool(BaseTool):
    """读取技能详情"""

    @property
    def name(self) -> str:
        return "read_skill"

    @property
    def description(self) -> str:
        return "读取技能的完整工作流。当需要使用某个技能时调用，获取详细的执行步骤。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "技能名称"
                }
            },
            "required": ["skill_name"]
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        skill_name = params.get("skill_name")
        skill_manager = context.get("skill_manager")

        if not skill_manager:
            return {"success": False, "error": "Skill 管理器未初始化"}

        skill = skill_manager.get_skill(skill_name)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_name}"}

        return {
            "success": True,
            "result": skill.workflow,
            "skill_name": skill_name,
            "description": skill.description,
            "tools": skill.tools
        }