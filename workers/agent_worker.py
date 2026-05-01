"""
Agent 后台工作线程 - 状态机版本 (完整版)
每个 Agent 有独立的 ToolRegistry
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
from core.tools import ToolRegistry, ToolResult
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
        self.waiting_for_response = False
        self.is_paused = False
        self.is_cancelled = False
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

        self.chat_tools = ToolRegistry("chat")
        self.coder_tools = ToolRegistry("coder")
        self.planner_tools = ToolRegistry("planner")
        self.judge_tools = ToolRegistry("judge")

        self.skill_manager = None
        self._init_skills()

        self._register_chat_tools()
        self._register_coder_tools()
        self._register_planner_tools()
        self._load_mcp_tools()

    # ========== 工具注册 ==========

    def _register_chat_tools(self):
        self.chat_tools.register_many([
            SearchMemoryTool(), GetStatusTool(), ResumeTaskTool(), PauseTaskTool(),
            UpdateAgentsTool(), AddDependencyTool(),
        ])
        if self.skill_manager:
            try:
                from core.tools.builtin.skill_tools import ListSkillsTool, ReadSkillTool
                self.chat_tools.register(ListSkillsTool())
                self.chat_tools.register(ReadSkillTool())
            except Exception as e:
                print(f"Skill 工具注册失败: {e}")

    def _register_coder_tools(self):
        self.coder_tools.register_many([
            CreateFileTool(), ModifyFileTool(), ReadFileTool(), ListFilesTool(),
        ])

    def _register_planner_tools(self):
        self.planner_tools.register_many([ListFilesTool(), ReadFileTool()])

    def _load_mcp_tools(self):
        try:
            from core.mcp.connectors.streamable_http import StreamableHttpConnector
            from core.mcp.connectors.mcp_tool import MCPToolAdapter

            agent_registries = {
                "chat": self.chat_tools, "coder": self.coder_tools,
                "planner": self.planner_tools, "judge": self.judge_tools,
            }
            for agent_name, registry in agent_registries.items():
                mcp_config = self.config.get(f"mcp_{agent_name}", {})
                if isinstance(mcp_config, str):
                    try:
                        mcp_config = json.loads(mcp_config)
                    except:
                        continue
                servers = mcp_config.get("mcpServers", {})
                for server_name, server_config in servers.items():
                    url = server_config.get("url", "")
                    if url:
                        try:
                            connector = StreamableHttpConnector()
                            if connector.connect({"url": url, "headers": {}}):
                                for tool_config in connector.list_tools():
                                    tool_name = tool_config.get("name", "")
                                    prefixed_name = f"mcp_{server_name}__{tool_name}"
                                    adapter = MCPToolAdapter(tool_name, tool_config, connector)
                                    registry.register(adapter)
                        except Exception as e:
                            pass
        except Exception as e:
            pass

    def _on_state_changed(self, old_state: AgentState, new_state: AgentState, reason: str):
        self.state_signal.emit(new_state.value)
        self.add_log(f"📌 {reason or f'状态: {new_state.value}'}", "info")

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
                self.add_log("📁 已加载会话", "success")
            else:
                self.sm.transition_to(AgentState.PLANNING, "开始规划")
                self._generate_initial_plan()
        except Exception as e:
            self.error_signal.emit(str(e))
            self.sm.force_transition(AgentState.IDLE)

    # ========== 用户输入处理 ==========

    def handle_user_input(self, message: str):
        self.add_log(f"👤 用户: {message}", "user")
        self._flush_logs()
        if message == "结束":
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
            return

        if self.sm.state == AgentState.WAITING_CONFIRM:
            self._handle_confirmation(message)
            return
        if self.sm.state == AgentState.EXECUTING:
            intent = self._quick_classify(message)
            if intent == "modify":
                self.sm.transition_to(AgentState.MODIFYING, "执行中穿插修改")
                self._handle_chat(message)
                self.sm.transition_to(AgentState.EXECUTING, "修改完成")
            elif intent == "pause":
                self.sm.transition_to(AgentState.PAUSED, "用户暂停")
            else:
                self._handle_chat(message)
            return
        if self.sm.state == AgentState.IDLE:
            intent = self._quick_classify(message)
            if intent == "new_task":
                self.sm.transition_to(AgentState.PLANNING, "新任务")
                self.user_task = message
                self._generate_initial_plan()
            elif intent == "resume":
                self.sm.transition_to(AgentState.EXECUTING, "恢复执行")
                self._continue_from_step(self._get_pending_step())
            else:
                self._handle_chat(message)
            return

        self._handle_chat(message)

    def _handle_confirmation(self, message: str):
        """处理确认状态的用户输入，直接处理不递归"""
        self.add_log(f"用户响应: {message}", "user")

        if self.ctx.pending_action == "confirm_plan":
            if message == "确认执行":
                self.sm.transition_to(AgentState.EXECUTING, "开始执行")
                self._continue_from_step(self._get_pending_step())
            elif message == "修改计划":
                self.sm.transition_to(AgentState.PLANNING, "修改计划")
            else:
                self.sm.transition_to(AgentState.IDLE, "用户取消")
        elif self.ctx.pending_action == "confirm_impact_update":
            if message == "确认修改":
                self._execute_impact_update(self.pending_impact_update)
            self.sm.transition_to(AgentState.IDLE, "影响更新完成")
        elif message == "确认修改":
            if self.pending_modify_file_path and self.pending_modify_content:
                try:
                    Path(self.pending_modify_file_path).write_text(self.pending_modify_content, encoding="utf-8")
                    self.add_log("✅ 文件已覆盖", "success")
                    self.finished_signal.emit({"success": True, "refresh": True})
                except Exception as e:
                    self.add_log(f"❌ 保存失败: {e}", "error")
            self.sm.transition_to(AgentState.IDLE, "修改确认完成")

    def _quick_classify(self, message: str) -> str:
        if any(kw in message for kw in ["暂停", "停一下"]):
            return "pause"
        if any(kw in message for kw in ["继续", "接着", "恢复"]):
            return "resume"
        if any(kw in message for kw in ["做一个", "创建一个", "搭建", "开发"]):
            return "new_task"
        if any(kw in message for kw in ["修改", "改", "添加", "删除", "创建", "新建", "生成", "写"]):
            return "modify"
        return "chat"

    # ========== 聊天处理 ==========

    def _handle_chat(self, message: str, max_rounds: int = 5):
        original_message = message
        tool_results = []
        all_tool_names = []

        for round_num in range(max_rounds):
            intent = self._classify_intent_with_llm(message)
            if intent.get("tool") == "chat":
                response = intent.get("params", {}).get("response", "")
                if response:
                    self.add_log(f"🤖 Agent: {response}", "ai")
                    self._flush_logs()
                return
            tool_name = intent.get("tool")
            if not tool_name:
                return

            all_tool_names.append(tool_name)
            if len(all_tool_names) >= 3 and len(set(all_tool_names[-3:])) == 1:
                break

            self.add_log(f"🔧 调用工具: {tool_name}", "info")
            result = self._execute_tool(tool_name, intent.get("params", {}))
            tool_results.append({"tool": tool_name, "result": result})

            results_summary = self._format_tool_results(tool_results)
            message = f"""原始请求: {original_message}
