from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional

from .aggregation import effective_category_count, exposure_rate, median_or_none, pooled_ratio_pct
from .common import clamp, mad, median
from .metric_specs import DOMAIN_INDEXES
from .normalization import build_baselines, calculate_indexes
from .randomness import stable_rng


PROVENANCE = {"sourceType": "simulation", "calculationMode": "generated-from-events", "calculationVersion": "v2-events-1", "evidenceOrigin": "generated"}
ANCHORS = {
    "cognition": {"2025-W46", "2026-W06", "2026-W16", "2026-W33"},
    "sleep": {"2025-W46", "2026-W06", "2026-W16", "2026-W33"},
    "participation": {"2025-W46", "2026-W22", "2026-W29", "2026-W33"},
}


def rounded(value: Optional[float], digits: int = 4):
    return None if value is None else round(float(value), digits)


def summary_week(scenario, expected, valid, confidence, metrics, indexes, components):
    event = scenario.event
    return {
        "weekId": scenario.week_id, "weekIndex": scenario.week_index, "weekStart": scenario.week_start, "weekEnd": scenario.week_end,
        "status": scenario.status, "dataStatus": "sufficient", "provisional": scenario.status == "in_progress",
        "observedThroughDate": scenario.observed_through_date, "expectedUnits": expected, "validUnits": valid,
        "confidencePct": rounded(confidence), "metricConfidencePct": {key: rounded(confidence) for key in indexes},
        "phase": scenario.phase, "event": event.label if event else None, "eventKind": event.kind if event else None,
        "note": "当前周数据截至 2026-08-13，结果为暂定" if scenario.status == "in_progress" else None,
        "metrics": {key: rounded(value) for key, value in metrics.items()},
        "indexes": {key: rounded(value) for key, value in indexes.items()},
        "indexComponents": {key: {metric: rounded(value) for metric, value in values.items()} for key, values in components.items()},
    }


def finalize(domain: str, scenario_weeks, lite_weeks: List[dict], metric_rows: List[dict], expected_units: List[int]):
    baselines = build_baselines(metric_rows)
    weeks = []
    for scenario, lite, metrics, expected in zip(scenario_weeks, lite_weeks, metric_rows, expected_units):
        indexes, components = calculate_indexes(metrics, baselines, DOMAIN_INDEXES[domain])
        weeks.append(summary_week(scenario, expected, expected, lite["confidencePct"], metrics, indexes, components))
        lite["weekAggregate"] = {"metrics": {key: rounded(value) for key, value in metrics.items()}}
    summary = {"schemaVersion": "1.0", "personId": "P-1047", "domain": domain, **PROVENANCE, "baseline": {"weekIds": [week.week_id for week in scenario_weeks[:5]]}, "weeks": weeks}
    evidence = {"schemaVersion": "1.0", "personId": "P-1047", "domain": domain, **PROVENANCE, "detailLevel": "lite", "weeks": lite_weeks}
    full = {week["weekId"]: {"schemaVersion": "1.0", "personId": "P-1047", "domain": domain, **PROVENANCE, **week, "detailLevel": "full"} for week in lite_weeks if week["weekId"] in ANCHORS[domain]}
    return summary, evidence, full


COGNITION_TASKS = {
    "prepare_outing": ["change_clothes", "get_phone", "get_keys", "put_on_shoes", "leave_home"],
    "make_tea": ["prepare_cup", "get_water", "add_tea", "pour_water", "finish"],
    "organize_medication": ["open_box", "check_day", "select_dose", "place_dose", "close_box", "confirm"],
}


