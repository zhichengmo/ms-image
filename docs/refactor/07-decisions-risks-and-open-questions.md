# MS-Image 决策、风险与待确认项

状态：`CURRENT_DECISION_VIEW`（当前决策视图）
更新规则：改变架构前先更新本文件和设计母文，再开始实现。

## 1. 已接受的核心决策

| 决策 | 理由 | 允许推翻的证据 |
|---|---|---|
| 权威按规则授权、实现事实、外部事实、目标设计、实施指导、医学准确率和历史解释分轴 | 单一线性排序会把旧 schema 当目标、把设计当实现或把工程通过当准确率 | 只能细化每条轴的来源和时效，不能重新跨轴混排 |
| 表数量不设上限，10+4 只是当前候选基线 | 架构按事实 owner 和生命周期设计，不按数字设计 | 新事实满足独立状态、查询、事务/恢复、权限或保留准入条件时直接评审增表 |
| 代码可以完全重构 | 用户明确授权；旧 XRay 专项内部结构不是兼容目标 | 仍须保留或受控迁移外部合同、唯一事实、可靠性和可回滚性 |
| 保留入口的内部模块化重构 | 可靠性骨架可复用，避免第二套事实源 | 现有入口或骨架被真实负载证明无法满足目标 |
| 在线 10 表为候选基线 | 每表当前有独立 owner/lifecycle | 实现后某表无独立状态/查询，或 JSON 被高频扫描 |
| 隔离评测 4 表 | Job/Outbox/Run/Artifact 足以先冻结实验 | 出现逐病例交互标注、法规逐行审计或权限瓶颈 |
| 无公共 file_asset（文件资产表） | owner 表才能闭环对象保留和删除 | 多领域对象确需独立生命周期且 owner 仍可唯一证明 |
| 8 个在线业务 Service | 覆盖业务用例，不把组件伪装成服务 | 新能力有独立业务状态、事务和外部合同 |
| 5 个注册 Stage Service | 只保留最短核心与一条候选分支 | 真实生产 Profile 增加并通过资格验证 |
| Primary 默认是 Final owner | 最短链、单一医学来源、可评测 | Targeted 候选在可信 paired/Holdout 中持续胜出 |
| DecisionFinalization 不改判 | 防止 Python 或规则成为第二医学 owner | 不应推翻；若需医学改判必须由明确医生/模型 owner |
| 首期无人工复核 | 没有领取、SLA、资格和裁决合同 | 业务明确提供完整人审 owner 与状态机 |
| XRay 只是 modality | 支持 CT/MRI 等统一数据边界 | 模态真实样本证明公共模型无法表达且适配器不足 |
| P1 自带 Image 校验最小 Outbox/Relay/Worker | 图片 ready 依赖事务后大对象校验，不能同步塞进 API，也不能等 Task 阶段才补可靠性 | 只有等价机制能证明上传完成到 ready/quarantined 的崩溃恢复闭环时才可替换 |
| 目标表删除 `tenant_id` 但不删除认证 | 数据分区字段和访问控制不是同一职责 | 目标 identity/scope/资源归属合同发生经批准的替代变化 |

## 2. 已否决

| 方案 | 否决原因 |
|---|---|
| 固定二次 `FinalMedicalReader` | NOR9 直接对照从 Primary 的 4 正常/4 异常/1 不确定退化为 2 正常/5 异常/2 不确定，成本和第二 owner 风险增加 |
| 按器官/犬猫长名称默认多次调用 | 分类与调用拓扑耦合，证据不独立、成本高、难以归因 |
| 直接复制旧 XRay 专表 | 无法支持通用模态，保留冗余和历史租户语义 |
| 公共 `file_asset` 表 | 对象 owner、删除权、保留期和业务状态变模糊 |
| Task 保存 delivery_status | 首期没有 callback/ack，和 Report 状态/current pointer 双写 |
| 在线 Python 投票/阈值改判 | 工程代码不能成为医学结论来源 |
| 数据库存动态 Python path/latest | 无法重放、回滚和证明旧 Task 版本 |
| 任意可拖拽 DAG 首期上线 | 单链未闭环，组合状态和校验成本过高 |
| DeepSeek Harness 进入线上链 | 无线上恢复、医学 owner 和确定性 scorer 合同 |

## 3. 实验性能力

