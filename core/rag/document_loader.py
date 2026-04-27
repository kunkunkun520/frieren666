"""
文档加载器 - 精简版
只加载三个核心文件：AGENTS.md、session.json、file_index.json
"""

from pathlib import Path
from typing import List, Dict
from datetime import datetime


class DocumentLoader:
    """文档加载器 - 只加载核心文件"""

    def __init__(self, workspace_path: Path, context_manager):
        self.workspace_path = workspace_path
        self.context = context_manager

    def load_all(self) -> List[Dict]:
        """加载核心文档"""
        documents = []

        # 1. AGENTS.md - 项目约定
        documents.extend(self._load_agents_md())

        # 2. session.json - 步骤和设计意图（通过 ContextManager）
        documents.extend(self._load_session_data())

        # 3. file_index.json - 代码文件摘要
        documents.extend(self._load_file_summaries())

        print(f"文档加载完成: AGENTS.md + session + file_index, 共 {len(documents)} 条")
        return documents

    def _load_agents_md(self) -> List[Dict]:
        """加载 AGENTS.md"""
        docs = []
        agents_path = self.workspace_path / "AGENTS.md"
        if agents_path.exists():
            content = agents_path.read_text(encoding="utf-8")
            # 按 ## 章节拆分
            sections = content.split("\n## ")
            for i, section in enumerate(sections):
                if section.strip():
                    docs.append({
                        "content": f"项目约定: {section.strip()[:1000]}",
                        "source": "AGENTS.md",
                        "type": "project_convention",
                        "section_index": i,
                        "timestamp": datetime.now().isoformat()
                    })
        return docs

    def _load_session_data(self) -> List[Dict]:
        """加载 session 数据（步骤、设计意图、进展）"""
        docs = []
        session = self.context.current_session
        if not session:
            return docs

        # 用户任务
        if session.user_task:
            docs.append({
                "content": f"项目任务: {session.user_task}",
                "source": "session.json",
                "type": "task_description",
                "timestamp": session.created_at
            })

        # 每个步骤的详细信息
        for step in self.context.current_steps:
            parts = [f"Step {step.id}: {step.description}"]
            if step.design_notes:
                parts.append(f"设计意图: {step.design_notes}")
            if step.exported_api:
                parts.append(f"导出接口: {step.exported_api}")
            if step.result:
                parts.append(f"结果: {step.result}")
            if step.error:
                parts.append(f"错误: {step.error}")

            docs.append({
                "content": "\n".join(parts),
                "source": f"session.json (step_{step.id})",
                "type": "step_detail",
                "status": step.status,
                "timestamp": session.updated_at
            })

        # 完成和失败统计
        completed = [s for s in self.context.current_steps if s.status == "success"]
        failed = [s for s in self.context.current_steps if s.status == "failed"]

        if completed:
            docs.append({
                "content": f"已完成步骤: {', '.join([f'Step {s.id}: {s.description}' for s in completed])}",
                "source": "session.json",
                "type": "progress_summary",
                "timestamp": session.updated_at
            })

        if failed:
            docs.append({
                "content": f"失败步骤: {', '.join([f'Step {s.id}: {s.description} - {s.error}' for s in failed])}",
                "source": "session.json",
                "type": "progress_summary",
                "timestamp": session.updated_at
            })

        print(f"加载了 {len(docs)} 条 session 数据")
        return docs

    def _load_file_summaries(self) -> List[Dict]:
        """加载 file_index.json 中的文件摘要"""
        docs = []
        file_index = self.context.file_index

        # 遍历所有文件
        for file_path, info in file_index.get("files", {}).items():
            summary = info.get("summary", "")
            module_name = info.get("module_name", "")

            if summary:
                docs.append({
                    "content": f"文件 {file_path} ({module_name}): {summary}",
                    "source": "file_index.json",
                    "type": "code_summary",
                    "file_path": file_path,
                    "timestamp": datetime.now().isoformat()
                })

        print(f"加载了 {len(docs)} 条文件摘要")
        return docs

    def load_incremental(self) -> List[Dict]:
        """增量加载（只加载最新变更）"""
        # 重新加载 session 数据即可
        return self._load_session_data()