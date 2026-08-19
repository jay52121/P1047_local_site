from __future__ import annotations

from datetime import date, timedelta
from math import exp

from .common import clamp, mad, median
from .randomness import stable_rng

TASKS = {
    "homework": ("课后作业", 22, 48), "piano": ("钢琴练习", 14, 35),
    "reading": ("独立阅读", 12, 32), "writing": ("汉字书写", 10, 28),
    "building": ("益智拼搭", 18, 45), "tidying": ("房间整理", 8, 22),
}
INDEXES = ("sustainedEngagement", "effectiveFocus", "distractionControl", "recoveryIndependence", "taskCompletion")
DISPLAY_FLOORS = {"firstShare":8,"focusRate":5,"distractionRate":.7,"offTaskRate":4,"leaveRate":.35,"autonomousRate":10,"recoveryLatency":1,"promptRate":.35,"completion":10}


def rounded(value): return None if value is None else round(float(value), 4)


def poisson(rng, lam):
    limit, product, count = exp(-lam), 1.0, 0
    while product > limit:
        count += 1; product *= rng.random()
    return max(0, count - 1)


def burden_for(index):
    if index <= 4: return .18 + index * .012
    if index <= 11: return .24 + (index - 4) * .06
    if index <= 19: return .66 - (index - 11) * .055
    return .25 + (index - 19) * .008


def build_session(week_id, day, order, task_id, burden):
    label, low, high = TASKS[task_id]; rng = stable_rng("C-2308", "attention-v2", week_id, day.isoformat(), task_id, order)
    duration = clamp(rng.uniform(low, high) * (1 - .08 * burden), low * .82, high)
    load = clamp(burden + {"homework":.08,"writing":.06,"piano":.02,"reading":0,"building":-.08,"tidying":-.12}[task_id] + rng.gauss(0,.055), .03, .92)
    distraction_count = min(5, poisson(rng, .12 + 2.75 * load)); early_end = rng.random() < .02 + .18 * load
    actual_duration = duration * rng.uniform(.62,.88) if early_end else duration
    event_times = sorted(rng.uniform(3, max(3.2, actual_duration - 3)) for _ in range(distraction_count))
    segments, events, cursor, prompts, autonomous, recovery_latencies, off_task = [], [], 0.0, 0, 0, [], 0.0
    for event_index, at in enumerate(event_times):
        if at < cursor + 1: at = cursor + 1
        if at >= actual_duration - 1: continue
        if at > cursor: segments.append({"startMin":rounded(cursor),"endMin":rounded(at),"state":"focused"})
        kind = rng.choices(["deviating","distracted","off_task"], weights=[.42,.42,.16 + .22*load])[0]
        length = clamp(rng.uniform(0.7, 2.4) + (5.5 * load if kind == "off_task" else 1.5 * load), .6, min(9, actual_duration-at))
        end = min(actual_duration, at + length); segments.append({"startMin":rounded(at),"endMin":rounded(end),"state":kind}); off_task += end-at
        events.append({"minute":rounded(at),"type":"distraction","subtype":kind,"order":event_index+1})
        if kind == "off_task" and task_id != "tidying" and rng.random() < .58: events.append({"minute":rounded(at+.15),"type":"leave_seat"})
        self_recover = rng.random() < clamp(.88 - .62*load,.2,.9)
        recovered = self_recover or rng.random() < .88
        if recovered:
            if self_recover: autonomous += 1
            else: prompts += 1; events.append({"minute":rounded(max(at,end-.45)),"type":"prompt"})
            events.append({"minute":rounded(end),"type":"recovery","origin":"self" if self_recover else "prompt"}); recovery_latencies.append(end-at)
        cursor=end
    if cursor < actual_duration: segments.append({"startMin":rounded(cursor),"endMin":rounded(actual_duration),"state":"focused"})
    if rng.random() < .08 + .25*load: events.append({"minute":rounded(rng.uniform(2,max(2.1,actual_duration-2))),"type":"task_switch"})
    completed = not early_end and rng.random() > .04 + .12*load
    events.append({"minute":rounded(actual_duration),"type":"completion" if completed else "early_end"})
    focused=sum(s["endMin"]-s["startMin"] for s in segments if s["state"]=="focused")
    first=event_times[0] if event_times else None
    return {"sessionId":f"{week_id}-{day.isoformat()}-{task_id}-{order+1:02d}","date":day.isoformat(),"startTime":f"{15+min(order,4):02d}:{rng.choice((0,10,20,30,40,50)):02d}","taskId":task_id,"taskLabel":label,"plannedDurationMin":rounded(duration),"durationMin":rounded(actual_duration),"valid":True,"segments":segments,"events":events,"result":{"firstDistractionMin":rounded(first),"focusedRatePct":rounded(focused/actual_duration*100),"distractionCount":len(event_times),"offTaskMin":rounded(off_task),"leaveSeatCount":sum(e["type"]=="leave_seat" for e in events),"taskSwitchCount":sum(e["type"]=="task_switch" for e in events),"autonomousRecoveryRatePct":rounded(autonomous/len(event_times)*100) if event_times else 100.0,"recoveryLatencyMin":rounded(median(recovery_latencies)) if recovery_latencies else 0.0,"promptCount":prompts,"completed":completed,"unpromptedCompletion":completed and prompts==0,"earlyEnd":early_end}}