| 能力 | 可能价值 | 主要风险 | 当前边界 |
|---|---|---|---|
| FamilyRouting + TargetedReview | 疑难专项补充信息 | 选择偏差、误报、额外成本和失败回退歧义 | validation-only/shadow，整体 paired A/B |
| Evidence Graph（证据图） | 显式支持/反驳/冲突 | 模型生成边可能幻觉，复杂度和延迟 | 仅离线 Artifact |
| Calibration/Conformal（校准/保序） | 风险量化和覆盖分析 | 小样本伪概率、漂移 | development Gold 离线拟合 |
| Topology/OOD（拓扑/分布外） | 发现数据覆盖空洞 | 聚类不等于医学结论 | 只做离线质量研究 |
| Harness（离线研究框架） | 失败归因和实验建议 | 工具建议污染 Gold/发布 | 只读脱敏 Artifact，人审后才形成候选 |
| Segmentation/Crop（分割/裁剪） | 局部结构可见性 | 原图上下文丢失、同源证据重复 | 只作补充，Final 始终可见完整原图 |

## 4. 延后能力

- 人工复核执行系统。
- 任意 DAG Compiler（通用流水线编译器）。
- 每个 Stage 的网络微服务化。
- CT/MRI/视频/WSI 医学执行链。
- 在线 Finding（影像发现）明细检索。
- callback/ack 交付状态机。
- 法规 append-only 通用事件表，除非 AuditSink 不能满足。

## 5. 当前高风险

| 风险 | 影响 | 当前控制 |
|---|---|---|
| 旧 AI 表存在明文 API key 设计 | Secret 泄漏 | 外置、轮换、扫描；不得迁移 |
| Worker 可能在事务内执行外部 I/O | 锁扩大、重复调用 | claim/I-O/result 拆成短事务 |
| 当前目标 Stage/Registry 未实现 | 文档与运行事实误读 | 始终标注 PROPOSED/NOT IMPLEMENTED |
| TraceEvent 删除过早 | 技术审计断链 | AuditSink 资格完成前保留 |
| 旧 PASS-LOCAL Artifact 过期 | 错误放行 | 绑定 captured_at、代码、环境和命令 |
| Gold/病例切分不可信 | 医学结论无效、数据泄漏 | 病例级去重、双专家仲裁、隔离 Holdout |
| Targeted 技术失败静默回退 | 选择性报告、错误医学结果 | Task technical failure + not_produced |
| 多模态被 XRay 抽象限制 | 后续持续加专用字段 | 真实样本先验证 Adapter 与数据边界 |
| 直接删除 tenant dependency | 可能让旧 API 越权或失去资源范围 | tenant claim 暂作兼容 scope；目标 owner 校验闭环后再移除 |
| 新旧 OSS key 并存 | 新 key 不再 tenant 派生，但旧对象仍需读取和归属校验 | 现有网关内兼容解析、owner/hash 对账；不盲目重写对象，不建第二 Gateway |

## 6. UNKNOWN（待确认）

1. 目标仓库干净基线、依赖 lock 和 `import main` 是否完全可复现。
2. API/Admin/Worker 生产启动命令、root path、资源和 liveness/readiness。
3. 生产 JWT/service identity、scope 和资源归属传播。
4. RabbitMQ/Celery 生产拓扑、TTL、重试、consumer timeout 和 DLQ 保留参数。
5. OSS bucket/region、KMS、retention、legal hold 和孤儿宽限期。
6. DICOM/PNG/JPG/视频/WSI 首期格式、windowing、orientation 和转换合同。
7. CT/MRI 上游 Study/Series/SOP UID、预期实例数和完成信号质量。
8. GPT-5.6 Sol、Gemini 3.7 Flash 等候选的真实 API model ID、视觉、JSON、区域、保留和 receipt 能力。
9. trusted Gold、病例级 split、failure bank 和 isolated Holdout 可用规模。
10. 旧 XRay API 的兼容期限、上游 owner 和下线门禁。
11. AuditSink 是否满足幂等、保留、授权检索、导出和删除证明。
12. Active Config 是否只允许 global，还是需要受信 experiment scope。
13. 现有 `xray_accuracy_*` 表最终归档、只读兼容还是受控导入。
14. 人工复核是否未来形成真实业务合同；当前答案仍为不考虑。
15. 旧 tenant claim 的兼容期限、目标 subject/service identity 映射和资源 owner 查询合同。
16. 新 OSS owner namespace 的精确格式，以及历史 tenant-derived key 的只读退出门禁。

## 7. 决策提交流程

任何改变表、Service、Stage 或医学拓扑的提案必须回答：

1. 现有失败或约束是什么，有什么可复核证据？
2. 变化影响哪个唯一事实 owner？
3. 为什么不能由现有表/Service/Stage 表达？
4. 作用机制如何影响中间量和最终指标？
5. 哪个冻结实验能隔离这个变量？
6. 停止、回滚和兼容条件是什么？
7. 哪些文档、Schema、Artifact 和 Gate 需要同步？

无法回答时保持现状，不以“以后可能需要”为理由提前加表或字段。
