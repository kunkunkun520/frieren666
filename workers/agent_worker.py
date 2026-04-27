"""
Agent 后台工作线程 - 状态机版本 (完整版)
"""

import time
import re
import json
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import QApplication

from core.planner import Planner
from core.coder import Coder
from core.judge import Judge
from core.context_manager import ContextManager, Step, StepStatus
from core.agent_state import AgentState, AgentContext, StateMachine
from core.tools import tool_registry, ToolResult
from core.tools.builtin import (
    CreateFileTool, ModifyFileTool, ReadFileTool, ListFilesTool,
    GetStatusTool, ResumeTaskTool, PauseTaskTool,
    UpdateAgentsTool, AddDependencyTool, SearchMemoryTool
)
from utils.config import Config


class AgentWorker(QThread):
    log_signal = Signal(str, str)
    status_signal = Signal(str)
    plan_signal = Signal(list)
    step_signal = Signal(int, str, str)
    ask_signal = Signal(str, list, dict)
    finished_signal = Signal(dict)
    error_signal = Signal(str)
    diff_signal = Signal(str, str, str)
    state_signal = Signal(str)

    def __init__(self, user_task: str, workspace_path: Path, is_load_mode: bool = False, session_id: str = None):
        super().__init__()
        self.user_task = user_task
        self.workspace_path = workspace_path
        self.is_load_mode = is_load_mode
        self.session_id = session_id

        self.sm = StateMachine()
        self.sm.on_transition(self._on_state_changed)
        self.ctx = AgentContext(user_task=user_task)

        self.steps: List[Step] = []
        self.step_status_map = {}
        self.pending_modify_file_path = None
        self.pending_modify_content = None
        self.pending_impact_update = None

        self._pending_logs = []
        self._log_timer = None
        self._log_level = "info"
        self._response_timeout_timer = None

        self.workspace_path.mkdir(parents=True, exist_ok=True)

        self.config = Config()
        planner_config = self.config.get_planner_config()
        coder_config = self.config.get_coder_config()
        judge_config = self.config.get_judge_config()

        from utils.llm_client import LLMClient
        self.llm_client = LLMClient(planner_config)

        self.context = ContextManager(self.workspace_path, llm_client=self.llm_client)

        if is_load_mode and session_id:
            session = self.context.load_session(session_id)
            if session:
                self.steps = self.context.current_steps
                for step in self.steps:
                    self.step_status_map[step.id] = (step.status == StepStatus.SUCCESS.value)
                self.ctx.steps = self.steps
                self.ctx.step_status_map = self.step_status_map
                self.ctx.user_task = session.user_task
        elif not is_load_mode:
            self.context.create_session(user_task)

        self.planner = Planner(planner_config, self.context)
        self.coder = Coder(coder_config, self.workspace_path)
        self.judge = Judge(judge_config)
        self._register_builtin_tools()

    def _on_state_changed(self, old_state: AgentState, new_state: AgentState, reason: str):
        self.state_signal.emit(new_state.value)
        self.add_log(f"📌 {reason or f'状态: {new_state.value}'}", "info")
        self._flush_logs()

    def run(self):
        QApplication.processEvents()
        try:
            if self.is_load_mode:
                self.sm.force_transition(AgentState.IDLE)
                if self.steps:
                    step_descriptions = [f"{s.id}. {s.description}" for s in self.steps]
                    self.plan_signal.emit(step_descriptions)
                    for step in self.steps:
                        if step.status == StepStatus.SUCCESS.value:
                            self.step_signal.emit(step.id, "success", step.description)
                        elif step.status == StepStatus.FAILED.value:
                            self.step_signal.emit(step.id, "failed", step.description)
                        elif step.status == StepStatus.RUNNING.value:
                            self.step_signal.emit(step.id, "running", step.description)
                self.add_log("📁 已加载会话", "success")
                self.add_log("输入「恢复执行」继续未完成的任务", "info")
                self._flush_logs()
            else:
                self.sm.transition_to(AgentState.PLANNING, "开始规划")
                self._generate_initial_plan()
        except Exception as e:
            self.error_signal.emit(str(e))
            self.sm.force_transition(AgentState.IDLE)

    def handle_user_input(self, message: str):
        self.add_log(f"👤 用户: {message}", "user")
        self._flush_logs()

        if message == "结束":
            self._save_current_state()
            self.finished_signal.emit({"success": True, "completed": True})
            return

        if message == "恢复执行":
            if self.sm.state == AgentState.IDLE and self.steps:
                has_pending = any(s.status not in [StepStatus.SUCCESS.value] for s in self.steps)
                if has_pending:
                    self.sm.transition_to(AgentState.EXECUTING, "恢复执行")
                    self._continue_from_step(self._get_pending_step())
                else:
                    self.add_log("所有步骤已完成", "info")
            else:
                self.add_log("当前无法恢复执行", "warning")
            return

        if self.sm.state == AgentState.WAITING_CONFIRM:
            self._handle_confirmation(message)
            return

        if self.sm.state == AgentState.EXECUTING:
            self._handle_during_execution(message)
            return

        if self.sm.state == AgentState.IDLE:
            self._handle_idle(message)
            return

        self._handle_chat(message)

    def _handle_confirmation(self, message: str):
        self.on_user_response(message, {"action": self.ctx.pending_action})

    def _handle_during_execution(self, message: str):
        intent = self._quick_classify(message)
        if intent == "modify":
            self.sm.transition_to(AgentState.MODIFYING, "执行中穿插修改")
            self._execute_modify_from_message(message)
            self.sm.transition_to(AgentState.EXECUTING, "修改完成，继续执行")
        elif intent == "pause":
            self.sm.transition_to(AgentState.PAUSED, "用户暂停")
            self.pause()
        else:
            self._handle_chat(message)

    def _handle_idle(self, message: str):
        intent = self._quick_classify(message)
        if intent == "new_task":
            self.sm.transition_to(AgentState.PLANNING, "新任务")
            self.user_task = message
            self._generate_initial_plan()
        elif intent == "modify":
            self.sm.transition_to(AgentState.TOOL_EXECUTING, "执行工具")
            self._execute_modify_from_message(message)
            self.sm.transition_to(AgentState.IDLE, "工具执行完成")
        elif intent == "resume":
            self.sm.transition_to(AgentState.EXECUTING, "恢复执行")
            self._continue_from_step(self._get_pending_step())
        else:
            self._handle_chat(message)

    def _quick_classify(self, message: str) -> str:
        modify_keywords = ["修改", "改", "添加", "删除", "更新", "创建", "新建", "生成", "写"]
        task_keywords = ["做一个", "创建一个", "搭建", "开发", "写一个项目"]
        pause_keywords = ["暂停", "停一下", "休息"]
        resume_keywords = ["继续", "接着", "恢复"]

        if any(kw in message for kw in pause_keywords):
            return "pause"
        if any(kw in message for kw in resume_keywords):
            return "resume"
        if any(kw in message for kw in task_keywords):
            return "new_task"
        if any(kw in message for kw in modify_keywords):
            return "modify"
        return "chat"

    def _handle_chat(self, message: str):
        intent = self._classify_intent_with_llm(message)

        if intent.get("tool") == "chat":
            response = intent.get("params", {}).get("response", "好的")
            self.add_log(f"🤖 Agent: {response}", "ai")
            self._flush_logs()
            return

        tool_name = intent.get("tool")
        tool_params = intent.get("params", {})

        if not tool_name:
            self.add_log("🤖 抱歉，我不太明白。", "ai")
            return

        self.sm.transition_to(AgentState.TOOL_EXECUTING, f"调用工具: {tool_name}")
        self.add_log(f"🔧 调用工具: {tool_name}", "info")
        result = self._execute_tool(tool_name, tool_params)

        if result.success:
            response = self._generate_response_after_tool(message, tool_name, result)
        else:
            response = f"执行 {tool_name} 失败: {result.error}"

        self.add_log(f"🤖 Agent: {response}", "ai")
        self._flush_logs()
        self.sm.transition_to(AgentState.IDLE, "工具执行完成")

    def _register_builtin_tools(self):
        tool_registry.clear()
        tool_registry.register_many([
            CreateFileTool(), ModifyFileTool(), ReadFileTool(), ListFilesTool(),
            GetStatusTool(), ResumeTaskTool(), PauseTaskTool(),
            UpdateAgentsTool(), AddDependencyTool(), SearchMemoryTool(),
        ])

    def _call_llm_with_retry(self, messages: list, max_retries: int = 3, timeout: int = 120) -> str:
        last_error = None
        for attempt in range(max_retries):
            try:
                self.add_log(f"⏳ LLM 调用中... ({attempt+1}/{max_retries})", "info")
                self._flush_logs()
                QApplication.processEvents()
                result = self.llm_client.chat(messages, timeout=timeout)
                return result
            except Exception as e:
                last_error = str(e)
                self.add_log(f"⚠️ 调用失败: {e}", "warning")
                self._flush_logs()
                if attempt < max_retries - 1:
                    time.sleep(3)
        raise Exception(f"LLM 调用失败: {last_error}")

    def _clean_code(self, response: str) -> str:
        code = response.strip()
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            parts = code.split("```")
            if len(parts) >= 3:
                code = parts[1]
        return code.strip()

    def _extract_key_constraints(self, agents_md: str) -> str:
        if not agents_md:
            return "暂无项目约定"
        lines = []
        if "## 技术栈" in agents_md:
            tech_section = agents_md.split("## 技术栈")[1].split("##")[0]
            lines.append("**技术栈**:")
            for line in tech_section.strip().split('\n'):
                if line.strip() and not line.strip().startswith('#'):
                    lines.append(line.strip())
        if "## 可用依赖" in agents_md:
            dep_section = agents_md.split("## 可用依赖")[1].split("##")[0]
            lines.append("\n**可用依赖（只能使用这些）**:")
            for line in dep_section.strip().split('\n'):
                if line.strip() and not line.strip().startswith('#'):
                    lines.append(line.strip())
        if "## 禁止事项" in agents_md:
            ban_section = agents_md.split("## 禁止事项")[1].split("##")[0]
            lines.append("\n**禁止事项**:")
            for line in ban_section.strip().split('\n'):
                if line.strip() and not line.strip().startswith('#'):
                    lines.append(line.strip())
        return '\n'.join(lines) if lines else "暂无项目约定"

    def _classify_intent_with_llm(self, message: str) -> dict:
        tools_prompt = tool_registry.get_tools_prompt()
        project_structure = self.context.get_project_structure(self.workspace_path)
        agents_md = self.context.read_agents_md()
        constraints = self._extract_key_constraints(agents_md)
        total = len(self.steps) if self.steps else 0
        completed = sum(1 for s in self.steps if s.status == StepStatus.SUCCESS.value) if self.steps else 0

        prompt = f"""## ⚠️ 必须输出 JSON，禁止直接输出代码

## 项目约定（必须遵守）
{constraints}

## 可用工具
{tools_prompt}

## 项目状态: 总{total}步, 已完成{completed}步

## 项目结构
{project_structure}

## 用户消息
{message}

## 重要提醒
- 严格遵守项目约定中的技术栈和依赖清单
- 如果约定要求 FastAPI，不要生成 Flask 代码
- 调用工具时使用项目结构中存在的精确路径

输出 JSON：{{"tool": "工具名", "params": {{...}}}} 或 {{"tool": "chat", "params": {{"response": "回复"}}}}"""
        try:
            response = self._call_llm_with_retry([
                {"role": "system", "content": "只输出 JSON。"},
                {"role": "user", "content": prompt}
            ])
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        return {"tool": "chat", "params": {"response": "抱歉，我不太明白。"}}

    def _execute_tool(self, tool_name: str, params: dict) -> ToolResult:
        context = {
            "worker": self, "coder": self.coder,
            "context_manager": self.context, "workspace_path": self.workspace_path,
            "steps": self.steps,
        }
        try:
            return tool_registry.execute(tool_name, params, context)
        except Exception as e:
            return ToolResult.fail(f"工具执行异常: {e}")

    def _generate_response_after_tool(self, user_message: str, tool_name: str, result: ToolResult) -> str:
        prompt = f"""用户: {user_message}
工具: {tool_name}
结果: {result.to_dict()}
请友好回复。"""
        try:
            return self._call_llm_with_retry([
                {"role": "system", "content": "友好回复。"},
                {"role": "user", "content": prompt}
            ])
        except:
            return f"✅ 已完成 {tool_name}" if result.success else f"❌ {result.error}"

    def _emit_log_batch(self):
        if self._pending_logs:
            self.log_signal.emit("\n".join(self._pending_logs), self._log_level)
            self._pending_logs.clear()
            self._log_level = "info"

    def add_log(self, message: str, level: str = "info"):
        self._pending_logs.append(message)
        self._log_level = level if level != "info" else self._log_level
        if len(self._pending_logs) >= 3:
            self._emit_log_batch()
        elif self._log_timer is None:
            self._log_timer = QTimer()
            self._log_timer.setSingleShot(True)
            self._log_timer.timeout.connect(self._emit_log_batch)
            self._log_timer.start(80)

    def _flush_logs(self):
        if self._pending_logs:
            self._emit_log_batch()

    def _generate_initial_plan(self):
        self.add_log("正在生成计划...", "info")
        try:
            existing_agents = self.context.read_agents_md()
            if not existing_agents:
                self.add_log("正在推断项目约定...", "info")
                agents_md = self.planner.generate_agents_md(self.user_task)
                self.context.save_agents_md(agents_md)
                self.add_log("项目约定已生成", "success")
            else:
                self.add_log("使用已有项目约定", "success")
            self.steps = self.planner.plan(self.user_task)
            self.context.set_plan(self.steps)
            for step in self.steps:
                self.step_status_map[step.id] = False
        except Exception as e:
            self.error_signal.emit(f"规划失败: {e}")
            self.sm.transition_to(AgentState.IDLE, "规划失败")
            return

        step_descriptions = [f"{s.id}. {s.description}" for s in self.steps]
        self.plan_signal.emit(step_descriptions)
        self.add_log(f"计划已生成，共 {len(self.steps)} 个步骤", "success")
        self.sm.transition_to(AgentState.WAITING_CONFIRM, "等待确认计划")
        self.ctx.pending_action = "confirm_plan"
        self.ask_signal.emit("请确认计划", ["确认执行", "修改计划", "取消"], {"action": "confirm_plan"})

    def _get_pending_step(self) -> Optional[Step]:
        for step in self.steps:
            if step.status not in [StepStatus.SUCCESS.value, StepStatus.SKIPPED.value]:
                return step
        return None

    def _continue_from_step(self, start_step: Step):
        if not start_step:
            self._finish_execution()
            return
        self._finish_execution()

    def _finish_execution(self):
        self.add_log("✅ 任务完成！", "success")
        self.sm.transition_to(AgentState.IDLE, "任务完成")
        self._flush_logs()

    def _save_current_state(self):
        try:
            self.context._save_session()
            self.context._save_index()
        except:
            pass

    def _execute_modify_from_message(self, message: str):
        self._handle_chat(message)

    def on_user_response(self, response: str, data: dict = None):
        self.add_log(f"用户响应: {response}", "user")
        self._flush_logs()

        if data and data.get("action") == "confirm_impact_update":
            if response == "确认修改":
                self._execute_impact_update(self.pending_impact_update)
            self.sm.transition_to(AgentState.IDLE, "影响更新完成")
            return

        if data and data.get("action") == "confirm_plan":
            if response == "确认执行":
                self.sm.transition_to(AgentState.EXECUTING, "开始执行")
                self._continue_from_step(self._get_pending_step())
            elif response == "修改计划":
                self.sm.transition_to(AgentState.PLANNING, "修改计划")
                self.modify_plan("用户要求修改计划")
            else:
                self.sm.transition_to(AgentState.IDLE, "用户取消")
            return

        if response == "确认修改":
            if self.pending_modify_file_path and self.pending_modify_content:
                try:
                    Path(self.pending_modify_file_path).write_text(self.pending_modify_content, encoding="utf-8")
                    self.add_log("✅ 文件已覆盖", "success")
                    self.finished_signal.emit({"success": True, "refresh": True})
                except Exception as e:
                    self.add_log(f"❌ 保存失败: {e}", "error")
            self.sm.transition_to(AgentState.IDLE, "修改确认完成")
            return

        if response == "结束":
            self.finished_signal.emit({"success": True, "completed": True})
            return

        if response == "确认执行":
            self.sm.transition_to(AgentState.EXECUTING, "开始执行")
            self._continue_from_step(self._get_pending_step())
        else:
            self.handle_user_input(response)

    def start_execution(self):
        self.sm.transition_to(AgentState.EXECUTING, "开始执行")
        pending = self._get_pending_step()
        if pending:
            self._continue_from_step(pending)
        else:
            self._finish_execution()

    def pause(self):
        self.sm.transition_to(AgentState.PAUSED, "暂停")

    def resume(self):
        self.sm.transition_to(AgentState.EXECUTING, "恢复执行")

    def cancel(self):
        self.sm.transition_to(AgentState.CANCELLED, "取消")

    def modify_plan(self, feedback: str):
        self.add_log(f"修改计划: {feedback}", "info")
        self.ask_signal.emit("请确认计划", ["确认执行", "修改计划", "取消"], {"action": "confirm_plan"})

    def resume_execution(self):
        self.sm.transition_to(AgentState.EXECUTING, "恢复执行")
        pending = self._get_pending_step()
        if pending:
            self._continue_from_step(pending)

    def on_modify_feedback(self, feedback: str):
        self.modify_plan(feedback)

    def analyze_impact_and_update(self, file_path: str, old_content: str, new_content: str):
        self.add_log(f"🔍 分析 {file_path} 的影响范围...", "info")
        self._flush_logs()
        QApplication.processEvents()

        module_name = Path(file_path).stem
        related_files = self._find_files_importing_module(module_name)
        related_contents = []
        for rel_path in related_files[:10]:
            full_path = self.workspace_path / rel_path
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding="utf-8")
                    related_contents.append(f"\n### {rel_path}\n```\n{content[:1500]}\n```")
                except:
                    pass

        structure = self.context.get_project_structure(self.workspace_path)

        impact_prompt = f"""## 用户修改的文件: {file_path}
### 修改前
{old_content[:2000]}{"..." if len(old_content) > 2000 else ""}
### 修改后
{new_content[:2000]}{"..." if len(new_content) > 2000 else ""}
## 项目结构
{structure}
## 导入了该模块的文件
{chr(10).join([f"- {f}" for f in related_files]) if related_files else "无"}
## 相关文件内容
{chr(10).join(related_contents) if related_contents else "无"}
## 任务
分析修改影响。输出 JSON: {{"affected_files": [{{"path": "路径", "reason": "原因", "suggested_change": "建议"}}], "summary": "摘要"}}
如果没有影响，返回空数组。"""

        try:
            response = self._call_llm_with_retry([
                {"role": "system", "content": "你是代码分析专家。"},
                {"role": "user", "content": impact_prompt}
            ], timeout=180)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                self.add_log("❌ 无法解析 JSON", "error")
                return
            impact_data = json.loads(json_match.group())
            affected_files = impact_data.get("affected_files", [])
            summary = impact_data.get("summary", "")

            if not affected_files:
                self.add_log(f"✅ {summary or '没有影响'}", "success")
                return

            self.add_log(f"📋 发现 {len(affected_files)} 个文件受影响", "info")
            for f in affected_files:
                self.add_log(f"  - {f['path']}: {f['reason']}", "info")
            self._flush_logs()

            self.pending_impact_update = affected_files
            self.ask_signal.emit(
                f"发现 {len(affected_files)} 个文件可能受影响，是否自动修改？\n\n{summary}",
                ["确认修改", "跳过"],
                {"action": "confirm_impact_update"}
            )
        except Exception as e:
            self.add_log(f"❌ 影响分析失败: {e}", "error")

    def _find_files_importing_module(self, module_name: str) -> List[str]:
        importing_files = []
        for py_file in self.workspace_path.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
                patterns = [
                    f"from .{module_name} import", f"from {module_name} import",
                    f"import {module_name}", f"from .models.{module_name} import",
                    f"from models.{module_name} import",
                ]
                for pattern in patterns:
                    if pattern in content:
                        importing_files.append(str(py_file.relative_to(self.workspace_path)))
                        break
            except:
                pass
        return importing_files

    def _execute_impact_update(self, affected_files: list):
        total = len(affected_files)
        structure = self.context.get_project_structure(self.workspace_path)
        for i, file_info in enumerate(affected_files):
            QApplication.processEvents()
            file_path = file_info["path"]
            self.add_log(f"🔄 [{i+1}/{total}] 修改 {file_path}...", "info")
            self._flush_logs()
            full_path = self.workspace_path / file_path
            if not full_path.exists():
                self.add_log(f"⚠️ 文件不存在: {file_path}", "warning")
                continue
            try:
                old_content = full_path.read_text(encoding="utf-8")
                modify_prompt = f"""## 文件: {file_path}
## 原因: {file_info['reason']}
## 建议: {file_info.get('suggested_change', '')}
## 项目结构
{structure}
## 当前内容
{old_content}
输出修改后的完整代码，不要用 markdown 包裹。"""
                response = self._call_llm_with_retry([
                    {"role": "system", "content": "只输出修改后的完整代码。"},
                    {"role": "user", "content": modify_prompt}
                ], timeout=120)
                new_content = self._clean_code(response)
                if file_path.endswith('.py'):
                    try:
                        compile(new_content, file_path, 'exec')
                    except SyntaxError as e:
                        self.add_log(f"❌ 语法错误: {e}", "error")
                        continue
                full_path.write_text(new_content, encoding="utf-8")
                self.add_log(f"✅ [{i+1}/{total}] 已更新: {file_path}", "success")
            except Exception as e:
                self.add_log(f"❌ 修改失败: {e}", "error")
            self._flush_logs()
        self.add_log("✅ 影响更新完成", "success")
        self.finished_signal.emit({"success": True, "refresh": True})