def aggregate(sessions):
    total=sum(s["durationMin"] for s in sessions); focus=sum(s["durationMin"]*s["result"]["focusedRatePct"]/100 for s in sessions); distractions=sum(s["result"]["distractionCount"] for s in sessions)
    first=[s["result"]["firstDistractionMin"]/s["durationMin"]*100 for s in sessions if s["result"]["firstDistractionMin"] is not None]
    recover=[s["result"]["autonomousRecoveryRatePct"] for s in sessions if s["result"]["distractionCount"]]
    return {"focusRatePct":focus/total*100,"firstDistractionSharePct":median(first) if first else 100.0,"distractionsPer30Min":distractions/total*30,"offTaskRatePct":sum(s["result"]["offTaskMin"] for s in sessions)/total*100,"leaveSeatPer30Min":sum(s["result"]["leaveSeatCount"] for s in sessions)/total*30,"autonomousRecoveryRatePct":median(recover) if recover else 100.0,"recoveryLatencyMin":median(s["result"]["recoveryLatencyMin"] for s in sessions),"promptsPerSession":sum(s["result"]["promptCount"] for s in sessions)/len(sessions),"completionRatePct":sum(s["result"]["completed"] for s in sessions)/len(sessions)*100,"unpromptedCompletionRatePct":sum(s["result"]["unpromptedCompletion"] for s in sessions)/len(sessions)*100,"earlyEndRatePct":sum(s["result"]["earlyEnd"] for s in sessions)/len(sessions)*100}


def clock_add(start_time, minutes):
    hour, minute = map(int, start_time.split(":")); value = hour * 60 + minute + round(minutes)
    if value >= 1440: raise ValueError("Attention sessions must not cross midnight")
    return f"{value // 60:02d}:{value % 60:02d}"


def session_display_raw(session):
    result, duration = session["result"], session["durationMin"]
    first = result["firstDistractionMin"]
    return {"firstShare":100.0 if first is None else first/duration*100,"focusRate":result["focusedRatePct"],"distractionRate":result["distractionCount"]/duration*30,"offTaskRate":result["offTaskMin"]/duration*100,"leaveRate":result["leaveSeatCount"]/duration*30,"autonomousRate":result["autonomousRecoveryRatePct"] if result["distractionCount"] else None,"recoveryLatency":result["recoveryLatencyMin"] if result["distractionCount"] else None,"promptRate":result["promptCount"],"completion":100.0 if result["completed"] else 70.0 if result["earlyEnd"] else 82.0}


