from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.agent.graph import app as agent_app
from src.agent.state import AgentState

app = FastAPI(title="Linux Kernel Agent API", version="0.1.0")

class UserRequest(BaseModel):
    request: str

@app.post("/agent/run")
async def run_agent(user_req: UserRequest):
    """
    Run the agent with the given user request.
    """
    try:
        initial_state = AgentState(
            user_request=user_req.request,
            retrieved_docs={},
            cocci_script="",
            mock_c_code="",
            validation_output="",
            patch_diff="",
            error_log=[],
            iteration_count=0,
            status="start"
        )
        
        # Invoke the graph
        # Note: invoke returns the final state
        final_state = agent_app.invoke(initial_state)
        
        return {
            "status": final_state.get("status"),
            "cocci_script": final_state.get("cocci_script"),
            "patch_diff": final_state.get("patch_diff"),
            "error_log": final_state.get("error_log")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}
