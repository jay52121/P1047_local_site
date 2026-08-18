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
