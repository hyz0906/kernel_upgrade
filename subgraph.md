这是一个非常高阶的工程化需求。将 **LK-SPG (Linux Kernel Semantic Patch Generator)** 封装为 LangGraph 中的一个 **SubGraph (子图)** 是最佳实践。这样它可以作为一个“黑盒”节点嵌入到更大的流水线中。

以下是基于 **LangGraph** 实现的完整代码架构。这个模块作为一个独立的子图（`spg_subgraph`），接收上游分析结果，内部进行“生成-验证-修复”闭环，最终输出给下游检视。

### 1. 状态定义 (State Schema)

我们需要定义这个子图内部流转的“显存”。

```python
from typing import TypedDict, List, Optional, Literal
from langchain_core.messages import BaseMessage

# 定义子图的专用状态
class SpgState(TypedDict):
    # --- Input (来自上游) ---
    task_description: str       # 上游分析的升级方案描述
    target_files: List[str]     # 需要修改的内核源文件路径 (Sandbox内路径)
    
    # --- Internal Context ---
    retrieved_patterns: str     # RAG 检索到的参考 SmPL 代码
    
    # --- Artifacts (中间产物) ---
    cocci_script: str           # 当前版本的 .cocci 脚本
    mock_c_code: str            # 用于 Dry Run 的最小复现 C 代码
    
    # --- Feedback Loop ---
    validation_error: str       # spatch 语法报错或 dry run 失败原因
    patch_preview: str          # Dry run 生成的 patch 预览
    iteration_count: int        # 循环计数器 (防止死循环)
    
    # --- Output (传给下游) ---
    final_cocci_script: str     # 最终定稿脚本
    applied_diff: str           # 实际应用到 Kernel 文件的 Diff
    status: Literal["processing", "success", "failed"]

```

---

### 2. 工具层封装 (MCP/Spatch Tools)

这里模拟 MCP 工具调用的 Python 封装，实际部署时应调用 Docker Sandbox 中的命令。

```python
import subprocess
import os

class SpatchService:
    @staticmethod
    def check_syntax(script: str) -> str:
        """调用 spatch --parse-cocci"""
        # 实际应写入临时文件调用
        # cmd: spatch --parse-cocci temp.cocci
        # 返回: "OK" 或 错误日志
        return "OK" # Mock

    @staticmethod
    def dry_run(script: str, mock_c: str) -> str:
        """调用 spatch --sp-file script mock.c"""
        # 返回生成的 patch。如果为空字符串，表示未匹配。
        return "diff -u mock.c ..." # Mock

    @staticmethod
    def apply_in_place(script: str, target_files: List[str]) -> str:
        """调用 spatch --in-place --sp-file script target_files"""
        # 对实际文件应用，并返回 git diff 结果
        return "diff --git a/drivers/..." # Mock

# 实例化工具服务
spatch_tool = SpatchService()

```

---

### 3. 节点逻辑实现 (Node Implementation)

这些是 LangGraph 中的功能节点。

#### 3.1. RAG 检索节点

```python
def node_rag_retrieve(state: SpgState):
    print("--- [Node] RAG Retrieval ---")
    # 模拟向量库检索：查找类似的 cocci 模式
    # query = state['task_description']
    # docs = vector_store.search(query)
    patterns = """
    // Reference Pattern: Rename function argument
    @@ expression E; @@
    - old_func(E)
    + new_func(E, GFP_KERNEL)
    """
    return {"retrieved_patterns": patterns, "iteration_count": 0}

```

#### 3.2. 架构师节点 (Drafting)

```python
def node_architect_draft(state: SpgState):
    print(f"--- [Node] Architect Drafting (Iter: {state.get('iteration_count', 0)}) ---")
    
    # 构建 Prompt
    prompt = f"""
    Task: {state['task_description']}
    Reference Patterns: {state['retrieved_patterns']}
    Previous Error (if any): {state.get('validation_error', 'None')}
    
    Write two things:
    1. A minimal Mock C file (mock.c) reproducing the old usage.
    2. The Coccinelle (.cocci) script to fix it.
    """
    
    # 调用 LLM (假设 llm 已经初始化)
    # result = llm.invoke(prompt)
    
    # Mock 解析 LLM 输出
    new_script = "@@ ... @@" 
    new_mock = "void test() { ... }"
    
    return {
        "cocci_script": new_script,
        "mock_c_code": new_mock,
        "iteration_count": state["iteration_count"] + 1
    }

```

#### 3.3. 校验节点 (Validator - Syntax & Dry Run)

这是核心的“双塔博弈”逻辑。

```python
def node_validate_and_test(state: SpgState):
    print("--- [Node] Validation & Dry Run ---")
    script = state['cocci_script']
    mock_c = state['mock_c_code']
    
    # 1. 语法检查
    syntax_res = spatch_tool.check_syntax(script)
    if syntax_res != "OK":
        return {
            "validation_error": f"Syntax Error: {syntax_res}",
            "status": "processing" # 需要修复
        }
        
    # 2. Dry Run (逻辑检查)
    patch_res = spatch_tool.dry_run(script, mock_c)
    if not patch_res.strip():
        return {
            "validation_error": "Logic Error: Script is valid but matched nothing in Mock code.",
            "status": "processing" # 需要修复
        }
        
    # 通过验证
    return {
        "validation_error": None,
        "patch_preview": patch_res,
        "status": "success"
    }

```

#### 3.4. 应用节点 (In-Place Apply)

