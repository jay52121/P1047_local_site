import { AutoClock } from "/person/P-1047/longitudinal-function/assets/auto-clock.js";
import { JsonDataRepository } from "/person/P-1047/longitudinal-function/assets/data-repository.js";

const repository = new JsonDataRepository();
const clock = new AutoClock(10000);
const state = { personId: "C-2308", taskId: "homework", summary: null, metric: "firstDistractionMin", loadToken: 0, removeClockView: null };
const main = document.getElementById("main");
const TASK_LABELS = { homework: "课后作业", piano: "钢琴练习", reading: "独立阅读", writing: "汉字书写", building: "益智拼搭", tidying: "房间整理" };
const METRICS = {
  firstDistractionMin: { label: "首次注意偏离", unit: "min", higher: true },
  sustainedFocusRatePct: { label: "持续专注率", unit: "%", higher: true },
  promptCount: { label: "提示次数", unit: "次", higher: false },
  completionRatePct: { label: "任务完成率", unit: "%", higher: true },
  withinWeekCvPct: { label: "周内波动", unit: "%", higher: false },
};

document.getElementById("serverStatus").textContent = location.host || "127.0.0.1:5173";
function date(value) { return new Date(`${value}T00:00:00`); }
function formatDate(value) { const d = date(value); return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`; }
function weekText(week) { return `${formatDate(week.weekStart)} — ${formatDate(week.weekEnd)}`; }
function relative(left, right) { return (right / left - 1) * 100; }
function classify(definition, left, right) { const value = relative(left, right); if (Math.abs(value) < 2) return ["稳定", "neutral"]; const good = definition.higher ? value > 0 : value < 0; return [good ? "改善" : "下降", good ? "good" : "bad"]; }

function renderProfile(profile) { document.getElementById("personMeta").innerHTML = `<span class="personId">${profile.displayId}</span><span>${profile.ageText}</span><span>${profile.region}</span><span>观察周期 ${profile.observationWeeks} 周</span><span>中断 ${profile.interruptedDays} 天</span>`; }

function renderPage() {
  const task = state.summary;
  main.innerHTML = `<section class="panel hero"><div class="heroRow"><div class="weekBox"><div class="weekLabel">历史周</div><select id="leftWeek" class="weekSelect"></select><div id="leftMeta" class="weekMeta"></div></div><div class="vs">VS</div><div class="weekBox"><div class="weekLabel">比较周</div><select id="rightWeek" class="weekSelect"></select><div id="rightMeta" class="weekMeta"></div></div></div><div class="summaryLine"><div class="summaryText"><b>${task.taskLabel}</b> · 各项变化相对左侧所选周</div><div class="summaryPills" id="summaryPills"></div></div></section><div class="metricGrid" id="metricGrid"></div><div class="contentGrid"><section class="panel chartPanel"><div class="panelHeader"><div><div class="panelTitle" id="chartTitle"></div><div class="panelSub" id="chartSub"></div></div><div class="legend"><span><i style="background:#2f6fe4"></i>周观察值</span><span><i style="background:#8ea9db"></i>4周趋势</span><span><i style="background:#ef9b3a"></i>任务事件</span></div></div><div class="chartWrap"><svg id="chart"></svg></div><div class="timelineFooter"><div class="phaseBar" id="phaseBar"></div></div></section><aside class="panel detailPanel"><div class="detailTitle" id="detailTitle"></div><div class="detailExplain">由同一类任务的底层时间片段和离散事件聚合形成，用于观察长期变化。</div><div id="evidenceList"></div><div class="noteBox">本页为匿名模拟纵向数据，用于研究不同任务中的注意与行为变化曲线，不构成儿童发展或医学诊断。</div></aside></div><section class="panel autoEvidence"><div class="evidenceHead"><div><div class="evidenceTitle">核心数据 · 任务分钟轴</div><div class="evidenceSub" id="timelineSub"></div><div class="taskLegend"><span><i style="background:#bfe4d5"></i>专注</span><span><i style="background:#f5beb8"></i>明确分心</span><span><i style="background:#f5d9a9"></i>轻度偏离</span></div></div><span class="clockBadge">自动扫描</span></div><div class="progressTrack"><span id="autoProgress"></span></div><div class="evidenceBody"><div class="taskTimelineGrid" id="timelineGrid"></div></div></section>`;
  const left = document.getElementById("leftWeek"), right = document.getElementById("rightWeek"); task.weeks.forEach((week, index) => { const option = document.createElement("option"); option.value = index; option.textContent = weekText(week); left.appendChild(option.cloneNode(true)); right.appendChild(option); }); left.value = 0; right.value = task.weeks.length - 1; left.onchange = () => { if (+left.value > +right.value) right.value = left.value; update(); }; right.onchange = () => { if (+right.value < +left.value) left.value = right.value; update(); };
  state.removeClockView?.();
  state.removeClockView = clock.add({ renderAt(phase) { document.querySelectorAll(".taskCursor").forEach(cursor => cursor.style.left = `${phase * 100}%`); const progress = document.getElementById("autoProgress"); if (progress) progress.style.width = `${phase * 100}%`; } }); update();
}

function update() {
  const weeks = state.summary.weeks, leftIndex = +leftWeek.value, rightIndex = +rightWeek.value, left = weeks[leftIndex], right = weeks[rightIndex];
  leftMeta.innerHTML = `<span>${left.validSessions} 次有效任务</span><span>可信度 ${left.confidencePct}%</span><span>完整周</span>`; rightMeta.innerHTML = `<span>${right.validSessions} 次有效任务</span><span>可信度 ${right.confidencePct}%</span><span>完整周</span>`;
  let good = 0, bad = 0, stable = 0; Object.entries(METRICS).forEach(([key, definition]) => { const result = classify(definition, left.metrics[key], right.metrics[key])[1]; result === "good" ? good++ : result === "bad" ? bad++ : stable++; }); summaryPills.innerHTML = `<span class="pill good">${good} 项改善</span><span class="pill bad">${bad} 项下降</span><span class="pill neutral">${stable} 项稳定</span>`;
  metricGrid.innerHTML = Object.entries(METRICS).map(([key, definition]) => { const value = right.metrics[key], percent = relative(left.metrics[key], value), [label, css] = classify(definition, left.metrics[key], value); return `<article class="metric ${key === state.metric ? "selected" : ""}" data-metric="${key}"><div class="metricLabel">${key === "firstDistractionMin" ? state.summary.firstEventLabel : definition.label}</div><div class="metricValue">${value.toFixed(1)}<small>${definition.unit}</small></div><div class="metricDelta ${css}">${percent >= 0 ? "+" : ""}${percent.toFixed(1)}% · ${label}</div></article>`; }).join(""); document.querySelectorAll("[data-metric]").forEach(card => card.onclick = () => { state.metric = card.dataset.metric; update(); });
  renderDetail(left, right); renderChart(leftIndex, rightIndex); scheduleTimelines(leftIndex, rightIndex);
}

function renderDetail(left, right) {
  const definition = METRICS[state.metric], label = state.metric === "firstDistractionMin" ? state.summary.firstEventLabel : definition.label; detailTitle.textContent = `${label} · 变化依据`;
  const fields = [[label, state.metric, definition.unit, definition.higher], ["平均连续专注段", "meanContinuousFocusMin", "min", true], ["任务切换次数", "taskSwitchCount", "次", false], ["偏离任务累计", "offTaskTotalMin", "min", false]];
  evidenceList.innerHTML = fields.map(([name, key, unit, higher]) => { const a = left.metrics[key], b = right.metrics[key], percent = relative(a, b), stable = Math.abs(percent) <= 2, good = higher ? percent > 0 : percent < 0, css = stable ? "neutral" : good ? "good" : "bad", text = stable ? "稳定" : good ? "改善" : "下降"; return `<div class="evidence"><div class="evRow"><div class="evName">${name}</div><div><div class="evVals">${a.toFixed(1)}${unit} → ${b.toFixed(1)}${unit}</div><div class="evDelta ${css}">${percent >= 0 ? "+" : ""}${percent.toFixed(1)}% · ${text}</div></div></div><div class="evBar"><span style="width:${Math.min(100, Math.max(7, Math.abs(percent) * 3))}%;background:${css === "good" ? "#1c8b62" : css === "bad" ? "#d45454" : "#c79a54"}"></span></div></div>`; }).join("");
}

