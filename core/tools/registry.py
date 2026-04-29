"""
工具注册表 - 管理所有工具
支持多个实例（每个 Agent 一个）
"""

from typing import Dict, List, Optional, Any
from core.tools.base import BaseTool, ToolResult


class ToolRegistry:
    """工具注册表 - 支持多个实例（每个 Agent 一个）"""

    def __init__(self, name: str = "default"):
        self.name = name
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        if tool.name in self._tools:
            print(f"警告: 工具 '{tool.name}' 已存在于 {self.name}，将被覆盖")
        self._tools[tool.name] = tool
        print(f"✅ [{self.name}] 工具已注册: {tool.name}")

    def register_many(self, tools: List[BaseTool]) -> None:
        """批量注册工具"""
        for tool in tools:
            self.register(tool)

    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            print(f"🗑️ [{self.name}] 工具已注销: {name}")
            return True
        return False

    def clear(self) -> None:
        """清空所有工具"""
        count = len(self._tools)
        self._tools.clear()
        print(f"🗑️ [{self.name}] 已清空 {count} 个工具")

    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)

    def list_all(self) -> List[BaseTool]:
        """列出所有工具"""
        return list(self._tools.values())

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的 Schema（用于生成 Prompt）"""
        return [tool.to_dict() for tool in self._tools.values()]

    def get_tools_prompt(self) -> str:
        """生成工具列表 Prompt"""
        if not self._tools:
            return "暂无可用工具"

        lines = ["## 可用工具"]
        for tool in self._tools.values():
            lines.append(f"\n### {tool.name}")
            lines.append(f"**描述**: {tool.description}")
            lines.append(f"**参数**:")
            params = tool.parameters.get("properties", {})
            required = tool.parameters.get("required", [])
            for param_name, param_info in params.items():
                is_required = "必填" if param_name in required else "可选"
                param_desc = param_info.get('description', '')
                param_type = param_info.get('type', 'string')
                lines.append(f"  - `{param_name}` ({param_type}, {is_required}): {param_desc}")

        return "\n".join(lines)

    def execute(self, name: str, params: Dict[str, Any], context: Any = None) -> ToolResult:
        """执行工具"""
        tool = self.get(name)
        if not tool:
            return ToolResult.fail(f"工具不存在: {name}")

        try:
            result = tool.execute(params, context)
            if isinstance(result, dict):
                return ToolResult(
                    success=result.get("success", False),
                    result=result.get("result"),
                    error=result.get("error")
                )
            elif isinstance(result, ToolResult):
                return result
            else:
                return ToolResult.ok(result)
        except Exception as e:
            return ToolResult.fail(f"工具执行异常: {str(e)}")

    @property
    def count(self) -> int:
        """工具数量"""
        return len(self._tools)


# 全局默认注册表（向后兼容旧代码）
tool_registry = ToolRegistry("default")

# 分 Agent 的注册表
chat_tool_registry = ToolRegistry("chat")
coder_tool_registry = ToolRegistry("coder")
planner_tool_registry = ToolRegistry("planner")