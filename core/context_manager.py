"""
上下文/记忆管理器
保存会话历史、决策记录、经验教训
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_CONFIRM = "waiting_confirm"


class SessionType(Enum):
    CODE_GEN = "code_generation"
    MODIFY = "modify"
    DEBUG = "debug"
    REFACTOR = "refactor"


@dataclass
class Step:
    """单个步骤"""
    id: int
    description: str
    type: str
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None
    files_modified: List[str] = None
    depends_on: List[int] = None
    requires_approval: bool = False

    def __post_init__(self):
        if self.files_modified is None:
            self.files_modified = []
        if self.depends_on is None:
            self.depends_on = []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "type": self.type,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "files_modified": self.files_modified,
            "depends_on": self.depends_on,
            "requires_approval": self.requires_approval
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Step":
        return cls(
            id=data["id"],
            description=data["description"],
            type=data["type"],
            status=data.get("status", "pending"),
            result=data.get("result"),
            error=data.get("error"),
            files_modified=data.get("files_modified", []),
            depends_on=data.get("depends_on", []),
            requires_approval=data.get("requires_approval", False)
        )


@dataclass
class Session:
    """完整会话"""
    session_id: str
    created_at: str
    updated_at: str
    user_task: str
    session_type: str
    plan: List[dict]
    completed_steps: List[int]
    failed_steps: List[dict]
    git_commits: List[str]
    final_score: Optional[int] = None
    final_status: str = "pending"

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "user_task": self.user_task,
            "session_type": self.session_type,
            "plan": self.plan,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "git_commits": self.git_commits,
            "final_score": self.final_score,
            "final_status": self.final_status
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(
            session_id=data["session_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            user_task=data["user_task"],
            session_type=data["session_type"],
            plan=data["plan"],
            completed_steps=data.get("completed_steps", []),
            failed_steps=data.get("failed_steps", []),
            git_commits=data.get("git_commits", []),
            final_score=data.get("final_score"),
            final_status=data.get("final_status", "pending")
        )


class ContextManager:
    """上下文管理器 - 负责保存和加载会话"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path)
        self.sessions_path = self.workspace_path / "sessions"
        self.sessions_path.mkdir(parents=True, exist_ok=True)

        self.current_session: Optional[Session] = None
        self.current_steps: List[Step] = []
        self.file_index = {"files": {}, "exports": {}}

        # 延迟导入 CodeParser，避免循环依赖
        self._code_parser = None

    @property
    def code_parser(self):
        """延迟加载 CodeParser"""
        if self._code_parser is None:
            from core.code_parser import CodeParser
            self._code_parser = CodeParser
        return self._code_parser

    def create_session(self, user_task: str, session_type: str = "code_generation") -> str:
        """创建新会话"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        now = datetime.now().isoformat()

        self.current_session = Session(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            user_task=user_task,
            session_type=session_type,
            plan=[],
            completed_steps=[],
            failed_steps=[],
            git_commits=[]
        )

        self.current_steps = []
        self._save_session()
        return session_id

    def set_plan(self, steps: List[Step]):
        """设置计划步骤"""
        self.current_steps = steps
        self.current_session.plan = [s.to_dict() for s in steps]
        self.current_session.updated_at = datetime.now().isoformat()
        self._save_session()

    def update_step_status(self, step_id: int, status: str, result: str = None, error: str = None):
        """更新步骤状态"""
        for step in self.current_steps:
            if step.id == step_id:
                step.status = status
                if result:
                    step.result = result
                if error:
                    step.error = error
                break

        if status == StepStatus.SUCCESS.value:
            if step_id not in self.current_session.completed_steps:
                self.current_session.completed_steps.append(step_id)
        elif status == StepStatus.FAILED.value:
            self.current_session.failed_steps.append({
                "step_id": step_id,
                "error": error,
                "timestamp": datetime.now().isoformat()
            })

        self.current_session.plan = [s.to_dict() for s in self.current_steps]
        self.current_session.updated_at = datetime.now().isoformat()
        self._save_session()

    def add_git_commit(self, commit_msg: str):
        """添加 Git 提交记录"""
        self.current_session.git_commits.append(commit_msg)
        self.current_session.updated_at = datetime.now().isoformat()
        self._save_session()

    def set_final_result(self, score: int, status: str):
        """设置最终结果"""
        self.current_session.final_score = score
        self.current_session.final_status = status
        self.current_session.updated_at = datetime.now().isoformat()
        self._save_session()

    def get_current_step(self) -> Optional[Step]:
        """获取当前待执行的步骤"""
        for step in self.current_steps:
            if step.status == StepStatus.PENDING.value:
                return step
        return None

    def get_step_by_id(self, step_id: int) -> Optional[Step]:
        """根据ID获取步骤"""
        for step in self.current_steps:
            if step.id == step_id:
                return step
        return None

    def get_session_summary(self) -> str:
        """获取会话摘要"""
        if not self.current_session:
            return "无活动会话"

        summary = f"""# 会话摘要

