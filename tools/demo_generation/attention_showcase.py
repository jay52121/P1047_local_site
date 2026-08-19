from __future__ import annotations

from datetime import date, timedelta
from math import exp

from .common import clamp, mad, median
from .randomness import stable_rng


TASKS = {
    "homework": ("课后作业", 25, 50),
    "piano": ("钢琴练习", 18, 35),
    "reading": ("独立阅读", 15, 35),
    "writing": ("汉字书写", 15, 30),
    "building": ("益智拼搭", 20, 45),
    "tidying": ("房间整理", 10, 25),
}
INDEXES = ("sustainedEngagement", "effectiveFocus", "distractionControl", "recoveryIndependence", "taskCompletion")
DISPLAY_FLOORS = {"firstShare": 8, "focusRate": 5, "distractionRate": .7, "offTaskRate": 4, "leaveRate": .35, "autonomousRate": 10, "recoveryLatency": 1, "promptRate": .35, "completion": 10}
SUBJECTS = {"chinese": "语文作业", "math": "数学作业", "english": "英语作业", "other": "综合作业"}
PREFERRED_DAYS = {
    "reading": [0, 1, 2, 3, 6, 4, 5],
    "piano": [1, 3, 5, 6, 2, 0, 4],
    "writing": [0, 2, 4, 1, 3, 5, 6],
    "building": [5, 6, 2, 4, 3, 1, 0],
    "tidying": [5, 6, 4, 3, 2, 1, 0],
}
TASK_OFFSETS = {"homework": .10, "writing": .07, "piano": .03, "reading": -.02, "building": -.06, "tidying": -.05}
BASE_DISTRACTIONS = {"homework": 1.05, "writing": .95, "piano": .80, "reading": .65, "tidying": .70, "building": .55}
RECOVERY_SENSITIVITY = {"homework": .75, "writing": .72, "piano": .90, "reading": 1.05, "building": 1.10, "tidying": 1.00}
BEHAVIOR_SUBTYPES = {
    "homework": ["look_away", "unrelated_object", "task_switch", "leave_seat"],
    "piano": ["stop_playing", "random_playing", "restart_piece", "leave_bench"],
    "reading": ["look_away", "unrelated_page_turn", "handle_other_object", "leave_seat"],
    "writing": ["pen_stop", "unrelated_drawing", "look_away", "leave_seat"],
    "building": ["abandon_step", "switch_piece_set", "idle", "leave_area"],
    "tidying": ["play_with_object", "switch_goal", "stop_tidying", "unrelated_activity"],
}


def rounded(value):
    return None if value is None else round(float(value), 4)


def poisson(rng, lam):
    limit, product, count = exp(-lam), 1.0, 0
    while product > limit:
        count += 1
        product *= rng.random()
    return max(0, count - 1)


def clock_add(start_time, minutes):
    hour, minute = map(int, start_time.split(":"))
    value = hour * 60 + minute + round(minutes)
    if value >= 1440:
        raise ValueError("Attention sessions must not cross midnight")
    return f"{value // 60:02d}:{value % 60:02d}"


def minutes_of(clock):
    hour, minute = map(int, clock.split(":"))
    return hour * 60 + minute


def calendar_mode(index):
    if index <= 7:
        return "school_normal"
    if index <= 11:
        return "school_pressure"
    if index <= 18:
        return "school_supported"
    return "summer_break"


def base_burden(index):
    if index <= 4:
        return .20 + index * .012
    if index <= 11:
        return .25 + (index - 4) * .06
    if index <= 19:
        return .67 - (index - 11) * .052
    return .17 + (index - 19) * .012


def build_week_loads():
    loads, previous = [], 0.0
    for index in range(24):
        week_id = f"2026-W{index + 9:02d}"
        rng = stable_rng("C-2308", "attention-v3", week_id, "week-load")
        previous = clamp(.55 * previous + rng.gauss(0, .035), -.08, .08)
        loads.append(clamp(base_burden(index) + previous, .05, .85))
    return loads


def choose_day_statuses(start):
    days = [start + timedelta(days=offset) for offset in range(168)]
    ranked = sorted(days, key=lambda day: stable_rng("C-2308", "attention-v3", day.isoformat(), "status").random())
    invalid = set(ranked[:3])
    unobserved = set(ranked[3:10])
    rest_pool = sorted(
        (day for day in days if day not in invalid | unobserved),
        key=lambda day: (0 if day.weekday() >= 5 else 1, stable_rng("C-2308", "attention-v3", day.isoformat(), "rest").random()),
    )
    rest = set(rest_pool[:16])
    return invalid, unobserved, rest


