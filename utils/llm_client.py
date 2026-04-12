"""
统一的 LLM 客户端
支持 Ollama、OpenAI、Anthropic 等
"""

import requests
import json
from typing import List, Dict, Any, Optional


class LLMClient:
    """统一的 LLM 客户端接口"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("provider", "ollama")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """发送聊天请求，返回响应内容"""
        temperature = kwargs.get("temperature", self.config.get("temperature", 0.7))
        max_tokens = kwargs.get("max_tokens", self.config.get("max_tokens", 4096))

        if self.provider == "ollama":
            return self._chat_ollama(messages, temperature, max_tokens)
        elif self.provider in ["openai", "openai_compatible"]:
            return self._chat_openai(messages, temperature, max_tokens)
        elif self.provider == "anthropic":
            return self._chat_anthropic(messages, temperature, max_tokens)
        else:
            raise ValueError(f"不支持的提供商: {self.provider}")

    def _chat_ollama(self, messages, temperature, max_tokens) -> str:
        """Ollama API 调用"""
        base_url = self.config.get("base_url", "http://localhost:11434")
        url = base_url.rstrip('/') + "/api/chat"

        payload = {
            "model": self.config.get("model_name", "qwen3-coder:30b"),
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result["message"]["content"]
        except requests.exceptions.ConnectionError:
            raise Exception(f"无法连接到 Ollama 服务，请确保 Ollama 正在运行: {url}")
        except requests.exceptions.Timeout:
            raise Exception("Ollama 请求超时")
        except Exception as e:
            raise Exception(f"Ollama 调用失败: {str(e)}")

    def _chat_openai(self, messages, temperature, max_tokens) -> str:
        """OpenAI 兼容 API 调用"""
        base_url = self.config.get("base_url", "https://api.openai.com/v1")
        url = base_url.rstrip('/') + "/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.config.get('api_key', '')}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.get("model_name", "gpt-4-turbo"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise Exception(f"OpenAI API 调用失败: {str(e)}")

    def _chat_anthropic(self, messages, temperature, max_tokens) -> str:
        """Anthropic API 调用"""
        system = ""
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.config.get("api_key", ""),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.get("model_name", "claude-3-opus-20240229"),
            "system": system,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            return response.json()["content"][0]["text"]
        except Exception as e:
            raise Exception(f"Anthropic API 调用失败: {str(e)}")

    def test_connection(self) -> tuple:
        """测试连接"""
        model_name = self.config.get("model_name", "")

        if not model_name:
            return False, "请先在设置中选择模型"

        try:
            if self.provider == "ollama":
                base_url = self.config.get("base_url", "http://localhost:11434")
                url = base_url.rstrip('/') + "/api/tags"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    models = [m["name"] for m in response.json().get("models", [])]
                    if model_name in models:
                        return True, f"模型 {model_name} 可用"
                    else:
                        return False, f"模型 {model_name} 未安装，请运行 ollama pull {model_name}"
                else:
                    return False, f"HTTP {response.status_code}"
            elif self.provider in ["openai", "openai_compatible"]:
                base_url = self.config.get("base_url", "https://api.openai.com/v1")
                url = base_url.rstrip('/') + "/models"
                headers = {"Authorization": f"Bearer {self.config.get('api_key', '')}"}
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    return True, "连接成功"
                else:
                    return False, f"HTTP {response.status_code}"
            elif self.provider == "anthropic":
                url = "https://api.anthropic.com/v1/models"
                headers = {"x-api-key": self.config.get("api_key", "")}
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    return True, "连接成功"
                else:
                    return False, f"HTTP {response.status_code}"
            else:
                return False, f"未知提供商: {self.provider}"
        except requests.exceptions.ConnectionError:
            return False, "无法连接，请检查服务是否运行"
        except requests.exceptions.Timeout:
            return False, "连接超时"
        except Exception as e:
            return False, str(e)