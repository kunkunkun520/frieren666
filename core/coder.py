"""
Coder 模块 - 代码生成与修正循环
"""

import re
import ast
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

from core.context_manager import ContextManager
from utils.llm_client import LLMClient


class Coder:
    def __init__(self, config: dict, workspace_path: Path):
        self.client = LLMClient(config)
        self.config = config
        self.workspace_path = workspace_path
        self.project_path = workspace_path / "project" if (workspace_path / "project").exists() else workspace_path
        self.max_attempts = 3

    # ========== 新方法：使用完整上下文生成 ==========

    def generate_code_with_context(self, task: str, file_path: str, full_context: str) -> Tuple[
        str, bool, Optional[str]]:
        """使用完整上下文生成代码"""

        system_prompt = """你是一个代码生成专家。只输出代码，不要有任何解释。
            不要用markdown代码块包裹，直接输出纯代码。
            代码要完整、可运行。
            严格遵守项目约定和已有模块的设计意图。

            ## 正确示例

            项目约定: FastAPI + SQLAlchemy，User 模型在 src/models/user.py
            任务: 创建认证服务

            正确输出:
            ```python
            from src.models.user import User
            from sqlalchemy.orm import Session

            class AuthService:
                def __init__(self, db: Session):
                    self.db = db

                def authenticate(self, username: str, password: str) -> User | None:
                    user = self.db.query(User).filter(User.username == username).first()
                    if user and user.verify_password(password):
                        return user
                    return None
            注意：正确导入了项目已有的 User 模型，使用了标准库，没有自创模块。
            from utils.logger import logger  # 错误：项目中不存在 utils.logger
            from models import User  # 错误：应该用完整路径 src.models.user
            import requests  # 错误：未在 AGENTS.md 中声明
            你必须严格遵守 AGENTS.md 中的「可用依赖」清单和「项目结构」。
        """
        prompt = f"""{full_context}
                请生成文件: {file_path}
                直接输出完整代码："""

        try:
            response = self.client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ])
            code = self._clean_code(response)

            # 语法检查
            if file_path.endswith('.py'):
                syntax_ok, syntax_error = self._check_syntax(code, file_path)
                if not syntax_ok:
                    return code, False, syntax_error

            return code, True, None
        except Exception as e:
            return "", False, str(e)

    # ========== 旧方法：保留但标记为废弃 ==========

    def generate_code(self, task: str, file_path: str, existing_files: List[Dict] = None) -> Tuple[
        str, bool, Optional[str]]:
        """生成代码 - 直接输出代码，不要JSON格式（已废弃，请使用 generate_code_with_context）"""
        existing_files = existing_files or []

        # 构建已有文件摘要
        existing_summary = self._format_existing_files(existing_files)

        system_prompt = """你是一个代码生成专家。只输出代码，不要有任何解释。
不要用markdown代码块包裹，直接输出纯代码。
代码要完整、可运行。
同一目录下使用相对导入: from .module import xxx"""

        prompt = f"""请生成文件: {file_path}
任务: {task}
已有代码文件:
{existing_summary if existing_summary else "暂无已有文件"}
请生成完整代码："""

        try:
            response = self.client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ])
            code = self._clean_code(response)

            # 语法检查
            if file_path.endswith('.py'):
                syntax_ok, syntax_error = self._check_syntax(code, file_path)
                if not syntax_ok:
                    return code, False, syntax_error

            return code, True, None
        except Exception as e:
            return "", False, str(e)

    def _format_existing_files(self, existing_files: List[Dict]) -> str:
        """格式化已有文件摘要（旧方法，保留兼容）"""
        if not existing_files:
            return ""
        lines = []
        for f in existing_files:
            path = f.get("path", "")
            provides = f.get("provides", [])
            if provides:
                lines.append(f"{path}: 提供 {', '.join(provides)}")
            else:
                lines.append(f"{path}: 已存在")
        return "\n".join(lines)

    # ========== 工具方法 ==========

    def _clean_code(self, response: str) -> str:
        """清理代码，去除markdown标记"""
        code = response.strip()
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```html" in code:
            code = code.split("```html")[1].split("```")[0]
        elif "```css" in code:
            code = code.split("```css")[1].split("```")[0]
        elif "```js" in code or "```javascript" in code:
            code = code.split("```js")[1].split("```")[0] if "```js" in code else \
            code.split("```javascript")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]
        return code.strip()

    def _check_syntax(self, code: str, file_path: str) -> Tuple[bool, Optional[str]]:
        """检查Python语法"""
        if not code:
            return False, "代码为空"
        if not file_path.endswith('.py'):
            return True, None
        try:
            compile(code, file_path, 'exec')
            return True, None
        except SyntaxError as e:
            return False, f"{str(e)} at line {e.lineno}"
        except Exception as e:
            return False, str(e)

    def write_file(self, file_path: str, content: str) -> Tuple[bool, Optional[str]]:
        """写入文件，支持绝对路径和相对路径"""
        try:
            path = Path(file_path)
            if path.is_absolute():
                full_path = path
            else:
                full_path = self.project_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            return True, None
        except Exception as e:
            return False, str(e)

    def read_file(self, file_path: str) -> Tuple[str, bool, Optional[str]]:
        """读取文件，支持绝对路径和相对路径"""
        try:
            path = Path(file_path)
            if path.is_absolute():
                full_path = path
            else:
                full_path = self.project_path / file_path

            if not full_path.exists():
                return "", False, f"文件不存在: {file_path}"
            content = full_path.read_text(encoding="utf-8")
            return content, True, None
        except Exception as e:
            return "", False, str(e)

    def extract_provides_from_code(self, code: str) -> List[str]:
        """提取代码中的导出符号（类名、函数名）"""
        provides = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    provides.append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    # 简单处理：顶层函数都算
                    provides.append(node.name)
        except:
            pass
        return provides

    def _validate_imports(self, code: str, file_path: str, context: ContextManager) -> tuple:
        """
        校验代码中的导入是否合法
        返回: (is_valid, invalid_imports, suggestions)
        """
        if not file_path.endswith('.py'):
            return True, [], []

        invalid_imports = []
        suggestions = []

        # 获取可用依赖清单
        agents_md = context.read_agents_md()
        allowed_deps = self._extract_allowed_deps(agents_md)

        # 获取项目中已有的模块
        existing_modules = self._get_existing_modules(context)

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # 检查 import xxx
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split('.')[0]
                        if module_name not in allowed_deps and module_name not in existing_modules:
                            # 排除 Python 标准库
                            if not self._is_stdlib(module_name):
                                invalid_imports.append(module_name)
                                suggestions.append(f"添加依赖: {module_name}")

                # 检查 from xxx import yyy
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split('.')[0]
                        if module_name not in allowed_deps and module_name not in existing_modules:
                            if not self._is_stdlib(module_name):
                                invalid_imports.append(module_name)
                                suggestions.append(f"添加依赖: {module_name}")
        except:
            # 语法错误时跳过校验
            pass

        return len(invalid_imports) == 0, invalid_imports, suggestions

    def _extract_allowed_deps(self, agents_md: str) -> set:
        """从 AGENTS.md 提取可用依赖"""
        deps = set()
        # 常见的标准库，默认允许
        stdlib = {'os', 'sys', 're', 'json', 'datetime', 'pathlib', 'typing', 'logging', 'time'}
        deps.update(stdlib)

        if not agents_md:
            return deps

        if "## 可用依赖" in agents_md:
            dep_section = agents_md.split("## 可用依赖")[1].split("##")[0]
            for line in dep_section.strip().split('\n'):
                line = line.strip().lstrip('-').strip()
                if line and not line.startswith('#'):
                    # 提取包名（去掉版本号）
                    pkg = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
                    deps.add(pkg)

        return deps

    def _get_existing_modules(self, context: ContextManager) -> set:
        """获取项目中已有的模块名"""
        modules = set()
        for file_path in context.file_index.get("files", {}).keys():
            if file_path.endswith('.py'):
                # 转换路径为模块名
                module = Path(file_path).stem
                modules.add(module)
                # 也添加完整路径作为模块名
                full_module = str(Path(file_path).with_suffix('')).replace('/', '.').replace('\\', '.')
                modules.add(full_module)
        return modules

    def _is_stdlib(self, module_name: str) -> bool:
        """检查是否是 Python 标准库"""
        stdlib_modules = {
            'os', 'sys', 're', 'json', 'datetime', 'pathlib', 'typing', 'logging', 'time',
            'math', 'random', 'collections', 'itertools', 'functools', 'io', 'csv',
            'hashlib', 'uuid', 'shutil', 'glob', 'subprocess', 'threading', 'asyncio',
            'unittest', 'pytest', 'argparse', 'configparser', 'dataclasses', 'enum',
            'abc', 'copy', 'pickle', 'sqlite3', 'urllib', 'http', 'xml', 'email'
        }

        return module_name in stdlib_modules