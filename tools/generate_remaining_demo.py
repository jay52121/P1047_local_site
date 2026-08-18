#!/usr/bin/env python3
import json
from pathlib import Path

from demo_generation.scenario import build_scenario
from demo_generation.showcase import generate_cognition, generate_participation, generate_sleep

ROOT = Path(__file__).resolve().parents[1]

def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def mapping(domain, raw, indexes):
    return {"schemaVersion":"1.0","domain":domain,"rawMetrics":{key:{"label":label,"unit":unit,"higherIsBetter":higher,"source":source} for key,(label,unit,higher,source) in raw.items()},"indexes":indexes}

MAPPINGS={
"cognition":mapping("cognition",{
"startupLatencySec":("任务启动延迟"," sec",False,"task sessions"),"stepCoveragePct":("步骤覆盖率","%",True,"task paths"),"taskCompletionRatePct":("任务完成率","%",True,"task sessions"),"orderIntegrityPct":("步骤顺序完整度","%",True,"task paths"),"repeatRatePct":("重复步骤率","%",False,"task paths"),"hesitationSecPerStep":("单步犹豫时长"," sec",False,"hesitation events"),"selfCorrectionRatePct":("自主纠正率","%",True,"correction events"),"correctionLatencySec":("纠正延迟"," sec",False,"correction events"),"promptPerStep":("单步提示次数","",False,"prompt events"),"unpromptedCompletionRatePct":("无提示完成率","%",True,"task sessions")},{
"taskInitiation":{"rawMetrics":["startupLatencySec"]},"taskCompleteness":{"rawMetrics":["stepCoveragePct","taskCompletionRatePct"]},"executionOrganization":{"rawMetrics":["orderIntegrityPct","repeatRatePct","hesitationSecPerStep"]},"selfCorrection":{"rawMetrics":["selfCorrectionRatePct","correctionLatencySec"]},"promptIndependence":{"rawMetrics":["promptPerStep","unpromptedCompletionRatePct"]}}),
"sleep":mapping("sleep",{
"onsetMADMin":("入睡时间波动"," min",False,"sleep nights"),"riseMADMin":("起床时间波动"," min",False,"sleep nights"),"sleepLatencyMin":("入睡延迟"," min",False,"sleep nights"),"sleepLatencyMADMin":("入睡延迟波动"," min",False,"sleep nights"),"sleepContinuityPct":("睡眠连续性","%",True,"sleep windows"),"awakeningsPerNight":("夜醒次数"," 次/夜",False,"awakening events"),"outOfBedMinPerNight":("夜间离床"," min/夜",False,"awakening events"),"napMinPerDay":("午睡时长"," min/日",False,"nap intervals"),"dayLowActivityRatePct":("白天低活动占比","%",False,"day observations"),"midpointDeviationMin":("睡眠中点偏离"," min",False,"sleep nights"),"dayActivitySharePct":("昼间活动占比","%",True,"day observations")},{
"scheduleRegularity":{"rawMetrics":["onsetMADMin","riseMADMin"]},"sleepOnsetStability":{"rawMetrics":["sleepLatencyMin","sleepLatencyMADMin"]},"nightContinuity":{"rawMetrics":["sleepContinuityPct","awakeningsPerNight","outOfBedMinPerNight"]},"daytimeWakefulness":{"rawMetrics":["napMinPerDay","dayLowActivityRatePct"]},"circadianAlignment":{"rawMetrics":["midpointDeviationMin","dayActivitySharePct"]}}),
"participation":mapping("participation",{
"effectiveZoneCount":("有效活动空间"," 个",True,"zone minutes"),"zoneTransitionsPer8h":("区域转换频率"," 次/8h",True,"zone transitions"),"activityEffectiveTypes":("有效活动类型"," 类",True,"activity minutes"),"activityCategoryCount":("活动类别数"," 类",True,"activity categories"),"outsideMinutesPerValidDay":("日均外出时间"," min/日",True,"outside segments"),"outingDaysRatePct":("外出天数占比","%",True,"outing events"),"outingsPerValidDay":("日均外出次数"," 次/日",True,"outing events"),"interactionMinutesPer8h":("互动时长"," min/8h",True,"interaction sessions"),"interactionEpisodesPer8h":("互动频率"," 次/8h",True,"interaction sessions"),"initiatedInteractionRatePct":("主动互动占比","%",True,"interaction sessions"),"participatingDaysRatePct":("参与日占比","%",True,"day summaries"),"longestLowParticipationStreakDays":("最长低参与连续日"," 天",False,"day summaries")},{
"spaceRange":{"rawMetrics":["effectiveZoneCount","zoneTransitionsPer8h"]},"activityDiversity":{"rawMetrics":["activityEffectiveTypes","activityCategoryCount"]},"outsideParticipation":{"rawMetrics":["outsideMinutesPerValidDay","outingDaysRatePct","outingsPerValidDay"]},"socialParticipation":{"rawMetrics":["interactionMinutesPer8h","interactionEpisodesPer8h","initiatedInteractionRatePct"]},"participationContinuity":{"rawMetrics":["participatingDaysRatePct","longestLowParticipationStreakDays"]}})}

def main():
    scenario=build_scenario()
    for domain,builder in (("cognition",generate_cognition),("sleep",generate_sleep),("participation",generate_participation)):
        summary,evidence,full=builder(scenario); base=ROOT/"data/demo/P-1047"/domain
        write(base/"weekly-summary.json",summary); write(base/"evidence-lite.json",evidence); write(base/"metric-mapping.json",MAPPINGS[domain])
        for week_id,payload in full.items(): write(base/"weeks"/f"{week_id}.json",payload)
        print(f"Generated {domain}: 40 lite weeks, {len(full)} full weeks")

if __name__=="__main__": main()
