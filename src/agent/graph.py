from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from src.agent.state import AgentState, SpgState
from src.agent.nodes import (
    analyze_feasibility,
    node_rag_retrieve,
    node_architect_draft,
    node_syntax_check,
    node_dry_run,
    node_refine_script,
    node_apply_real,
    llm_refactor_agent
)

# --- Define SPG Subgraph ---
def check_syntax_router(state: SpgState) -> Literal["dry_run", "refine_script", "failed"]:
    if state["status"] == "syntax_ok":
        return "dry_run"
    
    if state["iteration_count"] >= 5: 
        return "failed"
        
    return "refine_script"

def check_dry_run_router(state: SpgState) -> Literal["apply_real", "refine_script", "failed"]:
    if state["status"] == "success":
        return "apply_real"
    
    if state["iteration_count"] >= 5: 
        return "failed"
        
    return "refine_script"

spg_workflow = StateGraph(SpgState)
spg_workflow.add_node("rag_retrieve", node_rag_retrieve)
spg_workflow.add_node("architect_draft", node_architect_draft)
spg_workflow.add_node("syntax_check", node_syntax_check)
spg_workflow.add_node("dry_run", node_dry_run)
spg_workflow.add_node("refine_script", node_refine_script)
spg_workflow.add_node("apply_real", node_apply_real)

spg_workflow.set_entry_point("rag_retrieve")
spg_workflow.add_edge("rag_retrieve", "architect_draft")
spg_workflow.add_edge("architect_draft", "syntax_check")

# Syntax Check Router
spg_workflow.add_conditional_edges(
    "syntax_check",
    check_syntax_router,
    {
        "dry_run": "dry_run",
        "refine_script": "refine_script",
        "failed": END
    }
)

# Dry Run Router
spg_workflow.add_conditional_edges(
    "dry_run",
    check_dry_run_router,
    {
        "apply_real": "apply_real",
        "refine_script": "refine_script",
        "failed": END
    }
)

# Refine Loop
spg_workflow.add_edge("refine_script", "syntax_check")

spg_workflow.add_edge("apply_real", END)
spg_subgraph = spg_workflow.compile()


# --- Wrapper for Subgraph Integration ---
def spg_agent_wrapper(state: AgentState) -> Dict[str, Any]:
    print(">>> Entering SPG Subgraph >>>")
    
    # Map AgentState to SpgState
    # Note: target_files logic needs to be robust. 
    # For now, we pass empty list if not found, node_apply_real handles it.
    # Ideally, we'd extract this from feasibility_result or user_request.
    subgraph_input = {
        "task_description": state['user_request'],
        "target_files": [], # TODO: Extract targets from analysis
        "iteration_count": 0
    }
    
    result = spg_subgraph.invoke(subgraph_input)
    
    return {
        "spg_output": result,
        "final_diff": result.get("applied_diff"),
        "status": result.get("status")
    }

# --- Define Main Graph ---
def strategy_router(state: AgentState) -> Literal["spg_agent", "llm_refactor"]:
    strategy = state.get("strategy", "LLM_DIRECT")
    if strategy == "COCCI":
        return "spg_agent"
    return "llm_refactor"

main_workflow = StateGraph(AgentState)
main_workflow.add_node("analyze_feasibility", analyze_feasibility)
main_workflow.add_node("spg_agent", spg_agent_wrapper)
main_workflow.add_node("llm_refactor", llm_refactor_agent)

main_workflow.set_entry_point("analyze_feasibility")

main_workflow.add_conditional_edges(
    "analyze_feasibility",
    strategy_router,
    {
        "spg_agent": "spg_agent",
        "llm_refactor": "llm_refactor"
    }
)

main_workflow.add_edge("spg_agent", END)
main_workflow.add_edge("llm_refactor", END)

app = main_workflow.compile()

# For testing compilation
if __name__ == "__main__":
    print("Graph compiled successfully.")
