# Linux Kernel Semantic Patch Generator (LK-SPG) Agent

## Overview

The **Linux Kernel Semantic Patch Generator (LK-SPG) Agent** is an intelligent system designed to automate the creation of Coccinelle (SmPL) semantic patches. It leverages Large Language Models (LLMs) and Retrieval-Augmented Generation (RAG) to understand user requirements and generate precise, syntactically correct `.cocci` scripts for kernel refactoring and upgrades.

## Features

-   **Intelligent Agent**: Built with [LangGraph](https://github.com/langchain-ai/langgraph), the agent follows a multi-step workflow:
    1.  **Retrieve**: Fetches relevant Coccinelle syntax rules and historical examples from the knowledge base.
    2.  **Draft**: Generates an initial `.cocci` script based on the user request and retrieved context.
    3.  **Test Generation**: Creates a minimal reproducible C example to test the script.
    4.  **Validation**: Runs `spatch` (Coccinelle) to verify syntax and dry-run the script against the mock C code.
    5.  **Refinement**: Automatically fixes the script if validation fails.
-   **RAG Knowledge Base**:
    -   **Syntax Rules**: Indexed from `standard.h`, `standard.iso`, and the Coccinelle manual.
    -   **Historical Examples**: Indexed from git commit history, including the commit diffs for context.
-   **REST API**: A FastAPI-based server to expose the agent as a service.
-   **MCP Server**: Implements the Model Context Protocol for tool integration.

## Prerequisites

-   **Python**: 3.10 or higher.
-   **Coccinelle**: The `spatch` command line tool must be installed and available in your PATH.
    -   Ubuntu/Debian: `sudo apt-get install coccinelle`
-   **Git**: Required for analyzing commit history.

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/yourusername/lk-spg-agent.git
    cd lk-spg-agent
    ```

2.  Install dependencies:
    ```bash
    pip install .
    # Or for development:
    pip install -e .
    ```

3.  Set up environment variables:
    ```bash
    export OPENAI_API_KEY="your-api-key"
    ```

## Usage

### 1. Command Line Interface (CLI)

You can run the agent directly from the command line:

```bash
python3 run_agent.py "Your request here"
```

Example:
```bash
python3 run_agent.py "Fix the usage of usb_alloc_urb. It now takes gfp_flags as the second argument, previously it took iso_packets."
```

### 2. REST API

Start the API server:

```bash
python3 run_api.py
```

The server will start at `http://0.0.0.0:8000`.

**API Endpoints:**

-   `POST /agent/run`: Run the agent.
    -   **Body**: `{"request": "Your request here"}`
    -   **Response**: JSON containing the generated script, patch diff, and status.
-   `GET /health`: Health check.

Example Request:
```bash
curl -X POST "http://localhost:8000/agent/run" \
     -H "Content-Type: application/json" \
     -d '{"request": "Replace foo(x) with bar(x, 0)"}'
```

### 3. Knowledge Base Ingestion

To populate the RAG knowledge base, you can use the `ingest_knowledge` method in `src/rag/retriever.py`. (Note: A dedicated ingestion script can be added for convenience).

### 4. MCP Server

You can run the MCP server standalone:

```bash
python3 run_mcp_server.py
```

This uses the `mcp` library to run the server, which typically communicates over stdio for integration with MCP clients (like Claude Desktop or other agents).

## Project Structure

-   `src/agent`: Contains the LangGraph agent logic (`graph.py`, `nodes.py`, `state.py`).
-   `src/rag`: RAG implementation (`retriever.py`).
-   `src/api`: FastAPI server (`server.py`).
-   `src/mcp_server`: MCP server tools (`tools.py`).
-   `system_prompt.md`: The system prompt used by the agent.
-   `pyproject.toml`: Project dependencies and configuration.

## Contributing

Contributions are welcome! Please submit Pull Requests or open Issues for bugs and feature requests.