def target_count(mode, task_id, rng):
    ranges = {
        "school_normal": {"reading": (4, 4), "piano": (4, 4), "writing": (1, 2), "building": (2, 2), "tidying": (1, 2)},
        "school_pressure": {"reading": (3, 4), "piano": (3, 3), "writing": (2, 3), "building": (0, 1), "tidying": (1, 2)},
        "school_supported": {"reading": (4, 4), "piano": (4, 4), "writing": (1, 2), "building": (2, 2), "tidying": (1, 2)},
        "summer_break": {"reading": (5, 5), "piano": (4, 4), "writing": (1, 2), "building": (2, 3), "tidying": (2, 2)},
    }
    low, high = ranges[mode][task_id]
    return rng.randint(low, high)


def select_preferred_days(week_id, mode, task_id, count):
    rng = stable_rng("C-2308", "attention-v3", week_id, task_id, "routine")
    ordered = list(PREFERRED_DAYS[task_id])
    if mode == "summer_break":
        ordered = sorted(ordered, key=lambda day: (0 if day >= 5 else 1, ordered.index(day)))
    primary = ordered[:max(count + 1, 4)]
    rng.shuffle(primary)
    chosen = primary[:count]
    if rng.random() < .18 and chosen:
        alternatives = [day for day in ordered if day not in chosen]
        if alternatives:
            chosen[rng.randrange(len(chosen))] = alternatives[0]
    return sorted(set(chosen))


def homework_days(week_id, mode):
    rng = stable_rng("C-2308", "attention-v3", week_id, "homework-routine")
    if mode == "school_pressure":
        target = rng.choice([5, 5, 6])
    elif mode == "summer_break":
        target = rng.choice([2, 3, 3, 4])
    else:
        target = rng.choice([4, 4, 5, 5])
    if mode == "summer_break":
        pool = [0, 2, 4, 1, 3, 5, 6]
    else:
        weekdays = [0, 1, 2, 3]
        rng.shuffle(weekdays)
        pool = weekdays + [4, 5, 6]
    return sorted(pool[:target])


def task_context(task_id, mode):
    if task_id == "homework":
        return "holiday_review" if mode == "summer_break" else "assigned_homework"
    return {"piano": "practice", "reading": "leisure", "writing": "practice", "building": "leisure", "tidying": "routine"}[task_id]


def build_week_candidates(week_id, mode, week_start, day_status):
    rng = stable_rng("C-2308", "attention-v3", week_id, "weekly-plan")
    candidates = {index: [] for index in range(7)}
    homework_subjects = ["math", "chinese", "english", "other"]
    for weekday in homework_days(week_id, mode):
        day = week_start + timedelta(days=weekday)
        if day_status[day] != "observed":
            continue
        subject = rng.choice(homework_subjects[:3])
        candidates[weekday].append({"taskId": "homework", "subject": subject, "sessionRole": "primary"})
        secondary_probability = .24 if mode == "school_pressure" else .10 if mode != "summer_break" else .06
        if rng.random() < secondary_probability:
            second = rng.choice([value for value in homework_subjects if value != subject])
            candidates[weekday].append({"taskId": "homework", "subject": second, "sessionRole": "secondary"})
    for task_id in PREFERRED_DAYS:
        count = target_count(mode, task_id, rng)
        for weekday in select_preferred_days(week_id, mode, task_id, count):
            day = week_start + timedelta(days=weekday)
            if day_status[day] == "observed":
                candidates[weekday].append({"taskId": task_id, "subject": None, "sessionRole": "primary"})
    for weekday in range(7):
        day = week_start + timedelta(days=weekday)
        if day_status[day] != "observed":
            candidates[weekday] = []
        elif not candidates[weekday]:
            filler = "reading" if weekday < 5 else ("building" if mode == "summer_break" else "tidying")
            candidates[weekday].append({"taskId": filler, "subject": None, "sessionRole": "primary"})
    return candidates


def time_windows(task_id, weekday, mode, role):
    weekend = weekday >= 5
    if mode == "summer_break" or weekend:
        return {
            "homework": [(570, 690), (870, 1050)],
            "piano": [(600, 720), (990, 1170)],
            "reading": [(570, 660), (1200, 1275)],
            "writing": [(600, 690), (900, 1080)],
            "building": [(570, 720), (870, 1080)],
            "tidying": [(570, 690), (1020, 1140)],
        }[task_id]
    if task_id == "homework" and role == "secondary":
        return [(1125, 1220)]
    return {
        "homework": [(950, 1090), (1125, 1220)],
        "piano": [(1065, 1200)],
        "reading": [(1180, 1275)],
        "writing": [(1005, 1125), (1140, 1200)],
        "building": [(1035, 1170)],
        "tidying": [(1125, 1230)],
    }[task_id]


def planned_duration(candidate, mode, rng):
    task_id = candidate["taskId"]
    low, high = TASKS[task_id][1:]
    if mode == "school_pressure" and task_id in {"homework", "writing"}:
        low, high = low + 3, high + 5
    if mode == "school_supported" and task_id == "homework":
        high -= 5
    return round(rng.uniform(low, high), 1)