def generate_cognition(scenario_weeks):
    lite_weeks, metric_rows, expected_units = [], [], []
    for scenario in scenario_weeks:
        sessions = []
        tasks = list(COGNITION_TASKS)
        if scenario.status == "in_progress": tasks.append("prepare_outing")
        for order, task in enumerate(tasks):
            rng = stable_rng("P-1047", "cognition", scenario.week_id, task, order, "behavior")
            b = clamp(scenario.burdens["cognition"] + (0.05 if task == "organize_medication" else -0.02 if task == "make_tea" else 0) + rng.gauss(0, .018), 0, .9)
            expected = COGNITION_TASKS[task]
            startup = clamp((24 if task == "organize_medication" else 16 if task == "make_tea" else 18) + 70 * b + rng.gauss(0, 3), 8, 75)
            omission = 1 if rng.random() < .01 + .48 * b else 0
            repeat = 1 if rng.random() < .02 + .45 * b else 0
            prompt = 1 if omission and rng.random() < .25 + .7 * b else 0
            hesitation_count = sum(rng.random() < .08 + .95 * b for _ in expected)
            hesitation = hesitation_count * (2 + 18 * b) / len(expected)
            coverage = (len(expected) - omission) / len(expected) * 100
            order_integrity = clamp(100 - 38 * b - 8 * repeat + rng.gauss(0, 2), 55, 100)
            self_corrected = 1 if omission and not prompt and rng.random() < .88 - .65 * b else 0
            correction_rate = self_corrected / omission * 100 if omission else clamp(96 - 62 * b + rng.gauss(0, 3), 45, 100)
            correction_latency = 6 + 45 * b if self_corrected else clamp(8 + 35 * b + rng.gauss(0, 2), 5, 45)
            completed = rng.random() < .99 - .30 * b
            # The two comparison anchors are authored as observable events, then
            # flow through the same weekly aggregation/index calculation as every
            # other week. This keeps the 30-second demo story deterministic.
            if scenario.week_id == "2026-W06":
                omission, repeat, prompt, self_corrected, completed = 1, 1, 1, 0, True
                hesitation_count = max(2, hesitation_count)
                hesitation = hesitation_count * 8 / len(expected)
                coverage, order_integrity = (len(expected) - 1) / len(expected) * 100, min(order_integrity, 72)
                correction_rate, correction_latency = 0.0, None
            elif scenario.week_id == "2026-W16":
                omission, repeat, prompt, self_corrected, completed = 1, 0, 0, 1, True
                hesitation_count = min(1, hesitation_count)
                hesitation = hesitation_count * 2 / len(expected)
                coverage, order_integrity = 100.0, max(order_integrity, 97)
                correction_rate, correction_latency = 100.0, 7.0
            actual = list(expected)
            if omission: actual.pop(2 if len(actual) > 4 else 1)
            if repeat: actual.insert(2, actual[1])
            if omission and (self_corrected or prompt): actual.insert(-1, expected[2 if len(expected) > 4 else 1])
            result = {
                "startupLatencySec": rounded(startup), "stepCoveragePct": rounded(coverage), "completed": completed,
                "orderIntegrityPct": rounded(order_integrity), "repeatRatePct": rounded(repeat / len(expected) * 100),
                "hesitationSecPerStep": rounded(hesitation), "selfCorrectionRatePct": rounded(correction_rate),
                "correctionLatencySec": rounded(correction_latency), "promptPerStep": rounded(prompt / len(expected)),
                "unpromptedCompletion": completed and prompt == 0,
            }
            events = []
            if hesitation_count: events.append({"type": "hesitation", "label": f"犹豫 {hesitation_count} 次"})
            if repeat: events.append({"type": "repeat", "step": actual[1]})
            if omission: events.append({"type": "omission", "step": expected[2 if len(expected) > 4 else 1]})
            if prompt: events.append({"type": "prompt", "label": "外部提示"})
            if self_corrected or prompt: events.append({"type": "correction", "label": "返回正确路径"})
            sessions.append({"taskType": task, "expectedSteps": expected, "actualSteps": actual, "events": events, "result": result})
        results = [session["result"] for session in sessions]
        values = lambda key: [result[key] for result in results if result[key] is not None]
        metrics = {
            "startupLatencySec": median(values("startupLatencySec")), "stepCoveragePct": median(values("stepCoveragePct")),
            "taskCompletionRatePct": sum(result["completed"] for result in results) / len(results) * 100,
            "orderIntegrityPct": median(values("orderIntegrityPct")), "repeatRatePct": median(values("repeatRatePct")),
            "hesitationSecPerStep": median(values("hesitationSecPerStep")), "selfCorrectionRatePct": median_or_none(values("selfCorrectionRatePct")),
            "correctionLatencySec": median_or_none(values("correctionLatencySec")), "promptPerStep": median(values("promptPerStep")),
            "unpromptedCompletionRatePct": sum(result["unpromptedCompletion"] for result in results) / len(results) * 100,
        }
        confidence = 94 + stable_rng("P-1047", "cognition", scenario.week_id, "quality").uniform(-1.4, 1.4)
        lite_weeks.append({"weekId": scenario.week_id, "detailLevel": "lite", "confidencePct": rounded(confidence), "sessions": sessions})
        metric_rows.append(metrics); expected_units.append(len(sessions))
    return finalize("cognition", scenario_weeks, lite_weeks, metric_rows, expected_units)


