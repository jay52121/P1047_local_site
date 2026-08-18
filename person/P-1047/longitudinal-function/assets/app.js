import { AutoClock } from "./auto-clock.js";
import { JsonDataRepository } from "./data-repository.js";
import { DOMAINS, LIFE_EVIDENCE, LIFE_METRICS, LIFE_SECONDARY } from "./domain-defs.js";
import { mountEmotionView } from "./emotion-view.js";

const repository = new JsonDataRepository();
const clock = new AutoClock(12000);
const state = { personId: "P-1047", domain: "life", metric: "transfer", weeks: [], lifeWeeks: [], evidenceTimer: null, evidenceToken: 0, evidenceOpen: false, removeClockView: null, domainCleanup: null };

const main = document.getElementById("main");
document.getElementById("serverStatus").textContent = location.host || "127.0.0.1:5173";

function date(value) { return new Date(`${value}T00:00:00`); }
function formatDate(value) { const d = date(value); return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`; }
function weekText(week) { return `${formatDate(week.weekStart)} — ${formatDate(week.weekEnd)}`; }
function startOfWeek(value) { const d = new Date(value); const day = d.getDay() || 7; d.setDate(d.getDate() - day + 1); d.setHours(0, 0, 0, 0); return d; }
function weeksAgo(week) { return Math.max(0, Math.round((startOfWeek(new Date()) - startOfWeek(date(week.weekStart))) / 604800000)); }
function weekSelectText(week) { const count = weeksAgo(week); return `${weekText(week)}（${count} week${count === 1 ? "" : "s"} ago）`; }
function relative(left, right) { return 100 * right / left; }
function change(left, right) { const value = (right / left - 1) * 100; return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`; }
function classify(definition, left, right) { const ratio = right / left; if (Math.abs(ratio - 1) < .015) return ["稳定", "neutral"]; if (definition.risk) return ratio < 1 ? ["风险降低", "good"] : ["风险增加", "bad"]; return ratio > 1 ? ["改善", "good"] : ["下降", "bad"]; }

function sparkSvg(weeks, definition, leftIndex, rightIndex) {
  const base = weeks[leftIndex].indexes[definition.field];
  const values = weeks.slice(leftIndex, rightIndex + 1).map(week => relative(base, week.indexes[definition.field]));
  const width = 180, height = 34, padding = 2;
  let min = Math.min(...values), max = Math.max(...values); if (max - min < 1) { min -= .5; max += .5; }
  const path = values.map((value, index) => `${index ? "L" : "M"}${padding + index * (width - 2 * padding) / Math.max(1, values.length - 1)},${padding + (max - value) * (height - 2 * padding) / (max - min)}`).join(" ");
  const status = classify(definition, 100, values.at(-1))[1];
  const color = status === "good" ? "#1c8b62" : status === "bad" ? "#d45454" : "#8996a8";
  return `<svg viewBox="0 0 ${width} ${height}"><path d="${path}" fill="none" stroke="${color}" stroke-width="2.1" stroke-linecap="round"/><line x1="0" y1="${height / 2}" x2="${width}" y2="${height / 2}" stroke="#e9edf3"/></svg>`;
}

function renderProfile(profile) {
  document.getElementById("personMeta").innerHTML = `<span class="personId">${profile.displayId}</span><span>${profile.ageText}</span><span>${profile.region}</span><span>观察周期 ${profile.observationWeeks} 周</span><span>中断 ${profile.interruptedDays} 天</span>`;
}

