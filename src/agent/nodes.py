from typing import Any, Dict
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
    docs = retriever.retrieve(state['user_request'])
    return {"retrieved_docs": docs}

def draft_script(state: AgentState) -> Dict[str, Any]:
    """Architect Agent generates V1 script based on docs"""
    print("Drafting Coccinelle script...")
    
    system_prompt = """You are a Senior Linux Kernel Engineer specializing in Coccinelle Semantic Patch Language (SmPL).
Your Goal: Write a `.cocci` script to automate a kernel refactoring task.

### STRICT RULES (SmPL != C):
1.  **Do NOT act like a C Compiler.** SmPL is a pattern matching language.
2.  **Metavariables are King:** You MUST declare all metavariables between `@@` and `@@` before using them.
    - `expression E;` matches specific values.
    - `identifier f;` matches function/variable names.
    - `type T;` matches data types.
3.  **The "..." Operator:** - Use `...` to match arbitrary code execution paths.
    - Use `<... ...>` for code that might execute multiple times (loops/nesting).
4.  **Handling Context:** Do not write surrounding code unless it is required for disambiguation.

### RAG CONTEXT:
Here are similar patterns from the Linux Kernel codebase:
{retrieved_docs}

### WORKFLOW:
1.  **Analyze**: Breakdown the transform logic (What is removed? What is added?).
2.  **Define**: List necessary metavariables.
3.  **Draft**: Write the full `.cocci` script.
    
Output ONLY the code block for the .cocci script.
"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "User Request: {user_request}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({
        "user_request": state['user_request'], 
        "retrieved_docs": "\n\n".join(state['retrieved_docs'])
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
