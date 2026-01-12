# Claude Code Skill 需求说明书：内核 API 自动化迁移插件 (`kernel-migrator` v1.0)

## 1. 项目概述

本 Skill 旨在为内核开发者提供一个轻量级、高智能的 API 迁移助手。它不再依赖本地编译环境的配置，而是通过 LLM 对内核代码的深度理解，完成从“问题诊断”到“代码修复”再到“逻辑审计”的全流程。

## 2. 核心功能需求

### 2.1 多模态入口 (Flexible Entrance)

Skill 需支持两种触发模式，并自动切换工作流：

* **模式 A（诊断模式）：** 用户输入 `build.log` 或错误片段。Skill 调用 **DeepWiki API** 获取迁移建议。
* **模式 B（指令模式）：** 用户直接输入接口定义，例如：`"将 netif_napi_add(dev, napi, poll, weight) 替换为 netif_napi_add_weight(dev, napi, poll, weight)"`。Skill 跳过外部查询，直接进入重构。

### 2.2 纯 LLM 自动化重构 (LLM-Native Refactoring)

* **上下文补完：** Skill 在修改前必须使用 `read` 工具读取函数完整定义及相关的宏、结构体定义（通常为上下 100 行）。
* **智能重构：** * **参数映射：** 处理参数顺序调整、类型转换（如 `int` 转 `unsigned long`）。
* **副作用处理：** 识别 API 变更是否涉及锁（Locking）逻辑的变化或返回值检查逻辑的更新。
* **依赖管理：** 自动检查并补全 `#include` 声明。



### 2.3 语义级逻辑审查 (Pure LLM Review)

* **免编译验证：** 在 Review 阶段，LLM 充当高级审计员角色，从以下维度进行检查：
1. **逻辑一致性：** 替换后的逻辑是否与原逻辑语义对等？
2. **内核规范：** 是否符合 `Documentation/process/coding-style.rst` 规范？
3. **并发安全：** 是否在持锁状态下调用了可能睡眠的 API？


* **质量报告：** 输出一份简短的 Review Check-list，标注“已确认”或“潜在风险点”。

---

## 3. 工作流设计 (Workflow)

### 3.1 阶段详细定义

| 阶段 | 动作 | 输入 | 输出 |
| --- | --- | --- | --- |
| **Step 1: 任务规划** | 识别输入类型。若是日志，提取 Symbol；若是定义，解析映射关系。 | 用户 Prompt | 任务上下文对象 (Context Object) |
| **Step 2: 知识获取** | (可选) 若输入为日志，调用 `deepwiki_client.py` 检索方案。 | Symbol 名 | 迁移方案 (Migration Recipe) |
| **Step 3: 源码读取** | 使用 `ls` 和 `read` 准确定位文件并提取代码块。 | 文件路径 | 源码上下文 |
| **Step 4: LLM 重构** | 生成 Diff 代码块并使用 `write` 写入。 | 源码 + 迁移方案 | 修改后的代码 |
| **Step 5: 语义审查** | LLM 自我审计修改后的代码，检查死锁、空指针、引用计数等常见内核问题。 | 修改前后的代码 | Review Report |

---

## 4. 技术实现细节

### 4.1 SKILL.md 指令定义 (核心逻辑)

```markdown
---
name: kernel-migrate
description: LLM-based kernel API migration. Supports build logs or direct API definitions.
---
# Instructions
1. **Input Analysis**: Check if the user provided a log or a "from-to" definition.
2. **Knowledge Retrieval**: If it's a log, use `deepwiki_client.py` to get the fix. If it's a direct definition, use the provided mapping.
3. **Context Loading**: Find the source file and read the entire function where the error occurs.
4. **Refactor**: 
    - Apply the change directly to the file.
    - DO NOT use external tools like ast-grep.
    - Ensure coding style matches Linux kernel standards.
5. **LLM-Based Review**: 
    - Perform a "virtual review" of the changes.
    - Verify: Type safety, locking context, and return value handling.
    - Compilation is NOT required unless explicitly asked.
6. **Final Report**: Show the diff and the review findings.

```

### 4.2 配置与环境变量

* `DEEPWIKI_API_KEY`: 用于访问知识库。
* `KERNEL_SRC_ROOT`: 默认的内核源码根目录。

---

## 5. 验收标准

* **零配置运行：** 无需用户安装 `spatch` 或 `sg` 即可完成复杂迁移。
* **多入口兼容：** 能够准确区分并处理“日志输入”与“自定义映射输入”。
* **审查深度：** Review 报告能指出至少一项非语法层面的逻辑隐患（如漏掉 `unlock`）。

