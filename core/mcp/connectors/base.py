"""
MCP 连接器基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseConnector(ABC):
    """连接器基类"""

    def __init__(self):
        self._connected = False
        self._server_info = {}

    @abstractmethod
    def connect(self, config: Dict[str, Any]) -> bool:
        """
        建立连接
        返回 True/False
        """
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        获取远程服务器的工具列表
        返回 [{name, description, parameters}, ...]
        """
        pass

    @abstractmethod
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用远程工具
        返回 {success, result/error}
        """
        pass

    def is_connected(self) -> bool:
        return self._connected

    def get_server_info(self) -> Dict[str, Any]:
        return self._server_info