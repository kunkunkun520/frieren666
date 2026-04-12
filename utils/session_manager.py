"""
会话管理器 - 管理所有项目会话
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict


@dataclass
class Session:
    session_id: str
    name: str
    created_at: str
    updated_at: str
    user_task: str
    workspace_path: str
    status: str = "pending"
    steps_completed: int = 0
    total_steps: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(**data)


class SessionManager:
    def __init__(self, base_path: str = None):
        if base_path is None:
            base_path = Path.home() / "archon_workspace"
        self.base_path = Path(base_path)
        self.sessions_path = self.base_path / "sessions"
        self.sessions_path.mkdir(parents=True, exist_ok=True)

    def create_session(self, name: str, user_task: str) -> Session:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        now = datetime.now().isoformat()
        workspace_path = self.sessions_path / session_id / "project"
        workspace_path.mkdir(parents=True, exist_ok=True)
        session = Session(
            session_id=session_id,
            name=name,
            created_at=now,
            updated_at=now,
            user_task=user_task,
            workspace_path=str(workspace_path),
            status="pending"
        )
        self._save_session(session)
        return session

    def load_session(self, session_id: str) -> Optional[Session]:
        session_file = self.sessions_path / session_id / "session.json"
        if not session_file.exists():
            return None
        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return Session.from_dict(data)

    def update_session(self, session: Session):
        session.updated_at = datetime.now().isoformat()
        self._save_session(session)

    def _save_session(self, session: Session):
        session_dir = self.sessions_path / session.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / "session.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

    def list_sessions(self) -> List[Session]:
        sessions = []
        for session_dir in self.sessions_path.iterdir():
            if not session_dir.is_dir():
                continue
            session_file = session_dir / "session.json"
            if session_file.exists():
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sessions.append(Session.from_dict(data))
        sessions.sort(key=lambda x: x.created_at, reverse=True)
        return sessions

    def delete_session(self, session_id: str):
        session_dir = self.sessions_path / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)