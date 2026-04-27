"""
Embedding 模型封装
支持 Ollama、OpenAI、自定义 API
"""

import requests
from typing import List, Optional
from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """Embedding 基类"""

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """将文本列表转为向量列表"""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """将单个查询文本转为向量"""
        pass


class OllamaEmbedder(BaseEmbedder):
    """Ollama 本地 Embedding"""

    def __init__(self, model_name: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url.rstrip('/')

    def embed(self, texts: List[str]) -> List[List[float]]:
        url = f"{self.base_url}/api/embed"
        embeddings = []

        for text in texts:
            try:
                response = requests.post(url, json={
                    "model": self.model_name,
                    "input": text
                }, timeout=30)
                response.raise_for_status()
                data = response.json()
                embeddings.append(data["embeddings"][0])
            except Exception as e:
                print(f"Embedding 失败: {e}")
                embeddings.append([0.0] * 768)  # 降级返回零向量

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        result = self.embed([text])
        return result[0] if result else [0.0] * 768


class OpenAICompatibleEmbedder(BaseEmbedder):
    """OpenAI 兼容 API Embedding"""

    def __init__(self, model_name: str, base_url: str, api_key: str = ""):
        self.model_name = model_name
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def embed(self, texts: List[str]) -> List[List[float]]:
        url = f"{self.base_url}/embeddings"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = requests.post(url, json={
                "model": self.model_name,
                "input": texts
            }, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # 按索引排序
            embeddings = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in embeddings]
        except Exception as e:
            print(f"Embedding 失败: {e}")
            return [[0.0] * 1536 for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        result = self.embed([text])
        return result[0] if result else [0.0] * 1536


class EmbedderFactory:
    """Embedding 工厂"""

    @staticmethod
    def create(config: dict) -> BaseEmbedder:
        """根据配置创建 Embedder"""
        provider = config.get("embedding_provider", "ollama")

        if provider == "ollama":
            return OllamaEmbedder(
                model_name=config.get("embedding_model", "nomic-embed-text"),
                base_url=config.get("embedding_base_url", "http://localhost:11434")
            )
        elif provider in ["openai", "openai_compatible"]:
            return OpenAICompatibleEmbedder(
                model_name=config.get("embedding_model", "text-embedding-3-small"),
                base_url=config.get("embedding_base_url", "https://api.openai.com/v1"),
                api_key=config.get("embedding_api_key", "")
            )
        else:
            # 默认使用 Ollama
            return OllamaEmbedder()

    @staticmethod
    def get_available_embedding_models(provider: str, base_url: str, api_key: str = "") -> List[str]:
        """获取可用的 Embedding 模型列表"""
        if provider == "ollama":
            try:
                url = base_url.rstrip('/') + "/api/tags"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    models = [m["name"] for m in response.json().get("models", [])]
                    # 过滤出 embedding 模型
                    embedding_models = [m for m in models if "embed" in m.lower() or "nomic" in m.lower()]
                    return embedding_models if embedding_models else models
            except:
                pass
            return ["nomic-embed-text", "all-minilm"]

        elif provider in ["openai", "openai_compatible"]:
            return [
                "text-embedding-3-small",
                "text-embedding-3-large",
                "text-embedding-ada-002"
            ]

        return ["nomic-embed-text"]