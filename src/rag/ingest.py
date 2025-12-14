import os
import glob
import re
from typing import List
import chromadb
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

def parse_cocci_file(file_path: str) -> List[Document]:
    """
    Parses a .cocci file into multiple Documents (one per rule if possible, or whole file).
    Extracts description from /// comments.
    """
    with open(file_path, 'r', errors='ignore') as f:
        content = f.read()

    documents = []
    
    # Simple heuristic: split by rule names if possible, but .cocci structure varies.
    # For now, we treat the whole file as a document but try to extract metadata.
    
    # Extract description from /// comments
    description = []
    for line in content.splitlines():
        if line.strip().startswith('///'):
            description.append(line.strip().replace('///', '').strip())
    
    metadata = {
        "source": file_path,
        "filename": os.path.basename(file_path),
        "description": " ".join(description)
    }
    
    # TODO: Implement more granular splitting by rules if needed.
    # For now, chunking by file is a safe start for RAG.
    
    doc = Document(page_content=content, metadata=metadata)
    documents.append(doc)
    return documents

def parse_standard_files(cocci_dir: str) -> List[Document]:
    """
    Parses standard.h, standard.iso, and cocci_syntax.tex if they exist.
    """
    documents = []
    files_to_check = ['standard.h', 'standard.iso', 'cocci_syntax.tex']
    
    for filename in files_to_check:
        file_path = os.path.join(cocci_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', errors='ignore') as f:
                content = f.read()
            
            metadata = {
                "source": file_path,
                "filename": filename,
                "type": "standard_definition"
            }
            documents.append(Document(page_content=content, metadata=metadata))
            
    return documents

def ingest_data(kernel_dir: str, db_path: str):
    """
    Ingests .cocci files from kernel source and standard definitions into ChromaDB.
    """
    print(f"Scanning {kernel_dir} for .cocci files...")
    
    cocci_files = glob.glob(os.path.join(kernel_dir, 'coccinelle/**/*.cocci'), recursive=True)
    print(f"Found {len(cocci_files)} .cocci files.")
    
    all_docs = []
    
    # Parse Kernel Cocci Files
    for file_path in cocci_files:
        docs = parse_cocci_file(file_path)
        all_docs.extend(docs)
        
    # Parse Standard Definitions (Assuming they might be in the same dir or a specific one)
    # If standard files are in the kernel tree, they might be in scripts/coccinelle/ or elsewhere.
    # Often they are part of the coccinelle installation, not the kernel source.
    # But if the user provided them in the workspace, we check there.
    # For this implementation, we check the kernel_dir/scripts/coccinelle root.
    standard_docs = parse_standard_files(os.path.join(kernel_dir, 'coccinelle'))
    all_docs.extend(standard_docs)
    print(len(all_docs), len(standard_docs))
    if not all_docs:
        print("No documents found to ingest.")
        return

    # Custom splitter since langchain_text_splitters is missing
    class SimpleCharacterTextSplitter:
        def __init__(self, chunk_size, chunk_overlap):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
        
        def split_documents(self, documents):
            new_docs = []
            from langchain_core.documents import Document
            for doc in documents:
                text = doc.page_content
                if not text:
                    continue
                start = 0
                text_len = len(text)
                chunk_index = 0
                while start < text_len:
                    end = min(start + self.chunk_size, text_len)
                    chunk_text = text[start:end]
                    
                    metadata = doc.metadata.copy() if doc.metadata else {}
                    metadata["chunk"] = chunk_index
                    new_docs.append(Document(page_content=chunk_text, metadata=metadata))
                    
                    if end == text_len:
                        break
                    start += (self.chunk_size - self.chunk_overlap)
                    chunk_index += 1
            return new_docs

    # Reduce chunk size further to 250 to be extremely safe against token limits
    text_splitter = SimpleCharacterTextSplitter(
        chunk_size=250,
        chunk_overlap=50
    )
    
    split_docs = text_splitter.split_documents(all_docs)
    print(f"Split {len(all_docs)} documents into {len(split_docs)} chunks.")

    print(f"Ingesting {len(split_docs)} documents into ChromaDB at {db_path}...")
    
    # Initialize Chroma
    # Note: We use Silicon Flow embeddings via get_embedding_model
    from embeddings import get_embedding_model
    embeddings = get_embedding_model()
    
    vector_store = Chroma(
        collection_name="cocci_patterns",
        embedding_function=embeddings,
        persist_directory=db_path
    )
    
    # Add documents
    # Process in batches to avoid hitting limits if any
    # Batch size limited to 32 by Silicon Flow API, reducing to 5 to avoid token totals
    batch_size = 5
    import time
    for i in range(0, len(split_docs), batch_size):
        batch = split_docs[i:i+batch_size]
        try:
            vector_store.add_documents(batch)
            print(f"Ingested batch {i//batch_size + 1}/{(len(split_docs)-1)//batch_size + 1}")
            # Sleep to avoid RPM limit (403)
            time.sleep(1.2)
        except Exception as e:
            print(f"Error ingesting batch {i//batch_size + 1}: {e}")
            # Try to continue or re-raise? For now, we print and continue best effort
            pass
        
    print("Ingestion complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel-dir", required=True, help="Path to Linux Kernel source")
    parser.add_argument("--db-path", default="./chroma_db", help="Path to persist ChromaDB")
    args = parser.parse_args()
    
    ingest_data(args.kernel_dir, args.db_path)