def interval_available(start, duration, placed, gap=10):
    end = start + duration
    return all(end + gap <= item["startMinute"] or start >= item["plannedEndMinute"] + gap for item in placed)


def schedule_day(week_id, day, mode, candidates):
    priorities = {"homework": 1, "writing": 1, "piano": 2, "reading": 3, "building": 4, "tidying": 4}
    placed = []
    ordered = sorted(candidates, key=lambda item: (priorities[item["taskId"]], item["sessionRole"] != "primary"))
    for order, candidate in enumerate(ordered):
        task_id = candidate["taskId"]
        rng = stable_rng("C-2308", "attention-v3", week_id, day.isoformat(), task_id, candidate.get("subject"), order, "schedule")
        duration = planned_duration(candidate, mode, rng)
        windows = time_windows(task_id, day.weekday(), mode, candidate["sessionRole"])
        selected = None
        for window_start, window_end in windows:
            anchor = (window_start + window_end - duration) / 2
            sigma = 10 if task_id == "reading" else 12
            for _ in range(8):
                start = round(clamp(rng.gauss(anchor, sigma), window_start, window_end - duration))
                if interval_available(start, duration, placed):
                    selected = start
                    break
            if selected is not None:
                break
        if selected is None:
            for window_start, window_end in windows:
                for start in range(window_start, int(window_end - duration) + 1):
                    if interval_available(start, duration, placed):
                        selected = start
                        break
                if selected is not None:
                    break
        if selected is None and task_id == "homework":
            for start in range(570, int(1275 - duration) + 1):
                if interval_available(start, duration, placed, gap=0):
                    selected = start
                    break
        if selected is None:
            continue
        row = dict(candidate)
        row.update({"plannedDurationMin": duration, "startMinute": selected, "plannedEndMinute": selected + duration})
        placed.append(row)
    return sorted(placed, key=lambda item: item["startMinute"])


def time_of_day_offset(start, day):
    if day.weekday() >= 5 and start < 720:
        return -.03
    if start < 1020:
        return 0.0
    if start < 1110:
        return .02
    if start < 1170:
        return .04
    return .09


def session_load(week_load, task_id, start, day, prior_minutes, gap, previous, rng, mode):
    recovery = max(0.0, .58 - week_load) * (RECOVERY_SENSITIVITY[task_id] - 1) * .30 if mode in {"school_supported", "summer_break"} else 0.0
    cumulative = min(.12, prior_minutes / 120 * .10)
    gap_penalty = .07 if gap is not None and gap < 10 else .03 if gap is not None and gap < 20 else 0.0
    carry = 0.0
    if previous:
        if previous["result"]["terminalStatus"] in {"partial", "abandoned"}:
            carry += .06
        if previous["result"]["offTaskMin"] / previous["durationMin"] > .15:
            carry += .04
        if previous["result"]["completed"] and previous["result"]["unpromptedCompletion"]:
            carry -= .02
    weekday = .025 if day.weekday() == 4 else -.01 if day.weekday() >= 5 else 0.0
    return clamp(week_load + TASK_OFFSETS[task_id] + weekday + time_of_day_offset(start, day) + cumulative + gap_penalty + clamp(carry, -.03, .08) + recovery + rng.gauss(0, .06), .03, .95)


def spaced_event_times(rng, count, duration):
    values = []
    for _ in range(80):
        if len(values) >= count:
            break
        candidate = rng.uniform(2.5, max(2.6, duration - 2.0))
        if all(abs(candidate - value) >= 1.5 for value in values):
            values.append(candidate)
    return sorted(values)


