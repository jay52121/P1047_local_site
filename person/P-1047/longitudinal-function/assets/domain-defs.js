export const DOMAINS = {
  life: { label: "综合生活能力", available: true },
  emotion: { label: "心理情绪状态", available: false },
  cognition: { label: "认知行为状态", available: false },
  sleep: { label: "睡眠与生活节律", available: false },
  attention: { label: "专注与学习状态", available: false },
  participation: { label: "活动与社会参与", available: false },
};

export const LIFE_METRICS = {
  transfer: { label: "起居转移能力", field: "transfer", risk: false, description: "反映起身、坐下与位置转换相关运动表现的长期相对变化。" },
  walking: { label: "行走移动能力", field: "walking", risk: false, description: "反映日常移动速度、转身效率、停顿与步态节律的长期相对变化。" },
  balance: { label: "平衡稳定能力", field: "balance", risk: false, description: "反映站起、转身和移动过程中姿势稳定性与左右控制的长期相对变化。" },
  strength: { label: "下肢发力能力", field: "strength", risk: false, description: "由下肢伸展速度、发力阶段时长和支撑策略等长期特征综合估计。" },
  fallRisk: { label: "跌倒相关风险", field: "fallRisk", risk: true, description: "由移动、平衡、转移、下肢发力和周内波动共同形成的个人相对风险变化。" },
};

export const LIFE_EVIDENCE = {
  transfer: [["位置 A · 转移完成时间", "transferCompletionSec", "s", false], ["位置 A · 主要发力阶段", "powerPhaseSec", "s", false], ["位置 A · 手部支撑率", "handSupportRatePct", "%", false], ["位置 A · 重试率", "retryRatePct", "%", false], ["位置 A · 动作流畅度", "movementFluency", "", true]],
  walking: [["位置 B · 归一化移动速度", "walkingSpeedBodyLengthSec", " BL/s", true], ["位置 B · 180°转身时间", "turn180Sec", "s", false], ["位置 B · 移动停顿率", "walkingPauseRatePct", "%", false], ["位置 D · 单步时间", "singleStepSec", "s", false]],
  balance: [["位置 A · 站起后稳定", "standingStabilizationSec", "s", false], ["位置 C · 转身后稳定", "postTurnStabilizationSec", "s", false], ["位置 C · 横向摆动", "lateralSwayHeightPct", "%", false], ["位置 C · 左右不对称", "leftRightAsymmetryPct", "%", false]],
  strength: [["位置 A · 主要发力阶段", "powerPhaseSec", "s", false], ["膝伸展峰值速度", "kneeExtensionPeakDegSec", "°/s", true], ["髋伸展峰值速度", "hipExtensionPeakDegSec", "°/s", true], ["位置 A · 手部支撑率", "handSupportRatePct", "%", false], ["位置 D · 单步时间", "singleStepSec", "s", false]],
  fallRisk: [["起居转移能力", "transfer", "", true, "indexes"], ["行走移动能力", "walking", "", true, "indexes"], ["平衡稳定能力", "balance", "", true, "indexes"], ["下肢发力能力", "strength", "", true, "indexes"], ["跨位置周内波动", "crossLocationCvPct", "%", false]],
};

export const LIFE_SECONDARY = {
  transfer: [["膝关节运动表现", "knee"], ["髋关节运动表现", "hip"], ["动作协调性", "coordination"]],
  walking: [["左右对称性", "symmetry"], ["动作协调性", "coordination"]],
  balance: [["左右对称性", "symmetry"], ["动作协调性", "coordination"]],
  strength: [["膝关节运动表现", "knee"], ["髋关节运动表现", "hip"]],
  fallRisk: [["膝关节运动表现", "knee"], ["髋关节运动表现", "hip"], ["左右对称性", "symmetry"], ["动作协调性", "coordination"]],
};
