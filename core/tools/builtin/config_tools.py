"""
配置管理工具
"""

from typing import Dict, Any
from core.tools.base import BaseTool


class UpdateAgentsTool(BaseTool):
    """修改项目约定"""

    @property
    def name(self) -> str:
        return "update_agents"

    @property
    def description(self) -> str:
        return "修改项目约定（AGENTS.md）。当用户说「改用 xxx 框架」「添加 xxx 规范」「更新技术栈」时使用。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": "要修改的章节，如「技术栈」「可用依赖」「编码规范」"
                },
                "content": {
                    "type": "string",
                    "description": "新的内容"
                }
            },
            "required": ["section", "content"]
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        section = params.get("section")
        content = params.get("content")

        if not section or not content:
            return {"success": False, "error": "缺少必要参数"}

        context_manager = context.get("context_manager")

        try:
            context_manager.append_to_agents(section, content)
            return {"success": True, "result": f"已更新项目约定中的「{section}」章节"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class AddDependencyTool(BaseTool):
    """添加依赖"""

    @property
    def name(self) -> str:
        return "add_dependency"

    @property
    def description(self) -> str:
        return "添加项目依赖。当用户说「需要用到 xxx 库」「安装 xxx」时使用。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dependency": {
                    "type": "string",
                    "description": "依赖名称和版本，如 fastapi==0.100.0"
                }
            },
            "required": ["dependency"]
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        dependency = params.get("dependency")

        if not dependency:
            return {"success": False, "error": "缺少必要参数"}

        context_manager = context.get("context_manager")

        try:
            context_manager.append_to_agents("可用依赖", f"- {dependency}")
            return {"success": True, "result": f"已添加依赖: {dependency}"}
        except Exception as e:
            return {"success": False, "error": str(e)}