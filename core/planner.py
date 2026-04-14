"""
Planner 模块 - 任务规划
"""

import json
import re
from typing import List, Dict, Any, Optional
from utils.llm_client import LLMClient
from core.context_manager import Step, StepStatus, ContextManager


def infer_step_type(path: str) -> str:
    if 'test' in path:
        return 'test'
    if 'requirements' in path or 'package' in path:
        return 'setup'
    return 'code'


def parse_plan_to_steps(plan_text: str) -> List[Dict[str, Any]]:
    steps = []
    step_id = 1
    for line in plan_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('-') or line.startswith('*') or re.match(r'^\d+\.', line):
            if line.startswith('-') or line.startswith('*'):
                content = line.lstrip('-*').strip()
            else:
                content = re.sub(r'^\d+\.', '', line).strip()

            has_path = False
            path = ""
            desc = content

            path_match = re.search(r'([\w/]+\.(py|html|css|js|json|md|txt|yml|yaml))', content)
            if path_match:
                path = path_match.group(1)
                has_path = True
                if ':' in content:
                    parts = content.split(':', 1)
                    desc = parts[1].strip() if len(parts) > 1 else content
                else:
                    desc = content.replace(path, '').strip()

            steps.append({
                "id": step_id,
                "path": path,
                "description": desc,
                "type": infer_step_type(path) if has_path else "code",
                "depends_on": [step_id - 1] if step_id > 1 else []
            })
            step_id += 1

    return steps


class Planner:
    def __init__(self, config: dict, context_manager: ContextManager):
        self.client = LLMClient(config)
        self.config = config
        self.context = context_manager

    def generate_agents_md(self, user_task: str) -> str:
        prompt = f"""用户任务：{user_task}

请推断这个项目需要的技术栈和目录结构，生成 AGENTS.md。

要求：
1. 技术栈选主流、稳定的
2. 目录结构清晰、分层合理
3. 包含编码规范（命名、导入方式等）
4. 留出扩展空间

格式：
# 项目约定

## 技术栈
- 后端：xxx
- 数据库：xxx
- 其他：xxx

## 目录结构
src/
├── models/
├── services/
├── api/
└── utils

## 编码规范
- 导入方式：xxx
- 命名规则：xxx
- 错误处理：xxx

## 特殊约束
- 如有特殊要求在此说明

直接输出 Markdown，不要解释。"""
        response = self.client.chat([
            {"role": "system", "content": "你是项目架构专家，为项目生成约定文档。"},
            {"role": "user", "content": prompt}
        ])
        return response

    def update_agents_md(self, user_feedback: str) -> str:
        current = self.context.read_agents_md()
        prompt = f"""当前项目约定：
{current}

用户反馈：{user_feedback}

请根据反馈更新项目约定，输出完整的 AGENTS.md。

直接输出 Markdown，不要解释。"""
        response = self.client.chat([
            {"role": "system", "content": "你是项目架构专家，更新项目约定文档。"},
            {"role": "user", "content": prompt}
        ])
        return response

    def plan(self, user_task: str) -> List[Step]:
        """生成任务计划（AGENTS.md 已经存在）"""
        plan_text = self._generate_plan(user_task)
        steps_data = parse_plan_to_steps(plan_text)
        steps = []
        for step_data in steps_data:
            step = Step(
                id=step_data["id"],
                description=f"{step_data['path']}: {step_data['description']}" if step_data['path'] else step_data[
                    'description'],
                type=step_data["type"],
                status=StepStatus.PENDING.value,
                depends_on=step_data.get("depends_on", []),
                requires_approval=False
            )
            steps.append(step)
        return steps

    def _generate_plan(self, user_task: str) -> str:
        agents_md = self.context.read_agents_md()
        system_prompt = """你是一个项目规划专家，将用户需求拆分成详细的任务清单。
输出格式：每个任务一行，以 - 开头，包含文件路径和描述。
示例：
- src/database.py: 数据库连接配置
- src/models/user.py: 用户数据模型
- src/services/auth.py: 认证服务
- src/api/user.py: 用户API路由
- templates/index.html: 首页模板
只输出规划，不要解释。"""
        if agents_md:
            prompt = f"""项目约定：
{agents_md}

用户需求: {user_task}

请根据项目约定生成任务清单："""
        else:
            prompt = f"用户需求: {user_task}\n\n请生成任务清单："
        response = self.client.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        return response

    def replan(self, user_task: str, failed_step: Step, error_msg: str) -> List[Step]:
        agents_md = self.context.read_agents_md()
        system_prompt = "你是一个项目规划专家，根据失败信息重新规划剩余步骤。只输出剩余步骤，每行以 - 开头。"
        prompt = f"""项目约定：
{agents_md if agents_md else '无'}

原始任务: {user_task}
失败的步骤: {failed_step.description}
错误信息: {error_msg}

请重新规划剩余未完成的步骤："""
        response = self.client.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        steps_data = parse_plan_to_steps(response)
        existing_ids = [s.id for s in self.context.current_steps] if self.context.current_steps else [0]
        next_id = max(existing_ids) + 1
        steps = []
        for step_data in steps_data:
            step = Step(
                id=next_id,
                description=f"{step_data['path']}: {step_data['description']}" if step_data['path'] else step_data['description'],
                type=step_data["type"],
                status=StepStatus.PENDING.value,
                depends_on=step_data.get("depends_on", []),
                requires_approval=False
            )
            steps.append(step)
            next_id += 1
        return steps

    def modify_plan(self, user_task: str, current_steps: List[Step], feedback: str) -> List[Step]:
        agents_md = self.context.read_agents_md()
        steps_text = "\n".join([f"{s.id}. {s.description} ({s.type})" for s in current_steps])
        system_prompt = """你是一个项目规划专家，根据用户反馈修改任务计划。
输出格式为纯文本，每行以 - 开头，不要输出JSON。
示例：
- src/database.py: 数据库连接配置
- src/models.py: 用户数据模型
- src/vip_service.py: VIP用户专属价格逻辑
- src/api.py: API路由
只输出修改后的完整计划，不要解释。"""
        prompt = f"""项目约定：
{agents_md if agents_md else '无'}

原始任务: {user_task}
当前计划:
{steps_text}
用户反馈: {feedback}

请根据反馈修改计划，输出修改后的完整任务清单。"""
        response = self.client.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        steps_data = parse_plan_to_steps(response)
        new_steps = []
        for i, step_data in enumerate(steps_data):
            step = Step(
                id=i + 1,
                description=f"{step_data['path']}: {step_data['description']}" if step_data['path'] else step_data['description'],
                type=step_data["type"],
                status=StepStatus.PENDING.value,
                depends_on=[i] if i > 0 else [],
                requires_approval=False
            )
            new_steps.append(step)
        return new_steps

    def modify_plan_with_agents_update(self, user_task: str, current_steps: List[Step], feedback: str) -> tuple:
        if self._should_update_agents(feedback):
            new_agents = self.update_agents_md(feedback)
            self.context.save_agents_md(new_agents)
        new_steps = self.modify_plan(user_task, current_steps, feedback)
        return new_steps

    def _should_update_agents(self, feedback: str) -> bool:
        agents_keywords = ["技术栈", "框架", "数据库", "目录", "结构", "规范", "约定", "改成", "换成", "不用", "用"]
        feedback_lower = feedback.lower()
        return any(kw in feedback_lower for kw in agents_keywords)