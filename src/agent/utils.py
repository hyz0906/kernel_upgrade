import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from typing import Any, List, Optional

class MockLLM:
    def invoke(self, input: Any) -> Any:
        print(f"[MockLLM] Invoked with: {str(input)[:50]}...")
        return type('obj', (object,), {'content': "Mock response"})

    def __or__(self, other):
        return self

def get_llm():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Warning: OPENAI_API_KEY not found. Using MockLLM.")
        return MockLLM()
    
    return ChatOpenAI(model="gpt-4o", temperature=0.2)
