"""
Agent 后台工作线程
"""

import time
import ast
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from utils.file_operator import file_operator
from PySide6.QtCore import QThread, Signal

from core.planner import Planner
from core.coder import Coder
from core.judge import Judge
from core.context_manager import ContextManager, Step, StepStatus
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
    def __init__(self, user_task: str, workspace_path: Path, is_load_mode: bool = False, session_id: str = None):

        super().__init__()
        self.user_task = user_task
        self.workspace_path = workspace_path
        self.is_load_mode = is_load_mode
        self.session_id = session_id
        self.is_paused = False
        self.is_cancelled = False
        self.waiting_for_response = False
        self.user_response = None
        self.user_response_data = None
        self.is_planning_mode = True
        self.is_completed = False
        self.is_executing = False
        self.is_idle = True
        self.pending_modify_file_path = None
        self.pending_modify_content = None

        # ========== 提前初始化这些属性 ==========
        self.steps: List[Step] = []
        self.step_status_map = {}
        self.current_step_index = 0

        self.config = Config()
        planner_config = self.config.get_planner_config()
        coder_config = self.config.get_coder_config()
        judge_config = self.config.get_judge_config()

        self.workspace_path.mkdir(parents=True, exist_ok=True)

        from utils.llm_client import LLMClient
        self.llm_client = LLMClient(planner_config)

        self.context = ContextManager(self.workspace_path, llm_client=self.llm_client)

        if is_load_mode and session_id:
            # 加载已有会话
            session = self.context.load_session(session_id)
            if session:
                self.steps = self.context.current_steps
                for step in self.steps:
                    self.step_status_map[step.id] = (step.status == StepStatus.SUCCESS.value)
                self.user_task = session.user_task
                print(f"会话已加载: {session_id}, 共 {len(self.steps)} 个步骤")
            else:
                print(f"加载会话失败: {session_id}")
        elif not is_load_mode:
            new_session_id = self.context.create_session(user_task)
            print(f"新会话已创建: {new_session_id}")
        # 注意：不再重复初始化 steps 和 step_status_map

        self.planner = Planner(planner_config, self.context)
        self.coder = Coder(coder_config, self.workspace_path)
        self.judge = Judge(judge_config)

    def run(self):
        try:
            if self.is_load_mode:
                self._enter_modify_mode()
            else:
                self._generate_initial_plan()
        except Exception as e:
            self.error_signal.emit(str(e))
            self.log_signal.emit(f"执行出错: {str(e)}", "error")

    def _enter_modify_mode(self):
        self.is_completed = True
        self.is_planning_mode = False
        self.is_idle = True

        if self.context.current_steps:
            self.steps = self.context.current_steps
            for step in self.steps:
                self.step_status_map[step.id] = (step.status == StepStatus.SUCCESS.value)

            step_descriptions = [f"{s.id}. {s.description}" for s in self.steps]
            self.plan_signal.emit(step_descriptions)

            for step in self.steps:
                if step.status == StepStatus.SUCCESS.value:
                    self.step_signal.emit(step.id, "success", step.description)
                elif step.status == StepStatus.FAILED.value:
                    self.step_signal.emit(step.id, "failed", step.description)
                elif step.status == StepStatus.RUNNING.value:
                    self.step_signal.emit(step.id, "running", step.description)

        self.log_signal.emit(f"📁 已加载会话，工作区: {self.workspace_path}", "success")
        self.log_signal.emit("现在你可以输入修改指令：", "info")
        self.log_signal.emit("  🔧 修改 src/models.py，给 User 添加 phone 字段", "info")
        self.log_signal.emit("  🎨 重新写一个更丰富的 index 网页", "info")
        self.log_signal.emit("  🔄 输入「恢复执行」继续未完成的任务", "info")
        self.log_signal.emit("  ❌ 输入「结束」退出", "info")
        self.ask_signal.emit("请输入指令：", [], {"mode": "modify"})
        self.waiting_for_response = True

    def _generate_initial_plan(self):
        self.log_signal.emit("正在生成任务计划...", "info")
        self.status_signal.emit("planning")
        try:
            self.log_signal.emit("正在推断项目约定...", "info")
            agents_md = self.planner.generate_agents_md(self.user_task)
            self.context.save_agents_md(agents_md)
            self.log_signal.emit("项目约定已生成", "success")

            self.steps = self.planner.plan(self.user_task)
            self.context.set_plan(self.steps)
            for step in self.steps:
                self.step_status_map[step.id] = False
        except Exception as e:
            self.error_signal.emit(f"规划失败: {str(e)}")
            self.finished_signal.emit({"success": False, "reason": f"规划失败: {str(e)}"})
            return

        step_descriptions = [f"{s.id}. {s.description}" for s in self.steps]
        self.plan_signal.emit(step_descriptions)
        self.log_signal.emit(f"计划已生成，共 {len(self.steps)} 个步骤", "success")
        self.ask_signal.emit(
            "计划已生成，你可以：\n- 输入「修改计划」来调整步骤\n- 输入「确认执行」开始执行",
            ["确认执行", "修改计划", "取消"],
            {"steps": [s.to_dict() for s in self.steps]}
        )
        self.waiting_for_response = True

    def resume_execution(self):
        self.log_signal.emit("📋 从记忆恢复执行...", "info")
        self.status_signal.emit("executing")
        self.is_planning_mode = False
        self.is_executing = True
        self.is_idle = False

        pending_step = None
        for step in self.steps:
            if step.status not in [StepStatus.SUCCESS.value, StepStatus.SKIPPED.value]:
                pending_step = step
                break

        if not pending_step:
            self.log_signal.emit("所有步骤已完成，进入修改模式", "success")
            self._enter_modify_mode()
            return

        self.log_signal.emit(f"从步骤 {pending_step.id} 继续执行", "info")
        self._continue_from_step(pending_step)

    def _continue_from_step(self, start_step: Step):
        max_iterations = len(self.steps) * 2
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            if self.is_cancelled:
                break

            while self.is_paused and not self.is_cancelled:
                self.msleep(100)

            if self.is_cancelled:
                break

            executed = False
            for step in self.steps:
                if step.status == StepStatus.SUCCESS.value:
                    continue

                if step.id < start_step.id:
                    continue

                if self._check_dependencies(step):
                    self.log_signal.emit(f"执行步骤 {step.id}: {step.description}", "info")
                    self.step_signal.emit(step.id, "running", step.description)
                    self.context.update_step_status(step.id, StepStatus.RUNNING.value)

                    success = self._execute_step(step)

                    if success:
                        self.step_status_map[step.id] = True
                        self.context.update_step_status(step.id, StepStatus.SUCCESS.value)
                        self.step_signal.emit(step.id, "success", step.description)
                        self.log_signal.emit(f"步骤 {step.id} 完成", "success")
                        executed = True
                    else:
                        self.context.update_step_status(step.id, StepStatus.FAILED.value, error=step.error)
                        self.step_signal.emit(step.id, "failed", step.description)
                        self.log_signal.emit(f"步骤 {step.id} 失败: {step.error}", "error")
                        self._save_current_state()
                        self.waiting_for_response = True
                        self.user_response = None
                        self.ask_signal.emit(
                            f"步骤 {step.id} 执行失败。是否继续？",
                            ["继续", "停止"],
                            {"step": step.to_dict(), "error": step.error}
                        )
                        return
                    break

            if not executed:
                break

        self._finish_execution()

    def _finish_execution(self):
        completed_count = sum(1 for step in self.steps if step.status == StepStatus.SUCCESS.value)
        self.status_signal.emit("completed")
        self.context.set_final_result(0, "completed")
        self.is_completed = True
        self.is_executing = False
        self.is_idle = True

        self.log_signal.emit("✅ 任务执行完成！", "success")
        self.log_signal.emit("现在你可以继续输入修改指令：", "info")
        self.log_signal.emit("  🔧 修改 src/models.py，给 User 添加 phone 字段", "info")
        self.log_signal.emit("  🎨 重新写一个更丰富的 index 网页", "info")
        self.ask_signal.emit("请输入修改指令或输入「结束」退出：", [], {"mode": "modify"})
        self.waiting_for_response = True

    def _save_current_state(self):
        try:
            self.context._save_session()
            self.context._save_index()
            self.log_signal.emit("📝 当前状态已保存", "info")
        except Exception as e:
            self.log_signal.emit(f"保存状态失败: {e}", "warning")

    def modify_plan(self, user_feedback: str):
        self.log_signal.emit(f"根据反馈修改计划: {user_feedback}", "info")
        self.status_signal.emit("planning")
        try:
            new_steps = self.planner.modify_plan(self.user_task, self.steps, user_feedback)
            if new_steps:
                self.steps = new_steps
                self.context.set_plan(self.steps)
                for step in self.steps:
                    if step.id not in self.step_status_map:
                        self.step_status_map[step.id] = False
                step_descriptions = [f"{s.id}. {s.description}" for s in self.steps]
                self.plan_signal.emit(step_descriptions)
                self.log_signal.emit(f"计划已更新，共 {len(self.steps)} 个步骤", "success")
            else:
                self.log_signal.emit("无法理解您的修改请求，请重新描述", "warning")
        except Exception as e:
            self.log_signal.emit(f"修改计划失败: {str(e)}", "error")
        self.ask_signal.emit(
            "请确认计划：",
            ["确认执行", "修改计划", "取消"],
            {"steps": [s.to_dict() for s in self.steps]}
        )
        self.waiting_for_response = True

    def start_execution(self):
        self.log_signal.emit("开始执行任务...", "info")
        self.status_signal.emit("executing")
        self.is_planning_mode = False
        self.is_executing = True
        self.is_idle = False

        pending_step = None
        for step in self.steps:
            if step.status not in [StepStatus.SUCCESS.value, StepStatus.SKIPPED.value]:
                pending_step = step
                break

        if pending_step:
            self._continue_from_step(pending_step)
        else:
            self._finish_execution()

    def handle_chat_message(self, message: str):
        self.log_signal.emit(f"👤 用户: {message}", "user")

        if message == "结束":
            self._save_current_state()
            self.finished_signal.emit({"success": True, "completed": True})
            return

        if message == "恢复执行":
            if self.is_idle and self.steps:
                has_pending = any(s.status not in [StepStatus.SUCCESS.value] for s in self.steps)
                if has_pending:
                    self.resume_execution()
                else:
                    self.log_signal.emit("所有步骤已完成，无需恢复", "info")
            else:
                self.log_signal.emit("当前无法恢复执行", "warning")
            return

        intent = self._classify_intent(message)

        if intent == "modify" and self.is_idle:
            self._handle_modify_request_v2(message)
        elif intent == "modify" and self.is_executing:
            self.log_signal.emit("🤖 当前正在执行任务，请等待完成后再修改", "ai")
        elif intent == "ask_status":
            self._answer_from_memory(message)
        else:
            self._answer_from_memory(message)

    def _classify_intent(self, message: str) -> str:
        modify_keywords = ["修改", "改", "添加", "删除", "更新", "重新", "重写", "加上", "去掉"]
        ask_keywords = ["是什么", "有哪些", "怎么", "如何", "为什么", "什么", "谁", "哪", "字段", "表", "文件"]

        msg_lower = message.lower()

        if any(kw in msg_lower for kw in modify_keywords):
            return "modify"
        elif any(kw in msg_lower for kw in ask_keywords) or "?" in message or "？" in message:
            return "ask_status"
        else:
            return "general"

    def _answer_from_memory(self, question: str):
        self.log_signal.emit("🤖 正在从记忆中查找...", "info")

        context = self.context.get_context_for_modify(question)

        prompt = f"""
你是项目助手，根据以下项目信息回答用户问题。

{context}

用户问题：{question}

请简洁回答，如果信息不足，诚实说明。
直接输出回答。
"""

        try:
            answer = self.llm_client.chat([
                {"role": "system", "content": "你是项目助手，根据项目信息回答问题。"},
                {"role": "user", "content": prompt}
            ])
            self.log_signal.emit(f"🤖 {answer}", "ai")
        except Exception as e:
            self.log_signal.emit(f"🤖 抱歉，我暂时无法回答这个问题: {e}", "error")

    def _handle_modify_request_v2(self, command: str):
        self.log_signal.emit(f"处理修改请求: {command}", "info")

        context = self.context.get_context_for_modify(command)

        analysis_prompt = f"""用户想要修改项目文件，请分析并返回需要修改的内容。

{context}

用户指令: {command}

请输出JSON格式：
{{
    "target_file": "要修改的文件路径（相对于工作区，如 src/models/user.py）",
    "modification_type": "rewrite 或 partial",
    "content_description": "要改成什么样子的详细描述",
    "explanation": "简要说明"
}}

只输出JSON，不要其他内容。"""

        try:
            response = self.llm_client.chat([
                {"role": "system", "content": "你是一个代码分析专家。分析用户需求，输出要修改的文件路径和内容描述。"},
                {"role": "user", "content": analysis_prompt}
            ])

            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            analysis = json.loads(json_str)
            target_file = analysis.get("target_file", "")
            content_desc = analysis.get("content_description", "")

            if not target_file:
                self.log_signal.emit("无法确定要修改哪个文件", "warning")
                self._wait_for_next_command()
                return

            file_path = self.workspace_path / target_file
            if not file_path.exists():
                self.log_signal.emit(f"找不到文件: {target_file}", "warning")
                self._wait_for_next_command()
                return

            self.log_signal.emit(f"找到文件: {target_file}", "success")
            old_content = file_path.read_text(encoding="utf-8")

            modify_prompt = f"""请根据用户要求修改文件。

{context}

文件路径: {target_file}
用户指令: {command}
修改要求: {content_desc}

当前代码:
{old_content}

要求：
1. 根据用户要求修改代码
2. 输出修改后的完整代码
3. 不要用markdown代码块包裹"""

            mod_response = self.coder.client.chat([
                {"role": "system", "content": "你是一个代码修改专家。只输出修改后的完整代码，不要解释。"},
                {"role": "user", "content": modify_prompt}
            ])
            new_content = self._clean_code(mod_response)

            rel_path = str(file_path.relative_to(self.workspace_path))
            self.diff_signal.emit(rel_path, old_content, new_content)

            self.pending_modify_file_path = str(file_path)
            self.pending_modify_content = new_content

            self.ask_signal.emit(f"即将修改文件 {target_file}，是否确认？", ["确认修改", "取消"], {})
            self.waiting_for_response = True

        except Exception as e:
            self.log_signal.emit(f"处理失败: {str(e)}", "error")
            self._wait_for_next_command()

    def _wait_for_next_command(self):
        self.ask_signal.emit("请输入下一个修改指令，或输入「结束」退出：", [], {"mode": "modify"})
        self.waiting_for_response = True

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
            src_path = self.workspace_path / "src"
            tests_path = self.workspace_path / "tests"
            src_path.mkdir(parents=True, exist_ok=True)
            tests_path.mkdir(parents=True, exist_ok=True)
            step.files_modified.append(str(src_path))
            step.files_modified.append(str(tests_path))
            self.log_signal.emit(f"项目目录已创建: {self.workspace_path}", "success")
            return True
        except Exception as e:
            step.error = str(e)
            return False

    def _execute_code_step(self, step: Step) -> bool:
        self.log_signal.emit(f"生成代码: {step.description}", "info")

        try:
            file_path = self._extract_file_path(step.description)
            full_context = self.context.get_full_context_for_step(step)

            code, success, error = self.coder.generate_code_with_context(
                step.description, file_path, full_context
            )

            if not success:
                step.error = error
                return False

            # ========== 只对 Python 文件做语法检查 ==========
            if file_path.endswith('.py'):
                syntax_ok, syntax_error = self.coder._check_syntax(code, file_path)
                if not syntax_ok:
                    step.error = syntax_error
                    self.log_signal.emit(f"语法错误: {syntax_error}", "error")
                    return False

            success, error = self.coder.write_file(file_path, code)
            if not success:
                step.error = error
                return False

            step.files_modified.append(file_path)
            self.log_signal.emit(f"代码已保存: {file_path}", "success")

            self._update_context_after_step(step, code, file_path)

            return True

        except Exception as e:
            step.error = str(e)
            self.log_signal.emit(f"代码生成异常: {str(e)}", "error")
            return False
    def _update_context_after_step(self, step: Step, code: str, file_path: str):
        try:
            summary, design_notes = self.context.generate_step_summary(step, code)
            step.design_notes = design_notes
            step.exported_api = summary

            file_summary = self.context.generate_file_summary_for_index(file_path, code)
            self.context.add_file_summary(file_path, file_summary)

            self.context.write_daily_log(step, summary, code[:500])

            self.context.update_memory(step, summary)

            self.context.update_step(step)

            self.log_signal.emit(f"📝 记忆已更新", "success")

        except Exception as e:
            self.log_signal.emit(f"更新记忆失败: {e}", "warning")

    def _execute_test_step(self, step: Step) -> bool:
        self.log_signal.emit(f"生成测试: {step.description}", "info")
        return True

    def _extract_file_path(self, description: str) -> str:
        # Python
        match = re.search(r'([\w/]+\.py)', description)
        if match:
            return match.group(1)
        # HTML
        match = re.search(r'([\w/]+\.html)', description)
        if match:
            return match.group(1)
        # CSS
        match = re.search(r'([\w/]+\.css)', description)
        if match:
            return match.group(1)
        # JavaScript
        match = re.search(r'([\w/]+\.js)', description)
        if match:
            return match.group(1)
        # Markdown
        match = re.search(r'([\w/]+\.md)', description)
        if match:
            return match.group(1)
        # JSON
        match = re.search(r'([\w/]+\.json)', description)
        if match:
            return match.group(1)
        # 文本文件
        match = re.search(r'([\w/]+\.txt)', description)
        if match:
            return match.group(1)

        # 如果都匹配不到，尝试提取任何 单词/单词.扩展名 的模式
        match = re.search(r'([\w/]+\.[a-zA-Z]+)', description)
        if match:
            return match.group(1)

        return "src/step.py"

    def _clean_code(self, response: str) -> str:
        code = response.strip()
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```html" in code:
            code = code.split("```html")[1].split("```")[0]
        elif "```css" in code:
            code = code.split("```css")[1].split("```")[0]
        elif "```js" in code or "```javascript" in code:
            code = code.split("```js")[1].split("```")[0] if "```js" in code else code.split("```javascript")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]
        return code.strip()

    def _check_dependencies(self, step: Step) -> bool:
        if not step.depends_on:
            return True
        for dep_id in step.depends_on:
            dep_step = self.context.get_step_by_id(dep_id)
            if dep_step and dep_step.status != StepStatus.SUCCESS.value:
                return False
        return True

    def pause(self):
        self.is_paused = True
        self.status_signal.emit("paused")

    def resume(self):
        self.is_paused = False
        self.status_signal.emit("executing")

    def cancel(self):
        self.is_cancelled = True

    def on_user_response(self, response: str, data: dict = None):
        print(f"=== AgentWorker.on_user_response 被调用 ===")
        print(f"response: {response}")

        # ========== 特殊命令优先处理 ==========
        if response == "恢复执行":
            self.waiting_for_response = False
            if self.is_idle and self.steps:
                has_pending = any(s.status not in [StepStatus.SUCCESS.value] for s in self.steps)
                if has_pending:
                    self.resume_execution()
                else:
                    self.log_signal.emit("所有步骤已完成，无需恢复", "info")
                    self._wait_for_next_command()
            else:
                self.log_signal.emit("当前无法恢复执行", "warning")
                self._wait_for_next_command()
            return

        if response == "结束":
            self._save_current_state()
            self.finished_signal.emit({"success": True, "completed": True})
            return

        # ========== 正常响应处理 ==========
        self.user_response = response
        self.user_response_data = data
        self.waiting_for_response = False
        self.log_signal.emit(f"用户响应: {response}", "user")

        if response == "确认修改":
            self.log_signal.emit("========== 开始覆盖文件 ==========", "info")
            if self.pending_modify_file_path and self.pending_modify_content:
                try:
                    path = Path(self.pending_modify_file_path)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(self.pending_modify_content, encoding="utf-8")
                    self.log_signal.emit(f"✅ 文件已覆盖: {path}", "success")
                    self._save_current_state()
                    self.finished_signal.emit({"success": True, "refresh": True})
                except Exception as e:
                    self.log_signal.emit(f"❌ 保存失败: {str(e)}", "error")
                    self.finished_signal.emit({"success": False, "reason": str(e)})
            else:
                self.log_signal.emit("❌ 错误: pending_modify_file_path 或 pending_modify_content 为空", "error")
            self._wait_for_next_command()
            return

        if response == "取消":
            self._wait_for_next_command()
            return

        if response == "继续":
            if self.is_executing:
                pending = self._get_pending_step()
                if pending:
                    self._continue_from_step(pending)
            return

        if response == "停止":
            self._save_current_state()
            self.finished_signal.emit({"success": False, "reason": "用户停止"})
            return

        if data and data.get("mode") == "modify":
            self._handle_modify_request_v2(response)
        elif response == "确认执行":
            self.start_execution()
        elif response == "修改计划":
            self.ask_signal.emit(
                "请描述您想要修改的内容，例如：在步骤2后添加VIP功能",
                [],
                {"action": "modify_plan"}
            )

            self.waiting_for_response = True
    def on_modify_feedback(self, feedback: str):
        self.modify_plan(feedback)