验证成功后，对实际 Kernel 文件动手。

```python
def node_apply_real(state: SpgState):
    print("--- [Node] Apply In-Place ---")
    # 对实际的 target_files 运行 spatch
    real_diff = spatch_tool.apply_in_place(state['cocci_script'], state['target_files'])
    
    return {
        "applied_diff": real_diff,
        "final_cocci_script": state['cocci_script']
    }

```

---

### 4. 构建子图 (Graph Construction)

这是将上述节点串联成 **LK-SPG Agent** 的逻辑。

```python
from langgraph.graph import StateGraph, END

# 初始化子图构建器
workflow = StateGraph(SpgState)

# 添加节点
workflow.add_node("rag_retrieve", node_rag_retrieve)
workflow.add_node("architect_draft", node_architect_draft)
workflow.add_node("validator", node_validate_and_test)
workflow.add_node("apply_real", node_apply_real)

# 定义入口
workflow.set_entry_point("rag_retrieve")

# RAG -> Draft
workflow.add_edge("rag_retrieve", "architect_draft")

# Draft -> Validate
workflow.add_edge("architect_draft", "validator")

# 定义条件分支 (Router)
def validation_router(state: SpgState):
    if state["status"] == "success":
        return "apply_real"
    
    if state["iteration_count"] >= 5: # 最大重试次数
        return "failed"
        
    return "architect_draft" # 回炉重造

workflow.add_conditional_edges(
    "validator",
    validation_router,
    {
        "apply_real": "apply_real",
        "architect_draft": "architect_draft", # 带着 Error 回到 Drafting
        "failed": END
    }
)

# Apply -> End
workflow.add_edge("apply_real", END)

# 编译子图
spg_subgraph = workflow.compile()

```

---

### 5. 集成到主系统 (Parent Graph Integration)

现在，我们将这个复杂的 `spg_subgraph` 作为一个普通节点放入主流程中。

```python
# 主图的状态
class MainState(TypedDict):
    input_report: str
    patch_proposal: dict
    review_comments: str

# 上游分析节点
def node_analysis(state: MainState):
    # 分析 Kernel 变更，生成 Task
    return {"patch_proposal": {
        "task_description": "Replace usb_alloc_urb(0, mem_flags) with usb_alloc_urb(0, GFP_KERNEL)",
        "target_files": ["drivers/usb/core/urb.c"]
    }}

# 包装 SubGraph 节点
# 注意：需要将 MainState 转换为 SubGraph 所需的 SpgState
def node_spg_agent_wrapper(state: MainState):
    print(">>> Entering SPG Subgraph >>>")
    
    # 1. 构造子图输入
    subgraph_input = {
        "task_description": state['patch_proposal']['task_description'],
        "target_files": state['patch_proposal']['target_files']
    }
    
    # 2. 调用编译好的子图
    result = spg_subgraph.invoke(subgraph_input)
    
    # 3. 将子图结果映射回主图状态
    if result.get("applied_diff"):
        return {
            "patch_proposal": {
                **state['patch_proposal'], 
                "cocci_script": result['final_cocci_script'],
                "diff": result['applied_diff']
            }
        }
    else:
        # 处理失败情况
        return {"review_comments": "SPG Failed to generate valid patch."}

# 下游检视节点
def node_reviewer(state: MainState):
    print("--- [Node] Code Review ---")
    diff = state['patch_proposal'].get('diff')
    if diff:
        print(f"Reviewing Patch:\n{diff}")
        # LLM Review Logic here
    return {}

# 构建主图
main_builder = StateGraph(MainState)
main_builder.add_node("analysis", node_analysis)
main_builder.add_node("spg_agent", node_spg_agent_wrapper) # 这里放入了整个子系统
main_builder.add_node("reviewer", node_reviewer)

main_builder.set_entry_point("analysis")
main_builder.add_edge("analysis", "spg_agent")
main_builder.add_edge("spg_agent", "reviewer")
main_builder.add_edge("reviewer", END)

app = main_builder.compile()

```

### 6. 系统运行效果可视化

当这个系统运行时，它会形成如下的逻辑流：

1. **Main Graph**: `Analysis Node` 产出需求。
2. **Main Graph**: 进入 `SPG Agent Node`。
* **Sub Graph**: `RAG` 检索类似补丁。
* **Sub Graph**: `Architect` 生成 Patch V1 和 Mock V1。
* **Sub Graph**: `Validator` 运行 spatch。
* *Scenario A*: 语法错误 -> 回退给 `Architect` (Context 包含错误信息)。
* *Scenario B*: 语法正确但 Mock 没变 -> 回退给 `Architect` (提示匹配规则太严)。
* *Scenario C*: 验证通过。


* **Sub Graph**: `Apply` 对真实文件执行 spatch --in-place。


3. **Main Graph**: 退出子图，进入 `Reviewer Node` 检视最终生成的 Diff。

### 7. 关键优势

1. **隔离性 (Isolation)**: Coccinelle 复杂的试错逻辑被完全封装在子图中，主图非常干净。
2. **鲁棒性 (Robustness)**: 这里的 `validation_router` 实现了**自我修复 (Self-Correction)**。如果 LLM 第一次写的脚本语法不对，系统会自动把报错扔回去让它重写，直到 spatch 通过为止。
3. **可观测性 (Observability)**: 由于每个步骤都是 Node，你可以清楚地看到 Agent 为了写出一个正确的脚本，到底重试了多少次。