def add_display_summaries(details):
    baseline_sessions=[session for detail in details[:5] for session in detail["sessions"]]
    all_raw=[session_display_raw(session) for session in baseline_sessions]
    by_task={task_id:[session_display_raw(session) for session in baseline_sessions if session["taskId"]==task_id] for task_id in TASKS}
    def scales(rows,key):
        values=[row[key] for row in rows if row[key] is not None]
        if len(values)<3: values=[row[key] for row in all_raw if row[key] is not None]
        center=median(values); return center,max(1.4826*mad(values,center),DISPLAY_FLOORS[key])
    task_scales={task:{key:scales(rows,key) for key in DISPLAY_FLOORS} for task,rows in by_task.items()}
    lower={"distractionRate","offTaskRate","leaveRate","recoveryLatency","promptRate"}
    def normalized(raw,task,key):
        if raw[key] is None:return None
        center,scale=task_scales[task][key]; direction=-1 if key in lower else 1
        return clamp(100+10*direction*(raw[key]-center)/scale,70,130)
    for detail in details:
        by_date={}
        for session in detail["sessions"]:
            session["endTime"]=clock_add(session["startTime"],session["durationMin"])
            session["result"]["terminalStatus"]="completed" if session["result"]["completed"] else "early_end" if session["result"]["earlyEnd"] else "incomplete"
            raw=session_display_raw(session); task=session["taskId"]
            components={"engagement":normalized(raw,task,"firstShare"),"effectiveFocus":normalized(raw,task,"focusRate"),"distractionControl":None,"recovery":None,"completion":normalized(raw,task,"completion")}
            control_keys=[("distractionRate",.45),("offTaskRate",.35)]+([] if task=="tidying" else [("leaveRate",.20)])
            control=[(normalized(raw,task,key),weight) for key,weight in control_keys];components["distractionControl"]=sum(v*w for v,w in control)/sum(w for v,w in control)
            if raw["autonomousRate"] is not None:
                recovery=[(normalized(raw,task,"autonomousRate"),.5),(normalized(raw,task,"recoveryLatency"),.25),(normalized(raw,task,"promptRate"),.25)];components["recovery"]=sum(v*w for v,w in recovery)/sum(w for v,w in recovery)
            weights={"engagement":.25,"effectiveFocus":.25,"distractionControl":.20,"recovery":.15,"completion":.15}; available=[(components[k],w) for k,w in weights.items() if components[k] is not None]
            session["sessionComponentScores"]={k:rounded(v) for k,v in components.items()};session["sessionScore"]=rounded(sum(v*w for v,w in available)/sum(w for _,w in available));by_date.setdefault(session["date"],[]).append(session)
        day_summaries=[]; start=date.fromisoformat(detail["weekStart"])
        for weekday in range(7):
            current=(start+timedelta(days=weekday)).isoformat(); sessions=sorted(by_date.get(current,[]),key=lambda item:item["startTime"])
            if not sessions: day_summaries.append({"date":current,"weekdayIndex":weekday,"observationStatus":"no_task","validSessionCount":0,"sessionIds":[],"dayScore":None,"dayBand":"no_task","componentScores":{},"representativeSessionId":None,"representativeReason":None,"topFactors":[]});continue
            weights=[s["durationMin"]**.5 for s in sessions]; mean=sum(s["sessionScore"]*w for s,w in zip(sessions,weights))/sum(weights); worst=min(s["sessionScore"] for s in sessions); score=.8*mean+.2*worst
            band="strong_good" if score>=108 else "good" if score>=96 else "watch" if score>=86 else "poor"
            component_scores={}
            for key in ("engagement","effectiveFocus","distractionControl","recovery","completion"):
                rows=[(s["sessionComponentScores"][key],w) for s,w in zip(sessions,weights) if s["sessionComponentScores"][key] is not None]
                component_scores[key]=rounded(sum(v*w for v,w in rows)/sum(w for _,w in rows)) if rows else None
            representative=min(sessions,key=lambda s:s["sessionScore"]) if band in {"watch","poor"} else min(sessions,key=lambda s:(abs(s["sessionScore"]-score),-s["durationMin"]))
            factors=[key for key,value in sorted(component_scores.items(),key=lambda item:999 if item[1] is None else item[1])[:2]]
            day_summaries.append({"date":current,"weekdayIndex":weekday,"observationStatus":"observed","validSessionCount":len(sessions),"sessionIds":[s["sessionId"] for s in sessions],"dayScore":rounded(score),"dayBand":band,"componentScores":component_scores,"representativeSessionId":representative["sessionId"],"representativeReason":"lowest_score" if band in {"watch","poor"} else "closest_to_day_score","topFactors":factors})
        scores=[d["dayScore"] for d in day_summaries if d["dayScore"] is not None]; center=median(scores); spread=mad(scores,center) if len(scores)>=3 else None
        counts={band:sum(d["dayBand"]==band for d in day_summaries) for band in ("strong_good","good","watch","poor","no_task","invalid","unobserved")}
        detail["daySummaries"]=day_summaries;detail["weekDaySummary"]={"strongGoodDays":counts["strong_good"],"goodDays":counts["good"],"watchDays":counts["watch"],"poorDays":counts["poor"],"noTaskDays":counts["no_task"],"invalidDays":counts["invalid"],"unobservedDays":counts["unobserved"],"dayScoreMedian":rounded(center),"dayScoreMad":rounded(spread),"stabilityLabel":None if spread is None else "周内稳定" if spread<=5 else "有一定波动" if spread<=10 else "周内波动明显"}