def build_session(week_id, day, sequence, candidate, mode, week_load, prior_minutes, gap, previous):
    task_id = candidate["taskId"]
    label = SUBJECTS[candidate["subject"]] if task_id == "homework" else TASKS[task_id][0]
    rng = stable_rng("C-2308", "attention-v3", week_id, day.isoformat(), task_id, candidate.get("subject"), sequence, "behavior")
    load = session_load(week_load, task_id, candidate["startMinute"], day, prior_minutes, gap, previous, rng, mode)
    planned = candidate["plannedDurationMin"]
    distraction_count = min(6, poisson(rng, BASE_DISTRACTIONS[task_id] * (planned / 30) ** .85 * (.60 + 1.20 * load)))
    initial_early = rng.random() < clamp(.02 + .18 * load, .02, .30)
    actual = planned * rng.uniform(.58, .86) if initial_early else planned
    event_times = spaced_event_times(rng, distraction_count, actual)
    segments, events, cursor = [], [], 0.0
    prompts = autonomous = 0
    recovery_latencies = []
    off_task = 0.0
    forced_abandon = False
    severity_weights = [max(.30, .72 - .32 * load), .25 + .10 * load, .05 + .28 * load]
    for event_index, at in enumerate(event_times):
        if at < cursor + 1.5:
            continue
        if at > cursor:
            segments.append({"startMin": rounded(cursor), "endMin": rounded(at), "state": "focused"})
        severity = rng.choices(["brief_deviation", "clear_distraction", "long_off_task"], weights=severity_weights)[0]
        if severity == "brief_deviation":
            length, state = rng.uniform(.2, 1.2), "deviating"
        elif severity == "clear_distraction":
            length, state = rng.uniform(1.0, 3.0), "distracted"
        else:
            length, state = rng.uniform(3.0, 8.0), "off_task"
        end = min(actual, at + length)
        subtype = rng.choice(BEHAVIOR_SUBTYPES[task_id])
        events.append({"minute": rounded(at), "type": "distraction", "severity": severity, "subtype": subtype, "order": event_index + 1})
        leave_probability = None if task_id == "tidying" else {"homework": .10, "piano": .09, "reading": .04, "writing": .07, "building": .03}[task_id] + .18 * load
        if leave_probability is not None and severity != "brief_deviation" and rng.random() < leave_probability:
            events.append({"minute": rounded(min(end, at + .15)), "type": "leave_seat"})
        p_self = clamp(.20 + .70 * .68 - .48 * load + {"reading": .06, "building": .08, "homework": -.03, "writing": -.04}.get(task_id, 0), .12, .92)
        recovered, origin = True, "self"
        if rng.random() < p_self:
            autonomous += 1
        else:
            p_prompt = clamp(.16 + .55 * load + .25 * .32, .12, .88)
            if rng.random() < p_prompt:
                prompts += 1
                accepted = rng.random() < clamp(.88 - .38 * load, .35, .88)
                events.append({"minute": rounded(min(end, at + max(.2, length * .65))), "type": "prompt", "accepted": accepted})
                if accepted:
                    end, origin = min(actual, end + rng.uniform(.2, 1.0)), "prompt"
                elif rng.random() < .48:
                    end, origin = min(actual, end + rng.uniform(1.0, 3.0)), "delayed_self"
                else:
                    end, recovered, forced_abandon = actual, False, True
            else:
                end, origin = min(actual, end + rng.uniform(.6, 2.0)), "delayed_self"
        segments.append({"startMin": rounded(at), "endMin": rounded(end), "state": state})
        off_task += end - at
        if recovered and end < actual:
            events.append({"minute": rounded(end), "type": "recovery", "origin": origin})
            recovery_latencies.append(end - at)
        cursor = end
        if forced_abandon:
            break
    if cursor < actual:
        segments.append({"startMin": rounded(cursor), "endMin": rounded(actual), "state": "focused"})
    early_end = initial_early or forced_abandon
    completed = not early_end and rng.random() < clamp(.97 - .15 * load, .70, .97)
    terminal = "completed" if completed else "abandoned" if forced_abandon else "partial"
    events.append({"minute": rounded(actual), "type": "completion" if completed else "early_end", "status": terminal})
    focused = sum(segment["endMin"] - segment["startMin"] for segment in segments if segment["state"] == "focused")
    first = next((event["minute"] for event in events if event["type"] == "distraction"), None)
    start_time = f"{candidate['startMinute'] // 60:02d}:{candidate['startMinute'] % 60:02d}"
    session_id = f"{week_id}-{day.isoformat()}-{task_id}-{sequence:02d}"
    series_id = f"{task_id}-{day.isoformat()}-{candidate.get('subject') or 'general'}"
    leave_count = None if task_id == "tidying" else sum(event["type"] == "leave_seat" for event in events)
    return {
        "sessionId": session_id, "date": day.isoformat(), "startTime": start_time, "endTime": clock_add(start_time, actual),
        "taskId": task_id, "taskLabel": label, "subject": candidate.get("subject"), "taskContext": task_context(task_id, mode),
        "sessionRole": candidate["sessionRole"], "seriesId": series_id, "sequenceInDay": sequence, "continuationOfSessionId": None,
        "calendarMode": mode, "dayContext": "summer_day" if mode == "summer_break" else "weekend" if day.weekday() >= 5 else "school_day",
        "plannedDurationMin": rounded(planned), "durationMin": rounded(actual), "sessionLoad": rounded(load), "valid": True,
        "segments": segments, "events": events,
        "result": {"firstDistractionMin": rounded(first), "focusedRatePct": rounded(focused / actual * 100), "distractionCount": sum(event["type"] == "distraction" for event in events), "offTaskMin": rounded(off_task), "leaveSeatCount": leave_count, "taskSwitchCount": sum(event.get("subtype") in {"task_switch", "switch_piece_set", "switch_goal"} for event in events), "autonomousRecoveryRatePct": rounded(autonomous / max(1, sum(event["type"] == "distraction" for event in events)) * 100), "recoveryLatencyMin": rounded(median(recovery_latencies)) if recovery_latencies else 0.0, "promptCount": prompts, "completed": completed, "unpromptedCompletion": completed and prompts == 0, "earlyEnd": early_end, "terminalStatus": terminal},
    }


def aggregate(sessions):
    total = sum(session["durationMin"] for session in sessions)
    focus = sum(session["durationMin"] * session["result"]["focusedRatePct"] / 100 for session in sessions)
    distractions = sum(session["result"]["distractionCount"] for session in sessions)
    first = [session["result"]["firstDistractionMin"] / session["durationMin"] * 100 for session in sessions if session["result"]["firstDistractionMin"] is not None]
    recover = [session["result"]["autonomousRecoveryRatePct"] for session in sessions if session["result"]["distractionCount"]]
    recovery_latency = [session["result"]["recoveryLatencyMin"] for session in sessions if session["result"]["distractionCount"]]
    leave_sessions = [session for session in sessions if session["result"]["leaveSeatCount"] is not None]
    leave_duration = sum(session["durationMin"] for session in leave_sessions)
    return {"focusRatePct": focus / total * 100, "firstDistractionSharePct": median(first) if first else 100.0, "distractionsPer30Min": distractions / total * 30, "offTaskRatePct": sum(session["result"]["offTaskMin"] for session in sessions) / total * 100, "leaveSeatPer30Min": sum(session["result"]["leaveSeatCount"] for session in leave_sessions) / leave_duration * 30 if leave_duration else 0.0, "autonomousRecoveryRatePct": median(recover) if recover else 100.0, "recoveryLatencyMin": median(recovery_latency) if recovery_latency else 0.0, "promptsPerSession": sum(session["result"]["promptCount"] for session in sessions) / len(sessions), "completionRatePct": sum(session["result"]["completed"] for session in sessions) / len(sessions) * 100, "unpromptedCompletionRatePct": sum(session["result"]["unpromptedCompletion"] for session in sessions) / len(sessions) * 100, "earlyEndRatePct": sum(session["result"]["earlyEnd"] for session in sessions) / len(sessions) * 100}


def session_display_raw(session):
    result, duration = session["result"], session["durationMin"]
    first = result["firstDistractionMin"]
    return {"firstShare": 100.0 if first is None else first / duration * 100, "focusRate": result["focusedRatePct"], "distractionRate": result["distractionCount"] / duration * 30, "offTaskRate": result["offTaskMin"] / duration * 100, "leaveRate": None if result["leaveSeatCount"] is None else result["leaveSeatCount"] / duration * 30, "autonomousRate": result["autonomousRecoveryRatePct"] if result["distractionCount"] else None, "recoveryLatency": result["recoveryLatencyMin"] if result["distractionCount"] else None, "promptRate": result["promptCount"], "completion": 100.0 if result["completed"] else 70.0 if result["earlyEnd"] else 82.0}