已执行的操作:
{results_summary}
请判断任务是否完成。如果还需要调用其他工具，输出工具调用 JSON。如果任务已完成，输出 {{"tool": "chat", "params": {{"response": "你的最终回复"}}}}"""

        response = self._generate_final_response(original_message, tool_results)
        self.add_log(f"🤖 Agent: {response}", "ai")

    def _format_tool_results(self, tool_results: list) -> str:
        lines = []
        for i, item in enumerate(tool_results):
            if item["result"].success:
                lines.append(f"{i + 1}. {item['tool']} ✅: {str(item['result'].result)[:300]}")
            else:
                lines.append(f"{i + 1}. {item['tool']} ❌: {item['result'].error}")
        return "\n".join(lines)

    def _generate_final_response(self, original_message: str, tool_results: list) -> str:
        try:
            return self._call_llm_with_retry([
                {"role": "system", "content": "总结执行结果。"},
                {"role": "user", "content": f"请求: {original_message}\n结果: {self._format_tool_results(tool_results)}"}
            ])
        except:
            return f"✅ 完成 {sum(1 for r in tool_results if r['result'].success)}/{len(tool_results)} 个操作"

    def _classify_intent_with_llm(self, message: str) -> dict:
        tools_prompt = self.chat_tools.get_tools_prompt()
        if self.skill_manager:
            tools_prompt += f"\n\n{self.skill_manager.get_skills_prompt()}"
        project_structure = self.context.get_project_structure(self.workspace_path)
        agents_md = self.context.read_agents_md()
        constraints = self._extract_key_constraints(agents_md)

        prompt = f"""## ⚠️ 必须输出 JSON
    ## 项目约定
    {constraints}
    ## 可用工具
    {tools_prompt}
    ## 项目结构
    {project_structure}
    ## 用户消息
    {message}
    输出 JSON：{{"tool": "工具名", "params": {{...}}}} 或 {{"tool": "chat", "params": {{"response": "回复"}}}}"""
        try:
            response = self._call_llm_with_retry([
                {"role": "system", "content": "只输出 JSON。"},
                {"role": "user", "content": prompt}
            ])
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:

                parsed = json.loads(json_match.group())
                return parsed
            else:
                print(f"=== JSON 匹配失败 ===")
        except Exception as e:
            print(f"=== classify_intent 异常: {e} ===")

        return {"tool": "chat", "params": {"response": "抱歉，我不太明白。"}}
    def _extract_key_constraints(self, agents_md: str) -> str:
        if not agents_md:
            return "暂无项目约定"
        lines = []
        for section in ["## 技术栈", "## 可用依赖", "## 禁止事项"]:
            if section in agents_md:
                sec_content = agents_md.split(section)[1].split("##")[0]
                lines.append(f"**{section.replace('## ', '')}**:")
                for line in sec_content.strip().split('\n'):
                    if line.strip() and not line.strip().startswith('#'):
                        lines.append(line.strip())
        return '\n'.join(lines) if lines else "暂无项目约定"

    def _execute_tool(self, tool_name: str, params: dict) -> ToolResult:
        context = {
            "worker": self, "coder": self.coder,
            "context_manager": self.context, "workspace_path": self.workspace_path,
            "steps": self.steps, "skill_manager": self.skill_manager,
        }
        for registry in [self.chat_tools, self.coder_tools, self.planner_tools]:
            tool = registry.get(tool_name)
            if tool:
                try:
                    result = tool.execute(params, context)
                    if isinstance(result, dict):
                        return ToolResult(success=result.get("success", False), result=result.get("result"), error=result.get("error"))
                    elif isinstance(result, ToolResult):
                        return result
                    return ToolResult.ok(result)
                except Exception as e:
                    return ToolResult.fail(f"工具执行异常: {e}")
        return ToolResult.fail(f"工具不存在: {tool_name}")

    # ========== LLM 调用 ==========

    def _call_llm_with_retry(self, messages: list, max_retries: int = 3, timeout: int = 120) -> str:
        last_error = None
        for attempt in range(max_retries):
            try:
                return self.llm_client.chat(messages, timeout=timeout)
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    time.sleep(3)
        raise Exception(f"LLM 调用失败: {last_error}")

    def on_user_response(self, response: str, data: dict = None):
        """处理用户响应（按钮点击等）"""
        self.add_log(f"用户响应: {response}", "user")

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
    def _clean_code(self, response: str) -> str:
        code = response.strip()
        if "```python" in code:
            return code.split("```python")[1].split("```")[0]
        elif "```" in code:
            parts = code.split("```")
            if len(parts) >= 3:
                return parts[1]
        return code

    # ========== 日志 ==========

    def _emit_log_batch(self):
        if self._pending_logs:
            self.log_signal.emit("\n".join(self._pending_logs), self._log_level)
            self._pending_logs.clear()

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

    # ========== 计划生成 ==========

    def _generate_initial_plan(self):
        self.add_log("正在生成计划...", "info")
        try:
            existing_agents = self.context.read_agents_md()
            if not existing_agents:
                agents_md = self.planner.generate_agents_md(self.user_task)
                self.context.save_agents_md(agents_md)
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
        self.waiting_for_response = True

    # ========== 步骤执行 ==========

    def _get_pending_step(self) -> Optional[Step]:
        for step in self.steps:
            if step.status not in [StepStatus.SUCCESS.value, StepStatus.SKIPPED.value]:
                return step
        return None

    def _continue_from_step(self, start_step: Step):
        if not start_step:
            self._finish_execution()
            return

        max_iterations = len(self.steps) * 2
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            QApplication.processEvents()

            if self.is_cancelled:
                break

            executed = False
            for step in self.steps:
                if step.status == StepStatus.SUCCESS.value:
                    continue
                if step.id < start_step.id:
                    continue
                if self._check_dependencies(step):
                    self.add_log(f"执行步骤 {step.id}: {step.description}", "info")
                    self.step_signal.emit(step.id, "running", step.description)
                    self.context.update_step_status(step.id, StepStatus.RUNNING.value)
                    QApplication.processEvents()

                    success = self._execute_step(step)
                    if success:
                        self.step_status_map[step.id] = True
                        self.context.update_step_status(step.id, StepStatus.SUCCESS.value)
                        self.step_signal.emit(step.id, "success", step.description)
                        self.add_log(f"步骤 {step.id} 完成", "success")
                        executed = True
                    else:
                        self.context.update_step_status(step.id, StepStatus.FAILED.value, error=step.error)
                        self.step_signal.emit(step.id, "failed", step.description)
                        self.add_log(f"步骤 {step.id} 失败: {step.error}", "error")
                        self.ask_signal.emit(f"步骤 {step.id} 失败。是否继续？", ["继续", "停止"], {})
                        self.waiting_for_response = True
                        return
                    break
            if not executed:
                break

        self._finish_execution()

    def _execute_step(self, step: Step) -> bool:
        try:
            if step.type == "setup":
                return self._execute_setup_step(step)
            elif step.type == "code":
                return self._execute_code_step(step)
            elif step.type == "test":
                return self._execute_test_step(step)
            else:
                return self._execute_code_step(step)
        except Exception as e:
            step.error = str(e)
            return False

    def _execute_setup_step(self, step: Step) -> bool:
        try:
            (self.workspace_path / "src").mkdir(parents=True, exist_ok=True)
            (self.workspace_path / "tests").mkdir(parents=True, exist_ok=True)
            step.files_modified = ["src", "tests"]
            return True
        except Exception as e:
            step.error = str(e)
            return False

    def _execute_code_step(self, step: Step) -> bool:
        try:
            file_path = self._extract_file_path(step.description)
            full_context = self.context.get_full_context_for_step(step)
            code, success, error = self.coder.generate_code_with_context(step.description, file_path, full_context)
            if not success:
                step.error = error
                return False
            if file_path.endswith('.py'):
                syntax_ok, syntax_error = self.coder._check_syntax(code, file_path)
                if not syntax_ok:
                    step.error = syntax_error
                    return False
            success, error = self.coder.write_file(file_path, code)
            if not success:
                step.error = error
                return False
            step.files_modified.append(file_path)
            self._update_context_after_step(step, code, file_path)
            return True
        except Exception as e:
            step.error = str(e)
            return False

    def _execute_test_step(self, step: Step) -> bool:
        return True

    def _extract_file_path(self, description: str) -> str:
        for ext in ['.py', '.html', '.css', '.js', '.json', '.yaml', '.yml', '.md', '.txt']:
            match = re.search(rf'([\w/]+\.{ext[1:]})', description)
            if match:
                return match.group(1)
        match = re.search(r'([\w/]+\.[a-zA-Z]+)', description)
        return match.group(1) if match else "src/step.py"

    def _check_dependencies(self, step: Step) -> bool:
        if not step.depends_on:
            return True
        for dep_id in step.depends_on:
            dep_step = self.context.get_step_by_id(dep_id)
            if dep_step and dep_step.status != StepStatus.SUCCESS.value:
                return False
        return True

    def _update_context_after_step(self, step: Step, code: str, file_path: str):
        try:
            summary, design_notes = self.context.generate_step_summary(step, code)
            step.design_notes = design_notes
            step.exported_api = summary
            file_summary = self.context.generate_file_summary_for_index(file_path, code, summary)
            self.context.add_file_summary(file_path, file_summary)
            self.context.write_daily_log(step, summary, code[:500])
            if step.id % 5 == 0 or step.id == len(self.steps):
                self.context.update_memory(step, summary)
            self.context.update_step(step)
        except:
            pass

    def _finish_execution(self):
        self.add_log("✅ 任务完成！", "success")
        self.sm.transition_to(AgentState.IDLE, "任务完成")

    def _save_current_state(self):
        try:
            self.context._save_session()
            self.context._save_index()
        except:
            pass

    # ========== 影响分析 ==========

    def _generate_diff(self, old_content: str, new_content: str) -> str:
        import difflib
        return '\n'.join(difflib.unified_diff(old_content.splitlines(), new_content.splitlines(), fromfile='修改前', tofile='修改后', lineterm=''))

    def analyze_impact_and_update(self, file_path: str, old_content: str, new_content: str):
        self.add_log(f"🔍 分析 {file_path} 的影响范围...", "info")
        related_files = self._find_files_importing_module(Path(file_path).stem)
        related_contents = []
        for rel_path in related_files[:5]:
            full_path = self.workspace_path / rel_path
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding="utf-8")
                    related_contents.append(f"\n### {rel_path}\n```\n{content}\n```")
                except:
                    pass

        diff = self._generate_diff(old_content, new_content)
        impact_prompt = f"""## 用户修改的文件: {file_path}
