# 系统设计文档：`kernel-migrator` 自动化迁移工具

## 1. 逻辑架构 (System Architecture)

系统采用 **实时编排 (Real-time Orchestration)** 模式。移除了本地缓存层后，系统变为“全在线”模式，确保在处理 Linux 不同稳定分支（如 v5.10 到 v6.6）时，获取的 API 映射关系具有绝对的准确性。

---

## 2. 核心模块设计 (Functional Modules)

### 2.1 统一入口解析器 (Unified Input Parser)

支持多模态输入，并在第一阶段完成任务定性。

* **模式 A (Log-Driven)**：提取文件名、行号及未定义符号。
* **模式 B (Definition-Driven)**：直接解析用户提供的 `old_func -> new_func` 映射指令。

### 2.2 实时知识检索引擎 (Real-time Knowledge Engine)

通过 `bin/deepwiki_client.py` 封装对 `deepwiki.com` 的实时调用。

* **无状态查询**：系统不存储任何历史查询结果。
* **数据时效性**：每一次 Analysis 都会发起一次新的 API 请求，以获取 DeepWiki 针对特定内核版本的最新维护建议。
* **回退逻辑**：若 API 响应超时，系统将基于当前 LLM 的内置知识库进行“启发式尝试”，并在最终报告中明确标注“未经过外部知识校验”。

### 2.3 上下文感知重构引擎 (Refactor Engine)

* **动态采样**：根据错误点，利用 `read` 工具进行滑动窗口式读取（±100 行），确保覆盖函数体全貌。
* **原子重构**：LLM 负责处理参数重排、类型强制转换及配套的结构体成员修改。

### 2.4 语义审查器 (Semantic Reviewer)

替代物理编译的逻辑验证层，执行以下静态审计：

* **上下文安全性**：验证 API 变更是否违反了原有的临界区约束。
* **空指针与错误处理**：检查新 API 返回值的判断逻辑是否完备。
* **符号可见性**：检查是否遗漏了必要的头文件（Header files）。

---

## 3. 数据流与状态机 (Data Flow & State Machine)

由于去除了缓存，状态机更加线性：

1. **START**: 接收输入。
2. **DIRECT_QUERY**: (仅日志模式) 直接向 DeepWiki 请求实时数据。
3. **LOAD_CONTEXT**: 从本地文件系统读取源码。
4. **LLM_TRANSFORM**: 执行内存中的代码变换。
5. **LOGIC_AUDIT**: 进行语义审计。
6. **APPLY**: 将最终代码写入磁盘。

---

## 4. 文件与目录结构设计

移除了 `storage/` 目录，简化了 Skill 的文件足迹：

```text
.claude/
└── skills/
    └── kernel-migrator/
        ├── SKILL.md              # 状态机指令与核心逻辑
        ├── bin/
        │   └── deepwiki_client.py # 实时 API 客户端
        └── prompts/
            ├── refactor.tmpl     # 重构 Prompt 模板
            └── review.tmpl       # 语义审计 Prompt 模板

```

---

## 5. 关键 Prompt 策略设计

### 5.1 重构阶段 (Refactor Prompt)

> "你正在执行实时内核重构。请根据最新的 API 变更建议：[DeepWiki_Response]，对源码进行原子化修改。**特别注意**：由于未执行编译，你必须通过上下文分析确保类型匹配。"

### 5.2 审计阶段 (Review Prompt)

> "请作为资深维护者进行 Code Review。检查以下修改：1. 资源泄露风险；2. 锁深度一致性；3. 错误处理路径。给出明确的 Pass/Fail 结论。"

---

## 6. 系统优势

* **极简设计**：移除了复杂的缓存维护逻辑，降低了 Skill 的开发与调试成本。
* **高可靠性**：所有决策均基于 DeepWiki 的实时权威数据。
* **环境无关**：不依赖任何本地编译工具，使其可以在任何安装了 Claude Code 的开发机上无缝运行。

---