function renderChart(leftIndex, rightIndex) {
  const definition = METRICS[state.metric], label = state.metric === "firstDistractionMin" ? state.summary.firstEventLabel : definition.label, slice = state.summary.weeks.slice(leftIndex, rightIndex + 1), values = slice.map(week => week.metrics[state.metric]), moving = values.map((_, index) => values.slice(Math.max(0, index - 3), index + 1).reduce((sum, value) => sum + value, 0) / Math.min(4, index + 1)); let min = Math.min(...values, ...moving), max = Math.max(...values, ...moving), padding = (max - min) * .14 || 1; min -= padding; max += padding;
  const W = 900, H = 290, L = 48, R = 18, T = 17, B = 38, x = index => L + index * (W - L - R) / Math.max(1, slice.length - 1), y = value => T + (max - value) * (H - T - B) / (max - min); let html = ""; [min, (min + max) / 2, max].forEach(value => html += `<line x1="${L}" y1="${y(value)}" x2="${W - R}" y2="${y(value)}" stroke="#edf0f4"/><text x="${L - 8}" y="${y(value) + 4}" text-anchor="end" font-size="10" fill="#94a0b1">${value.toFixed(1)}</text>`); const path = values.map((value, index) => `${index ? "L" : "M"}${x(index)},${y(value)}`).join(" "), movingPath = moving.map((value, index) => `${index ? "L" : "M"}${x(index)},${y(value)}`).join(" "); html += `<path d="${path}" fill="none" stroke="#2f6fe4" stroke-width="2.4"/><path d="${movingPath}" fill="none" stroke="#8ea9db" stroke-width="1.7" stroke-dasharray="6 5"/>`; slice.forEach((week, index) => { if (week.event) html += `<line x1="${x(index)}" y1="${T}" x2="${x(index)}" y2="${H - B}" stroke="#ef9b3a" stroke-dasharray="3 4"/>`; html += `<circle cx="${x(index)}" cy="${y(values[index])}" r="4" fill="#fff" stroke="#2f6fe4" stroke-width="2"><title>${weekText(week)} · ${values[index].toFixed(1)}</title></circle>`; }); const step = Math.max(1, Math.ceil(slice.length / 6)); for (let index = 0; index < slice.length; index += step) html += `<text x="${x(index)}" y="${H - 14}" text-anchor="middle" font-size="10" fill="#8e9aac">${formatDate(slice[index].weekStart).slice(2, 7)}</text>`; chart.setAttribute("viewBox", `0 0 ${W} ${H}`); chart.innerHTML = html; chartTitle.textContent = `${label} · 长期变化曲线`; chartSub.textContent = `${slice.length} 周 · 最低 ${Math.min(...values).toFixed(1)} / 最高 ${Math.max(...values).toFixed(1)} / 当前 ${values.at(-1).toFixed(1)} ${definition.unit}`; const phases = []; slice.forEach(week => { if (week.phase && phases.at(-1) !== week.phase) phases.push(week.phase); }); phaseBar.innerHTML = phases.map(value => `<span class="phaseChip">${value}</span>`).join("") + slice.filter(week => week.event).map(week => `<span class="phaseChip event">${formatDate(week.weekStart).slice(5)} · ${week.event}</span>`).join("");
}

