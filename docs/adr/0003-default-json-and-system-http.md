# ADR-0003：默认 JSON Codec 与系统 HTTP Transport

- 状态：Accepted
- 日期：2026-10-06
- 决策者：Mcont
- 适用范围：Mconet Python 默认 Factory、JSON Codec、HTTP Transport 与 R1 Text Unary

## 背景

Mconet 需要在调用侧不注入基础组件时即可完成 R1 文本 unary 请求，同时保持 Codec 和 Transport 可替换、Core 不依赖具体网络库、默认安装不引入第三方运行时依赖。Python 标准库提供 JSON、HTTP(S) 与 TLS 基础能力，但没有原生异步 HTTP Client，因此默认实现必须诚实声明能力，不能伪装为流式或全双工 Transport。

本决策固定 Python 默认 Factory 使用的 JSON 与 HTTP 实现、支持边界、安全要求和替换规则。具体类型与行为由后续原子工作包实施；替代本决策必须新增 ADR。

## 决策

### 默认 JSON Codec

默认 Payload Encoder/Decoder 使用 Python 标准库 `json`，并通过 SDK 自己的 SPI 暴露，不把 `json.JSONEncoder`、`json.JSONDecoder` 或其他标准库实现类型泄漏到公共 API。

默认编码规则：

- Wire Media Type 为 `application/json`；
- 文本编码固定为 UTF-8，不写 BOM；
- 输出必须是 JSON object、array、string、number、boolean 或 null；
- 禁止 NaN、Infinity 和 `-Infinity` 等非标准数值；
- 不自动序列化任意 Python 对象、dataclass、datetime、Decimal 或 bytes；
- 领域对象必须先由 Adapter/Mapper 转换为受约束的 JsonValue；
- 未知字段保真、字段缺失/null/default 语义由 Schema 与 Mapper 决定，Codec 不擅自补值；
- 编码错误和解码错误转换为统一 Mconet 错误，不附带完整敏感 Body。

确定性 Fixture 或签名场景需要稳定 JSON 时，由明确的 canonical 配置执行键排序、紧凑分隔符和数值约束；普通协议请求不得把“实现当前恰好稳定”当成规范保证。

### 默认系统 HTTP Transport

默认 HTTP Transport 只使用 Python 标准库 HTTP(S) 与 TLS 能力，初始实现可基于 `urllib.request`/`http.client`，但这些类型不得出现在公共 SPI。异步公共入口通过 SDK 控制的线程卸载适配同步 I/O，不能阻塞事件循环线程。

R1 默认 Transport 只承诺：

- HTTP/1.1 unary 请求与完整响应；
- `http` 仅用于明确允许的本地开发或受控测试，生产 Endpoint 默认要求 `https`；
- 系统 CA、默认主机名校验和默认 TLS 验证；
- 请求方法、URL、Header 和 bytes Body 的确定映射；
- 连接、读取、总 deadline 与取消信号的能力范围内传播；
- 增量读取响应并在读取期间执行最大 Body 限制；
- 状态、Header 与 Body 映射为统一 TransportResponse；
- 统一网络、TLS、超时、取消和响应超限错误。

默认 Transport 不声明 server streaming、client streaming、duplex、WebSocket、gRPC、HTTP/2、HTTP Trailer、自定义连接池或精确中断底层阻塞系统调用的能力。线程卸载任务收到取消后必须停止继续处理结果并尽力关闭响应资源，但不能声称所有平台和所有阻塞阶段均可即时中断。能力计划要求超出已声明范围时必须在 I/O 前失败。

### 安全与重定向

默认 Transport 必须：

- 拒绝 Header 名或值中的 CR/LF；
- 不提供关闭 TLS 验证的生产选项；
- 不记录 Authorization、Cookie、Secret、完整请求 Body 或完整错误 Body；
- 在读取响应过程中执行大小限制，不能先无限读取再检查；
- 对跨 Origin 重定向移除 Authorization、Cookie 与签名 Header；
- 限制重定向次数，并拒绝重定向到不安全或不允许的 scheme；
- 不从环境、全局 opener 或进程级可变状态隐式取得业务认证。

