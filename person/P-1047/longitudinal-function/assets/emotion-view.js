import { EMOTION_METRICS } from "./domain-defs.js";

const DAY_NAMES = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"];
const STATE_LABELS = { active: "活跃", low_activity: "低活动", long_still: "长时间静止", unknown: "未知" };

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const parseDate = value => new Date(`${value}T00:00:00`);
const formatDate = value => { const d = parseDate(value); return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`; };
const startOfWeek = value => { const d = new Date(value); const day = d.getDay() || 7; d.setDate(d.getDate() - day + 1); d.setHours(0, 0, 0, 0); return d; };
const weeksAgo = week => Math.max(0, Math.round((startOfWeek(new Date()) - startOfWeek(parseDate(week.weekStart))) / 604800000));
const weekText = week => `${formatDate(week.weekStart)} — ${formatDate(week.weekEnd)}`;
const selectorText = week => { const count = weeksAgo(week); return `${weekText(week)}（${count} week${count === 1 ? "" : "s"} ago）`; };
const available = value => value !== null && value !== undefined && Number.isFinite(Number(value));
const relative = (left, right) => available(left) && available(right) && left !== 0 ? 100 * right / left : null;
const signed = value => `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
const metricValue = (value, digits = 1) => available(value) ? Number(value).toFixed(digits) : "—";

function classify(definition, left, right) {
  if (!available(left) || !available(right) || left === 0) return ["不可比较", "neutral"];
  const delta = (right / left - 1) * 100;
  if (Math.abs(delta) < 2) return ["稳定", "neutral"];
  if (definition.risk) return delta < 0 ? ["行为收缩减少", "good"] : ["行为收缩增加", "bad"];
  return delta > 0 ? ["改善", "good"] : ["下降", "bad"];
}

function statusText(week) {
  if (week.status === "in_progress") return "进行中 · 暂定";
  if (week.dataStatus === "partial") return "数据不完整";
  if (week.dataStatus === "insufficient") return "数据不足";
  return "完整周";
}

function meta(week) {
  return `<span>有效日 ${week.validUnits}/${week.expectedUnits}</span><span>可信度 ${week.confidencePct.toFixed(1)}%</span><span>${statusText(week)}</span>`;
}

function sparkSvg(weeks, definition, leftIndex, rightIndex) {
  const base = weeks[leftIndex].indexes[definition.field];
  const values = weeks.slice(leftIndex, rightIndex + 1).map(week => relative(base, week.indexes[definition.field]));
  const points = values.map((value, index) => available(value) ? { value, index } : null).filter(Boolean);
  if (points.length < 2) return `<div class="sparkEmpty">数据不足</div>`;
  const min = Math.min(...points.map(point => point.value)) - .5, max = Math.max(...points.map(point => point.value)) + .5;
  const x = index => 2 + index * 176 / Math.max(1, values.length - 1), y = value => 2 + (max - value) * 30 / Math.max(1, max - min);
  let paths = [], current = [];
  values.forEach((value, index) => { if (available(value)) current.push(`${current.length ? "L" : "M"}${x(index)},${y(value)}`); else if (current.length) { paths.push(current.join(" ")); current = []; } });
  if (current.length) paths.push(current.join(" "));
  const [, css] = classify(definition, base, weeks[rightIndex].indexes[definition.field]);
  const color = css === "good" ? "#1c8b62" : css === "bad" ? "#d45454" : "#8996a8";
  return `<svg viewBox="0 0 180 34">${paths.map(path => `<path d="${path}" fill="none" stroke="${color}" stroke-width="2.1"/>`).join("")}<line x1="0" y1="17" x2="180" y2="17" stroke="#e9edf3"/></svg>`;
}

function chartSvg(weeks, definition, leftIndex, rightIndex) {
  const slice = weeks.slice(leftIndex, rightIndex + 1), base = weeks[leftIndex].indexes[definition.field];
  const values = slice.map(week => relative(base, week.indexes[definition.field]));
  const moving = values.map((_, index) => { const sample = values.slice(Math.max(0, index - 3), index + 1).filter(available); return sample.length ? sample.reduce((sum, value) => sum + value, 0) / sample.length : null; });
  const finite = [...values, ...moving].filter(available);
  if (!finite.length) return { svg: `<text x="450" y="145" text-anchor="middle" fill="#8996a8">所选区间没有可比较指数</text>`, sub: "数据不足，趋势不连接" };
  let min = Math.min(...finite, 96), max = Math.max(...finite, 104), pad = (max - min) * .13 || 2; min -= pad; max += pad;
  const W = 900, H = 290, L = 48, R = 18, T = 17, B = 38, x = index => L + index * (W - L - R) / Math.max(1, slice.length - 1), y = value => T + (max - value) * (H - T - B) / (max - min);
  const paths = series => { let result = [], current = []; series.forEach((value, index) => { if (available(value)) current.push(`${current.length ? "L" : "M"}${x(index)},${y(value)}`); else if (current.length) { result.push(current.join(" ")); current = []; } }); if (current.length) result.push(current.join(" ")); return result; };
  let svg = "";
  [min, (min + max) / 2, max, 100].forEach(value => svg += `<line x1="${L}" y1="${y(value)}" x2="${W - R}" y2="${y(value)}" stroke="#edf0f4"/><text x="${L - 8}" y="${y(value) + 4}" text-anchor="end" font-size="10" fill="#94a0b1">${value.toFixed(0)}</text>`);
  svg += paths(values).map(path => `<path d="${path}" fill="none" stroke="#2f6fe4" stroke-width="2.4"/>`).join("");
  svg += paths(moving).map(path => `<path d="${path}" fill="none" stroke="#8ea9db" stroke-width="1.7" stroke-dasharray="6 5"/>`).join("");
  slice.forEach((week, index) => { if (week.event) svg += `<line x1="${x(index)}" y1="${T}" x2="${x(index)}" y2="${H - B}" stroke="#ef9b3a" stroke-dasharray="3 4"/>`; if (available(values[index])) svg += `<circle cx="${x(index)}" cy="${y(values[index])}" r="4" fill="${week.provisional ? "#fff" : "#2f6fe4"}" stroke="#2f6fe4" stroke-width="2"><title>${weekText(week)} · ${metricValue(values[index])}</title></circle>`; });
  const step = Math.max(1, Math.ceil(slice.length / 6)); for (let index = 0; index < slice.length; index += step) svg += `<text x="${x(index)}" y="${H - 14}" text-anchor="middle" font-size="10" fill="#8e9aac">${formatDate(slice[index].weekStart).slice(2, 7)}</text>`;
  return { svg, sub: `所选区间 ${slice.length} 周 · 空值处断开 · 暂定周为空心点` };
}

function evidenceHtml(definition, leftWeek, rightWeek, metricMapping) {
  const fields = metricMapping.indexes[definition.field].rawMetrics;
  return fields.map(field => {
    const metadata = metricMapping.rawMetrics[field], label = metadata.label, unit = metadata.unit, higher = metadata.higherIsBetter;
    const left = leftWeek.metrics[field], right = rightWeek.metrics[field];
    if (!available(left) || !available(right) || left === 0) return `<div class="evidence"><div class="evRow"><div class="evName">${label}</div><div class="evVals">本周评价机会不足</div></div></div>`;
    const delta = (right / left - 1) * 100, improved = higher ? delta > 0 : delta < 0, css = Math.abs(delta) < 2 ? "neutral" : improved ? "good" : "bad";
    return `<div class="evidence"><div class="evRow"><div class="evName">${label}</div><div><div class="evVals">${metricValue(left, 2)}${unit} → ${metricValue(right, 2)}${unit}</div><div class="evDelta ${css}">${signed(delta)}</div></div></div></div>`;
  }).join("");
}

function timelineHtml(unit) {
  const segments = unit.segments.map(segment => `<span class="emotionSegment ${segment.state}" style="width:${(segment.endMin - segment.startMin) / 10.2}%" title="${STATE_LABELS[segment.state]} · ${metricValue(segment.endMin - segment.startMin, 1)} min"></span>`).join("");
  const markers = unit.events.map(event => { const at = event.atMin ?? event.startMin; const type = event.type === "activity_start" && event.origin === "self" ? "self" : event.type === "interest_opportunity" ? "interest" : event.type === "social_opportunity" ? "social" : "other"; return `<i class="emotionEvent ${type}" style="left:${at / 10.2}%" title="${event.type}"></i>`; }).join("");
  const r = unit.result;
  return `<div class="emotionDay ${unit.valid ? "" : "invalid"}"><div class="emotionDayHead"><b>${DAY_NAMES[parseDate(unit.date).getDay() === 0 ? 6 : parseDate(unit.date).getDay() - 1]}</b><span>${formatDate(unit.date)}</span><em>${unit.valid ? "有效" : "无效"}</em></div><div class="emotionTimeline">${segments}${markers}</div><div class="emotionAxis"><span>06:00</span><span>14:30</span><span>23:00</span></div><div class="emotionDayStats"><span>活跃率 ${metricValue(r.activeRatePct)}%</span><span>自主启动 ${r.selfInitiatedStarts} 次</span><span>兴趣 ${r.interestAcceptedCount}/${r.interestOpportunityCount}</span><span>回应 ${r.socialRespondedCount}/${r.socialOpportunityCount}</span><span>长静止 ${metricValue(r.longStillMin)} min</span></div>${unit.valid ? "" : `<div class="invalidOverlay">本日数据不完整 · 不参与周基线</div>`}</div>`;
}

function summaryEvidence(detail, week) {
  const t = detail.weekAggregate.evidenceTotals, m = detail.weekAggregate.metrics;
  return `<div class="emotionWeekProof"><div class="proofTitle">周聚合计算链</div><div class="proofGrid"><span>行为活跃</span><b>${metricValue(t.activeMin, 1)} / ${metricValue(t.observedMinutes, 1)} min = ${metricValue(m.activeRatePct, 2)}%</b><span>自主启动</span><b>${t.selfInitiatedStarts} 次 = ${metricValue(m.initiativeEventsPer8h, 2)} 次/8h</b><span>兴趣接受 / 投入</span><b>${t.interestAcceptedCount}/${t.interestOpportunityCount} · ${metricValue(m.interestEngagementPct, 2)}%</b><span>互动回应 / 延迟</span><b>${t.socialRespondedCount}/${t.socialOpportunityCount} · ${metricValue(m.responseLatencySec, 1)} sec</b><span>长时间静止</span><b>${metricValue(t.longStillMin, 1)} min · ${metricValue(m.longStillRatePct, 2)}%</b></div><div class="proofIndexes">${Object.entries(EMOTION_METRICS).map(([key, definition]) => `<span>${definition.label}<b>${metricValue(week.indexes[key])}</b></span>`).join("")}</div></div>`;
}

export function mountEmotionView({ main, weeks, metricMapping, repository, clock, personId, initialEvidenceOpen = false, onEvidenceChange = () => {} }) {
  const view = { metric: "behaviorActivation", open: initialEvidenceOpen, token: 0, details: new Map(), visible: new Set(), observer: null, removeClock: null };
  main.innerHTML = `<section class="panel hero"><div class="heroRow"><div class="weekBox"><div class="weekLabel">历史周</div><select id="emotionLeftWeek" class="weekSelect"></select><div id="emotionLeftMeta" class="weekMeta"></div></div><div class="vs">VS</div><div class="weekBox"><div class="weekLabel">比较周</div><select id="emotionRightWeek" class="weekSelect"></select><div id="emotionRightMeta" class="weekMeta"></div></div></div><div class="summaryLine"><div class="summaryText"><b>心理情绪状态</b> · 相对变化基于左侧所选周</div><div class="summaryPills" id="emotionPills"></div></div></section><div class="metricGrid" id="emotionMetricGrid"></div><div class="contentGrid"><section class="panel chartPanel"><div class="panelHeader"><div><div class="panelTitle" id="emotionChartTitle"></div><div class="panelSub" id="emotionChartSub"></div></div><div class="legend"><span><i style="background:#2f6fe4"></i>周基线</span><span><i style="background:#8ea9db"></i>4周趋势</span><span><i style="background:#ef9b3a"></i>事件</span></div></div><div class="chartWrap"><svg id="emotionChart" viewBox="0 0 900 290"></svg></div><div class="timelineFooter"><div class="phaseBar" id="emotionPhaseBar"></div><button class="videoButton" id="emotionEvidenceButton" type="button" aria-label="展开心理情绪核心数据" title="展开核心数据"><span>▶</span></button></div></section><aside class="panel detailPanel"><div class="detailTitle" id="emotionDetailTitle"></div><div class="detailExplain" id="emotionDetailExplain"></div><div id="emotionEvidenceList"></div><div class="noteBox">本域描述行为中的情绪相关线索，不构成心理或精神疾病诊断。</div></aside></div><section class="panel autoEvidence" id="emotionAutoEvidence" ${view.open ? "" : "hidden"}><div class="evidenceHead"><div><div class="evidenceTitle">核心数据 · 日内行为证据</div><div class="evidenceSub" id="emotionEvidenceSub"></div></div><span class="clockBadge">自动运行</span></div><div class="progressTrack"><span id="emotionProgress"></span></div><div class="emotionGrid" id="emotionGrid"></div></section>`;
  const left = document.getElementById("emotionLeftWeek"), right = document.getElementById("emotionRightWeek");
  weeks.forEach((week, index) => { const option = document.createElement("option"); option.value = index; option.textContent = selectorText(week); left.appendChild(option.cloneNode(true)); right.appendChild(option); });
  left.value = Math.min(19, weeks.length - 1); right.value = weeks.length - 1;

  function update() {
    const leftIndex = +left.value, rightIndex = +right.value, leftWeek = weeks[leftIndex], rightWeek = weeks[rightIndex];
    document.getElementById("emotionLeftMeta").innerHTML = meta(leftWeek); document.getElementById("emotionRightMeta").innerHTML = meta(rightWeek);
    let good = 0, bad = 0, stable = 0, comparable = 0;
    Object.values(EMOTION_METRICS).forEach(definition => { const [label, css] = classify(definition, leftWeek.indexes[definition.field], rightWeek.indexes[definition.field]); if (label === "不可比较") return; comparable++; css === "good" ? good++ : css === "bad" ? bad++ : stable++; });
    document.getElementById("emotionPills").innerHTML = `<span class="pill good">${good} 项改善</span><span class="pill bad">${bad} 项下降</span><span class="pill neutral">${stable} 项稳定</span><span class="pill neutral">可比较 ${comparable}/5</span>`;
    document.getElementById("emotionMetricGrid").innerHTML = Object.entries(EMOTION_METRICS).map(([key, definition]) => { const l = leftWeek.indexes[key], r = rightWeek.indexes[key], value = relative(l, r), [label, css] = classify(definition, l, r); return `<article class="metric ${view.metric === key ? "selected" : ""}" data-emotion-metric="${key}"><div class="metricLabel">${definition.label}</div><div class="metricValue">${metricValue(value)}<small>相对值</small></div><div class="metricDelta ${css}">${available(value) ? signed(value - 100) : "—"} · ${label}</div><div class="spark">${sparkSvg(weeks, definition, leftIndex, rightIndex)}</div></article>`; }).join("");
    document.querySelectorAll("[data-emotion-metric]").forEach(card => card.onclick = () => { view.metric = card.dataset.emotionMetric; update(); });
    const definition = EMOTION_METRICS[view.metric], chart = chartSvg(weeks, definition, leftIndex, rightIndex);
    document.getElementById("emotionDetailTitle").textContent = `${definition.label} · 变化依据`; document.getElementById("emotionDetailExplain").textContent = definition.description; document.getElementById("emotionEvidenceList").innerHTML = evidenceHtml(definition, leftWeek, rightWeek, metricMapping);
    document.getElementById("emotionChartTitle").textContent = `${definition.label} · 长期变化曲线`; document.getElementById("emotionChartSub").textContent = chart.sub; document.getElementById("emotionChart").innerHTML = chart.svg;
    const slice = weeks.slice(leftIndex, rightIndex + 1), phases = [...new Set(slice.map(week => week.phase))], events = slice.filter(week => week.event);
    document.getElementById("emotionPhaseBar").innerHTML = phases.map(label => `<span class="phaseChip">${label}</span>`).join("") + events.map(week => `<span class="phaseChip event">${formatDate(week.weekStart).slice(5)} · ${week.event}</span>`).join("");
    if (view.open) loadEvidence(leftIndex, rightIndex);
  }

  async function loadEvidence(leftIndex, rightIndex) {
    const token = ++view.token, selected = weeks.slice(leftIndex, rightIndex + 1), grid = document.getElementById("emotionGrid");
    document.getElementById("emotionEvidenceSub").textContent = `正在准备所选区间的 ${selected.length} 周核心数据`;
    grid.innerHTML = selected.map(week => `<article class="emotionCard loading" data-week-id="${week.weekId}"><div class="emotionCardHead"><b>${weekText(week)}</b><span>${statusText(week)}</span></div><div class="emotionLoading"><span class="spinner"></span><span>核心数据 loading</span></div></article>`).join("");
    view.observer?.disconnect(); view.visible.clear();
    view.observer = new IntersectionObserver(entries => entries.forEach(entry => entry.isIntersecting ? view.visible.add(entry.target) : view.visible.delete(entry.target)), { rootMargin: "160px" });
    grid.querySelectorAll(".emotionCard").forEach(card => view.observer.observe(card));
    await wait(1000);
    for (const week of selected) {
      if (token !== view.token) return;
      let detail = view.details.get(week.weekId);
      if (!detail) { detail = await repository.getWeekDetail(personId, "emotion", week.weekId); view.details.set(week.weekId, detail); }
      const card = grid.querySelector(`[data-week-id="${week.weekId}"]`); if (!card) return;
      card.classList.remove("loading"); card._emotionDetail = detail; card._emotionWeek = week; renderCard(card, 0);
      await wait(140);
    }
    document.getElementById("emotionEvidenceSub").textContent = `所选区间共 ${selected.length} 周 · 日内行为与周聚合同源`; clock.restart();
  }

  function renderCard(card, phase) {
    const detail = card._emotionDetail, week = card._emotionWeek; if (!detail) return;
    const dayIndex = Math.min(6, Math.floor(phase / .12));
    if (phase >= .84) { card.innerHTML = `<div class="emotionCardHead"><b>${weekText(week)}</b><span>${statusText(week)}</span></div>${summaryEvidence(detail, week)}`; return; }
    const unit = detail.units[dayIndex];
    card.innerHTML = `<div class="emotionCardHead"><b>${weekText(week)}</b><span>${statusText(week)}</span></div>${unit ? timelineHtml(unit) : `<div class="emotionNotObserved"><b>${DAY_NAMES[dayIndex]}</b><span>尚未观察</span></div>`}`;
  }

  left.onchange = () => { if (+left.value > +right.value) right.value = left.value; update(); };
  right.onchange = () => { if (+right.value < +left.value) left.value = right.value; update(); };
  document.getElementById("emotionEvidenceButton").onclick = () => { view.open = !view.open; onEvidenceChange(view.open); const section = document.getElementById("emotionAutoEvidence"); section.hidden = !view.open; if (view.open) { loadEvidence(+left.value, +right.value); section.scrollIntoView({ behavior: "smooth", block: "start" }); } else { view.token++; view.observer?.disconnect(); view.visible.clear(); } };
  view.removeClock = clock.add({ renderAt(phase) { const progress = document.getElementById("emotionProgress"); if (progress) progress.style.width = `${phase * 100}%`; view.visible.forEach(card => renderCard(card, phase)); } });
  update();
  return () => { view.token++; view.observer?.disconnect(); view.visible.clear(); view.removeClock?.(); };
}
