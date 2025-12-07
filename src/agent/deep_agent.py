from typing import Any, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.agent.state import AgentState
from src.mcp_server.tools import kernel_grep, read_window, list_tree, lookup_symbol_def
from src.agent.utils import get_llm
import os

# Initialize LLM
llm = get_llm()

def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    Planner Node: Generates a migration plan based on the user request.
    """
    print("DeepAgent: Planning...")
    
    system_prompt = """You are a Senior Linux Kernel Architect.
    Your goal is to create a detailed migration plan for a kernel update task.
    
    Task: {user_request}
    
    You have access to the following context (if any):
    {retrieved_rules}
    
    Output a Markdown formatted plan (MIGRATION_PLAN.md).
    Steps should include:
    1. Identify files to search (Explorer).
    2. Identify context to read (Explorer).
    3. Specific code changes (Coder).
    4. Verification steps.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Please generate the plan.")
    ])
    
    # Format retrieved docs
    retrieved_rules = ""
    if state.get("retrieved_docs"):
         retrieved_rules = "\n".join(str(d) for d in state["retrieved_docs"])

    chain = prompt | llm | StrOutputParser()
    plan = chain.invoke({
        "user_request": state["user_request"],
        "retrieved_rules": retrieved_rules
    })
    
    return {"plan": plan, "status": "planning"}

def explorer_node(state: AgentState) -> Dict[str, Any]:
    """
    Explorer Node: Executes search and read operations to gather context.
    Note: For simplicity, this node essentially asks the LLM "What should I look for?" 
    and then executes those search commands (simulated or real).
    """
    print("DeepAgent: Exploring...")
    
    # 1. Ask LLM what to search for based on the Plan
    plan = state["plan"]
    
    prompt_search = f"""
    Based on the following plan, what specific 'kernel_grep' or 'list_tree' commands should I run to locate the relevant code?
    Output ONLY a list of commands, one per line.
    Supported commands:
    - grep "pattern" "path"
    - list "path"
    - lookup "symbol" "path"
    
    Plan:
    {plan}
    """
    
    response = llm.invoke(prompt_search).content
    commands = response.strip().split('\n')
    
    context_results = []
    
    # 2. Execute commands (Safe execution wrapper)
    # Note: In a real agent, we might loop this. Here we do one pass.
    root_dir = "/home/hyz0906/workspace/kernel_upgrade" # Assume workspace root
    # Ideally should be dynamic found or passed.
    
    for cmd in commands:
        cmd = cmd.strip()
        result = ""
        if cmd.startswith('grep '):
            # Parse: grep "pattern" "path"
            try:
                parts = cmd.split('"')
                if len(parts) >= 4:
                    pattern = parts[1]
                    path = parts[3]
                    # Ensure path is relative and safe?
                    full_path = os.path.join(root_dir, path.lstrip('/'))
                    result = kernel_grep(pattern, full_path)
            except Exception as e:
                result = f"Error parsing cmd '{cmd}': {e}"
                
        elif cmd.startswith('list '):
             try:
                parts = cmd.split('"')
                if len(parts) >= 2:
                    path = parts[1]
                    full_path = os.path.join(root_dir, path.lstrip('/'))
                    result = list_tree(full_path)
             except Exception as e:
                result = f"Error parsing cmd '{cmd}': {e}"

        elif cmd.startswith('lookup '):
             try:
                parts = cmd.split('"')
                if len(parts) >= 4:
                    symbol = parts[1]
                    path = parts[3]
                    full_path = os.path.join(root_dir, path.lstrip('/'))
                    result = lookup_symbol_def(symbol, full_path)
             except Exception as e:
                result = f"Error parsing cmd '{cmd}': {e}"
        
        if result:
            context_results.append(f"CMD: {cmd}\nRESULT:\n{result}\n")
    
    # 3. If we found matches, maybe read some windows?
    # Simple heuristic: If grep found matches, read the first match's window.
    # (Enhancement logic)
    
    full_context = "\n".join(context_results)
    
    return {"context_data": full_context, "status": "exploring"}

def coder_node(state: AgentState) -> Dict[str, Any]:
    """
    Coder Node: Generates the patch/code based on Plan and Context.
    """
    print("DeepAgent: Coding...")
    
    plan = state["plan"]
    context = state["context_data"]
    
    prompt = f"""
    You are a Linux Kernel Developer.
    Execute the following plan using the provided context.
    
    Plan:
    {plan}
    
    Context Data (Search Results):
    {context}
    
    Task: Generate a Unified Diff (Patch) to apply the changes.
    Output ONLY the diff.
    """
    
    response = llm.invoke(prompt).content
    
    # Extract code block if wrapped
    patch = response
    if "```diff" in response:
        patch = response.split("```diff")[1].split("```")[0].strip()
    elif "```" in response:
        patch = response.split("```")[1].split("```")[0].strip()
        
    return {"unified_diff": patch, "status": "coding"}

def verifier_node(state: AgentState) -> Dict[str, Any]:
    """
    Verifier Node: Mocks the verification process.
    """
    print("DeepAgent: Verifying...")
    # In real world: Apply patch -> Make modules -> Run tests
    # Here: Just check if patch is not empty.
    
    patch = state.get("unified_diff", "")
    if patch and "diff --git" in patch:
        return {"status": "success"}
    else:
        return {"status": "failed", "error_log": ["No valid patch generated"]}