## 基本信息
- 会话ID: {self.current_session.session_id}
- 用户任务: {self.current_session.user_task}
- 创建时间: {self.current_session.created_at}
- 最后更新: {self.current_session.updated_at}
- 状态: {self.current_session.final_status}

## 已完成步骤 ({len(self.current_session.completed_steps)}/{len(self.current_steps)})
"""
        for step in self.current_steps:
            if step.id in self.current_session.completed_steps:
                summary += f"- ✅ 步骤{step.id}: {step.description}\n"

        summary += "\n## 失败记录\n"
        for fail in self.current_session.failed_steps:
            summary += f"- ❌ 步骤{fail['step_id']}: {fail['error']}\n"

        return summary

    def list_sessions(self) -> List[dict]:
        """列出所有会话"""
        sessions = []
        for file in self.sessions_path.glob("*.json"):
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sessions.append({
                    "session_id": data["session_id"],
                    "created_at": data["created_at"],
                    "user_task": data["user_task"][:50] + "..." if len(data["user_task"]) > 50 else data["user_task"],
                    "status": data["final_status"],
                    "file_path": str(file)
                })
        return sorted(sessions, key=lambda x: x["created_at"], reverse=True)

    def load_session(self, session_id: str) -> Optional[Session]:
        """加载指定会话"""
        file_path = self.sessions_path / f"{session_id}.json"
        if not file_path.exists():
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.current_session = Session.from_dict(data)
        self.current_steps = [Step.from_dict(s) for s in self.current_session.plan]
        return self.current_session

    def _save_session(self):
        """保存当前会话"""
        if not self.current_session:
            return

        file_path = self.sessions_path / f"{self.current_session.session_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.current_session.to_dict(), f, ensure_ascii=False, indent=2)

    def delete_session(self, session_id: str):
        """删除会话"""
        file_path = self.sessions_path / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()

    # ========== 文件索引方法 ==========

    def update_file_index(self, project_path: Path):
        """更新文件索引"""
        if not project_path or not project_path.exists():
            return

        try:
            index = self.code_parser.generate_index(project_path)
            self.file_index = index
            self._save_index()
        except Exception as e:
            print(f"更新索引失败: {e}")

    def get_file_index_summary(self) -> str:
        """获取文件索引的轻量摘要"""
        if not self.file_index or not self.file_index.get("exports"):
            return "暂无已有代码文件。"

        try:
            return self.code_parser.format_index_for_prompt(self.file_index)
        except Exception as e:
            print(f"格式化索引失败: {e}")
            return "暂无已有代码文件。"

    def _save_index(self):
        """保存索引到 JSON 文件"""
        index_path = self.workspace_path / "file_index.json"
        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(self.file_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存索引失败: {e}")

    def load_index(self):
        """加载索引"""
        index_path = self.workspace_path / "file_index.json"
        if index_path.exists():
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    self.file_index = json.load(f)
            except Exception as e:
                print(f"加载索引失败: {e}")
                self.file_index = {"files": {}, "exports": {}}
        else:
            self.file_index = {"files": {}, "exports": {}}