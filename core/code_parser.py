"""
代码解析器 - 提取文件中的类、函数、方法信息
（改造后：降级为辅助工具，主要用于扫描目录结构）
"""

import ast
from typing import Dict, List, Any, Optional
from pathlib import Path


class CodeParser:
    """解析Python代码，提取结构和导出信息（辅助用）"""

    @staticmethod
    def parse_file(file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            return {"error": "文件不存在", "classes": [], "functions": [], "methods": []}

        try:
            content = file_path.read_text(encoding="utf-8")
            return CodeParser.parse_code(content, str(file_path))
        except Exception as e:
            return {"error": str(e), "classes": [], "functions": [], "methods": []}

    @staticmethod
    def parse_code(code: str, file_path: str = "") -> Dict[str, Any]:
        result = {
            "file_path": file_path,
            "module_name": CodeParser._get_module_name(file_path),
            "classes": [],
            "functions": [],
            "methods": [],
            "imports": []
        }

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "type": "class",
                        "methods": [],
                        "docstring": ast.get_docstring(node)
                    }
                    for body_node in node.body:
                        if isinstance(body_node, ast.FunctionDef):
                            class_info["methods"].append({
                                "name": body_node.name,
                                "params": [arg.arg for arg in body_node.args.args]
                            })
                    result["classes"].append(class_info)

                elif isinstance(node, ast.FunctionDef):
                    result["functions"].append({
                        "name": node.name,
                        "type": "function",
                        "params": [arg.arg for arg in node.args.args],
                        "docstring": ast.get_docstring(node)
                    })

                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        result["imports"].append({
                            "type": "import",
                            "module": alias.name
                        })
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        result["imports"].append({
                            "type": "from_import",
                            "module": node.module,
                            "name": alias.name,
                            "level": node.level
                        })

            return result
        except SyntaxError as e:
            return {"error": f"语法错误: {str(e)}", "classes": [], "functions": [], "methods": []}

    @staticmethod
    def _get_module_name(file_path: str) -> str:
        if not file_path:
            return ""
        try:
            path = Path(file_path)
            return path.stem
        except Exception:
            return ""

    @staticmethod
    def generate_index(project_path: Path) -> Dict[str, Any]:
        index = {"files": {}, "exports": []}

        src_path = project_path / "src"
        if not src_path.exists():
            src_path = project_path

        for py_file in src_path.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue

            try:
                file_info = CodeParser.parse_file(py_file)
                module_name = file_info.get("module_name", py_file.stem)
                file_info["module_name"] = module_name
                rel_path = str(py_file.relative_to(project_path))
                index["files"][rel_path] = file_info

                for cls in file_info.get("classes", []):
                    index["exports"].append({
                        "name": cls["name"],
                        "type": "class",
                        "module": module_name,
                        "file": rel_path,
                        "methods": cls.get("methods", [])
                    })

                for func in file_info.get("functions", []):
                    index["exports"].append({
                        "name": func["name"],
                        "type": "function",
                        "module": module_name,
                        "file": rel_path
                    })

            except Exception as e:
                print(f"解析文件失败 {py_file}: {e}")
                continue

        return index

    @staticmethod
    def format_index_for_prompt(index: Dict[str, Any]) -> str:
        if not index.get("exports"):
            return "暂无已有代码文件。"

        lines = ["## 已有代码文件及导出内容\n"]
        lines.append("注意：")
        lines.append("- 类中的方法是类的成员，不能单独导入，必须通过类实例调用")
        lines.append("- 正确用法：from module import ClassName -> 然后 ClassName.method()")
        lines.append("- 错误用法：from module import method_name（如果method是类的方法）\n")

        by_module = {}
        for exp in index["exports"]:
            module = exp["module"]
            if module not in by_module:
                by_module[module] = []
            by_module[module].append(exp)

        for module_name, exports in by_module.items():
            lines.append(f"### 文件: {exports[0]['file']}")
            lines.append(f"模块名: {module_name}")
            lines.append("导出内容：")

            for exp in exports:
                if exp["type"] == "class":
                    methods = exp.get("methods", [])
                    if methods:
                        method_names = [m["name"] for m in methods]
                        lines.append(f"  📦 类: {exp['name']}")
                        lines.append(f"      方法: {', '.join(method_names)}")
                        lines.append(f"      导入方式: from {module_name} import {exp['name']}")
                        lines.append(f"      使用方式: instance = {exp['name']}(); instance.method_name()")
                    else:
                        lines.append(f"  📦 类: {exp['name']}")
                        lines.append(f"      导入方式: from {module_name} import {exp['name']}")
                else:
                    lines.append(f"  🔧 函数: {exp['name']}")
                    lines.append(f"      导入方式: from {module_name} import {exp['name']}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def scan_directory(project_path: Path) -> List[str]:
        files = []
        if not project_path.exists():
            return files

        for item in project_path.rglob("*"):
            if item.is_file() and not item.name.startswith('.') and item.name != '__pycache__':
                rel_path = str(item.relative_to(project_path))
                files.append(rel_path)

        return sorted(files)