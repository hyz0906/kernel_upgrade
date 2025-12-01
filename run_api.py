import uvicorn
import os

if __name__ == "__main__":
    # Ensure we are in the project root or src is in pythonpath
    # This script is expected to be run from the project root
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