def generate_attention_showcase():
    start=date(2026,2,23); details=[]; metrics=[]
    task_ids=list(TASKS)
    for wi in range(24):
        ws=start+timedelta(weeks=wi); week_id=f"{ws.isocalendar().year}-W{ws.isocalendar().week:02d}"; rng=stable_rng("C-2308","attention-v2",week_id,"schedule"); b=burden_for(wi)
        day_count=rng.randint(3,6); day_offsets=sorted(rng.sample(range(7),day_count)); sessions=[]
        target=rng.randint(max(4,day_count),10)
        for di,offset in enumerate(day_offsets):
            count=1+int(len(sessions)+len(day_offsets)-di<target and rng.random()<.72)+int(len(sessions)+len(day_offsets)-di+1<target and rng.random()<.22)
            for order in range(min(3,count)):
                task_id=rng.choices(task_ids,weights=[1.35,1.05,1.15,1,1,.75])[0];sessions.append(build_session(week_id,ws+timedelta(days=offset),order,task_id,b))
        sessions=sessions[:10]; row=aggregate(sessions);metrics.append(row)
        phase="逐步适应期" if wi<5 else "压力上升期" if wi<12 else "策略支持恢复期"
        event="任务要求增加" if wi==8 else "家庭策略介入" if wi==12 else None
        details.append({"schemaVersion":"1.0","personId":"C-2308","domain":"attention","weekId":week_id,"weekIndex":wi+1,"weekStart":ws.isoformat(),"weekEnd":(ws+timedelta(days=6)).isoformat(),"status":"complete","phase":phase,"event":event,"validSessions":len(sessions),"confidencePct":rounded(94+rng.uniform(-1.8,1.8)),"sessions":sessions,"metrics":{k:rounded(v) for k,v in row.items()}})
    add_display_summaries(details)
    centers={k:median(row[k] for row in metrics[:5]) for k in metrics[0]}; floors={"focusRatePct":5,"firstDistractionSharePct":8,"distractionsPer30Min":.6,"offTaskRatePct":4,"leaveSeatPer30Min":.3,"autonomousRecoveryRatePct":10,"recoveryLatencyMin":1,"promptsPerSession":.35,"completionRatePct":8,"unpromptedCompletionRatePct":10,"earlyEndRatePct":6}
    directions={k:(-1 if k in {"distractionsPer30Min","offTaskRatePct","leaveSeatPer30Min","recoveryLatencyMin","promptsPerSession","earlyEndRatePct"} else 1) for k in centers}
    def norm(row,key): return clamp(100+10*directions[key]*(row[key]-centers[key])/max(1.4826*mad([m[key] for m in metrics[:5]],centers[key]),floors[key]),70,130)
    groups={"sustainedEngagement":(("firstDistractionSharePct",.45),("focusRatePct",.55)),"effectiveFocus":(("focusRatePct",.65),("offTaskRatePct",.35)),"distractionControl":(("distractionsPer30Min",.55),("leaveSeatPer30Min",.25),("offTaskRatePct",.2)),"recoveryIndependence":(("autonomousRecoveryRatePct",.5),("recoveryLatencyMin",.25),("promptsPerSession",.25)),"taskCompletion":(("completionRatePct",.45),("unpromptedCompletionRatePct",.4),("earlyEndRatePct",.15))}
    weeks=[]
    for detail,row in zip(details,metrics):
        indexes={key:sum(norm(row,metric)*weight for metric,weight in parts) for key,parts in groups.items()}
        weeks.append({key:detail[key] for key in ("weekId","weekIndex","weekStart","weekEnd","status","phase","event","validSessions","confidencePct")}|{"expectedUnits":len(detail["sessions"]),"validUnits":len(detail["sessions"]),"metrics":detail["metrics"],"indexes":{k:rounded(v) for k,v in indexes.items()}})
    summary={"schemaVersion":"1.0","personId":"C-2308","domain":"attention","sourceType":"simulation","calculationMode":"generated-from-events","calculationVersion":"v2-attention-demo-1","evidenceOrigin":"generated","baseline":{"weekIds":[w["weekId"] for w in weeks[:5]]},"weeks":weeks}
    return summary,{detail["weekId"]:detail for detail in details}
