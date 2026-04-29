"""
Streamable HTTP 连接器 - 支持 MCP Session ID
"""

import json
import requests
from typing import Dict, Any, List
from core.mcp.connectors.base import BaseConnector


class StreamableHttpConnector(BaseConnector):
    """MCP Streamable HTTP 连接器"""

    def __init__(self):
        super().__init__()
        self.url = ""
        self.headers = {}
        self._request_id = 0
        self._tools_cache = []
        self._session_id = None

    def connect(self, config: Dict[str, Any]) -> bool:
        """建立与 MCP 服务器的连接"""
        self.url = config.get("url", "").rstrip('/')
        self.headers = config.get("headers", {})
        self.headers["Content-Type"] = "application/json"
        self.headers["Accept"] = "application/json, text/event-stream"  # ← 加这行
        if not self.url:
            return False

        try:
            # 第一步：发送 initialize 请求获取 session ID
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "archon",
                        "version": "1.0.0"
                    }
                }
            }

            response = requests.post(
                self.url,
                json=init_payload,
                headers=self.headers,
                timeout=30
            )

            # 从响应头获取 session ID
            self._session_id = response.headers.get("mcp-session-id")
            print(f"获取到 session ID: {self._session_id}")

            if response.status_code >= 400:
                # 检查是否返回了 session ID
                if not self._session_id:
                    print(f"initialize 失败: {response.status_code} {response.text[:200]}")
                    return False

            # 解析 initialize 响应
            try:
                result = response.json()
                self._server_info = result.get("result", {})
            except:
                pass

            self._connected = True

            # 第二步：发送 initialized 通知
            if self._session_id:
                self._send_notification("notifications/initialized", {})

            # 第三步：获取工具列表
            try:
                tools_response = self._send_request("tools/list", {})
                if not tools_response.get("error"):
                    self._tools_cache = tools_response.get("result", {}).get("tools", [])
                    print(f"获取到 {len(self._tools_cache)} 个工具")
                    for tool in self._tools_cache:
                        print(f"  - {tool.get('name', 'unknown')}: {tool.get('description', '')[:50]}")
            except Exception as e:
                print(f"tools/list 失败: {e}")

            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        self._connected = False
        self._tools_cache = []
        self._session_id = None

    def list_tools(self) -> List[Dict[str, Any]]:
        """获取远程工具列表"""
        if not self._connected:
            return []

        try:
            tools_response = self._send_request("tools/list", {})
            if not tools_response.get("error"):
                self._tools_cache = tools_response.get("result", {}).get("tools", [])
        except:
            pass

        return self._tools_cache

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用远程工具"""
        if not self._connected:
            return {"success": False, "error": "未连接到 MCP 服务器"}

        try:
            response = self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })

            if response.get("error"):
                return {
                    "success": False,
                    "error": response["error"].get("message", "未知错误")
                }

            result = response.get("result", {})
            content = result.get("content", [])

            text_parts = []
            for item in content:
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))

            return {
                "success": True,
                "result": "\n".join(text_parts) if text_parts else result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """发送 JSON-RPC 2.0 请求"""
        self._request_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params
        }

        headers = self.headers.copy()
        headers["Accept"] = "application/json, text/event-stream"  # ← 加这行

        if self._session_id:
            headers["mcp-session-id"] = self._session_id

        response = requests.post(
            self.url,
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        return response.json()

    def _send_notification(self, method: str, params: Dict[str, Any]):
        """发送 JSON-RPC 2.0 通知（无 id）"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }

        headers = self.headers.copy()
        if self._session_id:
            headers["mcp-session-id"] = self._session_id

        try:
            requests.post(self.url, json=payload, headers=headers, timeout=30)
        except:
            pass