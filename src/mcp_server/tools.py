import subprocess
import tempfile
import os
from typing import Tuple

def run_spatch_syntax_check(script_content: str) -> str:
    """
    Runs spatch --parse-cocci to check the syntax of the Coccinelle script.
    Returns "OK" if successful, otherwise returns the error message.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cocci', delete=False) as tmp:
        tmp.write(script_content)
        tmp_path = tmp.name

    try:
        # spatch --parse-cocci <file>
        # Note: spatch writes parse errors to stderr
        result = subprocess.run(
            ['spatch', '--parse-cocci', tmp_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return "OK"
        else:
            # Combine stdout and stderr for full context, though errors are usually in stderr
            return f"Syntax Error:\n{result.stderr}\n{result.stdout}"
            
    except FileNotFoundError:
        return "Error: 'spatch' command not found. Please ensure Coccinelle is installed."
    except Exception as e:
        return f"System Error: {str(e)}"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def run_spatch_dry_run(script_content: str, mock_c_code: str) -> str:
    """
    Runs spatch --sp-file <script> <mock_c_file> to generate a patch.
    Returns the generated patch (diff) or an empty string if no match/error.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cocci', delete=False) as tmp_cocci:
        tmp_cocci.write(script_content)
        cocci_path = tmp_cocci.name
        
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as tmp_c:
        tmp_c.write(mock_c_code)
        c_path = tmp_c.name

    try:
        # spatch --sp-file <cocci> <c>
        result = subprocess.run(
            ['spatch', '--sp-file', cocci_path, c_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # spatch outputs the diff to stdout
            return result.stdout
        else:
            # If spatch fails (e.g. syntax error in C file or runtime error), return error as output
            return f"Runtime Error:\n{result.stderr}"
            
    except FileNotFoundError:
        return "Error: 'spatch' command not found."
    except Exception as e:
        return f"System Error: {str(e)}"
    finally:
        if os.path.exists(cocci_path):
            os.remove(cocci_path)
        if os.path.exists(c_path):
            os.remove(c_path)

def kernel_grep(pattern: str, path: str) -> str:
    """
    Searches for a pattern in the specified path using grep.
    Args:
        pattern: The regex pattern to search for.
        path: The directory or file path to search in.
    Returns:
        The output of the grep command (matching lines).
    """
    try:
        # grep -rn "pattern" path
        result = subprocess.run(
            ['grep', '-rn', pattern, path],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            # Limit output to first 50 lines to prevent context overflow
            lines = result.stdout.splitlines()
            if len(lines) > 50:
                return "\n".join(lines[:50]) + f"\n... (and {len(lines) - 50} more matches)"
            return result.stdout
        elif result.returncode == 1:
            return "No matches found."
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"System Error: {str(e)}"

def list_tree(path: str, max_depth: int = 2) -> str:
    """
    Lists the directory structure up to a certain depth.
    Args:
        path: The directory path.
        max_depth: Maximum recursion depth.
    Returns:
        A string representation of the directory tree.
    """
    output = []
    try:
        for root, dirs, files in os.walk(path):
            # Calculate current depth
            depth = root[len(path):].count(os.sep)
            if depth > max_depth:
                del dirs[:] # Don't recurse further
                continue
            
            indent = "  " * depth
            output.append(f"{indent}{os.path.basename(root)}/")
            for f in files:
                output.append(f"{indent}  {f}")
        return "\n".join(output)
    except Exception as e:
        return f"Error listing directory: {str(e)}"

def read_window(file_path: str, line_number: int, window_size: int = 20) -> str:
    """
    Reads a window of code around a specific line number.
    Args:
        file_path: Path to the file.
        line_number: The center line number (1-indexed).
        window_size: Number of lines before and after to include.
    Returns:
        The file content with line numbers.
    """
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        start_line = max(0, line_number - 1 - window_size)
        end_line = min(len(lines), line_number + window_size)
        
        output = []
        for i in range(start_line, end_line):
            output.append(f"{i+1}: {lines[i].rstrip()}")
            
        return "\n".join(output)
    except Exception as e:
        return f"Error reading file: {str(e)}"

def lookup_symbol_def(symbol: str, path: str) -> str:
    """
    Attempts to find the definition of a symbol using grep (fallback for ctags/global).
    Heuristic: Looks for "struct symbol {" or "type symbol(" or "symbol ="
    """
    try:
        # Simple heuristic regex for C definitions
        # 1. struct definition: "struct symbol {"
        # 2. function definition: "type symbol(" - hard to catch all, but let's try "symbol(" at start of line or after type
        # Let's just grep for the symbol and let the agent filter.
        # Better: grep for "struct symbol" or "#define symbol"
        
        patterns = [
            f"struct {symbol}",
            f"#define {symbol}",
            f"{symbol}(",
        ]
        
        results = []
        for p in patterns:
            res = kernel_grep(p, path)
            if "No matches found" not in res:
                results.append(f"--- Matches for '{p}' ---\n{res}")
        
        if not results:
            return "No definition found (heuristics failed)."
        return "\n\n".join(results)
    except Exception as e:
        return f"System Error: {str(e)}"

