"""
示例本地 MCP 工具
"""

def get_tools():
    """返回工具列表"""
    return [
        {
            "name": "calculate",
            "description": "执行数学计算",
            "parameters": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，如 2+3*4"
                }
            },
            "handler": calculate
        },
        {
            "name": "get_current_time",
            "description": "获取当前时间",
            "parameters": {},
            "handler": get_time
        }
    ]


def calculate(params):
    """计算处理器"""
    expression = params.get("expression", "")
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_time(params):
    """获取当前时间"""
    from datetime import datetime
    return {
        "success": True,
        "result": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }