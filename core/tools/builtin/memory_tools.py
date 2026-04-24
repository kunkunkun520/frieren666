"""
记忆检索工具
"""

from typing import Dict, Any
from core.tools.base import BaseTool


class SearchMemoryTool(BaseTool):
    """搜索记忆"""

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return "从项目记忆中搜索信息。当用户问「之前怎么做的」「xxx 是怎么实现的」「回忆一下」时使用。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询内容"
                },
                "days": {
                    "type": "number",
                    "description": "搜索最近几天的记忆，默认 7 天"
                }
            },
            "required": ["query"]
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        query = params.get("query")
        days = params.get("days", 7)

        if not query:
            return {"success": False, "error": "缺少搜索内容"}

        context_manager = context.get("context_manager")
        worker = context.get("worker")

        # 获取记忆内容
        memory = context_manager.read_memory_md()
        recent_logs = context_manager.read_recent_logs(days=days)

        # 让 LLM 从记忆中检索相关信息
        search_prompt = f"""
## 长期记忆
{memory[:2000] if memory else "无"}

## 近期工作日志（{days}天）
{recent_logs[:2000] if recent_logs else "无"}

## 用户查询
{query}

请从上述记忆中找出与查询相关的信息，并简洁回答。如果找不到相关信息，诚实说明。
"""

        try:
            response = worker._call_llm_with_retry([
                {"role": "system", "content": "你是记忆检索助手，根据记忆内容回答问题。"},
                {"role": "user", "content": search_prompt}
            ])

            return {
                "success": True,
                "result": response,
                "query": query
            }
        except Exception as e:
            return {"success": False, "error": str(e)}