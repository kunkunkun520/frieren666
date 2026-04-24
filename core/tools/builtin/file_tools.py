"""
文件操作工具
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from core.tools.base import BaseTool


class CreateFileTool(BaseTool):
    """创建新文件"""

    @property
    def name(self) -> str:
        return "create_file"

    @property
    def description(self) -> str:
        return "创建新文件。当用户要求「创建 xxx 文件」「新建 xxx」「生成一个 xxx 网页」时使用。注意：必须先分析项目结构，选择合适的目录。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径，相对于项目根目录。需要根据项目结构智能选择，如 HTML 放 templates/，Python 放 src/"
                },
                "content_description": {
                    "type": "string",
                    "description": "文件内容的描述，可以包含「需要读取 xxx 文件」来引用其他文件的内容"
                }
            },
            "required": ["file_path", "content_description"]
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        file_path = params.get("file_path")
        content_desc = params.get("content_description")

        if not file_path or not content_desc:
            return {"success": False, "error": "缺少必要参数: file_path 或 content_description"}

        worker = context.get("worker")
        coder = context.get("coder")
        context_manager = context.get("context_manager")
        workspace_path = context.get("workspace_path")

        # 如果 content_description 中包含「需要读取 xxx」，先读取那个文件
        import re
        read_match = re.search(r'需要读取\s+([^\s]+)', content_desc)
        if read_match:
            read_path = read_match.group(1)
            actual_path = self._find_file(workspace_path, read_path)
            if actual_path:
                try:
                    read_content = actual_path.read_text(encoding="utf-8")
                    content_desc = f"{content_desc}\n\n参考文件 {actual_path.relative_to(workspace_path)} 的内容:\n```\n{read_content[:1500]}\n```"
                except:
                    pass

        # 获取完整上下文
        full_context = context_manager.get_context_for_modify(
            f"创建文件: {file_path}\n内容要求: {content_desc}"
        )

        # 生成代码
        code, success, error = coder.generate_code_with_context(
            content_desc, file_path, full_context
        )

        if not success:
            return {"success": False, "error": f"代码生成失败: {error}"}

        # 写入文件
        full_path = workspace_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(code, encoding="utf-8")

        # 更新上下文
        worker.add_log(f"✅ 文件已创建: {file_path}", "success")

        return {
            "success": True,
            "result": f"文件已创建: {file_path}",
            "file_path": file_path,
            "content_preview": code[:500]
        }

    def _find_file(self, workspace_path: Path, pattern: str) -> Optional[Path]:
        """根据模糊名称查找文件"""
        pattern_lower = pattern.lower().replace('.py', '').replace('.html', '').replace('.js', '')
        for f in workspace_path.rglob("*"):
            if f.is_file() and pattern_lower in f.name.lower():
                return f
        return None
class ModifyFileTool(BaseTool):
    """修改已有文件"""

    @property
    def name(self) -> str:
        return "modify_file"

    @property
    def description(self) -> str:
        return "修改已有文件。当用户要求「修改 xxx 文件」「给 xxx 添加 yyy 功能」时使用。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要修改的文件路径"
                },
                "instruction": {
                    "type": "string",
                    "description": "修改指令，描述要如何修改"
                }
            },
            "required": ["file_path", "instruction"]
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        file_path = params.get("file_path")
        instruction = params.get("instruction")

        if not file_path or not instruction:
            return {"success": False, "error": "缺少必要参数"}

        worker = context.get("worker")
        coder = context.get("coder")
        context_manager = context.get("context_manager")
        workspace_path = context.get("workspace_path")

        full_path = workspace_path / file_path
        if not full_path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}

        try:
            old_content = full_path.read_text(encoding="utf-8")
            full_context = context_manager.get_context_for_modify(instruction)

            modify_prompt = f"""
{full_context}

文件路径: {file_path}
用户指令: {instruction}

当前代码:
{old_content}

请输出修改后的完整代码，不要用 markdown 包裹。
"""
            response = coder.client.chat([
                {"role": "system", "content": "你是代码修改专家，只输出修改后的完整代码。"},
                {"role": "user", "content": modify_prompt}
            ])

            new_content = worker._clean_code(response)

            # 显示 diff 并等待确认
            worker.diff_signal.emit(file_path, old_content, new_content)
            worker.pending_modify_file_path = str(full_path)
            worker.pending_modify_content = new_content

            return {
                "success": True,
                "result": "已生成修改预览，等待用户确认",
                "needs_confirmation": True,
                "file_path": file_path,
                "old_content": old_content[:500],
                "new_content": new_content[:500]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class ReadFileTool(BaseTool):
    """读取文件内容"""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取文件内容。当用户问「xxx 文件里有什么」「看一下 xxx」时使用。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要读取的文件路径，支持模糊匹配"
                }
            },
            "required": ["file_path"]
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        file_path = params.get("file_path")
        workspace_path = context.get("workspace_path")
        context_manager = context.get("context_manager")

        # 尝试精确匹配
        full_path = workspace_path / file_path
        if full_path.exists():
            try:
                content = full_path.read_text(encoding="utf-8")
                return {
                    "success": True,
                    "result": content[:5000] if len(content) > 5000 else content,
                    "file_path": file_path,
                    "truncated": len(content) > 5000
                }
            except Exception as e:
                return {"success": False, "error": str(e)}

        # 模糊搜索
        keyword = file_path.replace('.py', '').replace('.js', '').replace('/', ' ').replace('\\', ' ')
        matches = []
        for f in workspace_path.rglob("*"):
            if f.is_file() and keyword.lower() in f.name.lower():
                matches.append(str(f.relative_to(workspace_path)))

        if not matches:
            structure = context_manager.get_project_structure(workspace_path)
            return {
                "success": False,
                "error": f"找不到文件: {file_path}",
                "project_structure": structure
            }

        if len(matches) == 1:
            full_path = workspace_path / matches[0]
            content = full_path.read_text(encoding="utf-8")
            return {
                "success": True,
                "result": content[:5000] if len(content) > 5000 else content,
                "file_path": matches[0],
                "truncated": len(content) > 5000
            }

        return {
            "success": False,
            "error": f"找到多个匹配文件",
            "candidates": matches[:10]
        }


class ListFilesTool(BaseTool):
    """列出项目文件"""

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return "列出项目文件结构。当用户问「项目里有什么」「有哪些文件」时使用。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "要列出的目录，默认为项目根目录"
                },
                "pattern": {
                    "type": "string",
                    "description": "文件名匹配模式，如 *.py"
                }
            },
            "required": []
        }

    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        directory = params.get("directory", ".")
        pattern = params.get("pattern")
        workspace_path = context.get("workspace_path")
        context_manager = context.get("context_manager")

        structure = context_manager.get_project_structure(workspace_path)

        return {
            "success": True,
            "result": structure,
            "directory": directory

        }