def add_display_summaries(details):
    baseline_sessions = [session for detail in details[:5] for session in detail["sessions"]]
    all_raw = [session_display_raw(session) for session in baseline_sessions]
    by_task = {task_id: [session_display_raw(session) for session in baseline_sessions if session["taskId"] == task_id] for task_id in TASKS}

    def scales(rows, key):
        values = [row[key] for row in rows if row[key] is not None]
        if len(values) < 3:
            values = [row[key] for row in all_raw if row[key] is not None]
        center = median(values)
        return center, max(1.4826 * mad(values, center), DISPLAY_FLOORS[key])

    task_scales = {task: {key: scales(rows, key) for key in DISPLAY_FLOORS} for task, rows in by_task.items()}
    lower = {"distractionRate", "offTaskRate", "leaveRate", "recoveryLatency", "promptRate"}

    def normalized(raw, task, key):
        if raw[key] is None:
            return None
        center, scale = task_scales[task][key]
        return clamp(100 + 10 * (-1 if key in lower else 1) * (raw[key] - center) / scale, 70, 130)

    for detail in details:
        by_date = {}
        for session in detail["sessions"]:
            raw, task = session_display_raw(session), session["taskId"]
            components = {"engagement": normalized(raw, task, "firstShare"), "effectiveFocus": normalized(raw, task, "focusRate"), "distractionControl": None, "recovery": None, "completion": normalized(raw, task, "completion")}
            control_keys = [("distractionRate", .45), ("offTaskRate", .35)] + ([] if task == "tidying" else [("leaveRate", .20)])
            control = [(normalized(raw, task, key), weight) for key, weight in control_keys]
            components["distractionControl"] = sum(value * weight for value, weight in control) / sum(weight for _, weight in control)
            if raw["autonomousRate"] is not None:
                recovery = [(normalized(raw, task, "autonomousRate"), .5), (normalized(raw, task, "recoveryLatency"), .25), (normalized(raw, task, "promptRate"), .25)]
                components["recovery"] = sum(value * weight for value, weight in recovery) / sum(weight for _, weight in recovery)
            weights = {"engagement": .25, "effectiveFocus": .25, "distractionControl": .20, "recovery": .15, "completion": .15}
            available = [(components[key], weight) for key, weight in weights.items() if components[key] is not None]
            session["sessionComponentScores"] = {key: rounded(value) for key, value in components.items()}
            session["sessionScore"] = rounded(sum(value * weight for value, weight in available) / sum(weight for _, weight in available))
            by_date.setdefault(session["date"], []).append(session)
        day_summaries = []
        start = date.fromisoformat(detail["weekStart"])
        for weekday in range(7):
            current = (start + timedelta(days=weekday)).isoformat()
            day_meta = detail["_dayMeta"][current]
            sessions = sorted(by_date.get(current, []), key=lambda item: item["startTime"])
            common = {"date": current, "weekdayIndex": weekday, "dayContext": day_meta["dayContext"], "observationStatus": day_meta["observationStatus"], "taskStatus": "has_task" if sessions else "no_task", "validSessionCount": len(sessions), "sessionIds": [session["sessionId"] for session in sessions]}
            if not sessions:
                band = "invalid" if day_meta["observationStatus"] == "invalid" else "unobserved" if day_meta["observationStatus"] == "unobserved" else "rest_day" if day_meta["dayContext"] == "rest_day" else "no_task"
                day_summaries.append(common | {"dayScore": None, "dayBand": band, "componentScores": {}, "representativeSessionId": None, "representativeReason": None, "topFactors": []})
                continue
            duration_weights = [session["durationMin"] ** .5 for session in sessions]
            mean = sum(session["sessionScore"] * weight for session, weight in zip(sessions, duration_weights)) / sum(duration_weights)
            score = .8 * mean + .2 * min(session["sessionScore"] for session in sessions)
            band = "strong_good" if score >= 108 else "good" if score >= 96 else "watch" if score >= 86 else "poor"
            component_scores = {}
            for key in ("engagement", "effectiveFocus", "distractionControl", "recovery", "completion"):
                rows = [(session["sessionComponentScores"][key], weight) for session, weight in zip(sessions, duration_weights) if session["sessionComponentScores"][key] is not None]
                component_scores[key] = rounded(sum(value * weight for value, weight in rows) / sum(weight for _, weight in rows)) if rows else None
            representative = min(sessions, key=lambda session: session["sessionScore"]) if band in {"watch", "poor"} else min(sessions, key=lambda session: (abs(session["sessionScore"] - score), -session["durationMin"]))
            factors = [key for key, value in sorted(component_scores.items(), key=lambda item: 999 if item[1] is None else item[1])[:2]]
            day_summaries.append(common | {"dayScore": rounded(score), "dayBand": band, "componentScores": component_scores, "representativeSessionId": representative["sessionId"], "representativeReason": "lowest_score" if band in {"watch", "poor"} else "closest_to_day_score", "topFactors": factors})
        scores = [day["dayScore"] for day in day_summaries if day["dayScore"] is not None]
        center, spread = median(scores), mad(scores, median(scores)) if len(scores) >= 3 else None
        bands = ("strong_good", "good", "watch", "poor", "no_task", "rest_day", "invalid", "unobserved")
        counts = {band: sum(day["dayBand"] == band for day in day_summaries) for band in bands}
        completed = sum(session["result"]["completed"] for session in detail["sessions"])
        detail["daySummaries"] = day_summaries
        detail["taskDays"] = sum(day["taskStatus"] == "has_task" for day in day_summaries)
        detail["completedSessionCount"] = completed
        detail["completionRatePct"] = rounded(completed / len(detail["sessions"]) * 100)
        detail["weekDaySummary"] = {"strongGoodDays": counts["strong_good"], "goodDays": counts["good"], "watchDays": counts["watch"], "poorDays": counts["poor"], "noTaskDays": counts["no_task"], "restDays": counts["rest_day"], "invalidDays": counts["invalid"], "unobservedDays": counts["unobserved"], "taskDays": detail["taskDays"], "validSessionCount": len(detail["sessions"]), "completedSessionCount": completed, "completionRatePct": detail["completionRatePct"], "dayScoreMedian": rounded(center), "dayScoreMad": rounded(spread), "stabilityLabel": None if spread is None else "周内稳定" if spread <= 5 else "有一定波动" if spread <= 10 else "周内波动明显"}
        del detail["_dayMeta"]


