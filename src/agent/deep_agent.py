from typing import Any, Dict, List
from langchain_core.messages import BaseMessage
from deepagents import create_deep_agent
from src.agent.state import AgentState
from src.mcp_server.tools import kernel_grep, list_tree, read_window, lookup_symbol_def
from src.agent.utils import get_llm

def get_deep_agent_graph():
    """
    Creates and returns the compiled Deep Agent graph using the deepagents library.
    """
    # 1. Initialize LLM
    llm = get_llm()

    # 2. Define Tools
    # Deep Agents need tools to explore and verify.
    tools = [kernel_grep, list_tree, read_window, lookup_symbol_def]

    # 3. Create the Deep Agent
    # create_deep_agent typically returns a compiled LangGraph application
    # We map the tools and the model.
    graph = create_deep_agent(
        model=llm,
        tools=tools,
        # You might want to pass a specific system prompt or config here if supported
        # agent_type="planner" # Example if there are variants
    )

    return graph

def deep_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Wraps the Deep Agent graph execution within our main graph.
    """
    print("--- Invoking Deep Agent ---")
    
    # 1. Get the compiled graph
    graph = get_deep_agent_graph()
    
    # 2. Prepare input for the deep agent
    # It likely expects a list of messages or a specific input key.
    # We'll pass the user request.
    inputs = {"messages": [("user", state["user_request"])]}
    
    # 3. Invoke
    # The output format depends on deepagents. Assuming it returns a dict with 'messages'.
    result = graph.invoke(inputs)
    
    # 4. Extract result
    # We might need to parse the last message content to update our state.
    messages = result.get("messages", [])
    if messages:
        last_msg = messages[-1]
        content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        return {
            "status": "success", 
            "validation_output": "Deep Agent finished",
            "patch_diff": content # Assuming the agent outputs the result/patch in the last message
        }
        
    return {"status": "failed", "error_log": ["Deep Agent returned no messages"]}
