from typing import Any, Dict
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.agent.state import AgentState
from src.rag.retriever import CocciRetriever
from src.mcp_server.tools import run_spatch_syntax_check, run_spatch_dry_run

# Initialize LLM
# Note: Ensure OPENAI_API_KEY is set in the environment
llm = ChatOpenAI(model="gpt-4o", temperature=0.2)

# Initialize Retriever
retriever = CocciRetriever()

def retrieve_knowledge(state: AgentState) -> Dict[str, Any]:
    """Query VectorDB for similar .cocci patterns"""
    print(f"Retrieving knowledge for: {state['user_request']}")
    # Use structured retrieval to get syntax rules and examples separately
    docs = retriever.retrieve_structured(state['user_request'])
    return {"retrieved_docs": docs}

def draft_script(state: AgentState) -> Dict[str, Any]:
    """Architect Agent generates V1 script based on docs"""
    print("Drafting Coccinelle script...")
    
    # Load system prompt from file
    try:
        with open("system_prompt.md", "r") as f:
            system_prompt = f.read()
    except FileNotFoundError:
        # Fallback if file not found (though it should exist)
        print("Warning: system_prompt.md not found, using default.")
        system_prompt = """You are a Senior Linux Kernel Engineer specializing in Coccinelle Semantic Patch Language (SmPL)."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "User Request: {user_request}")
    ])
    
    # Format the retrieved docs for the prompt
    # The system prompt expects specific sections or we can append them
    # But wait, the system prompt in the file has placeholders? 
    # Let's check system_prompt.md content again.
    # It says: "You have access to two distinct knowledge sources via RAG retrieval."
    # It doesn't seem to have {retrieved_docs} placeholder.
    # So we should probably inject the context into the user message or append to system prompt.
    # However, to be safe and follow the plan, let's inject it into the prompt variables.
    
    # Actually, let's look at the system_prompt.md content I read earlier.
    # It describes how to use the knowledge, but doesn't explicitly have a {retrieved_docs} placeholder.
    # I should probably append the context to the system prompt or pass it as a variable if I modify the system prompt to include it.
    
    # Let's assume I need to inject it. I will modify the system prompt string in memory to include the context.
    
    retrieved_docs = state['retrieved_docs']
    context_str = f"""
### RAG CONTEXT - SYNTAX & RULES:
{retrieved_docs.get('syntax_rules', '')}

### RAG CONTEXT - HISTORICAL EXAMPLES:
{retrieved_docs.get('examples', '')}
"""
    
    # Append context to the system prompt
    final_system_prompt = system_prompt + "\n" + context_str

    prompt = ChatPromptTemplate.from_messages([
        ("system", final_system_prompt),
        ("user", "User Request: {user_request}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({
        "user_request": state['user_request']
    })
    
    # Extract code block if present
    script = response
    if "```cocci" in response:
        script = response.split("```cocci")[1].split("```")[0].strip()
    elif "```" in response:
        script = response.split("```")[1].split("```")[0].strip()
        
    return {"cocci_script": script, "status": "drafting", "iteration_count": 0}

def generate_test_case(state: AgentState) -> Dict[str, Any]:
    """Test Engineer generates mock C code"""
    print("Generating mock C test case...")
    
    system_prompt = """You are a QA Engineer.
Your sole task is to create a **Minimal Reproducible Example (MRE)** in C language to test a specific Kernel API change.
1.  Do NOT fix the code. Write the "Old Code" that uses the deprecated API.
2.  Include dummy struct definitions if necessary so the code is syntactically plausible.
3.  Keep it short (under 20 lines).
4.  Output ONLY the C code.
"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "User Request: {user_request}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"user_request": state['user_request']})
    
    # Extract code block
    code = response
    if "```c" in response:
        code = response.split("```c")[1].split("```")[0].strip()
    elif "```" in response:
        code = response.split("```")[1].split("```")[0].strip()
        
    return {"mock_c_code": code}

def validate_script(state: AgentState) -> Dict[str, Any]:
    """Tool Executor runs spatch --parse-cocci and dry run"""
    print("Validating script...")
    
    # 1. Syntax Check
    syntax_error = run_spatch_syntax_check(state['cocci_script'])
    if syntax_error != "OK":
        print(f"Syntax Error: {syntax_error}")
        return {
            "validation_output": syntax_error, 
            "status": "syntax_error",
            "error_log": state.get('error_log', []) + [f"Syntax Error: {syntax_error}"]
        }
    
    # 2. Dry Run
    patch = run_spatch_dry_run(state['cocci_script'], state['mock_c_code'])
    if not patch.strip():
        msg = "Script parsed but NO PATCH generated on mock code. The pattern might not match the mock code."
        print(msg)
        return {
            "validation_output": msg, 
            "status": "logic_error",
            "error_log": state.get('error_log', []) + [msg]
        }
    
    print("Validation Success!")
    return {"patch_diff": patch, "status": "success"}

def refine_script(state: AgentState) -> Dict[str, Any]:
    """Architect Agent fixes script based on error log"""
    print(f"Refining script (Iteration {state['iteration_count'] + 1})...")
    
    prompt_text = f"""
    The script you wrote failed validation.
    
    User Request: {state['user_request']}
    
    Current Script:
    ```cocci
    {state['cocci_script']}
    ```
    
    Mock C Code:
    ```c
    {state['mock_c_code']}
    ```
    
    Error Message: 
    {state['validation_output']}
    
    Fix the syntax or relax the matching rules (e.g., change specific types to expressions).
    Output ONLY the corrected .cocci script.
    """
    
    response = llm.invoke(prompt_text)
    content = response.content
    
    # Extract code block
    script = content
    if "```cocci" in content:
        script = content.split("```cocci")[1].split("```")[0].strip()
    elif "```" in content:
        script = content.split("```")[1].split("```")[0].strip()
        
    return {
        "cocci_script": script, 
        "iteration_count": state['iteration_count'] + 1,
        "status": "fixing"
    }
