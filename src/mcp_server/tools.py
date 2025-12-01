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