def generate_attention_showcase():
    start = date(2026, 2, 23)
    invalid_dates, unobserved_dates, rest_dates = choose_day_statuses(start)
    loads = build_week_loads()
    details, metrics = [], []
    for week_index in range(24):
        week_start = start + timedelta(weeks=week_index)
        week_id = f"{week_start.isocalendar().year}-W{week_start.isocalendar().week:02d}"
        mode = calendar_mode(week_index)
        schedule_rng = stable_rng("C-2308", "attention-v3", week_id, "schedule")
        day_status, day_meta = {}, {}
        for weekday in range(7):
            current = week_start + timedelta(days=weekday)
            status = "invalid" if current in invalid_dates else "unobserved" if current in unobserved_dates else "rest" if current in rest_dates else "observed"
            day_status[current] = status
            day_meta[current.isoformat()] = {"observationStatus": status if status in {"invalid", "unobserved"} else "observed", "dayContext": "rest_day" if status == "rest" else "summer_day" if mode == "summer_break" else "weekend" if weekday >= 5 else "school_day"}
        candidates = build_week_candidates(week_id, mode, week_start, day_status)
        sessions = []
        for weekday in range(7):
            current = week_start + timedelta(days=weekday)
            planned = schedule_day(week_id, current, mode, candidates[weekday])
            previous, prior_minutes, prior_end = None, 0.0, None
            for sequence, candidate in enumerate(planned, 1):
                gap = None if prior_end is None else candidate["startMinute"] - prior_end
                session = build_session(week_id, current, sequence, candidate, mode, loads[week_index], prior_minutes, gap, previous)
                sessions.append(session)
                previous, prior_end = session, minutes_of(session["endTime"])
                prior_minutes += session["durationMin"]
        row = aggregate(sessions)
        metrics.append(row)
        phase = "逐步适应期" if week_index < 5 else "压力上升期" if week_index < 12 else "策略支持恢复期" if week_index < 19 else "暑期稳定期"
        event = "任务要求增加" if week_index == 8 else "家庭策略介入" if week_index == 12 else None
        details.append({"schemaVersion": "1.1", "personId": "C-2308", "domain": "attention", "weekId": week_id, "weekIndex": week_index + 1, "weekStart": week_start.isoformat(), "weekEnd": (week_start + timedelta(days=6)).isoformat(), "status": "complete", "calendarMode": mode, "phase": phase, "event": event, "weekLoad": rounded(loads[week_index]), "validSessions": len(sessions), "confidencePct": rounded(94 + schedule_rng.uniform(-1.8, 1.8)), "_dayMeta": day_meta, "sessions": sessions, "metrics": {key: rounded(value) for key, value in row.items()}})
    add_display_summaries(details)
    centers = {key: median(row[key] for row in metrics[:5]) for key in metrics[0]}
    floors = {"focusRatePct": 5, "firstDistractionSharePct": 8, "distractionsPer30Min": .6, "offTaskRatePct": 4, "leaveSeatPer30Min": .3, "autonomousRecoveryRatePct": 10, "recoveryLatencyMin": 1, "promptsPerSession": .35, "completionRatePct": 8, "unpromptedCompletionRatePct": 10, "earlyEndRatePct": 6}
    directions = {key: (-1 if key in {"distractionsPer30Min", "offTaskRatePct", "leaveSeatPer30Min", "recoveryLatencyMin", "promptsPerSession", "earlyEndRatePct"} else 1) for key in centers}

    def norm(row, key):
        return clamp(100 + 10 * directions[key] * (row[key] - centers[key]) / max(1.4826 * mad([metric[key] for metric in metrics[:5]], centers[key]), floors[key]), 70, 130)

    groups = {"sustainedEngagement": (("firstDistractionSharePct", .45), ("focusRatePct", .55)), "effectiveFocus": (("focusRatePct", .65), ("offTaskRatePct", .35)), "distractionControl": (("distractionsPer30Min", .55), ("leaveSeatPer30Min", .25), ("offTaskRatePct", .2)), "recoveryIndependence": (("autonomousRecoveryRatePct", .5), ("recoveryLatencyMin", .25), ("promptsPerSession", .25)), "taskCompletion": (("completionRatePct", .45), ("unpromptedCompletionRatePct", .4), ("earlyEndRatePct", .15))}
    weeks = []
    for detail, row in zip(details, metrics):
        indexes = {key: sum(norm(row, metric) * weight for metric, weight in parts) for key, parts in groups.items()}
        week = {key: detail[key] for key in ("weekId", "weekIndex", "weekStart", "weekEnd", "status", "calendarMode", "phase", "event", "validSessions", "taskDays", "completedSessionCount", "completionRatePct", "confidencePct")}
        weeks.append(week | {"expectedUnits": 7, "validUnits": detail["taskDays"], "metrics": detail["metrics"], "indexes": {key: rounded(value) for key, value in indexes.items()}})
    summary = {"schemaVersion": "1.1", "personId": "C-2308", "domain": "attention", "sourceType": "simulation", "calculationMode": "generated-from-events", "calculationVersion": "v3-routine-events-1", "evidenceOrigin": "generated", "baseline": {"weekIds": [week["weekId"] for week in weeks[:5]]}, "weeks": weeks}
    return summary, {detail["weekId"]: detail for detail in details}


