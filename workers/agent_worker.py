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

    def __init__(self, user_task: str, workspace_path: Path, is_load_mode: bool = False):
        super().__init__()
        self.user_task = user_task
        self.workspace_path = workspace_path
        self.is_load_mode = is_load_mode
        self.is_paused = False
        self.is_cancelled = False
        self.waiting_for_response = False
        self.user_response = None
        self.user_response_data = None
        self.is_planning_mode = True
        self.is_completed = False
        self.pending_modify_file_path = None
        self.pending_modify_content = None

        self.config = Config()
        planner_config = self.config.get_planner_config()
        coder_config = self.config.get_coder_config()
        judge_config = self.config.get_judge_config()

        self.workspace_path.mkdir(parents=True, exist_ok=True)

        self.context = ContextManager(self.workspace_path.parent)

        if not is_load_mode:
            session_id = self.context.create_session(user_task)
            print(f"新会话已创建: {session_id}")

        self.planner = Planner(planner_config, self.context)
        self.coder = Coder(coder_config, self.workspace_path)
        self.judge = Judge(judge_config)

        self.current_step_index = 0
        self.steps: List[Step] = []
        self.step_status_map = {}

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
        self.log_signal.emit(f"📁 已加载会话，工作区: {self.workspace_path}", "success")
        self.log_signal.emit("现在你可以输入修改指令：", "info")
        self.log_signal.emit("  🔧 修改 src/models.py，给 User 添加 phone 字段", "info")
        self.log_signal.emit("  🎨 重新写一个更丰富的 index 网页", "info")
        self.log_signal.emit("  ❌ 输入「结束」退出", "info")
        self.ask_signal.emit("请输入修改指令：", [], {"mode": "modify"})
        self.waiting_for_response = True

    def _generate_initial_plan(self):
        self.log_signal.emit("正在生成任务计划...", "info")
        self.status_signal.emit("planning")
        try:
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
        self.ask_signal.emit("计划已生成，你可以：\n- 输入「修改计划」来调整步骤\n- 输入「确认执行」开始执行", ["确认执行", "修改计划", "取消"], {"steps": [s.to_dict() for s in self.steps]})
        self.waiting_for_response = True

    def modify_plan(self, user_feedback: str):
        self.log_signal.emit(f"根据反馈修改计划: {user_feedback}", "info")
        self.status_signal.emit("planning")
        try:
            new_steps = self.planner.modify_plan(self.user_task, self.steps, user_feedback)
            if new_steps:
                self.steps = new_steps
                self.context.set_plan(self.steps)
                step_descriptions = [f"{s.id}. {s.description}" for s in self.steps]
                self.plan_signal.emit(step_descriptions)
                self.log_signal.emit(f"计划已更新，共 {len(self.steps)} 个步骤", "success")
            else:
                self.log_signal.emit("无法理解您的修改请求，请重新描述", "warning")
        except Exception as e:
            self.log_signal.emit(f"修改计划失败: {str(e)}", "error")
        self.ask_signal.emit("请确认计划：", ["确认执行", "修改计划", "取消"], {"steps": [s.to_dict() for s in self.steps]})
        self.waiting_for_response = True

    def start_execution(self):
        self.log_signal.emit("开始执行任务...", "info")
        self.status_signal.emit("executing")
        self.is_planning_mode = False
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
                if self.step_status_map.get(step.id, False):
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
                        self.waiting_for_response = True
                        self.user_response = None
                        self.ask_signal.emit(f"步骤 {step.id} 执行失败。是否继续？", ["继续", "停止"], {"step": step.to_dict(), "error": step.error})
                        while self.waiting_for_response and not self.is_cancelled:
                            self.msleep(100)
                        if self.user_response != "继续":
                            self.finished_signal.emit({"success": False, "reason": f"步骤 {step.id} 失败"})
                            return
                    break
            if not executed:
                break
        completed_count = sum(1 for step in self.steps if self.step_status_map.get(step.id, False))
        self.status_signal.emit("completed")
        self.context.set_final_result(0, "completed")
        self.is_completed = True
        self.log_signal.emit("✅ 任务执行完成！", "success")
        self.log_signal.emit("现在你可以继续输入修改指令：", "info")
        self.log_signal.emit("  🔧 修改 src/models.py，给 User 添加 phone 字段", "info")
        self.log_signal.emit("  🎨 重新写一个更丰富的 index 网页", "info")
        self.ask_signal.emit("请输入修改指令或输入「结束」退出：", [], {"mode": "modify"})
        self.waiting_for_response = True

    def _find_file_by_name(self, target_name: str) -> Optional[Path]:
        target_name_lower = target_name.lower()
        name_mapping = {
            "index.html": ["index.html", "src/templates/index.html", "templates/index.html"],
            "style.css": ["style.css", "src/static/css/style.css", "static/css/style.css", "css/style.css"],
            "main.js": ["main.js", "src/static/js/main.js", "static/js/main.js", "js/main.js"],
        }
        if target_name_lower in name_mapping:
            for mapped_path in name_mapping[target_name_lower]:
                full_path = self.workspace_path / mapped_path
                if full_path.exists():
                    return full_path
        for file_path in self.workspace_path.rglob("*"):
            if file_path.is_file() and file_path.name.lower() == target_name_lower:
                return file_path
        return None

    def _collect_project_context(self) -> str:
        context = []
        context.append(f"项目根目录: {self.workspace_path}")
        context.append("")
        key_files = [
            "src/templates/index.html",
            "src/templates/base.html",
            "src/app.py",
            "src/models.py",
            "src/api.py"
        ]
        for key_file in key_files:
            file_path = self.workspace_path / key_file
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                preview = content[:500] + "..." if len(content) > 500 else content
                context.append(f"=== {key_file} ===")
                context.append(preview)
                context.append("")
        context.append("=== 项目文件列表 ===")
        for file_path in self.workspace_path.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                rel_path = file_path.relative_to(self.workspace_path)
                context.append(f"  - {rel_path}")
        return "\n".join(context)

    def _handle_modify_request(self, command: str):
        self.log_signal.emit(f"处理修改请求: {command}", "info")
        project_context = self._collect_project_context()
        analysis_prompt = f"""用户想要修改项目文件，请分析并返回需要修改的内容。

用户指令: {command}

【项目当前状态】
{project_context}

请输出JSON格式，格式如下：
{{
    "target_file": "要修改的文件名（如 index.html 或 style.css，只需要文件名，不需要路径）",
    "modification_type": "rewrite",
    "content_description": "要改成什么样子的详细描述",
    "explanation": "简要说明"
}}

只输出JSON，不要其他内容。"""

        try:
            response = self.planner.client.chat([
                {"role": "system", "content": "你是一个代码分析专家。分析用户需求，输出要修改的文件名和内容描述。"},
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

            file_path = self._find_file_by_name(target_file)
            if not file_path:
                self.log_signal.emit(f"找不到文件: {target_file}", "warning")
                self._wait_for_next_command()
                return

            self.log_signal.emit(f"找到文件: {file_path}", "success")
            old_content = file_path.read_text(encoding="utf-8")

            modify_prompt = f"""请根据用户要求修改文件。

文件路径: {file_path}
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

            rel_path = file_path.relative_to(self.workspace_path)
            self.diff_signal.emit(str(rel_path), old_content, new_content)

            # 保存绝对路径和新内容
            self.pending_modify_file_path = str(file_path)
            self.pending_modify_content = new_content

            self.ask_signal.emit(f"即将修改文件 {target_file}，是否确认？", ["确认修改", "取消"], {})
            self.waiting_for_response = True

        except Exception as e:
            self.log_signal.emit(f"处理失败: {str(e)}", "error")
            self._wait_for_next_command()

    def handle_modify_command(self, command: str):
        self._handle_modify_request(command)

    def _wait_for_next_command(self):
        self.ask_signal.emit("请输入下一个修改指令，或输入「结束」退出：", [], {"mode": "modify"})
        self.waiting_for_response = True

    def _clean_code(self, response: str) -> str:
        code = response.strip()
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]
        return code.strip()

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
            existing_files = self._get_existing_files_summary()
            code, success, error = self.coder.generate_code(step.description, file_path, existing_files)
            if not success:
                step.error = error
                return False
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
            return True
        except Exception as e:
            step.error = str(e)
            self.log_signal.emit(f"代码生成异常: {str(e)}", "error")
            return False

    def _execute_test_step(self, step: Step) -> bool:
        self.log_signal.emit(f"生成测试: {step.description}", "info")
        return True

    def _extract_file_path(self, description: str) -> str:
        match = re.search(r'([\w/]+\.py)', description)
        if match:
            return match.group(1)
        match = re.search(r'([\w/]+\.html)', description)
        if match:
            return match.group(1)
        match = re.search(r'([\w/]+\.css)', description)
        if match:
            return match.group(1)
        match = re.search(r'([\w/]+\.js)', description)
        if match:
            return match.group(1)
        return "src/step.py"

    def _get_existing_files_summary(self) -> List[Dict]:
        existing_files = []
        src_path = self.workspace_path / "src"
        if not src_path.exists():
            return existing_files
        for py_file in src_path.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            content, success, _ = self.coder.read_file(f"src/{py_file.name}")
            if success and content:
                provides = self._extract_provides(content)
                existing_files.append({
                    "path": f"src/{py_file.name}",
                    "provides": provides
                })
        return existing_files

    def _extract_provides(self, code: str) -> List[str]:
        provides = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    provides.append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    parent = getattr(node, 'parent', None)
                    if not parent or not isinstance(parent, ast.ClassDef):
                        provides.append(node.name)
        except:
            pass
        return provides

    def _check_dependencies(self, step: Step) -> bool:
        if not step.depends_on:
            return True
        for dep_id in step.depends_on:
            if not self.step_status_map.get(dep_id, False):
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
        print(f"data: {data}")

        self.user_response = response
        self.user_response_data = data
        self.waiting_for_response = False
        self.log_signal.emit(f"用户响应: {response}", "user")

        # 先判断 response 内容，不依赖 data 中的 mode
        if response == "确认修改":
            self.log_signal.emit("========== 开始覆盖文件 ==========", "info")
            self.log_signal.emit(f"文件路径: {self.pending_modify_file_path}", "info")
            self.log_signal.emit(f"内容长度: {len(self.pending_modify_content) if self.pending_modify_content else 0}",
                                 "info")

            if self.pending_modify_file_path and self.pending_modify_content:
                try:
                    path = Path(self.pending_modify_file_path)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(self.pending_modify_content, encoding="utf-8")
                    self.log_signal.emit(f"✅ 文件已覆盖: {path}", "success")
                    self.finished_signal.emit({"success": True, "refresh": True})
                except Exception as e:
                    self.log_signal.emit(f"❌ 保存失败: {str(e)}", "error")
                    self.finished_signal.emit({"success": False, "reason": str(e)})
            else:
                self.log_signal.emit("❌ 错误: pending_modify_file_path 或 pending_modify_content 为空", "error")

            self._wait_for_next_command()
            return

        if response == "结束":
            self.finished_signal.emit({"success": True, "completed": True})
            return

        if response == "取消":
            self._wait_for_next_command()
            return

        # 处理其他情况（如 data 中有 mode）
        if data and data.get("mode") == "modify":
            self.handle_modify_command(response)
        elif response == "确认执行":
            self.start_execution()
        elif response == "取消":
            self.finished_signal.emit({"success": False, "reason": "用户取消"})
        elif response == "修改计划":
            self.ask_signal.emit("请描述您想要修改的内容，例如：在步骤2后添加VIP功能", [], {"action": "modify_plan"})
            self.waiting_for_response = True
    def on_modify_feedback(self, feedback: str):
        self.modify_plan(feedback)