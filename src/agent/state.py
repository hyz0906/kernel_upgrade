from typing import TypedDict, List, Optional

class AgentState(TypedDict):
    user_request: str          # User's natural language request or git diff
    retrieved_docs: List[str]  # SmPL patterns retrieved from RAG
    cocci_script: str          # The generated .cocci script
    mock_c_code: str           # The generated mock C code for testing
    validation_output: str     # Output from spatch (stderr/stdout)
    patch_diff: str            # The generated patch from dry run
    iteration_count: int       # Counter to prevent infinite loops
    error_log: List[str]       # History of errors for refinement
    status: str                # Current status: "drafting", "validating", "fixing", "success", "failed"
    
    # DeepAgent specific fields
    plan: Optional[str]        # The migration plan content (markdown)
    context_data: Optional[str]# Information gathered by Explorer
    current_file: Optional[str]# File currently being modified
    unified_diff: Optional[str]# Final generated patch for the codebase
