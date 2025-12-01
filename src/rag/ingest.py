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
    
    cocci_files = glob.glob(os.path.join(kernel_dir, 'scripts/coccinelle/**/*.cocci'), recursive=True)
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
    standard_docs = parse_standard_files(os.path.join(kernel_dir, 'scripts/coccinelle'))
    all_docs.extend(standard_docs)
    
    if not all_docs:
        print("No documents found to ingest.")
        return

    print(f"Ingesting {len(all_docs)} documents into ChromaDB at {db_path}...")
    
    # Initialize Chroma
    # Note: We use OpenAIEmbeddings by default, requires OPENAI_API_KEY env var.
    embeddings = OpenAIEmbeddings()
    
    vector_store = Chroma(
        collection_name="cocci_patterns",
        embedding_function=embeddings,
        persist_directory=db_path
    )
    
    # Add documents
    # Process in batches to avoid hitting limits if any
    batch_size = 100
    for i in range(0, len(all_docs), batch_size):
        batch = all_docs[i:i+batch_size]
        vector_store.add_documents(batch)
        print(f"Ingested batch {i//batch_size + 1}/{(len(all_docs)-1)//batch_size + 1}")
        
    print("Ingestion complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel-dir", required=True, help="Path to Linux Kernel source")
    parser.add_argument("--db-path", default="./chroma_db", help="Path to persist ChromaDB")
    args = parser.parse_args()
    
    ingest_data(args.kernel_dir, args.db_path)
