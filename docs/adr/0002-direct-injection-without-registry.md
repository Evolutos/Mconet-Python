# ADR-0002：直接注入且不提供 Registry 或组件 ID

- 状态：Accepted
- 日期：2026-10-06
- 决策者：Mcont
- 适用范围：Mconet Python 公共配置、组件解析、模型集成与 Runtime

## 背景

Mconet 必须允许业务替换 Adapter、Resolver、Codec、Transport、Authorization、Artifact 和 Monitoring 组件，同时保持选择结果确定、错误可诊断且生命周期明确。公共 Registry、组件 ID 或动态 Binding 注册虽然看似灵活，但会引入隐藏全局状态、字符串到实例的二次映射、注册顺序依赖和运行时热加载风险，也会与 Client 级和单次级覆盖形成重复配置机制。

本决策固定唯一的业务扩展入口、组件选择优先级、默认回退与失败语义。后续变更不得增加与直接注入并行的注册体系；替代本决策必须新增 ADR。

## 决策

### 唯一业务扩展入口

业务只能通过以下两个作用域直接传入实现现有 SPI 的实例或 Factory：

1. `ModelClientConfiguration.components`：在可复用 Client 生命周期内提供默认组件；
2. `InteractionOptions.components`：只覆盖当前一次交互。

单值行为组件直接传实例；Framer、Accumulator 等单次有状态对象传 Factory；AuthorizationHandler、Artifact Reader/Uploader/Transformer、Capability Provider 等按输入分派的能力传候选实例列表。公共配置不提供 `additional` 字典、任意角色 Map、服务定位器或依赖注入键。

公开 API 不提供：

- `Registry`、`register`、`add`、`remove` 或全局插件容器；
- 用字符串、整数或开放标识查找组件实例的 Component ID；
- 调用侧构造或注册 `ModelIntegrationBinding`；
- 运行时插件热加载；
- 在 `extensions`、Manifest、RawPayload 或环境变量中保存可执行组件引用。

`ComponentDescriptor.name/version` 只用于日志、监测和诊断，不要求全局唯一，也不得参与组件选择。

### 集成解析

`ModelIntegrationBinding` 是 SDK 或协议插件内部构造的不可变组合，不是公共注册项。默认 `ModelIntegrationResolver` 可以使用代码内不可变 Type 表或有序责任链，并在 Factory 构造阶段固定内容与顺序；不得暴露运行时注册 API。

业务若要改变整体集成查找策略，直接注入 `ModelIntegrationResolver`。若已直接注入 `TaskProtocolAdapter`，Runtime 必须先校验该 Adapter 是否支持当前 request 和 mode，再构造最小 direct `ModelIntegrationPlan`；该分支绕过默认集成 Resolver。显式 Adapter 不支持时立即失败，不得静默回退到 Binding 或 SDK 默认 Adapter。

### 确定性优先级

所有可替换单值组件使用同一优先级：

```text
1. InteractionOptions.components 直接实例
2. ModelClientConfiguration.components 直接实例
3. 当前 ModelIntegrationBinding 或协议插件明确提供的实例
4. SDK 默认实例
5. 无匹配：component_not_found
```

同一最高有效层级存在多个匹配时返回 `ambiguous_component_selection`。不得用组件名、注册顺序、列表顺序、导入顺序或隐藏 ID 静默选取。显式注入的单值组件只要存在就是调用侧最终选择；类型、端口或能力不兼容时在网络 I/O 前失败，不能降级到低优先级实现。

列表组件按上述层级合并并固化为当前交互的不可变候选集合，再由相应专用 Resolver 根据实际输入选择唯一实例。列表顺序不能代替 `supports`、类型契约、能力约束和歧义检测。

### 默认回退边界

SDK 默认 Factory 可以提供无需业务注册的基础实例。默认实例的具体技术选择由独立 ADR 固定；本 ADR 只规定它们位于最低成功优先级，且必须实现与注入组件相同的 SPI 和契约检查。

如果 Adapter 计划要求默认集合之外的编码、传输或交互能力，当前协议插件必须直接持有兼容实现，或由业务直接注入；否则在 I/O 前返回稳定的缺失组件或不支持能力错误。Runtime 不得通过网络探测、包扫描或动态导入寻找替代实现。

### 生命周期与执行快照

Factory 在返回 Client 前验证 Client 级注入组件的 SPI、角色和静态类型契约。Runtime 在每次交互开始时合并 Client 与单次注入，解析唯一组件并生成不可变执行快照；交互开始后的外部配置变化不得影响该快照。

业务注入实例及其底层网络客户端默认由业务持有，`ModelClient.close()` 不得擅自释放；只有构造 API 明确转移所有权时才能由 SDK 关闭。SDK 自行创建的默认资源由 SDK 管理并幂等释放。

## 不变量与评审检查

后续变更必须确认：

- 新扩展是否能通过现有 SPI 的 Client 级或单次级直接注入完成；
- 是否新增了 Registry、组件 ID、任意角色 Map 或动态 Binding 注册；
- 直接 Adapter 是否在默认 Resolver 前校验并形成唯一计划；
- 单值组件是否按固定层级唯一选择，歧义是否显式失败；
- 不兼容的高优先级显式组件是否错误地回退到低优先级；
- 列表候选是否在交互快照中固化并由专用 Resolver 选择；
- 业务资源所有权是否被 Client 错误接管；
- 解析过程中是否执行网络探测、包扫描或动态插件加载。

违反任一不变量的实现不得通过架构评审或组件解析契约测试。

## 被否决的方案

### 公共全局 Registry

否决。它引入全局可变状态、测试污染和并发顺序问题，并使 Client 的真实依赖无法从配置中直接观察。

### Component ID 到实例的二次解析

否决。ID 增加一套命名、冲突和生命周期协议，却不提供直接实例注入无法表达的能力。Descriptor 名称只能用于诊断。

### 公共 Binding 注册

否决。Binding 是协议插件内部的不可变组合。允许业务注册会泄漏 Runtime 组装细节，并与直接 Adapter/Resolver 注入重复。

### 自动包扫描与运行时热加载

否决。扫描结果依赖环境和导入顺序，难以跨端复现，也扩大供应链和可执行代码边界。

### 不兼容时静默回退

否决。显式注入代表调用侧最终选择；静默回退会隐藏配置错误，使实际使用的网络、编码或授权实现不可预测。

## 结果

正向结果：

- 业务依赖在 Client 或单次配置中显式可见；
- 组件选择跨运行环境保持确定，不受注册和导入顺序影响；
- 单个特殊协议可直接注入 Adapter，无需实现或修改全局 Resolver；
- 类型、能力、歧义和缺失错误可以在 I/O 前稳定报告；
- Client 复用与单次覆盖使用同一组合模型。

代价与约束：

- 动态插件系统必须由宿主应用在 SDK 外部完成，再把实例直接传入；
- 协议插件需要在自身 Factory 内显式组装 Binding；
- 列表型扩展必须提供确定的 supports/Resolver 规则，不能依赖先后顺序；
- 新组件角色只有满足 Core SPI 准入条件后才能版本化增加。
