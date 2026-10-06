# ADR-0004：R1 仅支持文本 Unary

- 状态：Accepted
- 日期：2026-10-06
- 决策者：Mcont
- 适用范围：Mconet Python R1 公共 API、验证、集成、Runtime、Fixture 与发布 Gate
- 规范 Profile：`r1.text-unary`

## 背景

Mconet 的长期架构支持多任务、多模态、流式、双向与长时操作，但第一版必须形成可测试、可跨端对齐且可发布的最小闭环。一次性暴露尚未实现完整生命周期、错误语义和契约测试的能力会产生空壳 API、silent fallback 和无法兑现的兼容承诺。

本决策固定 R1 的唯一支持范围和显式拒绝范围。机器可读真相保存在 `spec/r1-scope.json`；本 ADR 解释其边界和运行时行为。扩大或缩小 R1 必须同时更新 Scope、Fixture、Contract/Conformance Suite、公共 API 基线和替代 ADR。

## 决策

### 支持范围

R1 只支持以下能力的交集：

```text
Task: conversation.generate
Mode: unary
Message Content: content.text
Message Roles: message.system | message.user | message.assistant
Wire Format: application/json
Transport: http | https
Authorization: none | api-key-header | bearer
Reference Protocol: openai.chat-completions
```

一次成功交互必须使用 Conversation Task，其中 Conversation Input Node 持有只包含支持角色和文本内容的 MessageDocument。请求和响应通过完整 bytes Body 执行 JSON 编解码与一次 HTTP(S) 请求响应。Unicode、emoji、组合字符、换行、空白和多轮顺序必须按文本契约保真。

`http` 只允许明确的本地开发或受控测试；生产 Endpoint 默认要求 `https`。OpenAI-compatible Endpoint 形态与协议字段版本分别由 S0.36 和 S0.37 冻结，本 ADR 不提前扩展它们。

### 显式拒绝范围

R1 不支持：

- `server_stream`、`client_stream`、`duplex`、`long_running`；
- Embedding、Rerank、图像生成、音频转写、视频生成及其他非 Conversation Task；
- JSON Message Content、Artifact Message Content、未知 Content；
- Tool Call、Tool Result 和工具实际执行；
- 图片、音频、视频、文件及任何非空 ArtifactCatalog；
- WebSocket、gRPC、QUIC；
- Protobuf、XML、自定义二进制 Wire Format；
- OAuth refresh、Body signing、chunked signing；
- Agent Loop、RAG、会话持久化、历史裁剪、自动重试、自动模型切换和业务降级。

领域类型可以为后续版本保留开放标识、unknown 保真和稳定引用作用域，但 R1 Runtime 不得把“可以表示”解释为“可以执行”。公共 R1 RuntimeComponents 不暴露没有真实实现的流式、Artifact 或 Operation 空字段。

### 拒绝时机与错误

所有越界能力必须在网络 I/O 前由 Request/Task/Message/Artifact Validator、计划校验或 Capability Resolution 明确拒绝。不得：

- 丢弃不支持的字段后继续请求；
- 把非 unary 模式降级为 unary；
- 把 Artifact、Tool 或未知内容转成普通文本；
- 用完整缓冲伪装流式；
- 自动切换模型、协议、Endpoint、Codec 或 Transport；
- 延迟到服务端返回错误后才声明 SDK 不支持。

错误必须使用稳定的 Mconet category、phase 和 code，并包含不泄漏 Secret/Body 的 Diagnostic。具体错误码由后续对应 Validator 工作包逐项冻结；同一拒绝条件在所有平台必须产生等价结果。

### 执行与发布 Gate

R1 执行计划只允许 unary、JSON 兼容媒体类型和完整 bytes Body。成功 Decoder 与错误 Decoder 在 I/O 前分别固化；响应 outcome 只选择已固化 Decoder，Content-Type 只做兼容校验。

R1 发布前必须同时具备：

- Conversation/Text Domain、Schema、Validator 与 Builder；
- OpenAI-compatible 请求、响应和错误映射；
- 默认 JSON Codec、系统 HTTP Transport 与基础 Authorization；
- Client/Interaction 直接注入与默认回退；
- Unit、Contract、Conformance、Mock Server 和受控 Live 验证；
- 同一 `r1.text-unary` Golden Fixture 的跨端等价结果；
- 独立示例只依赖候选发布制品完成调用；
- 所有拒绝项在 I/O 前返回稳定错误。

仅定义接口、返回 Mock、跳过失败测试或依赖后续版本补齐生命周期，均不能声明 R1 支持。

## 不变量与评审检查

后续 R1 变更必须确认：

- 支持项是否仍严格等于 `spec/r1-scope.json`；
- 是否意外暴露流式、Artifact、Tool 或 Operation 空 API；
- 非文本内容和非 unary 模式是否在 I/O 前失败；
- unknown 保真是否被错误解释为可执行支持；
- 是否存在 silent fallback、字段丢弃或自动切换；
- 新增能力是否拥有自己的版本、生命周期、错误和 Contract/Conformance 测试；
- README、示例和发布元数据是否没有宣称超出 R1 的能力。

违反任一不变量的候选版本不得发布。

## 被否决的方案

### R1 同时提供文本流式

否决。流式需要 Framer、事件映射、聚合、背压、取消和消费权语义，不能作为 unary 的布尔开关或缓冲包装。

### 先暴露未来 API，后续再实现

否决。无实现的公共入口会形成错误兼容承诺，且无法通过公共 API 等价和发布制品消费验证。

### 对不支持内容做最佳努力降级

否决。把 Artifact/Tool/未知内容转文本或直接丢弃会改变业务语义，并造成跨端差异。

### 将 unknown 保真视为执行支持

否决。保真用于旧端读取和转存未来数据；执行仍需当前版本具有明确 Adapter、能力与测试。

## 结果

正向结果：

- 第一版范围可独立完成、测试和发布；
- 跨端 Fixture 与错误语义具有明确比较边界；
- 后续能力按版本增量加入，不破坏 R1 unary 契约；
- 调用方可以在执行前得到确定的不支持错误。

代价与约束：

- R1 无法用于流式、多模态、Tool、Embedding 等场景；
- 部分领域抽象在 R1 中只用于表达和前向兼容，不允许执行；
- 每项新增能力都必须完成独立生命周期与 Release Gate 后才能公开支持。