def attention_realism_stats(summary, details):
    sessions = [session for detail in details.values() for session in detail["sessions"]]
    days = [day for detail in details.values() for day in detail["daySummaries"]]
    task_counts = {task_id: sum(session["taskId"] == task_id for session in sessions) for task_id in TASKS}
    time_counts = {
        "morning": sum(minutes_of(session["startTime"]) < 720 for session in sessions),
        "afternoon": sum(720 <= minutes_of(session["startTime"]) < 1080 for session in sessions),
        "evening": sum(minutes_of(session["startTime"]) >= 1080 for session in sessions),
    }
    return {
        "totalSessions": len(sessions),
        "taskSessions": task_counts,
        "taskDays": sum(day["taskStatus"] == "has_task" for day in days),
        "restDays": sum(day["dayBand"] in {"no_task", "rest_day"} for day in days),
        "unobservedDays": sum(day["observationStatus"] == "unobserved" for day in days),
        "invalidDays": sum(day["observationStatus"] == "invalid" for day in days),
        "timeBuckets": time_counts,
        "naturalMinuteRate": rounded(sum(minutes_of(session["startTime"]) % 10 != 0 for session in sessions) / len(sessions)),
        "zeroDistractionSessions": sum(session["result"]["distractionCount"] == 0 for session in sessions),
        "oneDistractionSessions": sum(session["result"]["distractionCount"] == 1 for session in sessions),
        "multipleDistractionSessions": sum(session["result"]["distractionCount"] >= 2 for session in sessions),
        "earlyEndSessions": sum(session["result"]["earlyEnd"] for session in sessions),
        "promptRejectedEvents": sum(event["type"] == "prompt" and event.get("accepted") is False for session in sessions for event in session["events"]),
    }


def validate_attention_schedule_realism(summary, details):
    errors = []
    stats = attention_realism_stats(summary, details)
    sessions = [session for detail in details.values() for session in detail["sessions"]]
    if not 280 <= stats["totalSessions"] <= 380:
        errors.append("total sessions must be within 280-380")
    if not 105 <= stats["taskSessions"]["homework"] <= 135:
        errors.append("homework sessions must be within 105-135")
    task_ranges = {"reading": (70, 105), "piano": (65, 90), "writing": (35, 60), "building": (30, 55), "tidying": (25, 45)}
    for task_id, (low, high) in task_ranges.items():
        if not low <= stats["taskSessions"][task_id] <= high:
            errors.append(f"{task_id} sessions must be within {low}-{high}")
    if not 135 <= stats["taskDays"] <= 145:
        errors.append("task days must be within 135-145")
    if not 14 <= stats["restDays"] <= 20 or not 5 <= stats["unobservedDays"] <= 8 or not 2 <= stats["invalidDays"] <= 4:
        errors.append("day status distribution is outside the demo range")
    if min(stats["timeBuckets"].values()) == 0:
        errors.append("sessions must cover morning, afternoon, and evening")
    if stats["naturalMinuteRate"] < .70:
        errors.append("at least 70% of starts must avoid ten-minute buckets")
    for detail in details.values():
        homework_days_count = len({session["date"] for session in detail["sessions"] if session["taskId"] == "homework" and date.fromisoformat(session["date"]).weekday() < 5})
        if detail["calendarMode"] != "summer_break" and homework_days_count < 3:
            errors.append(f"{detail['weekId']} has fewer than three weekday homework days")
        by_date = {}
        for session in detail["sessions"]:
            by_date.setdefault(session["date"], []).append(session)
        for day, rows in by_date.items():
            ordered = sorted(rows, key=lambda session: session["startTime"])
            for left, right in zip(ordered, ordered[1:]):
                if minutes_of(left["endTime"]) > minutes_of(right["startTime"]):
                    errors.append(f"{day} has overlapping sessions")
            repeated = {}
            for session in ordered:
                repeated.setdefault(session["taskId"], []).append(session)
            for task_id, same_task in repeated.items():
                if len(same_task) > 1 and len({(session.get("subject"), session.get("sessionRole"), session.get("sequenceInDay")) for session in same_task}) != len(same_task):
                    errors.append(f"{day}/{task_id} repeated sessions have no distinct semantics")
    event_types = {event["type"] for session in sessions for event in session["events"]}
    severities = {event.get("severity") for session in sessions for event in session["events"] if event["type"] == "distraction"}
    if not all(stats[key] for key in ("zeroDistractionSessions", "oneDistractionSessions", "multipleDistractionSessions", "earlyEndSessions", "promptRejectedEvents")):
        errors.append("behavior outcome variety is incomplete")
    if not {"leave_seat", "prompt", "recovery"}.issubset(event_types) or not {"brief_deviation", "clear_distraction", "long_off_task"}.issubset(severities):
        errors.append("event or severity variety is incomplete")
    recovery_weeks = summary["weeks"][8:20]
    averages = [sum(week["indexes"].values()) / len(week["indexes"]) for week in recovery_weeks]
    directions = [right - left for left, right in zip(averages, averages[1:])]
    if sum(left * right < 0 for left, right in zip(directions, directions[1:])) < 2:
        errors.append("pressure/recovery story is too monotonic")
    return errors
