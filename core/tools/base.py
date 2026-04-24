"""
工具基类 - 定义所有工具的抽象接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseTool(ABC):
    """所有工具的抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（唯一标识）"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（告诉 LLM 这个工具是干什么的）"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        工具参数定义（JSON Schema 格式）
        例如：
        {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"}
            },
            "required": ["file_path", "content"]
        }
        """
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        """
        执行工具
        返回：{"success": bool, "result": Any, "error": str}
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """转为字典，用于生成 Prompt"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    def validate_params(self, params: Dict[str, Any]) -> tuple:
        """
        校验参数
        返回: (is_valid, error_message)
        """
        schema = self.parameters
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # 检查必填参数
        for req in required:
            if req not in params or params[req] is None:
                return False, f"缺少必填参数: {req}"

        # 检查参数类型
        for key, value in params.items():
            if key in properties:
                expected_type = properties[key].get("type", "string")
                if expected_type == "string" and not isinstance(value, str):
                    return False, f"参数 {key} 应为字符串"
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    return False, f"参数 {key} 应为数字"
                elif expected_type == "boolean" and not isinstance(value, bool):
                    return False, f"参数 {key} 应为布尔值"
                elif expected_type == "object" and not isinstance(value, dict):
                    return False, f"参数 {key} 应为对象"
                elif expected_type == "array" and not isinstance(value, list):
                    return False, f"参数 {key} 应为数组"

        return True, None

    def execute_safe(self, params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        """带校验的执行"""
        is_valid, error = self.validate_params(params)
        if not is_valid:
            return {"success": False, "error": error}

        try:
            return self.execute(params, context)
        except Exception as e:
            return {"success": False, "error": f"工具执行异常: {str(e)}"}
    def __repr__(self):
        return f"<Tool: {self.name}>"


class ToolResult:
    """工具执行结果"""

    def __init__(self, success: bool, result: Any = None, error: str = None):
        self.success = success
        self.result = result
        self.error = error

    @classmethod
    def ok(cls, result: Any = None) -> "ToolResult":
        return cls(True, result=result)

    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        return cls(False, error=error)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error
        }