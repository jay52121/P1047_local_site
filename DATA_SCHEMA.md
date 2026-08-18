# SISP 静态演示数据规范

当前运行时只读取 HTML、CSS、JavaScript 和 JSON，不需要数据库或业务后端。公开仓库中的数据全部必须标记为 `sourceType: "simulation"`。

## 数据包结构

```text
data/demo/
├── persons.json
├── P-1047/
│   ├── profile.json
│   ├── manifest.json
│   └── life/
│       ├── weekly-summary.json
│       └── weeks/{weekId}.json
└── C-2308/
    ├── profile.json
    ├── manifest.json
    └── attention/
        ├── {taskId}-weekly-summary.json
        └── weeks/{taskId}/{weekId}.json
```

`weekly-summary.json` 服务于日期选择、指标卡、两周比较和长期趋势。`weeks/*.json` 保存自动动态证据所需的代表动作、状态片段和离散事件。

## 周标识

`weekId` 使用 ISO 周格式 `YYYY-Www`。`weekStart` 必须为周一，`weekEnd` 必须为之后的周日。

## 计算约定

- 页面两周相对值：`右侧周指标 ÷ 左侧周指标 × 100`。
- 普通能力指标变化小于 1.5% 视为稳定；越高表示改善。
- 风险指标变化小于 1.5% 视为稳定；越低表示风险降低。
- 专注任务指标变化小于 2% 视为稳定，指标定义决定高值或低值是否更好。
- 4 周趋势为包含当前周在内、最多四周的简单移动平均。
- `confidencePct` 只表示数据覆盖和质量，不参与能力指数计算。
- `in_progress` 周只包含已完成日期，必须同时提供说明。

V1 已有周指标按 `calculationVersion: "v1-migrated"` 原值迁移，页面显示结果与迁移前一致。新生成的详情数据用于建立证据结构，不反向改变 V1 指标。

第二阶段新增四域采用正式的 event-first 模式：

```json
{
  "sourceType": "simulation",
  "calculationMode": "generated-from-events",
  "calculationVersion": "v2-events-1",
  "evidenceOrigin": "generated"
}
```

三个字段分别表达数据来源、计算方式和证据来源。现有 life/attention 保持 `migrated-summary + reconstructed`，未来真实数据使用 `real + generated-from-events + observed`。

## 第二阶段稳健个人基线

四个新域的每个周级原始量使用建立期 W46–W50：

```text
B = median(五周原始量)
R = max(1.4826 × MAD, sensitivityFloor)
```

越高越好的量：`clamp(100 + 10 × (x-B)/R, 70, 130)`；越低越好的量反向计算。所有 sensitivity floor 和一级指数权重集中保存在 `tools/demo_generation/metric_specs.py`。

## 缺失与数据状态

- `0`：已观察且事件确实没有发生。
- `null`：数学上不可定义或没有评价机会。
- `invalid`：应当可以观察，但数据质量不足；通过 unit 的 `valid: false` 和 `invalidReason` 表达。
- `status` 只表达日历状态：`complete / in_progress`。
- `dataStatus` 只表达数据充分度：`sufficient / partial / insufficient`。

`confidencePct` 只根据 coverage、continuity、structural completeness 和有效 unit 数量计算，不包含行为表现和 CV。

## 心理情绪状态（Phase 2B）

心理情绪状态采用完整 event-first 链路：`segments/events → day result → weekAggregate.metrics → W46–W50 个人基线 → indexes`。它是行为代理（behavioral proxy），不是情绪识别或心理状态分类器，底层不生成 sadness、happiness、depression、anxiety 或 mood score。日观察窗固定为 06:00–23:00；基础状态为 `active / low_activity / long_still / unknown`，事件只允许 `activity_start / interest_opportunity / social_opportunity`。

周级正式原始量严格为 9 项：行为活跃占比、自主启动频率与占比、兴趣机会接受率与投入比例、交流机会回应率与回应延迟、长时间静止占比、低活动 episode 中位时长。外出、位置、活动范围和实际互动总量不进入该域。`emotion_metric_mapping.json` 保存一级指数、原始量和底层事实的可追溯关系；detail 的 `evidenceSummary` 只是从正式指标生成的排序缓存，删除后不影响任何指标重算。

完整周至少 5 个有效日才能生成正式指数；W33 截至 2026-08-13，仅包含周一至周四，并以 `in_progress + provisional` 表达。生成器使用 SHA-256 稳定随机流，并将 quality 与 behavior 随机源分离，保证数据质量不受行为表现影响。

## 自动证据

综合生活能力详情包含代表性坐站动作参数。专注详情包含：

```text
segments: focused / deviating / distracted / off_task
events: distraction / prompt / task_switch / recovery / completion
```

首次分心时间必须等于第一条 `distraction` 事件时间；所有任务片段必须连续覆盖整个任务时长。

## 工具

```bash
python3 tools/generate_demo_details.py
python3 tools/validate_demo_data.py
```

生成器从已审核的周汇总确定性重建周详情。校验器检查周连续性、ISO 周编号、详情完整性、事件与周指标一致性，以及公开数据边界。

## 未来真实数据

真实数据只能写入未提交的 `runtime/` 或 `~/Library/Application Support/SISP/`。未来可实现 `ApiDataRepository` 替换当前 `JsonDataRepository`，页面和六个动态视图不需要改变。