def generate_sleep(scenario_weeks):
    lite_weeks, expected_units = [], []
    weekday = (-.01, 0, .01, 0, .01, .03, -.04)
    for scenario in scenario_weeks:
        count = 4 if scenario.status == "in_progress" else 7
        nights = []
        start = date.fromisoformat(scenario.week_start)
        for day_index in range(count):
            day = start + timedelta(days=day_index); rng = stable_rng("P-1047", "sleep", day.isoformat(), "behavior")
            b = clamp(scenario.burdens["sleep"] + weekday[day_index] + rng.gauss(0, .018), 0, .9)
            bed = clamp(615 + 35 * b + rng.gauss(0, 7 + 12 * b), 570, 720)
            latency = clamp(18 + 55 * b + rng.gauss(0, 4), 8, 75); onset = bed + latency
            wake = clamp(1120 + 18 * b + rng.gauss(0, 7 + 15 * b), onset + 320, 1260); rise = min(1290, wake + clamp(12 + 12 * b + rng.gauss(0, 3), 5, 35))
            lam = .45 + 3.1 * b; awakening_count = min(4, int(lam) + int(rng.random() < lam % 1))
            awakenings = []
            for index in range(awakening_count):
                at = onset + 65 + (index + 1) * max(45, (wake - onset - 120) / (awakening_count + 1))
                duration = clamp(4 + 23 * b + rng.gauss(0, 2.5), 3, 35)
                left = rng.random() < .22 + .78 * b
                awakenings.append({"startMin": rounded(at), "endMin": rounded(min(wake - 3, at + duration)), "outOfBedMin": rounded(duration * rng.uniform(.55, .9) if left else 0)})
            naps = []
            if rng.random() < .14 + .85 * b:
                nap_start = rng.uniform(60, 250); nap_duration = clamp(12 + 58 * b + rng.gauss(0, 6), 10, 75)
                naps.append({"startMin": rounded(nap_start), "endMin": rounded(nap_start + nap_duration)})
            day_observed = 900 + rng.uniform(-35, 35); low_rate = clamp(14 + 28 * b + rng.gauss(0, 2), 12, 38)
            window = wake - onset; awake = sum(item["endMin"] - item["startMin"] for item in awakenings); estimated = window - awake
            nights.append({"date": day.isoformat(), "valid": True, "bedEntryMin": rounded(bed), "sleepOnsetMin": rounded(onset), "finalWakeMin": rounded(wake), "finalRiseMin": rounded(rise), "awakenings": awakenings, "napIntervals": naps, "dayObservedMin": rounded(day_observed), "dayLowActivityMin": rounded(day_observed * low_rate / 100), "dayActiveMin": rounded(day_observed * clamp(92 - 19 * b, 76, 94) / 100), "sleepWindowMin": rounded(window), "estimatedSleepMin": rounded(estimated), "sleepMidpointMin": rounded(onset + window / 2)})
        confidence = 95 + stable_rng("P-1047", "sleep", scenario.week_id, "quality").uniform(-1.3, 1.3)
        lite_weeks.append({"weekId": scenario.week_id, "detailLevel": "lite", "confidencePct": rounded(confidence), "nights": nights})
        expected_units.append(count)
    baseline_midpoint = median(night["sleepMidpointMin"] for week in lite_weeks[:5] for night in week["nights"])
    metric_rows = []
    for week in lite_weeks:
        nights = week["nights"]; onsets = [n["sleepOnsetMin"] for n in nights]; rises = [n["finalRiseMin"] for n in nights]; latencies = [n["sleepOnsetMin"] - n["bedEntryMin"] for n in nights]
        total_window = sum(n["sleepWindowMin"] for n in nights); total_sleep = sum(n["estimatedSleepMin"] for n in nights); awakenings = [a for n in nights for a in n["awakenings"]]
        nap_min = sum(i["endMin"] - i["startMin"] for n in nights for i in n["napIntervals"]); day_obs = sum(n["dayObservedMin"] for n in nights); day_low = sum(n["dayLowActivityMin"] for n in nights); day_active = sum(n["dayActiveMin"] for n in nights); night_active = sum(a["endMin"] - a["startMin"] for a in awakenings)
        metrics = {"onsetMADMin": mad(onsets), "riseMADMin": mad(rises), "sleepLatencyMin": median(latencies), "sleepLatencyMADMin": mad(latencies), "sleepContinuityPct": total_sleep / total_window * 100, "awakeningsPerNight": len(awakenings) / len(nights), "outOfBedMinPerNight": sum(a["outOfBedMin"] for a in awakenings) / len(nights), "napMinPerDay": nap_min / len(nights), "dayLowActivityRatePct": day_low / day_obs * 100, "midpointDeviationMin": median(abs(n["sleepMidpointMin"] - baseline_midpoint) for n in nights), "dayActivitySharePct": day_active / (day_active + night_active) * 100}
        week["representativeNightDate"] = min(nights, key=lambda n: abs(n["sleepOnsetMin"] - median(onsets)) + abs(n["finalRiseMin"] - median(rises)))["date"]
        metric_rows.append(metrics)
    return finalize("sleep", scenario_weeks, lite_weeks, metric_rows, expected_units)