代理、系统证书和平台网络策略可以由宿主运行环境控制，但其有效配置必须可诊断，不能改变公共 Transport 语义。

### 默认组合与替换

当 ProtocolExecutionPlan 要求 JSON + unary HTTP(S)，且调用侧和当前 Binding 都未提供兼容 Codec/Transport 时，默认 Factory 按 ADR-0002 的最低成功优先级提供标准 JSON Codec 与系统 HTTP Transport。

调用侧可以在 Client 级或单次级直接注入兼容的 Encoder、成功/错误 Decoder 和 Transport。协议插件也可以在内部 Binding 中提供特殊实现。显式高优先级组件不兼容时立即失败，不得静默切换回默认实现。要改用 Protobuf、gRPC、WebSocket 或其他 Wire/Transport，必须同时提供能生成对应计划的 Adapter 和兼容组件，Codec 或 Transport 不得反向改写协议计划。

默认实现与注入实现必须通过相同的 Codec/Transport Contract Suite。Core Runtime 只能依赖 SPI，不得出现 `json`、`urllib`、`http.client` 或第三方网络库分支。

### 生命周期与资源所有权

默认 JSON Codec 无状态，可安全复用。默认 Transport 由 SDK Factory 创建并由 Client 幂等关闭其自有资源；单次响应和线程卸载任务必须在成功、失败和取消路径释放资源。

业务注入的 Transport、opener、连接池或网络客户端默认由业务持有，Client 关闭时不得释放；只有构造 API 明确转移所有权时例外。

## 不变量与评审检查

后续变更必须确认：

- 默认安装是否仍无第三方运行时依赖；
- 标准库 JSON/HTTP 类型是否泄漏到公共 SPI；
- JSON 是否拒绝非标准数值和任意对象隐式序列化；
- 响应上限是否在读取过程中执行；
- TLS、Header 和跨 Origin 重定向规则是否保持安全；
- 同步系统 I/O 是否被错误地放在事件循环线程执行；
- 默认 Transport 是否声明了无法可靠提供的流式、双向或协议能力；
- 显式注入不兼容时是否错误地回退到默认实现；
- Codec/Transport 是否反向修改 Adapter 已生成的协议计划；
- 业务注入资源是否被 SDK 错误释放。

违反任一不变量的实现不得通过架构评审、Contract Suite 或安全 Gate。

## 被否决的方案

### 默认依赖第三方异步 HTTP Client

否决作为基础默认项。它会增加默认安装依赖并把第三方生命周期与异常类型带入核心路径。业务仍可直接注入 httpx、aiohttp 或内部网络层的适配器。

### 在 Core Runtime 中直接调用 json 或 urllib

否决。Core 只能依赖 Codec/Transport SPI；具体库调用属于独立实现模块。

### 默认 Transport 宣称流式或 HTTP/2 能力

否决。标准库同步接口不能稳定提供跨平台等价的异步流、背压和协议控制；虚假能力会把失败推迟到网络 I/O。

### 不兼容时自动选择其他 Codec 或 Transport

否决。实际组件必须由计划与固定优先级确定，不能根据响应 Content-Type、URL 或运行时异常静默更换。

## 结果

正向结果：

- R1 JSON + HTTP(S) unary 在零基础组件注入时可用；
- 默认发布制品保持零第三方运行时依赖；
- Core 与具体 JSON/HTTP 库隔离；
- 业务可以直接替换企业网络层、代理、连接池或其他协议实现；
- 默认能力不足会在 I/O 前明确失败。

代价与约束：

- 标准库同步 HTTP 需要线程卸载，取消能力存在明确限制；
- 高性能连接池、HTTP/2、流式与双向能力需要注入更强 Transport；
- JSON 领域映射必须由 Adapter/Mapper 显式完成，Codec 不提供任意对象魔法序列化；
- 后续实现必须为默认和注入组件运行同一契约测试。
