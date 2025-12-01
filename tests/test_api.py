import os
os.environ["OPENAI_API_KEY"] = "dummy"
from fastapi.testclient import TestClient
from src.api.server import app
from unittest.mock import MagicMock, patch

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch("src.api.server.agent_app")
def test_run_agent(mock_agent_app):
    # Mock the agent response
    mock_agent_app.invoke.return_value = {
        "status": "success",
        "cocci_script": "@@...@@",
        "patch_diff": "+ code",
        "error_log": []
    }
    
    response = client.post("/agent/run", json={"request": "test request"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["cocci_script"] == "@@...@@"

if __name__ == "__main__":
    test_health()
    test_run_agent()
    print("All tests passed!")
