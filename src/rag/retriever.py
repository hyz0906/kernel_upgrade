from typing import List, Dict, Any
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
import os
import re
import git
import subprocess

class CocciRetriever:
    def __init__(self, db_path: str = "./chroma_db"):
        # Use Silicon Flow embeddings
        from src.rag.embeddings import get_embedding_model
        try:
             self.embeddings = get_embedding_model()
        except Exception as e:
             print(f"Failed to initialize embeddings: {e}")
             print("Falling back to FakeEmbeddings for testing/offline support.")
             # Simple Fake Embeddings
             from langchain_core.embeddings import Embeddings
             class FakeEmbeddings(Embeddings):
                 def embed_documents(self, texts: List[str]) -> List[List[float]]:
                     return [[0.0] * 1024 for _ in texts]
                 def embed_query(self, text: str) -> List[float]:
                     return [0.0] * 1024
             self.embeddings = FakeEmbeddings()

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

    def retrieve_structured(self, query: str, k: int = 5) -> Dict[str, str]:
        """
        Retrieves knowledge separated by type (Syntax vs Examples).
        """
        # Retrieve Syntax Rules
        syntax_docs = self.vector_store.similarity_search(
            query, 
            k=3,
            filter={"type": "syntax"}
        )
        
        # Retrieve Examples
        example_docs = self.vector_store.similarity_search(
            query, 
            k=3,
            filter={"type": "example"}
        )
        
        return {
            "syntax_rules": "\n\n".join([d.page_content for d in syntax_docs]),
            "examples": "\n\n".join([d.page_content for d in example_docs])
        }

    def ingest_knowledge(self, kernel_dir: str, cocci_src_dir: str):
        """
        Ingests knowledge from standard files and git history.
        """
        documents = []
        
        # 1. Process standard.h and standard.iso
        documents.extend(self._process_standard_files(
            os.path.join(cocci_src_dir, "standard.h"),
            os.path.join(cocci_src_dir, "standard.iso")
        ))
        
        # 2. Process cocci_syntax.tex
        documents.extend(self._process_syntax_manual(
            os.path.join(cocci_src_dir, "docs/manual/cocci_syntax.tex")
        ))
        
        # 3. Process Commits
        documents.extend(self._process_commits(kernel_dir))
        
        if documents:
            # Custom splitter since langchain_text_splitters is missing
            class SimpleCharacterTextSplitter:
                def __init__(self, chunk_size, chunk_overlap):
                    self.chunk_size = chunk_size
                    self.chunk_overlap = chunk_overlap
                
                def split_documents(self, documents):
                    new_docs = []
                    # Assuming Document is imported in outer scope
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

            text_splitter = SimpleCharacterTextSplitter(
                chunk_size=250,
                chunk_overlap=50
            )
            split_docs = text_splitter.split_documents(documents)
            print(f"Split {len(documents)} documents into {len(split_docs)} chunks.")
            
            print(f"Adding {len(split_docs)} documents to VectorDB...")
            # Batch size limited to 32 by Silicon Flow API, reducing to 5
            batch_size = 5
            import time
            for i in range(0, len(split_docs), batch_size):
                batch = split_docs[i:i+batch_size]
                try:
                    self.vector_store.add_documents(batch)
                    print(f"Ingested batch {i//batch_size + 1}/{(len(split_docs)-1)//batch_size + 1}")
                    time.sleep(1.2) # Avoid RPM limit
                except Exception as e:
                     print(f"Error ingesting batch: {e}")
            print("Ingestion complete.")
        else:
            print("No documents found to ingest.")

    def _process_standard_files(self, standard_h_path, standard_iso_path) -> List[Document]:
        docs = []
        
        # standard.h
        if os.path.exists(standard_h_path):
            with open(standard_h_path, 'r', encoding='utf-8') as f:
                content = f.read()
            matches = re.findall(r'(#define\s+(\w+)\s*[^\n]*)', content)
            for full_line, name in matches:
                docs.append(Document(
                    page_content=f"Standard Macro '{name}':\n```c\n{full_line.strip()}\n```",
                    metadata={"type": "syntax", "source": "standard.h", "name": name}
                ))

        # standard.iso
        if os.path.exists(standard_iso_path):
            with open(standard_iso_path, 'r', encoding='utf-8') as f:
                content = f.read()
            iso_blocks = re.split(r'\n\n(?=Expression|Statement|Type|Declaration)', content)
            for block in iso_blocks:
                name_match = re.search(r'@\s*([\w_]+)\s*@', block)
                if name_match:
                    name = name_match.group(1)
                    docs.append(Document(
                        page_content=f"Isomorphism Rule '{name}':\n```\n{block.strip()}\n```",
                        metadata={"type": "syntax", "source": "standard.iso", "name": name}
                    ))
        return docs

    def _process_syntax_manual(self, tex_path) -> List[Document]:
        if not os.path.exists(tex_path):
            return []
        
        try:
            md_content = subprocess.check_output(['pandoc', '-f', 'latex', '-t', 'markdown', tex_path]).decode('utf-8')
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("Pandoc not found or failed. Skipping syntax manual.")
            return []

        docs = []
        sections = re.split(r'\n#+\s+', md_content)
        for sec in sections:
            lines = sec.split('\n')
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
            if len(body) > 20:
                docs.append(Document(
                    page_content=f"Syntax Guide - {title}:\n{body}",
                    metadata={"type": "syntax", "source": "manual", "title": title}
                ))
        return docs

    def _process_commits(self, repo_path, limit=500) -> List[Document]:
        try:
            repo = git.Repo(repo_path)
        except:
            print("Invalid git repo path")
            return []

        docs = []
        keywords = ["Generated by", "Generated using", "Generated with", "Coccinelle", "semantic patch"]
        commits = repo.iter_commits('master', max_count=limit, grep=keywords, regexp_ignore_case=True)
        
        for commit in commits:
            msg = commit.message
            script_match = re.search(r'(@@.*?@@.*)', msg, re.DOTALL)
            if not script_match:
                script_match = re.search(r'//\s*<smpl>(.*?)//\s*</smpl>', msg, re.DOTALL)
            
            if script_match:
                script_content = script_match.group(1).strip()
                summary = msg.split('\n')[0]
                
                # Get the diff
                try:
                    diff_content = repo.git.show(commit.hexsha, pretty="", patch=True)
                except Exception as e:
                    print(f"Failed to get diff for {commit.hexsha}: {e}")
                    diff_content = ""

                content = f"""Intent: {summary}
Reference Commit: {commit.hexsha}

Coccinelle Script:
```cocci
{script_content}
```

Commit Diff:
```diff
{diff_content}
```"""
                docs.append(Document(
                    page_content=content,
                    metadata={"type": "example", "commit": commit.hexsha}
                ))
        return docs
