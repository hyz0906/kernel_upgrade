from langgraph.graph import StateGraph, END
from src.agent.state import AgentState
from src.agent.nodes import (
    retrieve_knowledge,
    draft_script,
    generate_test_case,
    validate_script,
    refine_script
)

from src.agent.deep_agent import (
    planner_node,
    explorer_node,
    coder_node,
    verifier_node as deep_verifier_node
)

def router(state: AgentState):
    """Decide next step based on validation result"""
    if state['status'] == "success":
        return END
    if state['iteration_count'] > 5: # Safety break
        print("Max iterations reached. Stopping.")
        return END
    return "refiner"

def mode_router(state: AgentState):
    """Decide whether to use Classic Agent or Deep Agent based on complexity or keyword"""
    # Simple heuristic: if request contains "deep" or "refactor" or "context", go Deep.
    req = state['user_request'].lower()
    if "deep" in req or "refactor" in req or "plan" in req:
        return "planner"
    return "test_gen"

# Initialize Graph
workflow = StateGraph(AgentState)

# Add Nodes (Classic)
workflow.add_node("retrieve", retrieve_knowledge)
workflow.add_node("architect", draft_script)
workflow.add_node("test_gen", generate_test_case)
workflow.add_node("validator", validate_script)
workflow.add_node("refiner", refine_script)

# Add Nodes (DeepAgent)
workflow.add_node("planner", planner_node)
workflow.add_node("explorer", explorer_node)
workflow.add_node("coder", coder_node)
workflow.add_node("deep_verifier", deep_verifier_node)

# Add Edges
workflow.set_entry_point("retrieve")

# Route after retrieval
workflow.add_conditional_edges(
    "retrieve",
    mode_router,
    {
        "test_gen": "test_gen",
        "planner": "planner"
    }
)

# Classic Flow
workflow.add_edge("test_gen", "architect")
workflow.add_edge("architect", "validator")
workflow.add_conditional_edges(
    "validator", 
    router, 
    {
        END: END,
        "refiner": "refiner"
    }
)
workflow.add_edge("refiner", "validator")

# DeepAgent Flow
workflow.add_edge("planner", "explorer")
workflow.add_edge("explorer", "coder")
workflow.add_edge("coder", "deep_verifier")
workflow.add_edge("deep_verifier", END)

# Compile
app = workflow.compile()
