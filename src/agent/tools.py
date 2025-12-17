from langchain_core.tools import StructuredTool
from src.mcp_server.tools import (
    run_spatch_syntax_check,
    run_spatch_dry_run,
    run_spatch_apply,
    kernel_grep,
    list_tree,
    read_window,
    lookup_symbol_def
)

# Wrap MCP tools as LangChain StructuredTools
tools = [
    StructuredTool.from_function(
        func=run_spatch_syntax_check,
        name="check_cocci_syntax",
        description="Checks the syntax of a Coccinelle semantic patch script.",
    ),
    StructuredTool.from_function(
        func=run_spatch_dry_run,
        name="dry_run_cocci",
        description="Runs a dry run of a Coccinelle script on a mock C file to verify logic.",
    ),
    StructuredTool.from_function(
        func=kernel_grep,
        name="grep_kernel",
        description="Searches for a regex pattern in the kernel source code.",
    ),
    StructuredTool.from_function(
        func=list_tree,
        name="list_directory",
        description="Lists the directory structure up to a certain depth.",
    ),
    StructuredTool.from_function(
        func=read_window,
        name="read_file_window",
        description="Reads a window of code lines around a specific line number.",
    ),
    StructuredTool.from_function(
        func=lookup_symbol_def,
        name="lookup_symbol",
        description="Searches for the definition of a C symbol (struct/function) using heuristics.",
    ),
    StructuredTool.from_function(
        func=run_spatch_apply,
        name="apply_cocci",
        description="Applies a Coccinelle script to target files in-place.",
    ),
]

# Expose the list of tools
ALL_TOOLS = tools

def get_tools():
    """Returns the list of available tools."""
    return ALL_TOOLS
