from mcp.server.fastmcp import FastMCP
from src.mcp_server.tools import run_spatch_syntax_check, run_spatch_dry_run

# Initialize FastMCP server
mcp = FastMCP("LK-SPG-Server")

@mcp.tool()
def syntax_check(script_content: str) -> str:
    """
    Check the syntax of a Coccinelle (SmPL) script.
    
    Args:
        script_content: The content of the .cocci script.
        
    Returns:
        "OK" if syntax is correct, otherwise the error message.
    """
    return run_spatch_syntax_check(script_content)

@mcp.tool()
def dry_run_verification(script_content: str, mock_c_code: str) -> str:
    """
    Run a dry run of the Coccinelle script against a mock C file to verify it generates the expected patch.
    
    Args:
        script_content: The content of the .cocci script.
        mock_c_code: The content of the mock C file to test against.
        
    Returns:
        The generated patch (diff) or error message.
    """
    return run_spatch_dry_run(script_content, mock_c_code)

def main():
    mcp.run()

if __name__ == "__main__":
    main()
