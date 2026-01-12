# Claude Code Skill: Kernel API Migrator

## I. Identity & Intent
- **Purpose**: Automates the migration of Linux kernel APIs by analyzing build logs or accepting direct mapping instructions, leveraging offline/online knowledge to refactor code and perform semantic validation.
- **Triggers**: 
  - User asks to "fix kernel build errors" or "migrate API X to Y".
  - Input files match `build.log` or contain compiler error patterns.
  - User explicitly invokes `kernel-migrate`.

## II. Tool Requirements
- **System Tools**: `ls`, `read`, `grep`, `python3`
- **Helper Scripts**:
  - `bin/deepwiki_client.py`: For fetching migration recipes from DeepWiki (optional, falls back if offline).
- **Environment**:
  - `DEEPWIKI_API_KEY`: (Optional) API key for DeepWiki.

## III. Execution Pipeline

### 1. Discovery & Analysis
- **Input Classification**:
  - If input is a log file (e.g., `build.log`), extract the error symbol and file location.
  - If input is a directive (e.g., "replace A with B"), parse the mapping.
- **Context Loading**:
  - Identify the target C source file.
  - Use `read` to load the function containing the issue (context ±100 lines).

### 2. Knowledge Retrieval (Optional)
- If input is a log/symbol, invoke `bin/deepwiki_client.py <symbol>` to get the migration recipe.
- If the script fails or returns no data, use `prompts/fallback_knowledge.tmpl` to query the LLM's internal knowledge base for a migration recipe.

### 3. Execution (Refactoring)
- **Prompting**: Use `prompts/refactor.tmpl`.
- **Inputs**:
  - `QUERY`: The symbol or error being fixed.
  - `CONTEXT`: The source code.
  - `MIGRATION_RECIPE`: Output from Step 2 (Recipe from DeepWiki OR Fallback Prompt).
- **Action**:
  - The LLM will use the provided recipe. If empty, it will generate it internally (as per prompt instructions).
- **Action**:
  - Apply atomic changes to the function parameters, return values, and dependent structures.
  - **Constraint**: Do not use `ast-grep` or `sed` for complex logic; use `replace_file_content` (handled by Agent) but guided by the skill's logic description. *Note: As an Agent Skill, I will direct the Agent to use its native file editing tools.*
  - Ensure Linux kernel coding style (spaces/tabs, variable declarations) is respected.

### 4. Post-Action Verification (Semantic Review)
- **Virtual Review**: Instead of compiling immediately, perform a "Semantic Review" using `prompts/review.tmpl`.
- **Checks**:
  - **Type Safety**: Are the new argument types compatible?
  - **Locking**: Did the API change affect lock holding requirements?
  - **Resource Management**: Are there new error paths requiring cleanup?
- **Output**: A generated review report.

## IV. Guardrails & Safety
- **Forbidden Actions**:
  - Do NOT modify files outside the target function scope unless necessary (e.g., headers).
  - Do NOT assume a `make` environment exists.
- **Rollback**:
  - If the user rejects the changes or the "Virtual Review" finds critical flaws, revert the file edits using `git checkout` or internal history if available.

---
# Metadata
ID: KERNEL_MIGRATOR_V1
VERSION: 1.0.0
TYPE: REFACTOR
TAGS: kernel, migration, c, refactoring
