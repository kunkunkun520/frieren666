
import json
import ast
from typing import Dict, Any, Optional, Tuple
from utils.llm_client import LLMClient

JUDGE_SYSTEM_PROMPT = """你是一个严格的代码评审专家，给代码打分（0-100分）。评分标准：正确性（40分）：代码逻辑是否正确，是否能完成预期功能。可读性（20分）：变量命名是否清晰，代码结构是否合理。健壮性（20分）：错误处理是否完善，边界条件是否考虑。注释质量（20分）：关键逻辑是否有注释，注释是否清晰。输出格式（必须是纯JSON）：{"score": 85, "breakdown": {"correctness": 35, "readability": 18, "robustness": 16, "documentation": 16}, "issues": ["问题1", "问题2"], "suggestions": ["建议1", "建议2"]}"""

class Judge:
    def __init__(self, config: dict):
        self.client = LLMClient(config)
        self.config = config
    def score_code(self, code: str, task: str = "", test_result: dict = None) -> Tuple[int, dict]:
        test_info = ""
        if test_result:
            if test_result.get("passed"):
                test_info = "测试结果: 通过\n"
            else:
                test_info = f"测试结果: 失败\n错误信息: {test_result.get('error', '未知错误')}\n"
        prompt = f"任务描述: {task}\n{test_info}\n代码:\n```python\n{code}\n```\n请对上述代码进行评分。"
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        try:
            response = self.client.chat(messages)
            result = self._parse_response(response)
            score = result.get("score", 0)
            if test_result and not test_result.get("passed"):
                score = max(0, score - 30)
            return score, result
        except Exception as e:
            return 0, {"error": str(e), "score": 0}
    def _parse_response(self, response: str) -> dict:
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"score": 60, "issues": ["解析失败"], "suggestions": ["请检查代码"], "breakdown": {}}
    def quick_check(self, code: str) -> Tuple[bool, str]:
        try:
            ast.parse(code)
            return True, "语法正确"
        except SyntaxError as e:
            return False, str(e)
    def suggest_improvements(self, code: str, score: int, issues: list) -> str:
        if score >= 80:
            return "代码质量良好，可以接受"
        prompt = f"代码评分: {score}/100\n问题: {', '.join(issues)}\n代码:\n```python\n{code}\n```\n请给出3条具体的改进建议。"
        messages = [
            {"role": "system", "content": "你是代码优化专家，给出具体的改进建议。"},
            {"role": "user", "content": prompt}
        ]
        try:
            response = self.client.chat(messages)
            return response.strip()
        except Exception:
            return "请检查代码逻辑和错误处理"