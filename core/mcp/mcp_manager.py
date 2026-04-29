"""
MCP 管理器
负责加载、管理所有 MCP 服务
支持按 target_agent 分配到不同的 ToolRegistry
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

from core.mcp.connectors.streamable_http import StreamableHttpConnector
from core.mcp.connectors.local import LocalConnector
from core.mcp.connectors.mcp_tool import MCPToolAdapter
from core.tools import ToolRegistry


class MCPManager:
    """MCP 管理器"""

    def __init__(self, config_dir: Path = None, registries: Dict[str, ToolRegistry] = None):
        """
        config_dir: MCP 配置目录
        registries: {"chat": ToolRegistry, "coder": ToolRegistry, "planner": ToolRegistry}
        """
        self.config_dir = config_dir or Path("extensions/mcp_servers")
        self.registries = registries or {}
        self.connectors: Dict[str, Any] = {}
        self.adapters: Dict[str, MCPToolAdapter] = {}
        self._loaded = False

    def load_all(self) -> int:
        """加载所有 MCP 配置"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
            return 0

        count = 0

        # 加载 JSON 配置文件
        for config_file in sorted(self.config_dir.glob("*.json")):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if self._load_from_config(config):
                    count += 1
            except Exception as e:
                print(f"MCP 配置加载失败: {config_file.name} - {e}")

        # 加载本地 Python 模块
        for py_file in sorted(self.config_dir.glob("*.py")):
            if py_file.name.startswith("__") or py_file.name.startswith("example"):
                continue
            try:
                config = {
                    "name": py_file.stem,
                    "description": f"本地工具: {py_file.stem}",
                    "type": "local",
                    "target_agent": "chat",
                    "config": {"module_path": str(py_file)}
                }
                if self._load_from_config(config):
                    count += 1
            except Exception as e:
                print(f"本地 MCP 模块加载失败: {py_file.name} - {e}")

        self._loaded = True
        return count

    def _load_from_config(self, config: Dict[str, Any]) -> bool:
        """从配置字典加载 MCP 服务"""
        service_type = config.get("type", "streamable_http")
        service_name = config.get("name", "unnamed")
        target_agent = config.get("target_agent", "chat")
        connector_config = config.get("config", {})

        # 检查是否已加载
        if service_name in self.connectors:
            print(f"MCP 服务已存在: {service_name}")
            return False

        # 获取目标注册表
        target_registry = self.registries.get(target_agent)
        if target_registry is None:
            # 如果指定的 agent 不存在，默认注册到 chat
            target_registry = self.registries.get("chat")
            if target_registry is None:
                print(f"没有可用的 ToolRegistry，跳过: {service_name}")
                return False

        # 创建连接器
        if service_type == "streamable_http":
            connector = StreamableHttpConnector()
        elif service_type == "local":
            connector = LocalConnector()
        else:
            print(f"不支持的 MCP 类型: {service_type}")
            return False

        # 建立连接
        if not connector.connect(connector_config):
            print(f"MCP 服务连接失败: {service_name}")
            return False

        self.connectors[service_name] = connector

        # 获取工具列表
        tools = connector.list_tools()
        registered_count = 0

        for tool_config in tools:
            tool_name = tool_config.get("name", "")
            if not tool_name:
                continue

            # 构建带前缀的工具名，避免命名冲突
            prefixed_name = f"mcp_{service_name}__{tool_name}"

            # 创建适配器并注册到目标 Registry
            adapter = MCPToolAdapter(tool_name, tool_config, connector)

            # 修改适配器的 name 属性，使用带前缀的名字
            adapter._name = prefixed_name

            target_registry.register(adapter)
            self.adapters[prefixed_name] = adapter
            registered_count += 1

        if registered_count > 0:
            print(f"✅ MCP 服务 '{service_name}' → Agent '{target_agent}': 注册了 {registered_count} 个工具")
        else:
            print(f"⚠️ MCP 服务 '{service_name}' 没有提供任何工具")

        return True

    def unload_all(self):
        """卸载所有 MCP 服务"""
        # 从所有注册表中移除
        for name in list(self.adapters.keys()):
            for registry in self.registries.values():
                try:
                    registry.unregister(name)
                except:
                    pass

        # 断开所有连接
        for connector in self.connectors.values():
            connector.disconnect()

        self.connectors.clear()
        self.adapters.clear()
        self._loaded = False

    def reload_all(self) -> int:
        """重新加载所有 MCP 服务"""
        self.unload_all()
        return self.load_all()

    def get_status(self) -> list:
        """获取所有 MCP 服务状态"""
        return [
            {
                "name": name,
                "connected": conn.is_connected(),
                "tools_count": len(conn.list_tools()),
                "server_info": conn.get_server_info()
            }
            for name, conn in self.connectors.items()
        ]

    def get_registered_tools_by_agent(self) -> Dict[str, list]:
        """按 Agent 分组获取已注册的 MCP 工具"""
        result = {}
        for agent_name, registry in self.registries.items():
            mcp_tools = [t for t in registry.list_all() if t.name.startswith("mcp_")]
            result[agent_name] = [t.name for t in mcp_tools]
        return result

    def is_loaded(self) -> bool:
        return self._loaded