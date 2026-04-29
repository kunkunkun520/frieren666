"""
Skill 工具适配器
把 Skill 的自定义函数包装成 ToolRegistry 可用的工具
"""

from typing import Dict, Any, Callable
from core.tools.base import BaseTool


class SkillToolAdapter(BaseTool):
    """Skill 工具适配器"""

    def __init__(
        self,
        tool_name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable
    ):
        self._name = tool_name
        self._description = description
        self._parameters = {
            "type": "object",
            "properties": parameters,
            "required": list(parameters.keys())
        }
        self._handler = handler

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        try:
            return self._handler(params)
        except Exception as e:
            return {"success": False, "error": str(e)}