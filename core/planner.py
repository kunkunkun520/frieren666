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
            if '.py' in content:
                parts = content.split(':', 1)
                path_part = parts[0].strip()
                path_match = re.search(r'([\w/]+\.py)', path_part)
                if path_match:
                    path = path_match.group(1)
                    desc = parts[1].strip() if len(parts) > 1 else path_part
                    steps.append({
                        "id": step_id,
                        "path": path,
                        "description": desc,
                        "type": infer_step_type(path),
                        "depends_on": [step_id - 1] if step_id > 1 else []
                    })
                    step_id += 1
            else:
                steps.append({
                    "id": step_id,
                    "path": "",
                    "description": content,
                    "type": "code",
                    "depends_on": [step_id - 1] if step_id > 1 else []
                })
                step_id += 1
    return steps


class Planner:
    def __init__(self, config: dict, context_manager: ContextManager):
        self.client = LLMClient(config)
        self.config = config
        self.context = context_manager

    def plan(self, user_task: str) -> List[Step]:
        plan_text = self._generate_plan(user_task)
        steps_data = parse_plan_to_steps(plan_text)
        steps = []
        for step_data in steps_data:
            step = Step(
                id=step_data["id"],
                description=f"{step_data['path']}: {step_data['description']}" if step_data['path'] else step_data['description'],
                type=step_data["type"],
                status=StepStatus.PENDING.value,
                depends_on=step_data.get("depends_on", []),
                requires_approval=False
            )
            steps.append(step)
        return steps

    def _generate_plan(self, user_task: str) -> str:
        system_prompt = """你是一个项目规划专家，将用户需求拆分成详细的任务清单。
输出格式：每个任务一行，以 - 开头，包含文件路径和描述。
示例：
- src/database.py: 数据库连接配置
- src/models.py: 用户数据模型
- src/crud.py: CRUD操作
- src/api.py: API路由
只输出规划，不要解释。"""
        prompt = f"用户需求: {user_task}\n\n请生成任务清单："
        response = self.client.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        return response

    def replan(self, user_task: str, failed_step: Step, error_msg: str) -> List[Step]:
        system_prompt = "你是一个项目规划专家，根据失败信息重新规划剩余步骤。只输出剩余步骤，每行以 - 开头。"
        prompt = f"""原始任务: {user_task}
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
        """根据用户反馈修改计划"""
        steps_text = "\n".join([f"{s.id}. {s.description} ({s.type})" for s in current_steps])
        system_prompt = """你是一个项目规划专家，根据用户反馈修改任务计划。
输出格式为纯文本，每行以 - 开头，不要输出JSON。
示例：
- src/database.py: 数据库连接配置
- src/models.py: 用户数据模型
- src/vip_service.py: VIP用户专属价格逻辑
- src/api.py: API路由
只输出修改后的完整计划，不要解释。"""
        prompt = f"""原始任务: {user_task}
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