ZONES = ("bedroom", "living_room", "dining_room", "bathroom", "doorway", "outside")
CATEGORIES = ("self_care", "meal", "household", "leisure", "rehab_exercise", "outdoor", "social")


def generate_participation(scenario_weeks):
    lite_weeks, metric_rows, expected_units = [], [], []
    for scenario in scenario_weeks:
        count = 4 if scenario.status == "in_progress" else 7; start = date.fromisoformat(scenario.week_start); days = []
        for day_index in range(count):
            day = start + timedelta(days=day_index); rng = stable_rng("P-1047", "participation", day.isoformat(), "behavior")
            b = clamp(scenario.burdens["participation"] + ( -.05 if day_index == 5 else .04 if day_index == 6 else 0) + rng.gauss(0, .02), 0, .95)
            observed = clamp(720 + rng.gauss(0, 35), 600, 840); low_day = rng.random() < .02 + .48 * b
            if scenario.week_id == "2026-W22": low_day = day_index < 3
            elif scenario.week_id == "2026-W29": low_day = False
            outing = 0 if low_day else int(rng.random() < clamp(.84 - 1.04 * b + (.08 if day_index == 5 else 0), .08, .88)); outing_count = outing + int(outing and rng.random() < .18 * (1 - b)); outside = sum(clamp(90 - 95 * b + rng.gauss(0, 10), 15, 120) for _ in range(outing_count))
            if scenario.week_id == "2026-W29" and day_index < 5 and outing_count == 0:
                outing_count = 1; outside = clamp(82 - 65 * b + rng.gauss(0, 6), 20, 95)
            indoor = observed - outside; weights = {"bedroom": .26 + .34*b, "living_room": .31 - .09*b, "dining_room": .18 - .03*b, "bathroom": .09, "doorway": .025 + .01*outing_count}; total_weight = sum(weights.values()); zone = {key: indoor * value / total_weight for key, value in weights.items()}; zone["outside"] = outside
            meaningful = rng.uniform(25, 58) if low_day else clamp(270 - 150*b + rng.gauss(0, 18), 100, 300); episodes = rng.randint(1, 3) if low_day else rng.randint(4, 9)
            base = {"self_care":.17,"meal":.20,"household":.18*(1-.45*b),"leisure":.16*(1-.55*b),"rehab_exercise":.11*(1-.2*b),"outdoor":.10*(1-.85*b),"social":.08*(1-.45*b)}; weight_sum=sum(base.values()); cats={k:(meaningful*v/weight_sum if meaningful*v/weight_sum>=8 else 0) for k,v in base.items()}; cat_sum=sum(cats.values()) or 1; cats={k:v*meaningful/cat_sum for k,v in cats.items()}
            interactions = int(clamp(round(5.2 - 3.1*b + rng.gauss(0,.6)), 0, 7)); interaction_minutes=sum(clamp(9+8*(1-b)+rng.gauss(0,2.5),3,30) for _ in range(interactions)); initiated=sum(rng.random()<clamp(.68-.34*b,.28,.72) for _ in range(interactions)); transitions=int(clamp(round(16-10*b+rng.gauss(0,1)),4,18)); participating=meaningful>=60 or episodes>=4
            days.append({"date":day.isoformat(),"valid":True,"observedMinutes":rounded(observed),"zoneMinutes":{k:rounded(v) for k,v in zone.items()},"transitionCount":transitions,"outsideMinutes":rounded(outside),"outingCount":outing_count,"activityMinutesByCategory":{k:rounded(v) for k,v in cats.items()},"meaningfulActivityMinutes":rounded(meaningful),"meaningfulActivityEpisodes":episodes,"interactionMinutes":rounded(interaction_minutes),"interactionEpisodes":interactions,"initiatedInteractionEpisodes":initiated,"participatingDay":participating})
        observed=sum(d["observedMinutes"] for d in days); zone_total={z:sum(d["zoneMinutes"][z] for d in days) for z in ZONES}; cat_total={c:sum(d["activityMinutesByCategory"][c] for d in days) for c in CATEGORIES}; interaction_count=sum(d["interactionEpisodes"] for d in days); streak=best=current=0
        for d in days: current=0 if d["participatingDay"] else current+1; best=max(best,current)
        metrics={"effectiveZoneCount":effective_category_count(zone_total),"zoneTransitionsPer8h":exposure_rate(sum(d["transitionCount"] for d in days),observed),"activityEffectiveTypes":effective_category_count(cat_total),"activityCategoryCount":sum(v>0 for v in cat_total.values()),"outsideMinutesPerValidDay":sum(d["outsideMinutes"] for d in days)/len(days),"outingDaysRatePct":sum(d["outingCount"]>0 for d in days)/len(days)*100,"outingsPerValidDay":sum(d["outingCount"] for d in days)/len(days),"interactionMinutesPer8h":exposure_rate(sum(d["interactionMinutes"] for d in days),observed),"interactionEpisodesPer8h":exposure_rate(interaction_count,observed),"initiatedInteractionRatePct":pooled_ratio_pct([sum(d["initiatedInteractionEpisodes"] for d in days)],[interaction_count]),"participatingDaysRatePct":sum(d["participatingDay"] for d in days)/len(days)*100,"longestLowParticipationStreakDays":best}
        confidence=94.5+stable_rng("P-1047","participation",scenario.week_id,"quality").uniform(-1.5,1.5); rep=min(days,key=lambda d:abs(d["outsideMinutes"]-metrics["outsideMinutesPerValidDay"]))["date"]
        lite_weeks.append({"weekId":scenario.week_id,"detailLevel":"lite","confidencePct":rounded(confidence),"days":days,"representativeDay":rep}); metric_rows.append(metrics); expected_units.append(count)
    summary,evidence,full=finalize("participation",scenario_weeks,lite_weeks,metric_rows,expected_units)
    for detail in full.values():
        for day in detail["days"]:
            cursor=0.0; segments=[]
            for zone,value in day["zoneMinutes"].items():
                if value<=0: continue
                segments.append({"startMin":rounded(cursor),"endMin":rounded(cursor+value),"zone":zone}); cursor+=value
            day["locationSegments"]=segments
    return summary,evidence,full
