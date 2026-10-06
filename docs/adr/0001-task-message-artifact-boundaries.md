# ADR-0001：Task、Message 与 Artifact 领域边界

- 状态：Accepted
- 日期：2026-10-06
- 决策者：Mcont
- 适用范围：Mconet Python 公共领域模型、Schema、Validator、Builder、Mapper 与 Runtime

## 背景

Task、Message 和 Artifact 都可能包含层级、关系或扩展数据，但三者表达的业务语义不同。如果因为结构相似而共享公共语义基类，任务配置会进入消息模型，消息角色会污染非对话任务，资源读取与传输职责也会反向进入 Task 或 Message。此类耦合会阻止三个领域独立演进，并使跨端 Schema 难以保持一致。

本决策固定三个领域的职责、允许的组合方式和依赖方向。后续公开类型、Schema 与运行时实现必须遵守本 ADR；改变这些边界需要新增替代 ADR，不能直接修改本记录的历史结论。

## 决策

### Task 领域

Task 表达一次模型任务“做什么”，负责：

- `TaskDescriptor`、`ModelTaskRequest`、`ModelTaskResult`；
- `TaskDocument`、`TaskNode`、`TaskRelation`；
- 任务输入、配置、约束、进度和结果结构；
- 工具定义、生成参数、响应约束等任务级配置；
- 按任务类型选择 Validator、Builder 和协议 Adapter 所需的领域信息。

`TaskNode` 只表达 Task AST 中的位置和语义，不得继承 `MessageElement` 或通用的业务元素基类。对话任务通过专用的 Conversation Input Node 组合 `MessageDocument`；Embedding、Rerank、图像、音频和视频任务不需要伪造 Message。

### Message 领域

Message 表达对话角色、轮次、历史、消息结构和消息内容，负责：

- `MessageDocument`、`MessageElement`、`MessageRelation`；
- `MessageRole`、`MessageContent` 及工具调用和工具结果；
- 消息树与消息内容各自的验证、Schema 和协议映射；
- 对话顺序、未知消息类型与未知内容的前向兼容。

`MessageElement` 不得继承 `TaskNode` 或通用的业务元素基类。`MessageContent` 是 Message Entry 内的有序内容集合，不是 `MessageElement` 子树，也不得继承 `MessageElement`。Task 参数、授权、Endpoint、Transport 和供应商协议字段不得进入 Message 模型。

### Artifact 领域

Artifact 表达可被 Task 或 Message 引用的内容资源，负责：

- `Artifact`、`ArtifactKind`、`ArtifactSource`、`ArtifactDescriptor`；
- `ArtifactReference` 与请求或结果局部的 `ArtifactCatalog`；
- Artifact ID 唯一性、引用解析范围和资源元数据；
- 后续 Reader、Resolver、Uploader 与传输计划所需的领域契约。

Artifact 不属于 Task 树或 Message 树，不得继承 `TaskNode`、`MessageElement` 或 `MessageContent`。Artifact 不能反向引用 Task 或 Message。资源读取、上传和网络传输属于 SPI/Runtime 或适配层，不属于 Artifact 值模型。

### 组合与依赖方向

允许的领域组合只有：

```text
Task → MessageDocument
Task → ArtifactReference / ArtifactCatalog
Message → ArtifactReference
```

依赖方向必须满足：

1. Task 可以通过专用节点组合 MessageDocument，并可持有请求或结果范围内的 ArtifactCatalog。
2. Message 可以通过 MessageContent 或工具结果引用 Artifact，但只保存 Catalog-local ID 和关系元数据。
3. Artifact 不依赖 Task 或 Message；Message 不依赖 Task。
4. 每个 `ModelTaskRequest` 的 ArtifactReference 只在该请求的 ArtifactCatalog 中解析；结果使用独立 Catalog。
5. Catalog 缺失、跨请求查找或隐式使用 Client 级全局 Artifact 注册表均被禁止。
6. Task、Message、Artifact 分别维护 Schema、Validator、Builder/Mapper 和版本，不因字段相似而共用领域契约。

实现内部可以复用不携带领域语义的算法或值对象，例如树路径、确定性遍历和不可变集合工具；这些复用不得进入公开继承层次，也不得把三个领域合并为 `InteractionElement`、`AnyNode` 或等价的万能类型。

## 不变量与评审检查

后续变更评审必须确认：

- 新 Task 配置是否仍位于 TaskNode，而非 MessageElement；
- 新消息结构是否仍位于 MessageElement/MessageContent，而非 TaskNode；
- 新资源能力是否通过 ArtifactReference 和局部 Catalog 组合；
- 是否出现 Artifact 对 Task/Message 的反向依赖；
- 是否引入跨请求、跨 Client 或跨会话的隐式 Artifact 查找；
- 是否为了复用字段而新增公共语义基类；
- 未知 Task、Message 和 Artifact 是否能在各自领域内独立保真。

违反任一不变量的实现不得通过架构评审或模块依赖检查。

## 被否决的方案

### 共享 InteractionElement 基类

否决。它只复用了表面上的树结构，却把 Task、Message 与 Artifact 的版本、验证和扩展语义绑定在一起；Go 等平台也会被迫实现没有业务意义的公共接口。

### 使用 Message 表达所有模型输入

否决。Embedding、Rerank、图像、音频和视频任务并非对话，伪造角色或消息会造成错误的公共语义，并把任务配置塞入 Message。

### 将 Artifact 内联为 TaskNode 或 MessageContent 字节字段

否决。内联会混淆资源身份、来源、描述与传输策略，无法统一处理 URI、文件、流、远端资源和上传计划，也无法建立明确的引用作用域。

### 全局 Artifact Registry

否决。全局注册会产生隐式生命周期、跨请求污染、并发隔离和资源所有权问题。Artifact 只能由当前请求或结果的 Catalog 显式解析。

## 结果

正向结果：

- 三个领域可以独立增加类型、Schema、Validator 和 Fixture；
- 对话任务可以组合 Message，同时不迫使非对话任务依赖 Message；
- Artifact 可被 Task 和 Message 共同引用，而不反向污染两者；
- 模块依赖与跨端契约可以通过明确方向自动检查。

代价与约束：

- 相似的树或关系字段可能在 Task 与 Message 中分别定义；
- Mapper 必须显式处理领域间组合，不能依赖万能节点；
- Artifact 引用需要 Catalog 唯一性与缺失引用校验；
- 新能力必须先判断其属于 Task、Message 还是 Artifact，不能为了快速接入随意放置字段。
