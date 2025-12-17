# Linux Kernel Semantic Patch Generator (LK-SPG) Agent

## Overview

The **Linux Kernel Semantic Patch Generator (LK-SPG) Agent** is an intelligent system designed to automate the creation of Coccinelle (SmPL) semantic patches. It uses a **Feasibility Analysis** phase to determine the best refactoring strategy:

1.  **Coccinelle Strategy (Pattern-Based)**: For repetitive API changes, it uses a specialized subgraph to generate, validate, and test `.cocci` scripts.
2.  **LLM Direct Strategy (One-off)**: For complex or non-structural changes, it falls back to a direct LLM-based refactoring agent.

## Features

-   **Intelligent Routing**: The `Feasibility Analysis` node analyzes the request to select the optimal strategy (`COCCI` vs `LLM_DIRECT`).
-   **SPG Subgraph**: A dedicated LangGraph subgraph for Coccinelle workflows:
    -   **RAG Retrieval**: Fetches syntax rules and historical patterns.
    -   **Drafting**: Generates V1 script and mock C code.
    -   **Granular Validation**: Separate **Syntax Check** and **Dry Run** nodes ensure correctness.
    -   **Refinement Loop**: Automatically fixes scripts based on specific error feedback (syntax errors or logic mismatches).
-   **Structured Tools**: Internal tools (spatch execution, grep, etc.) are exposed as LangChain `StructuredTool` objects for reliable agent invocation.
-   **RAG Knowledge Base**: Indexes `standard.h`, `standard.iso`, and commit history.

## Prerequisites

-   **Python**: 3.10 or higher.
-   **Coccinelle**: `spatch` must be installed (`sudo apt-get install coccinelle`).
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
    ```

3.  Set environment variables:
    ```bash
    export OPENAI_API_KEY="your-api-key"
    ```

## Usage

### Command Line
Run the agent with a natural language request:

```bash
python3 run_agent.py "Fix the usage of usb_alloc_urb. It now takes gfp_flags as the second argument."
```

### REST API
Start the server:
```bash
python3 run_api.py
```
Endpoint: `POST /agent/run`

## Project Structure

-   `src/agent/`: LangGraph logic.
    -   `graph.py`: Main graph and subgraph definitions.
    -   `nodes.py`: Node implementations (Feasibility, SPG nodes, Validation).
    -   `tools.py`: LangChain `StructuredTool` definitions.
    -   `state.py`: State schemas (`AgentState`, `SpgState`).
-   `src/mcp_server/`: Underlying tool implementations.
    -   `tools.py`: Python functions for `spatch`, `grep`, etc.
-   `src/rag/`: Knowledge retrieval logic.
-   `feasibility_prompt.md`: System prompt for feasibility analysis.
-   `subgraph.md`: Design doc for the SPG subgraph.

## Contributing

Contributions are welcome! Please submit Pull Requests or open Issues.