async function scheduleTimelines(leftIndex, rightIndex) {
  const token = ++state.loadToken, weeks = state.summary.weeks.slice(leftIndex, rightIndex + 1); timelineSub.textContent = `正在准备 ${weeks.length} 周任务核心数据`; timelineGrid.innerHTML = weeks.map(week => `<article class="taskTimelineCard loading" id="timeline-${week.weekId}"><span class="spinner"></span><span>${formatDate(week.weekStart)}</span></article>`).join("");
  await new Promise(resolve => setTimeout(resolve, 1000)); if (token !== state.loadToken) return;
  const details = await Promise.all(weeks.map(week => repository.getWeekDetail(state.personId, "attention", week.weekId, state.taskId))); timelineSub.textContent = `${state.summary.taskLabel} · ${weeks.length} 周 · 自动同步扫描 0–30 分钟`; details.forEach((detail, index) => setTimeout(() => { if (token !== state.loadToken) return; renderTimeline(weeks[index], detail); }, index * 110)); clock.restart();
}

function renderTimeline(week, detail) {
  const card = document.getElementById(`timeline-${week.weekId}`); if (!card) return; const session = detail.representativeSession, duration = session.durationMin; card.className = "taskTimelineCard"; card.innerHTML = `<div class="taskWeek">第 ${week.weekIndex} 周 · ${weekText(week)}</div><div class="taskTimeline">${session.segments.map(segment => `<span class="taskSegment ${segment.state}" style="left:${segment.startMin / duration * 100}%;width:${(segment.endMin - segment.startMin) / duration * 100}%"></span>`).join("")}<span class="taskCursor"></span></div><div class="taskTicks"><span>0 min</span><span>15 min</span><span>30 min</span></div><div class="taskEvents">${session.events.filter(event => event.type !== "completion").map(event => `<span class="taskEvent ${event.type}">${event.minute.toFixed(1)} · ${event.type === "distraction" ? "分心" : event.type === "prompt" ? "提示" : "恢复"}</span>`).join("")}</div>`;
}

async function selectTask(taskId) {
  state.taskId = taskId; state.metric = "firstDistractionMin"; state.loadToken++; document.querySelectorAll("[data-task]").forEach(button => button.classList.toggle("active", button.dataset.task === taskId)); main.innerHTML = `<section class="panel taskSwitchLoading"><span class="spinner"></span><span>正在加载${TASK_LABELS[taskId]}数据…</span></section>`;
  try { state.summary = await repository.getWeeklySummary(state.personId, "attention", taskId); renderPage(); } catch (error) { console.error(error); main.innerHTML = `<section class="panel emptyState errorState">该任务核心数据加载失败。</section>`; }
}

async function initialize() {
  try { const profile = await repository.getProfile(state.personId); renderProfile(profile); document.querySelectorAll("[data-task]").forEach(button => button.onclick = () => selectTask(button.dataset.task)); await selectTask(state.taskId); } catch (error) { console.error(error); main.innerHTML = `<section class="panel emptyState errorState">核心数据加载失败，请确认本地服务和数据文件完整。</section>`; }
}

initialize();
