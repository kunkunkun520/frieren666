"""
MCP 工具适配器
把 MCP 远程工具包装成 ToolRegistry 可用的工具
"""

from typing import Dict, Any
from core.tools.base import BaseTool


class MCPToolAdapter(BaseTool):
    """MCP 工具适配器"""

    def __init__(self, tool_name: str, tool_config: Dict[str, Any], connector):
        self._name = f"mcp_{tool_name}"
        self._display_name = tool_name
        self._tool_config = tool_config
        self._connector = connector

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._tool_config.get("description", f"MCP 工具: {self._display_name}")

    @property
    def parameters(self) -> Dict[str, Any]:
        return self._tool_config.get("parameters", {
            "type": "object",
            "properties": {},
            "required": []
        })

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        return self._connector.call_tool(self._display_name, params)