function renderLife() {
  main.innerHTML = `<section class="panel hero"><div class="heroRow"><div class="weekBox"><div class="weekLabel">历史周</div><select id="leftWeek" class="weekSelect"></select><div id="leftMeta" class="weekMeta"></div></div><div class="vs">VS</div><div class="weekBox"><div class="weekLabel">比较周</div><select id="rightWeek" class="weekSelect"></select><div id="rightMeta" class="weekMeta"></div></div></div><div class="summaryLine"><div class="summaryText"><b>综合生活能力</b> · 相对变化基于左侧所选周</div><div class="summaryPills" id="summaryPills"></div></div></section><div class="metricGrid" id="metricGrid"></div><div class="contentGrid"><section class="panel chartPanel"><div class="panelHeader"><div><div class="panelTitle" id="chartTitle"></div><div class="panelSub" id="chartSub"></div></div><div class="legend"><span><i style="background:#2f6fe4"></i>周基线</span><span><i style="background:#8ea9db"></i>4周趋势</span><span><i style="background:#ef9b3a"></i>事件</span></div></div><div class="chartWrap"><svg id="chart"></svg></div><div class="timelineFooter"><div class="phaseBar" id="phaseBar"></div><button class="videoButton" id="evidenceButton" type="button" aria-label="播放核心数据" title="播放核心数据"><span>▶</span></button></div></section><aside class="panel detailPanel"><div class="detailTitle" id="detailTitle"></div><div class="detailExplain" id="detailExplain"></div><div id="evidenceList"></div><div class="noteBox">一级指数仅表达同一人的纵向相对变化。关节与运动学指标用于解释变化来源，不作为单次动作的临床绝对诊断。</div></aside></div><section class="panel autoEvidence" id="autoEvidence" hidden><div class="evidenceHead"><div><div class="evidenceTitle">核心数据 · 周代表动作</div><div class="evidenceSub" id="autoEvidenceSub"></div></div><span class="clockBadge">自动运行</span></div><div class="progressTrack"><span id="autoProgress"></span></div><div class="evidenceBody" id="autoEvidenceBody"></div></section>`;
  const left = document.getElementById("leftWeek"), right = document.getElementById("rightWeek");
  state.weeks.forEach((week, index) => { const option = document.createElement("option"); option.value = index; option.textContent = weekSelectText(week); left.appendChild(option.cloneNode(true)); right.appendChild(option); });
  left.value = Math.min(19, state.weeks.length - 1); right.value = state.weeks.length - 1;
  left.onchange = () => { if (+left.value > +right.value) right.value = left.value; updateLife(); };
  right.onchange = () => { if (+right.value < +left.value) left.value = right.value; updateLife(); };
  state.evidenceOpen = false;
  document.getElementById("evidenceButton").onclick = toggleAutoEvidence;
  state.removeClockView?.();
  state.removeClockView = clock.add({ renderAt(phase) { const bar = document.getElementById("autoProgress"); if (bar) bar.style.width = `${phase * 100}%`; } });
  updateLife();
}

function updateLife() {
  const leftIndex = +document.getElementById("leftWeek").value, rightIndex = +document.getElementById("rightWeek").value;
  const leftWeek = state.weeks[leftIndex], rightWeek = state.weeks[rightIndex];
  document.getElementById("leftMeta").innerHTML = `<span>${leftWeek.validSamples} 条有效片段</span><span>可信度 ${leftWeek.confidencePct.toFixed(1)}%</span><span>${leftWeek.status === "complete" ? "完整周" : "进行中"}</span>`;
  document.getElementById("rightMeta").innerHTML = `<span>${rightWeek.validSamples} 条有效片段</span><span>可信度 ${rightWeek.confidencePct.toFixed(1)}%</span><span>${rightWeek.status === "complete" ? "完整周" : "进行中"}</span>`;
  let good = 0, bad = 0, stable = 0;
  Object.values(LIFE_METRICS).forEach(definition => { const result = classify(definition, leftWeek.indexes[definition.field], rightWeek.indexes[definition.field])[1]; result === "good" ? good++ : result === "bad" ? bad++ : stable++; });
  document.getElementById("summaryPills").innerHTML = `<span class="pill good">${good} 项改善</span><span class="pill bad">${bad} 项下降</span><span class="pill neutral">${stable} 项稳定</span>`;
  document.getElementById("metricGrid").innerHTML = Object.entries(LIFE_METRICS).map(([key, definition]) => { const left = leftWeek.indexes[definition.field], right = rightWeek.indexes[definition.field], value = relative(left, right), [label, css] = classify(definition, left, right); return `<article class="metric ${key === state.metric ? "selected" : ""}" data-metric="${key}"><div class="metricLabel">${definition.label}</div><div class="metricValue">${value.toFixed(1)}<small>相对值</small></div><div class="metricDelta ${css}">${change(left, right)} · ${label}</div><div class="spark">${sparkSvg(state.weeks, definition, leftIndex, rightIndex)}</div></article>`; }).join("");
  document.querySelectorAll("[data-metric]").forEach(card => card.onclick = () => { state.metric = card.dataset.metric; updateLife(); });
  renderEvidence(leftWeek, rightWeek); renderChart(leftIndex, rightIndex); if (state.evidenceOpen) scheduleAutoEvidence(leftIndex, rightIndex);
}

