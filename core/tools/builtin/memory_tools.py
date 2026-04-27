"""
记忆检索工具
"""

from typing import Dict, Any
from core.tools.base import BaseTool


class SearchMemoryTool(BaseTool):
    """搜索记忆 - 优先使用 RAG，降级到全文检索"""

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return "搜索项目记忆的具体内容。当用户问「第 x 步做了什么」「之前怎么实现的」「xxx 功能在哪」「回忆一下」时使用。可以搜索步骤详情、代码摘要、设计意图。"

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
                },
                "filter_type": {
                    "type": "string",
                    "description": "过滤类型: long_term_memory, daily_log, code_summary, design_note。不填则搜索全部"
                }
            },
            "required": ["query"]
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        query = params.get("query")
        days = params.get("days", 7)
        filter_type = params.get("filter_type")

        if not query:
            return {"success": False, "error": "缺少搜索内容"}

        context_manager = context.get("context_manager")
        worker = context.get("worker")

        # 优先使用 RAG 检索
        try:
            rag_result = context_manager.search_memory_rag(query, top_k=5)
            if rag_result:
                return {
                    "success": True,
                    "result": rag_result,
                    "query": query,
                    "method": "rag"
                }
        except Exception as e:
            print(f"RAG 检索失败，降级到全文检索: {e}")

        # 降级：使用原有全文检索
        memory = context_manager.read_memory_md()
        recent_logs = context_manager.read_recent_logs(days=days)

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
                "query": query,
                "method": "fulltext"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}