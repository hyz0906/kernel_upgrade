import json
import os
import subprocess
from typing import Any, Dict, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from src.agent.state import AgentState, SpgState
from src.rag.retriever import CocciRetriever
from src.mcp_server.tools import run_spatch_syntax_check, run_spatch_dry_run
from src.agent.utils import get_llm

# Initialize LLM
llm = get_llm()

# Initialize Retriever
retriever = CocciRetriever()

def analyze_feasibility(state: AgentState) -> Dict[str, Any]:
    """
    Analyzes the user request to determine if Coccinelle (SPG) is feasible 
    or if we should fall back to direct LLM patching.
    """
    print("--- [Node] Feasibility Analysis ---")
    
    # Load system prompt
    try:
        with open("feasibility_prompt.md", "r") as f:
            system_prompt = f.read()
    except FileNotFoundError:
        return {"error": "feasibility_prompt.md not found"}
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Change Request Update: {user_request}")
    ])
    
    chain = prompt | llm | JsonOutputParser()
    
    try:
        result = chain.invoke({"user_request": state['user_request']})
        strategy = result.get("strategy", "LLM_DIRECT") # Default fallback
        print(f"Strategy Decision: {strategy}")
        return {
            "feasibility_result": result,
            "strategy": strategy
        }
    except Exception as e:
        print(f"Feasibility Analysis Failed: {e}")
        # Fallback to direct refactor if analysis fails
        return {
            "feasibility_result": {"error": str(e)},
            "strategy": "LLM_DIRECT"
        }

# --- SPG Subgraph Nodes ---

def node_rag_retrieve(state: SpgState) -> Dict[str, Any]:
    print("--- [Node] RAG Retrieval ---")
    query = state.get('task_description', '')
    # Use structured retrieval
    docs = retriever.retrieve_structured(query)
    
    patterns = f"""
    // Reference Syntax Rules
    {docs.get('syntax_rules', '')}
    
    // Reference Patterns
    {docs.get('examples', '')}
    """
    return {"retrieved_patterns": patterns, "iteration_count": 0}

def node_architect_draft(state: SpgState) -> Dict[str, Any]:
    iter_count = state.get('iteration_count', 0)
    print(f"--- [Node] Architect Drafting (Iter: {iter_count}) ---")
    
    # Construct prompt
    prompt_text = f"""
    Task: {state['task_description']}
    
    Reference Patterns: 
    {state.get('retrieved_patterns', 'None')}
    
    Previous Error (if any): {state.get('validation_error', 'None')}
    
    Write two things in a JSON object:
    1. "mock_c": A minimal Mock C file (mock.c) reproducing the old usage.
    2. "cocci_script": The Coccinelle (.cocci) script to fix it.
    
    Ensure your response is a valid JSON object.
    """
    
    response = llm.invoke(prompt_text)
    
    try:
        # Try to parse JSON directly
        content = response.content
        # Heuristic to find JSON if wrapped in markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
             content = content.split("```")[1].split("```")[0].strip()
             
        data = json.loads(content)
        return {
            "cocci_script": data.get("cocci_script", ""),
            "mock_c_code": data.get("mock_c", ""),
            "iteration_count": iter_count + 1
        }
    except Exception as e:
        print(f"Drafting failed to parse JSON: {e}")
        # Return error state or empty to fail validation
        return {
            "cocci_script": "",
            "mock_c_code": "",
            "validation_error": "Failed to generate valid JSON response",
            "iteration_count": iter_count + 1
        }

def node_syntax_check(state: SpgState) -> Dict[str, Any]:
    print("--- [Node] Syntax Check ---")
    script = state.get('cocci_script', "")
    
    if not script:
        return {
            "validation_error": "Empty script.",
            "status": "syntax_error"
        }
    
    # Syntax Check
    syntax_res = run_spatch_syntax_check(script)
    if syntax_res != "OK":
        return {
            "validation_error": f"Syntax Error: {syntax_res}",
            "status": "syntax_error"
        }
    
    return {
        "validation_error": None,
        "status": "syntax_ok"
    }

