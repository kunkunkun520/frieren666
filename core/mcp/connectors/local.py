"""
本地连接器
加载用户编写的 Python 模块作为 MCP 工具
"""

import importlib.util
import sys
from pathlib import Path
from typing import Dict, Any, List
from core.mcp.connectors.base import BaseConnector


class LocalConnector(BaseConnector):
    """本地 Python 模块连接器"""

    def __init__(self):
        super().__init__()
        self._module = None
        self._tools = []
        self._handlers = {}

    def connect(self, config: Dict[str, Any]) -> bool:
        """加载本地模块"""
        module_path = config.get("module_path", "")

        if not module_path:
            return False

        try:
            path = Path(module_path)
            if not path.exists():
                return False

            # 动态导入模块
            module_name = path.stem
            spec = importlib.util.spec_from_file_location(module_name, path)
            self._module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = self._module
            spec.loader.exec_module(self._module)

            # 获取工具列表
            if hasattr(self._module, "get_tools"):
                self._tools = self._module.get_tools()
            elif hasattr(self._module, "tools"):
                self._tools = self._module.tools
            else:
                self._tools = []

            # 注册处理器
            for tool in self._tools:
                handler = tool.get("handler")
                if handler:
                    self._handlers[tool["name"]] = handler

            self._connected = True
            return True
        except Exception as e:
            return False

    def disconnect(self):
        """卸载模块"""
        self._connected = False
        self._module = None
        self._tools = []
        self._handlers = {}

    def list_tools(self) -> List[Dict[str, Any]]:
        """获取工具列表"""
        return [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": t.get("parameters", {}),
                    "required": t.get("required", [])
                }
            }
            for t in self._tools
        ]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用本地工具"""
        handler = self._handlers.get(tool_name)
        if not handler:
            return {"success": False, "error": f"工具不存在: {tool_name}"}

        try:
            result = handler(arguments)
            if isinstance(result, dict):
                return result
            return {"success": True, "result": str(result)}
        except Exception as e:
            return {"success": False, "error": str(e)}