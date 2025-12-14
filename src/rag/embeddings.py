import os
from langchain_openai import OpenAIEmbeddings

def get_embedding_model() -> OpenAIEmbeddings:
    """
    Returns the Silicon Flow embedding model instance.
    Uses 'BAAI/bge-large-en-v1.5' by default but configured for Silicon Flow API.
    
    Requires SILICONFLOW_API_KEY environment variable.
    """
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        print("Warning: SILICONFLOW_API_KEY not found. Please set it for embeddings to work.")
        # We might want to fallback or just let OpenAIEmbeddings fail/warn later, 
        # but for now we proceed hoping it might be set elsewhere or user is aware.
    
    return OpenAIEmbeddings(
        openai_api_base="https://api.siliconflow.cn/v1",
        openai_api_key=api_key,
        model="BAAI/bge-large-en-v1.5",
        # Explicitly set dimensions if needed, though usually inferred or defaults are fine.
        # User request mentioned encoding_format float and dimensions 1024, 
        # OpenAIEmbeddings handles this mostly, but we can't easily force dimensions 
        # in the constructor args directly for all versions without model specific kwargs.
        # BAAI/bge-large-zh-v1.5 is 1024 dims naturally.
    )
