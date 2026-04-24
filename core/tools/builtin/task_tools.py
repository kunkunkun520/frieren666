"""
任务控制工具
"""

from typing import Dict, Any
from core.tools.base import BaseTool


class GetStatusTool(BaseTool):
    """获取项目进度"""

    @property
    def name(self) -> str:
        return "get_status"

    @property
    def description(self) -> str:
        return "获取当前任务进度。当用户问「进度怎么样」「做到哪了」「还有多少步骤」时使用。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        worker = context.get("worker")
        steps = context.get("steps", [])

        if not steps:
            return {"success": True, "result": "当前没有活动任务", "total": 0, "completed": 0, "pending": 0}

        total = len(steps)
        completed = sum(1 for s in steps if hasattr(s, 'status') and s.status == "success")
        failed = sum(1 for s in steps if hasattr(s, 'status') and s.status == "failed")
        pending = total - completed - failed

        status_text = f"总步骤: {total}, 已完成: {completed}, 失败: {failed}, 待执行: {pending}"

        # 获取当前执行的步骤
        current = None
        for s in steps:
            if hasattr(s, 'status') and s.status == "running":
                current = s.description
                break

        return {
            "success": True,
            "result": status_text,
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "current_step": current
        }


class ResumeTaskTool(BaseTool):
    """恢复执行"""

    @property
    def name(self) -> str:
        return "resume_task"

    @property
    def description(self) -> str:
        return "恢复执行未完成的任务。当用户说「继续」「接着做」「恢复」时使用。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        worker = context.get("worker")

        if worker.is_executing:
            return {"success": False, "error": "任务已在执行中"}

        if not worker.steps:
            return {"success": False, "error": "没有可恢复的任务"}

        has_pending = any(
            hasattr(s, 'status') and s.status not in ["success", "skipped"]
            for s in worker.steps
        )

        if not has_pending:
            return {"success": True, "result": "所有步骤已完成，无需恢复"}

        # 触发恢复执行
        worker.resume_execution()

        return {"success": True, "result": "任务已恢复执行"}


class PauseTaskTool(BaseTool):
    """暂停任务"""

    @property
    def name(self) -> str:
        return "pause_task"

    @property
    def description(self) -> str:
        return "暂停当前正在执行的任务。当用户说「暂停」「停一下」时使用。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        worker = context.get("worker")

        if not worker.is_executing:
            return {"success": False, "error": "当前没有正在执行的任务"}

        worker.pause()

        return {"success": True, "result": "任务已暂停"}