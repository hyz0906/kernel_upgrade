from typing import List
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

class CocciRetriever:
    def __init__(self, db_path: str = "./chroma_db"):
        self.embeddings = OpenAIEmbeddings()
        self.vector_store = Chroma(
            collection_name="cocci_patterns",
            embedding_function=self.embeddings,
            persist_directory=db_path
        )
        
    def retrieve(self, query: str, k: int = 5) -> List[str]:
        """
        Retrieves top-k similar Coccinelle patterns for the given query.
        Returns a list of document contents.
        """
        docs = self.vector_store.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]

    def retrieve_with_metadata(self, query: str, k: int = 5):
        """
        Retrieves top-k documents with metadata.
        """
        return self.vector_store.similarity_search(query, k=k)
