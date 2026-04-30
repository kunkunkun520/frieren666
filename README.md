# ✨ Archon - AI 编程助手
> 让 AI 像资深工程师一样工作 —— 一个支持多模型、多工具、可扩展的 AI 编程助手桌面应用。
## 📖 项目简介

Archon 是一个基于 PySide6 构建的桌面端 AI 编程助手，核心理念是**状态驱动的执行循环**。它能够根据用户的自然语言需求，自动完成项目规划、代码生成、文件修改、影响分析等全流程工作。

### 核心特性

- 🧠 **多模型支持**：兼容 Ollama、OpenAI、Anthropic 等多种 LLM 提供商
- 🔄 **状态机架构**：基于状态机的执行循环，支持规划、执行、修改、暂停等多状态切换
- 🛠️ **工具系统**：内置 10+ 工具（创建/修改/读取文件、任务控制、记忆检索等），支持 MCP 和 Skill 扩展
- 📝 **对话式初始化**：通过多轮对话确定项目约定（AGENTS.md），确保代码生成符合预期
- 🔍 **影响分析**：修改文件后自动分析对其他文件的连锁影响并批量更新
- 📚 **RAG 记忆系统**：基于 ChromaDB 的向量检索，跨会话记忆项目进展和关键决策
- 🎨 **深色主题 UI**：三栏布局（文件树 + 代码预览 + 对话区），支持代码编辑和差异对比

---

## 🏗️ 架构设计

### 整体架构

## 状态定义

| 状态 | 枚举值 | 说明 | 允许的用户操作 |
|------|--------|------|---------------|
| **IDLE** | `idle` | 空闲，等待用户输入 | 新建任务、修改文件、聊天、恢复执行 |
| **PLANNING** | `planning` | 正在生成任务计划 | 等待（不可操作） |
| **WAITING_CONFIRM** | `waiting_confirm` | 等待用户确认计划或修改 | 确认执行、修改计划、取消 |
| **EXECUTING** | `executing` | 正在按计划逐步执行 | 暂停、聊天提问、穿插修改文件 |
| **TOOL_EXECUTING** | `tool_executing` | 正在执行单个工具 | 等待（不可操作） |
| **MODIFYING** | `modifying` | 执行任务期间，用户要求修改文件 | 等待修改完成 |
| **PAUSED** | `paused` | 用户手动暂停 | 恢复执行、取消 |
| **CANCELLED** | `cancelled` | 用户取消任务 | 新建任务、修改文件、聊天 |

## 转换规则表

| 当前状态 | 触发事件 | 新状态 | 说明 |
|----------|----------|--------|------|
| IDLE | 用户输入新任务 | PLANNING | 开始规划流程 |
| IDLE | 用户输入修改指令 | TOOL_EXECUTING | 直接执行修改工具 |
| IDLE | 用户聊天/询问 | IDLE | 纯聊天，不改变状态 |
| IDLE | 用户说"继续"/"恢复" | EXECUTING | 恢复未完成的任务 |
| PLANNING | 计划生成成功 | WAITING_CONFIRM | 等待用户确认 |
| PLANNING | 计划生成失败 | IDLE | 回到空闲 |
| WAITING_CONFIRM | 用户点击"确认执行" | EXECUTING | 开始执行步骤 |
| WAITING_CONFIRM | 用户点击"修改计划" | PLANNING | 重新规划 |
| WAITING_CONFIRM | 用户点击"取消" | IDLE | 回到空闲 |
| EXECUTING | 当前 Step 执行成功，还有剩余 | EXECUTING | 继续下一个 Step |
| EXECUTING | 所有 Step 执行完成 | IDLE | 任务完成 |
| EXECUTING | Step 执行失败 | WAITING_CONFIRM | 询问用户是否继续 |
| EXECUTING | 用户要求修改文件 | MODIFYING | 暂停执行，先修改 |
| EXECUTING | 用户暂停 | PAUSED | 暂停执行 |
| EXECUTING | 用户聊天/提问 | EXECUTING | 不改变状态，异步回答 |
| TOOL_EXECUTING | 工具执行成功 | IDLE | 回到空闲 |
| TOOL_EXECUTING | 工具执行失败 | IDLE | 回到空闲，显示错误 |
| MODIFYING | 修改完成 | EXECUTING | 恢复执行 |
| PAUSED | 用户恢复 | EXECUTING | 继续执行 |
| PAUSED | 用户取消 | CANCELLED | 取消任务 |
| CANCELLED | — | IDLE | 自动重置 |