def node_dry_run(state: SpgState) -> Dict[str, Any]:
    print("--- [Node] Dry Run ---")
    script = state.get('cocci_script', "")
    mock_c = state.get('mock_c_code', "")
    
    if not mock_c:
         return {
            "validation_error": "Empty mock code.",
            "status": "logic_error"
        }

    # Dry Run
    patch_res = run_spatch_dry_run(script, mock_c)
    if not patch_res.strip():
        return {
            "validation_error": "Logic Error: Script is valid but matched nothing in Mock code.",
            "status": "logic_error"
        }
        
    return {
        "validation_error": None,
        "patch_preview": patch_res,
        "status": "success"
    }

def node_refine_script(state: SpgState) -> Dict[str, Any]:
    iter_count = state.get('iteration_count', 0)
    print(f"--- [Node] Refine Script (Iter: {iter_count}) ---")
    
    prompt_text = f"""
    The Coccinelle script failed validation.
    
    Task: {state['task_description']}
    
    Current Script:
    ```cocci
    {state['cocci_script']}
    ```
    
    Mock C Code:
    ```c
    {state['mock_c_code']}
    ```
    
    Error Message: 
    {state['validation_error']}
    
    Fix the errors. If it is a syntax error, fix the SmPL syntax. 
    If it is a logic error (no match), relax constraints or check against the mock code.
    
    Output ONLY the fixed .cocci script in a code block.
    """
    
    response = llm.invoke(prompt_text)
    content = response.content
    
    # Extract code
    script = content
    if "```cocci" in content:
        script = content.split("```cocci")[1].split("```")[0].strip()
    elif "```" in content:
        script = content.split("```")[1].split("```")[0].strip()
        
    return {
        "cocci_script": script,
        "iteration_count": iter_count + 1,
        "status": "fixed"
    }


def node_apply_real(state: SpgState) -> Dict[str, Any]:
    print("--- [Node] Apply In-Place ---")
    script = state['cocci_script']
    target_files = state['target_files']
    
    if not target_files:
        print("No target files specified.")
        return {"applied_diff": "No target files.", "final_cocci_script": script}

    # Write script to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cocci', delete=False) as tmp:
        tmp.write(script)
        script_path = tmp.name
        
    applied_diffs = []
    
    try:
        # Apply to each file
        # coccinelle can take multiple files, but for clarity let's do simple run
        # cmd: spatch --sp-file script --in-place file1 file2 ...
        cmd = ['spatch', '--sp-file', script_path, '--in-place'] + target_files
        
        # We want to capture the diff provided by --in-place?
        # Actually spatch --in-place modifies the file. We should use git diff to match it?
        # Or spatch output?
        # Let's run it.
        subprocess.run(cmd, check=True)
        
        # Now capture diff
        # Assuming we are in a git repo
        # If not, we can't easily get the diff without reading before/after.
        # But this is a workspace, presumably git tracked or we can just say "Applied".
        
        # Let's try to get diff using 'diff' command if not git
        # But for now, let's assume successful application.
        
        applied_diffs.append("Applied to " + str(target_files))
        
    except Exception as e:
        applied_diffs.append(f"Error applying patch: {e}")
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)
            
    return {
        "applied_diff": "\n".join(applied_diffs),
        "final_cocci_script": script,
        "status": "success"
    }

# --- LLM Direct Refactor Node ---

def llm_refactor_agent(state: AgentState) -> Dict[str, Any]:
    print("--- [Node] LLM Direct Refactor ---")
    # Placeholder for direct refactoring
    # In a real scenario, this would load files, edit them, and return diff.
    return {
        "llm_refactor_result": "LLM Direct Refactoring performed (Mock).",
        "final_diff": "Diff generated by LLM Direct"
    }

