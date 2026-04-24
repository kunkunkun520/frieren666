"""
Agent 状态机
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


class AgentState(Enum):
    """Agent 状态"""
    IDLE = "idle"                          # 空闲，等待用户输入
    PLANNING = "planning"                  # 正在生成计划
    WAITING_CONFIRM = "waiting_confirm"    # 等待用户确认（计划/修改）
    EXECUTING = "executing"                # 正在执行步骤
    TOOL_EXECUTING = "tool_executing"      # 正在执行单个工具
    MODIFYING = "modifying"                # 执行中穿插修改
    PAUSED = "paused"                      # 用户暂停
    CANCELLED = "cancelled"                # 已取消


# 状态转换规则：当前状态 → 允许转换到的状态集合
ALLOWED_TRANSITIONS = {
    AgentState.IDLE: {
        AgentState.PLANNING,
        AgentState.TOOL_EXECUTING,
        AgentState.IDLE,
    },
    AgentState.PLANNING: {
        AgentState.WAITING_CONFIRM,
        AgentState.CANCELLED,
    },
    AgentState.WAITING_CONFIRM: {
        AgentState.EXECUTING,
        AgentState.PLANNING,
        AgentState.IDLE,
        AgentState.CANCELLED,
    },
    AgentState.EXECUTING: {
        AgentState.IDLE,
        AgentState.WAITING_CONFIRM,
        AgentState.MODIFYING,
        AgentState.PAUSED,
        AgentState.CANCELLED,
    },
    AgentState.TOOL_EXECUTING: {
        AgentState.IDLE,
    },
    AgentState.MODIFYING: {
        AgentState.EXECUTING,
        AgentState.IDLE,
        AgentState.CANCELLED,
    },
    AgentState.PAUSED: {
        AgentState.EXECUTING,
        AgentState.CANCELLED,
    },
    AgentState.CANCELLED: {
        AgentState.IDLE,
    },
}


@dataclass
class AgentContext:
    """Agent 上下文数据"""
    state: AgentState = AgentState.IDLE
    user_task: str = ""
    steps: List[Any] = field(default_factory=list)
    current_step_index: int = 0
    step_status_map: Dict[int, bool] = field(default_factory=dict)
    pending_tool_name: str = ""
    pending_tool_params: dict = field(default_factory=dict)
    pending_question: str = ""
    pending_options: list = field(default_factory=list)
    pending_action: str = ""


class StateMachine:
    """状态机管理器"""

    def __init__(self):
        self._state = AgentState.IDLE
        self._listeners = []

    @property
    def state(self) -> AgentState:
        return self._state

    def can_transition(self, new_state: AgentState) -> bool:
        """检查是否可以转换到新状态"""
        return new_state in ALLOWED_TRANSITIONS.get(self._state, set())

    def transition_to(self, new_state: AgentState, reason: str = "") -> bool:
        """执行状态转换，返回是否成功"""
        if not self.can_transition(new_state):
            print(f"❌ 非法状态转换: {self._state.value} → {new_state.value}")
            return False

        old_state = self._state
        self._state = new_state
        msg = f"状态转换: {old_state.value} → {new_state.value}"
        if reason:
            msg += f" ({reason})"
        print(msg)

        for listener in self._listeners:
            listener(old_state, new_state, reason)

        return True

    def on_transition(self, callback):
        """注册状态转换监听器"""
        self._listeners.append(callback)

    def force_transition(self, new_state: AgentState):
        """强制转换（跳过规则检查，用于特殊情况）"""
        self._state = new_state

    def is_idle(self) -> bool:
        return self._state == AgentState.IDLE

    def is_executing(self) -> bool:
        return self._state == AgentState.EXECUTING

    def is_planning(self) -> bool:
        return self._state == AgentState.PLANNING

    def is_waiting(self) -> bool:

        return self._state == AgentState.WAITING_CONFIRM