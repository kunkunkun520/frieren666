"""
上下文/记忆管理器
保存会话历史、决策记录、经验教训
"""

import json
import os
from datetime import datetime, timedelta
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
    design_notes: Optional[str] = None      # 新增：设计意图
    exported_api: Optional[str] = None       # 新增：对外提供的接口摘要

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
            "requires_approval": self.requires_approval,
            "design_notes": self.design_notes,
            "exported_api": self.exported_api
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
            requires_approval=data.get("requires_approval", False),
            design_notes=data.get("design_notes"),
            exported_api=data.get("exported_api")
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
    """上下文管理器 - 负责保存和加载会话，管理记忆系统"""

    def __init__(self, workspace_path: Path, llm_client=None):
        self.workspace_path = Path(workspace_path)
        self.llm_client = llm_client  # 用于让模型写摘要、检索等

        # 原有路径
        self.sessions_path = self.workspace_path / "sessions"
        self.sessions_path.mkdir(parents=True, exist_ok=True)

        # 新增：记忆系统路径
        self.memory_path = self.workspace_path / "MEMORY.md"
        self.memory_dir = self.workspace_path / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.agents_path = self.workspace_path / "AGENTS.md"

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

    # ========== 原有方法保持不变 ==========

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

    def update_step(self, step: Step):
        """更新单个步骤的完整信息（包括 design_notes）"""
        for i, s in enumerate(self.current_steps):
            if s.id == step.id:
                self.current_steps[i] = step
                break
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

    def get_completed_steps(self) -> List[Step]:
        """获取所有已完成的步骤"""
        return [s for s in self.current_steps if s.status == StepStatus.SUCCESS.value]

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
        """加载指定会话，并设置 current_steps"""
        file_path = self.sessions_path / f"{session_id}.json"
        if not file_path.exists():
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.current_session = Session.from_dict(data)
        self.current_steps = [Step.from_dict(s) for s in self.current_session.plan]

        # 同时加载索引
        self.load_index()

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

    # ========== 文件索引方法（保留，但降级为辅助） ==========

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

    # ========== 新增：AGENTS.md 管理 ==========

    def save_agents_md(self, content: str):
        """保存 AGENTS.md"""
        self.agents_path.write_text(content, encoding='utf-8')

    def read_agents_md(self) -> str:
        """读取 AGENTS.md"""
        if self.agents_path.exists():
            return self.agents_path.read_text(encoding='utf-8')
        return ""

    def append_to_agents(self, section: str, content: str):
        """向 AGENTS.md 追加新章节"""
        current = self.read_agents_md()
        new_content = f"{current}\n\n## {section}\n{content}" if current else f"# 项目约定\n\n## {section}\n{content}"
        self.save_agents_md(new_content)

    # ========== 新增：MEMORY.md 管理 ==========

    def read_memory_md(self) -> str:
        """读取长期记忆"""
        if self.memory_path.exists():
            return self.memory_path.read_text(encoding='utf-8')
        return ""

    def update_memory(self, step: Step, summary: str):
        """每完成一个 Step，更新长期记忆"""

        if self.llm_client is None:
            print("警告：LLM 客户端未设置，无法更新记忆")
            return

        current = self.read_memory_md()

        if current:
            prompt = f"""
            当前长期记忆：
            {current}
            
            新完成的任务：
            - 步骤：{step.description}
            - 文件：{step.files_modified}
            - 摘要：{summary}
            - 设计意图：{step.design_notes or '无'}
            
            请把新任务**合并**到长期记忆中，输出完整的 MEMORY.md。
            
            要求：
            - 保留「项目进展」「关键决策」「踩过的坑」「待办」四个章节（如果没有就创建）
            - 更新项目进展（标记已完成✅，添加新进展）
            - 如有新的关键决策或坑，补充到对应章节
            - 保持结构清晰，篇幅控制在 50 行以内
            """
        else:
            prompt = f"""
            项目第一个完成的任务：
            - 步骤：{step.description}
            - 文件：{step.files_modified}
            - 摘要：{summary}
            - 设计意图：{step.design_notes or '无'}
            
            请创建一个 MEMORY.md，包含：
            ## 项目进展
            ## 关键决策
            ## 踩过的坑
            ## 待办
            
            直接输出完整的 MEMORY.md 内容。
            """

        try:
            new_memory = self.llm_client.chat([
                {"role": "system", "content": "你是记忆压缩助手，将工作记录合并成长期记忆。"},
                {"role": "user", "content": prompt}
            ])
            self.memory_path.write_text(new_memory, encoding='utf-8')
        except Exception as e:
            print(f"更新记忆失败: {e}")

    # ========== 新增：近期工作（每日日志）管理 ==========

    def write_daily_log(self, step: Step, summary: str, code_snippet: str = None):
        """追加到今日日志"""

        today = datetime.now().strftime("%Y-%m-%d")
        log_path = self.memory_dir / f"{today}.md"

        timestamp = datetime.now().strftime("%H:%M")

        entry = f"""
## {timestamp} - {step.description}

**文件**：{step.files_modified}
**类型**：{step.type}
**摘要**：{summary}
"""
        if step.design_notes:
            entry += f"**设计意图**：{step.design_notes}\n"

        if code_snippet:
            ext = Path(step.files_modified[0]).suffix.lstrip('.') if step.files_modified else "python"
            entry += f"\n**代码片段**：\n```{ext}\n{code_snippet}\n```\n"

        entry += "\n---\n"

        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(entry)

    def read_recent_logs(self, days: int = 3) -> str:
        """读取最近 N 天的日志"""

        if not self.memory_dir.exists():
            return ""

        log_files = sorted(self.memory_dir.glob("*.md"), reverse=True)[:days]

        content = []
        for log in log_files:
            content.append(f"## {log.stem}\n")
            content.append(log.read_text(encoding='utf-8'))
            content.append("\n")

        return "\n".join(content) if content else "暂无近期工作记录"

    # ========== 新增：项目结构展示 ==========

    def get_project_structure(self, project_path: Path = None) -> str:
        """生成项目目录树（带模型写的摘要）"""

        if project_path is None:
            project_path = self.workspace_path

        if not project_path.exists():
            return "暂无文件"

        # 从 file_index 获取已有的摘要
        file_summaries = {}
        for file_path_str, info in self.file_index.get("files", {}).items():
            if "summary" in info:
                file_summaries[file_path_str] = info["summary"]

        lines = ["## 当前项目结构\n"]
        lines.append("```")

        def walk(path: Path, indent: str = ""):
            items = sorted(path.iterdir())
            for item in items:
                if item.name.startswith('.') or item.name == '__pycache__':
                    continue

                rel_path = str(item.relative_to(self.workspace_path))

                if item.is_dir():
                    lines.append(f"{indent}{item.name}/")
                    walk(item, indent + "  ")
                else:
                    summary = file_summaries.get(rel_path, self._get_type_hint(item))
                    lines.append(f"{indent}{item.name} {summary}")

        walk(project_path)
        lines.append("```")

        return "\n".join(lines)

    def _get_type_hint(self, file_path: Path) -> str:
        """根据扩展名返回类型提示"""
        ext = file_path.suffix.lower()
        hints = {
            '.py': '',
            '.html': '→ [模板]',
            '.css': '→ [样式]',
            '.js': '→ [脚本]',
            '.json': '→ [配置]',
            '.md': '→ [文档]',
            '.txt': '→ [文本]',
        }
        return hints.get(ext, '')

    def add_file_summary(self, file_path: str, summary: str):
        """添加或更新文件的摘要"""
        if file_path not in self.file_index.get("files", {}):
            self.file_index["files"][file_path] = {}
        self.file_index["files"][file_path]["summary"] = summary
        self._save_index()

    # ========== 新增：相关模块检索 ==========

    def get_relevant_context(self, current_step: Step) -> str:
        """让模型判断需要哪些已完成步骤的上下文"""

        if self.llm_client is None:
            return ""

        completed_steps = self.get_completed_steps()
        if not completed_steps:
            return ""

        # 构建候选列表（粗筛：最多 10 个）
        candidates = completed_steps[:10]

        completed_summary = []
        for s in candidates:
            completed_summary.append(f"""
### Step {s.id}: {s.description}
**文件**：{s.files_modified}
**提供**：{s.exported_api or s.design_notes or '无摘要'}
""")

        prompt = f"""
        当前任务：{current_step.description}
        
        已完成的所有步骤：
        {chr(10).join(completed_summary)}
        
        请判断：上述步骤中，**哪些和当前任务相关**？
        只输出相关步骤的 ID，用逗号分隔，如：1,3,5
        如果没有相关的，输出"无"。
        """

        try:
            response = self.llm_client.chat([
                {"role": "system", "content": "你是代码分析专家，判断任务相关性。"},
                {"role": "user", "content": prompt}
            ])

            if response.strip() == "无":
                return ""

            relevant_ids = [int(x.strip()) for x in response.split(',') if x.strip().isdigit()]

            relevant_context = []
            for sid in relevant_ids:
                s = self.get_step_by_id(sid)
                if s:
                    relevant_context.append(f"""
### 相关模块：{s.description}
**文件**：{s.files_modified}
**设计意图**：{s.design_notes or '无'}
**导出接口**：{s.exported_api or '无'}
""")

            if relevant_context:
                return "## 相关模块上下文\n" + "\n".join(relevant_context)

        except Exception as e:
            print(f"检索相关模块失败: {e}")

        return ""

    # ========== 新增：统一上下文入口 ==========

    def get_full_context_for_step(self, step: Step) -> str:
        """为当前步骤组装完整上下文"""

        parts = []

        # 1. 项目约定
        agents = self.read_agents_md()
        if agents:
            parts.append(f"## 项目约定\n{agents}")

        # 2. 长期记忆
        memory = self.read_memory_md()
        if memory:
            parts.append(f"## 长期记忆\n{memory}")

        # 3. 近期工作
        recent = self.read_recent_logs(days=3)
        if recent and recent != "暂无近期工作记录":
            parts.append(f"## 近期工作\n{recent}")

        # 4. 相关模块上下文
        relevant = self.get_relevant_context(step)
        if relevant:
            parts.append(relevant)

        # 5. 项目结构
        structure = self.get_project_structure(self.workspace_path)
        parts.append(structure)

        # 6. 当前任务
        parts.append(f"## 当前任务\n请生成 {step.description}")

        return "\n\n".join(parts)

    def get_context_for_modify(self, user_request: str) -> str:
        """为修改请求组装上下文（不包含当前任务）"""

        parts = []

        agents = self.read_agents_md()
        if agents:
            parts.append(f"## 项目约定\n{agents}")

        memory = self.read_memory_md()
        if memory:
            parts.append(f"## 长期记忆\n{memory}")

        recent = self.read_recent_logs(days=3)
        if recent and recent != "暂无近期工作记录":
            parts.append(f"## 近期工作\n{recent}")

        structure = self.get_project_structure(self.workspace_path)
        parts.append(structure)

        parts.append(f"## 用户请求\n{user_request}")

        return "\n\n".join(parts)

    # ========== 新增：让模型写摘要 ==========

    def generate_step_summary(self, step: Step, code: str) -> tuple:
        """让模型为完成的步骤写摘要和设计意图"""

        if self.llm_client is None:
            return code[:200] + "...", None

        # 写工作摘要
        summary_prompt = f"""
        你刚完成了任务：{step.description}
        文件：{step.files_modified}
        代码：
        ```{step.files_modified[0].split('.')[-1] if step.files_modified else 'python'}
        {code[:800]}...
        请用 2-3 句话总结这个模块：

        提供了什么

        关键字段/方法

        需要注意的点

        直接输出摘要。
        """

        try:
            summary = self.llm_client.chat([
                {"role": "system", "content": "你是代码总结专家。"},
                {"role": "user", "content": summary_prompt}
            ])
        except Exception as e:
            summary = f"完成 {step.description}"

        # 写设计意图
        design_prompt = f"""
        你刚完成了：{step.description}
        代码：{code[:800]}...

        请写一段设计意图，给后续依赖这个模块的开发者看。

        包含：

        这个模块提供了什么（核心 API）

        使用时需要注意什么（约束、陷阱）

        和其他模块的关系（如果有）

        用 3-5 行，紧凑格式。
        直接输出。
        """

        try:
            design_notes = self.llm_client.chat([
                {"role": "system", "content": "你是软件架构专家。"},
                {"role": "user", "content": design_prompt}
            ])
        except Exception as e:
            design_notes = None

        return summary, design_notes

    def generate_file_summary_for_index(self, file_path: str, code: str) -> str:
        """为文件写一行摘要，用于项目结构展示"""

        if self.llm_client is None:
            return ""

        prompt = f"""
        文件：{file_path}
        代码：{code[:500]}...

        用一行话总结这个文件提供了什么（不超过 20 个字）。
        格式：→ [摘要]

        示例：
        → User 模型 (id, username, email)
        → login(), register() 认证函数
        → 数据库连接和 Base 类
        → 首页模板

        直接输出，不要解释。
        """

        try:
            return self.llm_client.chat([
                {"role": "system", "content": "你是代码总结专家，只输出一行摘要。"},
                {"role": "user", "content": prompt}
            ])
        except Exception as e:
            return self._get_type_hint(Path(file_path))