"""
RAG 管理器
使用 ChromaDB 作为向量数据库
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
from pathlib import Path

from core.rag.embedder import EmbedderFactory, BaseEmbedder
from core.rag.document_loader import DocumentLoader


class RAGManager:
    """RAG 管理器"""

    def __init__(self, workspace_path: Path, config: dict, context_manager=None):
        self.workspace_path = workspace_path
        self.config = config
        self.context = context_manager

        # Embedding 模型
        self.embedder = EmbedderFactory.create(config)

        # ChromaDB 客户端
        chroma_path = str(workspace_path / ".chroma_db")
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)

        # 获取或创建 collection
        try:
            self.collection = self.chroma_client.get_collection("archon_memory")
        except:
            self.collection = self.chroma_client.create_collection(
                name="archon_memory",
                metadata={"hnsw:space": "cosine"}
            )

        self.index_built = self.collection.count() > 0
        self.document_loader = DocumentLoader(workspace_path, context_manager)

    def build_index(self, force: bool = False):
        """建立索引"""
        if self.index_built and not force:
            print(f"索引已存在 ({self.collection.count()} 条记录)")
            return

        # 清空旧索引
        if force:
            self.chroma_client.delete_collection("archon_memory")
            self.collection = self.chroma_client.create_collection(
                name="archon_memory",
                metadata={"hnsw:space": "cosine"}
            )

        # 加载文档
        documents = self.document_loader.load_all()
        print(f"加载了 {len(documents)} 个文档")

        if not documents:
            return

        # 分批处理
        batch_size = 10
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            texts = [doc["content"] for doc in batch]
            embeddings = self.embedder.embed(texts)

            ids = [f"doc_{i + j}" for j in range(len(batch))]
            metadatas = [
                {
                    "source": doc.get("source", ""),
                    "type": doc.get("type", ""),
                    "timestamp": doc.get("timestamp", "")
                }
                for doc in batch
            ]

            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )

        self.index_built = True
        print(f"索引构建完成，共 {self.collection.count()} 条记录")

    def search(self, query: str, top_k: int = 5, filter_type: str = None) -> List[Dict]:
        """检索最相关的片段"""
        if not self.index_built:
            return []

        query_embedding = self.embedder.embed_query(query)

        where_filter = None
        if filter_type:
            where_filter = {"type": filter_type}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        formatted = []
        if results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                formatted.append({
                    "content": results["documents"][0][i],
                    "source": results["metadatas"][0][i].get("source", ""),
                    "type": results["metadatas"][0][i].get("type", ""),
                    "score": 1 - results["distances"][0][i] if results["distances"] else 0
                })

        return formatted

    def add_document(self, content: str, source: str, doc_type: str, timestamp: str = ""):
        """增量添加文档"""
        embedding = self.embedder.embed_query(content)

        doc_id = f"doc_{self.collection.count()}"
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{
                "source": source,
                "type": doc_type,
                "timestamp": timestamp
            }]
        )

    def search_formatted(self, query: str, top_k: int = 5) -> str:
        """检索并格式化为 Prompt 可用文本"""
        results = self.search(query, top_k)
        if not results:
            return ""

        lines = ["## 相关历史记录（RAG 检索）"]
        for i, r in enumerate(results):
            lines.append(f"\n### 相关片段 {i + 1} [{r['type']}] (来源: {r['source']})")
            lines.append(r["content"][:500])

        return "\n".join(lines)

    def get_stats(self) -> Dict:
        """获取索引统计"""
        return {
            "total_documents": self.collection.count(),
            "index_built": self.index_built,
            "embedding_model": self.config.get("embedding_model", "unknown")
        }