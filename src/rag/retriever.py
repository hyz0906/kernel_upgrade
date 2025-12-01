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
            print(f"Adding {len(documents)} documents to VectorDB...")
            self.vector_store.add_documents(documents)
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
