# 系统设计文档：Linux Kernel Semantic Patch Generator (LK-SPG) Agent

## 1. 概述 (Executive Summary)

**目标**：构建一个基于 LLM 的智能 Agent 系统，专用于自动化生成 Linux Kernel 升级所需的 Coccinelle (SmPL) 语义补丁，并支持复杂逻辑的深度重构。

**核心痛点**：
1. 通用 LLM 倾向于将 SmPL 误认为 C 语言，导致语法错误。
2. 传统的 Coccinelle 脚本难以处理跨文件、逻辑复杂的语义变更。

**解决方案**：采用 **"Dual-Track Architecture" (双轨架构)**。
1. **Classic Track (RAG + CoT)**: 用于生成标准的 Coccinelle 脚本。采用“写-测-改”闭环。
2. **DeepAgent Track (Plan-Explore-Execute)**: 用于处理复杂重构。模拟人类开发者的“规划-探索-执行”工作流，利用虚拟文件系统工具进行精确手术。

---

## 2. 系统架构 (System Architecture)

本系统基于 **LangGraph** 构建，集成 **MCP (Model Context Protocol)** 工具集。

### 2.1 核心流程 (Workflow)

系统通过 **Smart Router** 将用户请求分发到两个不同的子图 (Subgraph)：

1. **Classic Flow**:
   - `Retrieve` -> `TestGen` -> `Architect` -> `Validator` -> `Refiner`
   - 适用于：API 参数变更、简单的函数重命名、废弃 API 替换。

2. **DeepAgent Flow**:
   - `Planner` -> `Explorer` -> `Coder` -> `Verifier`
   - 适用于：复杂逻辑重构 (Refactoring)、上下文依赖的变更、结构体生命周期调整。

### 2.2 状态定义 (Agent State)

全局 `AgentState` 包含两类字段：

```python
class AgentState(TypedDict):
    # Common Fields
    user_request: str          # 用户请求
    status: str                # 状态: "start", "success", "failed", etc.
    iteration_count: int       # 迭代计数
    error_log: List[str]       # 错误日志

    # Classic Flow Fields
    retrieved_docs: List[str]  # RAG 检索结果
    cocci_script: str          # 生成的 Coccinelle 脚本
    mock_c_code: str           # Mock 测试代码
    validation_output: str     # spatch 输出
    patch_diff: str            # 生成的 Patch

    # DeepAgent Flow Fields
    plan: str                  # 迁移计划 (MIGRATION_PLAN.md)
    context_data: str          # Explorer 收集的代码上下文
    current_file: str          # 当前操作的文件
    unified_diff: str          # 最终的 Unified Patch
```

---

## 3. 详细模块设计

### 3.1 知识库 (RAG)

- **Vector DB**: ChromaDB
- **Embedding**: OpenAI Embeddings (支持 Mock fallback)
- **Content**:
    - `standard.h`, `standard.iso`: 基础 SmPL 语法。
    - `cocci_syntax.tex`: 官方手册。
    - Git History: 历史 Commit 中的 Coccinelle 脚本及其对应的 Patch。

### 3.2 工具层 (MCP / Tooling)

所有工具封装在 `src/mcp_server/tools.py`，供 Agent 调用。

#### A. Coccinelle Tools
- `syntax_check`: 运行 `spatch --parse-cocci`。
- `dry_run`: 运行 `spatch --sp-file <script> <mock_file>`。

#### B. DeepAgent Tools (FileSystem & Search)
- `kernel_grep`: `grep -rn "pattern" path`。
- `list_tree`: 递归列出目录结构。
- `read_window`: 读取指定行周围的代码 (Context Window)。
- `lookup_symbol_def`: 基于 heuristic 查找符号定义 (Struct/Function)。

### 3.3 DeepAgent Sub-Agents

1. **Planner Node**:
   - 职责：理解需求，结合 RAG 知识，生成 `MIGRATION_PLAN.md`。
   - 输出：包含搜索策略和修改步骤的 Markdown 计划。

2. **Explorer Node**:
   - 职责：执行搜索命令 (`kernel_grep`, `list_tree`)，读取关键代码 (`read_window`)。
   - 策略：将庞大的内核源码转化为有限的 Context Window 供 Coder 使用。

3. **Coder Node**:
   - 职责：根据 Plan 和 Explorer 提供的 Context，生成最终的 Patch 或直接修改文件。
   - 输出：Unified Diff。

4. **Verifier Node**:
   - 职责：(Mocked) 验证 Patch 是否合法，未来可集成 `make modules`。

---

## 4. LangGraph 实现细节

### Routing Logic

```python
def mode_router(state):
    # 简单的关键词路由
    req = state['user_request'].lower()
    if "deep" in req or "refactor" in req or "plan" in req:
        return "planner" # 进入 DeepAgent
    return "test_gen"    # 进入 Classic Flow
```

### DeepAgent Loop

虽然设计上 DeepAgent 内部是一个循环 (Plan-Explore-Execute)，目前实现为线性流程，但可以通过 Feedback Loop 扩展为循环。

---

## 5. 项目结构 (Current implementation)

```
.
├── src
│   ├── agent
│   │   ├── graph.py       # LangGraph 定义 (Main & Subgraphs)
│   │   ├── nodes.py       # Classic Flow Nodes
│   │   ├── deep_agent.py  # DeepAgent Nodes
│   │   ├── state.py       # TypedDict State
│   │   └── utils.py       # Utilities (LLM Init)
│   ├── mcp_server
│   │   └── tools.py       # All Tools (Spatch + FS)
│   └── rag
│       └── retriever.py   # RAG Logic
├── run_agent.py           # Entry Point
├── deepagent.md           # DeepAgent Design Spec
└── design.md              # System Design (This file)
```

## 6. 未来计划

1. **Docker Integration**: 将 `spatch` 和内核编译环境放入 Docker 容器，增强安全性。
2. **Looping DeepAgent**: 允许 Explorer 和 Planner 多轮交互，直到找到所有相关代码。
3. **Multi-File Coder**: 支持同时生成多个文件的 Patch。
