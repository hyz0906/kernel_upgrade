import os
import sys
from src.agent.graph import app

def main():
    # if "OPENAI_API_KEY" not in os.environ:
    #    print("Please set OPENAI_API_KEY environment variable.")
    #    # For demonstration purposes, we might want to allow running without key if we had mocks,
    #    # but for now we enforce it as the agent relies on LLM.
    #    return

    if len(sys.argv) > 1:
        user_request = " ".join(sys.argv[1:])
    else:
        user_request = "Plan a refactor for usb_alloc_urb to use gfp_flags."
    
    print(f"Running agent with request: {user_request}")
    
    initial_state = {
        "user_request": user_request,
        "iteration_count": 0,
        "error_log": [],
        "status": "start"
    }
    
    try:
        for event in app.stream(initial_state):
            for key, value in event.items():
                print(f"\n--- Node: {key} ---")
                # Print relevant info based on node
                if key == "architect":
                    print(f"Generated Script:\n{value.get('cocci_script', '')[:100]}...")
                elif key == "test_gen":
                    print(f"Generated Mock Code:\n{value.get('mock_c_code', '')[:100]}...")
                elif key == "validator":
                    print(f"Validation Status: {value.get('status')}")
                    if value.get('patch_diff'):
                        print(f"Patch Generated:\n{value.get('patch_diff')}")
                elif key == "refiner":
                    print("Refining script...")
    except Exception as e:
        print(f"Error running agent: {e}")

if __name__ == "__main__":
    main()