## 代码差异
{diff}
## 项目结构
{self.context.get_project_structure(self.workspace_path)}
## 相关文件内容
{chr(10).join(related_contents) if related_contents else "无"}
根据差异分析修改影响。输出 JSON: {{"affected_files": [{{"path": "路径", "reason": "原因", "suggested_change": "建议"}}], "summary": "摘要"}}"""

        try:
            response = self._call_llm_with_retry([
                {"role": "system", "content": "你是代码分析专家。"},
                {"role": "user", "content": impact_prompt}
            ], timeout=180)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return
            impact_data = json.loads(json_match.group())
            affected_files = impact_data.get("affected_files", [])
            if not affected_files:
                self.add_log("✅ 没有发现需要修改的其他文件", "success")
                return
            self.add_log(f"📋 发现 {len(affected_files)} 个文件可能受影响", "info")
            for f in affected_files:
                self.add_log(f"  - {f['path']}: {f['reason']}", "info")
            self.pending_impact_update = affected_files
            self.ask_signal.emit(f"发现 {len(affected_files)} 个文件可能受影响，是否自动修改？", ["确认修改", "跳过"], {"action": "confirm_impact_update"})
            self.ctx.pending_action = "confirm_impact_update"
            self.waiting_for_response = True
        except Exception as e:
            self.add_log(f"❌ 影响分析失败: {e}", "error")

    def _find_files_importing_module(self, module_name: str) -> List[str]:
        importing_files = []
        for py_file in self.workspace_path.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
                patterns = [f"from .{module_name} import", f"from {module_name} import", f"import {module_name}"]
                for pattern in patterns:
                    if pattern in content:
                        importing_files.append(str(py_file.relative_to(self.workspace_path)))
                        break
            except:
                pass
        return importing_files

    def _execute_impact_update(self, affected_files: list):
        structure = self.context.get_project_structure(self.workspace_path)
        for i, file_info in enumerate(affected_files):
            QApplication.processEvents()
            file_path = file_info["path"]
            full_path = self.workspace_path / file_path
            if not full_path.exists():
                continue
            try:
                old_content = full_path.read_text(encoding="utf-8")
                modify_prompt = f"""## 文件: {file_path}\n## 原因: {file_info['reason']}\n## 建议: {file_info.get('suggested_change', '')}\n## 当前内容\n{old_content}\n输出修改后的完整代码。"""
                response = self._call_llm_with_retry([
                    {"role": "system", "content": "只输出修改后的完整代码。"},
                    {"role": "user", "content": modify_prompt}
                ], timeout=120)
                new_content = self._clean_code(response)
                if file_path.endswith('.py'):
                    try:
                        compile(new_content, file_path, 'exec')
                    except SyntaxError:
                        continue
                full_path.write_text(new_content, encoding="utf-8")
                self.add_log(f"✅ 已更新: {file_path}", "success")
            except Exception as e:
                self.add_log(f"❌ 修改失败: {e}", "error")
        self.add_log("✅ 影响更新完成", "success")
        self.finished_signal.emit({"success": True, "refresh": True})

    # ========== Skill ==========

    def _init_skills(self):
        try:
            from core.skill.skill_manager import SkillManager
            self.skill_manager = SkillManager(Path("extensions/skills"))
            count = self.skill_manager.load_all()
            if count > 0:
                print(f"🧩 已加载 {count} 个 Skill")
        except:
            self.skill_manager = None

    # ========== 控制方法 ==========

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
        self.waiting_for_response = True

    def resume_execution(self):
        self.sm.transition_to(AgentState.EXECUTING, "恢复执行")
        pending = self._get_pending_step()
        if pending:
            self._continue_from_step(pending)

    def on_modify_feedback(self, feedback: str):
        self.modify_plan(feedback)