function toggleAutoEvidence() {
  const section = document.getElementById("autoEvidence");
  state.evidenceOpen = !state.evidenceOpen;
  section.hidden = !state.evidenceOpen;
  if (!state.evidenceOpen) { clearTimeout(state.evidenceTimer); state.evidenceToken++; return; }
  scheduleAutoEvidence(+document.getElementById("leftWeek").value, +document.getElementById("rightWeek").value);
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderEvidence(leftWeek, rightWeek) {
  const definition = LIFE_METRICS[state.metric]; document.getElementById("detailTitle").textContent = `${definition.label} · 变化依据`; document.getElementById("detailExplain").textContent = definition.description;
  const evidence = LIFE_EVIDENCE[state.metric].map(([name, field, unit, higher, source]) => { const left = source === "indexes" ? leftWeek.indexes[field] : leftWeek.metrics[field], right = source === "indexes" ? rightWeek.indexes[field] : rightWeek.metrics[field], percent = (right / left - 1) * 100; let css = "neutral", label = "稳定"; if (Math.abs(percent) > 1.5) { const improvement = higher ? percent > 0 : percent < 0; css = improvement ? "good" : "bad"; label = improvement ? "改善" : "下降"; } const decimals = unit === "s" ? 2 : 1; return `<div class="evidence"><div class="evRow"><div class="evName">${name}</div><div><div class="evVals">${left.toFixed(decimals)}${unit} → ${right.toFixed(decimals)}${unit}</div><div class="evDelta ${css}">${percent >= 0 ? "+" : ""}${percent.toFixed(1)}% · ${label}</div></div></div><div class="evBar"><span style="width:${Math.min(100, Math.max(7, Math.abs(percent) * 3))}%;background:${css === "good" ? "#1c8b62" : css === "bad" ? "#d45454" : "#c79a54"}"></span></div></div>`; }).join("");
  const secondary = `<div class="secondaryTitle">二级人体功能拆解</div><div class="secondaryGrid">${LIFE_SECONDARY[state.metric].map(([name, field]) => { const value = relative(leftWeek.indexes[field], rightWeek.indexes[field]), percent = value - 100, css = Math.abs(percent) < 1.5 ? "neutral" : percent > 0 ? "good" : "bad"; return `<div class="secondaryItem"><div class="secondaryName">${name}</div><div class="secondaryValue">${value.toFixed(1)}</div><div class="secondaryDelta ${css}">${percent >= 0 ? "+" : ""}${percent.toFixed(1)}%</div></div>`; }).join("")}</div>`;
  document.getElementById("evidenceList").innerHTML = evidence + secondary;
}

function renderChart(leftIndex, rightIndex) {
  const definition = LIFE_METRICS[state.metric], slice = state.weeks.slice(leftIndex, rightIndex + 1), base = state.weeks[leftIndex].indexes[definition.field], values = slice.map(week => relative(base, week.indexes[definition.field])), moving = values.map((_, index) => values.slice(Math.max(0, index - 3), index + 1).reduce((sum, value) => sum + value, 0) / Math.min(4, index + 1));
  let min = Math.min(...values, ...moving, 96), max = Math.max(...values, ...moving, 104), padding = (max - min) * .13 || 2; min -= padding; max += padding;
  const W = 900, H = 290, L = 48, R = 18, T = 17, B = 38, x = index => L + index * (W - L - R) / Math.max(1, slice.length - 1), y = value => T + (max - value) * (H - T - B) / (max - min);
  let html = `<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4d82eb" stop-opacity=".18"/><stop offset="1" stop-color="#4d82eb" stop-opacity="0"/></linearGradient></defs>`;
  [...new Set([min, (min + max) / 2, max, 100].map(value => +value.toFixed(2)))].sort((a, b) => a - b).forEach(value => html += `<line x1="${L}" y1="${y(value)}" x2="${W - R}" y2="${y(value)}" stroke="${Math.abs(value - 100) < .1 ? "#c8d2e2" : "#edf0f4"}" stroke-dasharray="${Math.abs(value - 100) < .1 ? "5 5" : "0"}"/><text x="${L - 8}" y="${y(value) + 4}" text-anchor="end" font-size="10" fill="#94a0b1">${value.toFixed(0)}</text>`);
  const path = values.map((value, index) => `${index ? "L" : "M"}${x(index)},${y(value)}`).join(" "), movingPath = moving.map((value, index) => `${index ? "L" : "M"}${x(index)},${y(value)}`).join(" ");
  html += `<path d="M${x(0)},${y(values[0])} ${path.slice(1)} L${x(values.length - 1)},${H - B} L${x(0)},${H - B} Z" fill="url(#area)"/><path d="${path}" fill="none" stroke="#2f6fe4" stroke-width="2.4"/><path d="${movingPath}" fill="none" stroke="#8ea9db" stroke-width="1.7" stroke-dasharray="6 5"/>`;
  slice.forEach((week, index) => { if (week.event) html += `<line x1="${x(index)}" y1="${T}" x2="${x(index)}" y2="${H - B}" stroke="#ef9b3a" stroke-dasharray="3 4"/><circle cx="${x(index)}" cy="${T + 7}" r="4" fill="#ef9b3a"><title>${week.event}</title></circle>`; html += `<circle cx="${x(index)}" cy="${y(values[index])}" r="4" fill="#fff" stroke="#2f6fe4" stroke-width="2"><title>${weekText(week)} · ${definition.label} ${values[index].toFixed(1)}</title></circle>`; });
  const step = Math.max(1, Math.ceil(slice.length / 6)); for (let index = 0; index < slice.length; index += step) html += `<text x="${x(index)}" y="${H - 14}" text-anchor="middle" font-size="10" fill="#8e9aac">${formatDate(slice[index].weekStart).slice(2, 7)}</text>`;
  const chart = document.getElementById("chart"); chart.setAttribute("viewBox", `0 0 ${W} ${H}`); chart.innerHTML = html; document.getElementById("chartTitle").textContent = `${definition.label} · 长期变化曲线`; document.getElementById("chartSub").textContent = `所选区间 ${slice.length} 周 · 相对左侧所选周 · 最低 ${Math.min(...values).toFixed(1)} / 最高 ${Math.max(...values).toFixed(1)} / 终点 ${values.at(-1).toFixed(1)}`;
  const phases = []; slice.forEach(week => { if (week.phase && phases.at(-1) !== week.phase) phases.push(week.phase); }); const events = slice.filter(week => week.event).map(week => `${formatDate(week.weekStart).slice(5)} · ${week.event}`); document.getElementById("phaseBar").innerHTML = phases.map(value => `<span class="phaseChip">${value}</span>`).join("") + events.map(value => `<span class="phaseChip event">${value}</span>`).join("");
}

function scheduleAutoEvidence(leftIndex, rightIndex) {
  clearTimeout(state.evidenceTimer); const token = ++state.evidenceToken, weeks = state.weeks.slice(leftIndex, rightIndex + 1), rows = Math.ceil(weeks.length / 4), height = 64 + rows * 230 + 2;
  document.getElementById("autoEvidenceSub").textContent = `正在准备所选区间的 ${weeks.length} 周核心数据`;
  document.getElementById("autoEvidenceBody").innerHTML = `<div class="loadingGrid">${weeks.map(week => `<div class="loadingCell"><span class="spinner"></span><span>${formatDate(week.weekStart)}</span></div>`).join("")}</div>`;
  state.evidenceTimer = setTimeout(() => { if (token !== state.evidenceToken) return; const params = new URLSearchParams({ count: String(weeks.length), autoplay: "1", controls: "0", stagger: "140" }); weeks.forEach(week => params.append("title", weekText(week))); document.getElementById("autoEvidenceSub").textContent = `所选区间共 ${weeks.length} 周 · 正在按日期顺序加载`; document.getElementById("autoEvidenceBody").innerHTML = `<iframe class="poseFrame" style="height:${height}px" src="/pose/pose-sessions.html?${params}" title="Pose Sessions · ${weeks.length} 周" loading="eager" scrolling="no"></iframe>`; clock.restart(); }, 1000);
}

async function selectDomain(domain) {
  state.domainCleanup?.(); state.domainCleanup = null; state.domain = domain; document.querySelectorAll("[data-domain]").forEach(button => button.classList.toggle("active", button.dataset.domain === domain)); clearTimeout(state.evidenceTimer); state.evidenceToken++;
  if (!DOMAINS[domain].available) { state.removeClockView?.(); state.removeClockView = null; main.innerHTML = `<section class="panel emptyState">选择的人物该数据为空</section>`; return; }
  if (domain === "life") { state.weeks = state.lifeWeeks; renderLife(); return; }
  if (domain === "emotion") {
    state.removeClockView?.(); state.removeClockView = null;
    main.innerHTML = `<section class="panel pageLoading"><span class="spinner"></span><span>正在加载心理情绪核心数据…</span></section>`;
    try {
      const summary = await repository.getWeeklySummary(state.personId, "emotion");
      if (state.domain !== "emotion") return;
      state.domainCleanup = mountEmotionView({ main, weeks: summary.weeks, repository, clock, personId: state.personId });
    } catch (error) {
      console.error(error); main.innerHTML = `<section class="panel emptyState errorState">心理情绪核心数据加载失败。</section>`;
    }
  }
}

async function initialize() {
  try { const [profile, manifest, summary] = await Promise.all([repository.getProfile(state.personId), repository.getManifest(state.personId), repository.getWeeklySummary(state.personId, "life")]); if (manifest.schemaVersion !== "1.0" || summary.schemaVersion !== "1.0") throw new Error("不支持的数据版本"); renderProfile(profile); state.lifeWeeks = summary.weeks; state.weeks = state.lifeWeeks; document.querySelectorAll("[data-domain]").forEach(button => button.onclick = () => selectDomain(button.dataset.domain)); renderLife(); } catch (error) { console.error(error); main.innerHTML = `<section class="panel emptyState errorState">核心数据加载失败，请确认本地服务和数据文件完整。</section>`; }
}

initialize();
