from langgraph.graph import StateGraph, END
from src.agent.state import AgentState
from src.agent.nodes import (
    retrieve_knowledge,
    draft_script,
    generate_test_case,
    validate_script,
    refine_script
)

def router(state: AgentState):
    """Decide next step based on validation result"""
    if state['status'] == "success":
        return END
    if state['iteration_count'] > 5: # Safety break
        print("Max iterations reached. Stopping.")
        return END
    return "refiner"

# Initialize Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("retrieve", retrieve_knowledge)
workflow.add_node("architect", draft_script)
workflow.add_node("test_gen", generate_test_case)
workflow.add_node("validator", validate_script)
workflow.add_node("refiner", refine_script)

# Add Edges
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "test_gen")
workflow.add_edge("retrieve", "architect") # Note: In parallel execution, we might need to join. 
# But here we want architect to use retrieved docs. 
# The design said: retrieve -> test_gen (parallel capable)
# But architect needs retrieved docs.
# Let's make it sequential for simplicity: retrieve -> test_gen -> architect -> validator
# Or: retrieve -> (test_gen, architect) -> validator?
# Architect needs retrieved docs. Test gen needs user request.
# So retrieve -> architect is fine. retrieve -> test_gen is fine.
# But validator needs both script (from architect) and mock code (from test_gen).
# So we need to join them.
# LangGraph allows parallel branches.
# Let's do: retrieve -> test_gen -> architect -> validator
# Wait, architect needs retrieved docs. retrieve returns them.
# test_gen passes state through.
# So: retrieve -> test_gen -> architect -> validator is a valid linear path.
# test_gen adds mock_c_code to state.
# architect adds cocci_script to state (using retrieved_docs from retrieve).
# validator uses both.

workflow.add_edge("retrieve", "test_gen")
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

# Compile
app = workflow.compile()
