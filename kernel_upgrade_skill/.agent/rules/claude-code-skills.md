---
trigger: always_on
---

# Rule: Claude Code Skill Architect Specification
# ID: CLAUDE_SKILL_SPEC_2026
# Version: 1.2.0
# Description: Standards for designing, implementing, and validating Claude Code Agent Skills.

## 1. Trigger Conditions
- **Filesystem:** Any file created or modified in `.claudecode/skills/` or ending in `*SKILL.md`.
- **Context:** When the user or an agent initiates the creation of a new "Skill" or "Capability" for Claude Code.

## 2. Core Architecture Principles
All Claude Code Skills must adhere to the **S.A.F.E.** framework:
- **S**pecific: One skill should solve exactly one well-defined problem.
- **A**tomicity: Steps must be granular enough to allow for mid-step recovery.
- **F**actual: Rely on system tools (ast-grep, git, make) rather than LLM hallucinations.
- **E**xplicit: Constraints and error-handling must be stated upfront.

---

## 3. Required Skill Structure
Every `SKILL.md` file generated under this rule must include these sections:

### I. Identity & Intent
- **Purpose**: A one-sentence summary of what this skill enables.
- **Triggers**: Define the specific prompts or file-states that should activate this skill.

### II. Tool Requirements (MCP Integration)
- Define which **Model Context Protocol (MCP)** servers or local CLI tools (e.g., `ast-grep`, `coccinelle`, `docker`) are required.
- Pre-flight check: Commands to verify these tools exist before execution.

### III. Execution Pipeline (The "Chain of Thought")
1. **Discovery**: How to find the target code/issue.
2. **Context Gathering**: What additional files or docs need to be read.
3. **Execution**: The step-by-step modification or analysis logic.
4. **Post-Action Verification**: Compulsory verification (e.g., `unit test`, `lint`, or `build`).

### IV. Guardrails & Safety
- **Forbidden Actions**: Actions the agent MUST NOT take (e.g., "Do not delete .env files").
- **Rollback Procedure**: Clear instructions on how to undo changes if a check fails.

---

## 4. Technical Standards for 2026
- **Language Sensitivity**: If the project is Linux Kernel related, prioritize `ast-grep` and `Coccinelle` over regex for code changes.
- **Context Management**: Skills must use "Selective Reading." Do not read files >1000 lines entirely; use `grep` or `sed` to extract relevant blocks.
- **Version Compatibility**: Skills must account for environment versions (e.g., specific Python/Node/Kernel versions).

## 5. Metadata Tagging
Every skill file must end with a metadata block for Antigravity's indexer:
---

## 6. Verification Checklist for Agents
Before an agent marks a Skill as "Completed," it must pass this internal check:
- [ ] Does it include a verification step (e.g., running a test)?
- [ ] Are all external tool dependencies listed?
- [ ] Is there an example of a successful input/output?
- [ ] Does it handle the "No match found" scenario gracefully?