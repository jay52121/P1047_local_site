const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const fmt = value => Number.isFinite(Number(value)) ? Number(value).toFixed(1) : "—";
const dateText = value => value.replaceAll("-", ".");
const weekText = week => `${dateText(week.weekStart)} — ${dateText(week.weekEnd)}`;

const CONFIG = {
  cognition: {
    title: "认知行为状态", metric: "executionOrganization", defaults: [12, 22],
    evidenceTitle: "任务路径 · 行为组织证据", note: "展示日常任务组织、遗漏、重复、犹豫与自主纠正线索，不构成认知障碍诊断。",
    labels: { taskInitiation: "任务启动", taskCompleteness: "任务完整", executionOrganization: "执行组织", selfCorrection: "自主纠正", promptIndependence: "提示独立" },
  },
  sleep: {
    title: "睡眠与生活节律", metric: "nightContinuity", defaults: [12, 22],
    evidenceTitle: "24 小时节律 · 睡眠连续性证据", note: "睡眠结果来自个人长期节律比较，仅表达相对变化，不替代医学睡眠评估。",
    labels: { scheduleRegularity: "作息规律", sleepOnsetStability: "入睡稳定", nightContinuity: "夜间连续", daytimeWakefulness: "昼间清醒", circadianAlignment: "昼夜对齐" },
  },
  participation: {
    title: "活动与社会参与", metric: "outsideParticipation", defaults: [28, 35],
    evidenceTitle: "活动轨迹 · 空间与参与证据", note: "空间、外出与互动指标仅用于同一个人的长期相对变化展示。",
    labels: { spaceRange: "活动空间", activityDiversity: "活动多样", outsideParticipation: "外出参与", socialParticipation: "社会互动", participationContinuity: "参与连续" },
  },
};

function selectorText(week) {
  const now = new Date(), start = new Date(`${week.weekStart}T00:00:00`);
  const count = Math.max(0, Math.round((now - start) / 604800000));
  return `${weekText(week)}（${count} week${count === 1 ? "" : "s"} ago）`;
}

function classify(left, right) {
  if (!Number.isFinite(left) || !Number.isFinite(right)) return ["不可比较", "neutral", 0];
  const delta = right / left * 100 - 100;
  if (Math.abs(delta) < 2) return ["稳定", "neutral", delta];
  return delta > 0 ? ["改善", "good", delta] : ["下降", "bad", delta];
}

function chartSvg(weeks, key, leftIndex, rightIndex) {
  const slice = weeks.slice(leftIndex, rightIndex + 1), base = slice[0].indexes[key];
  const values = slice.map(week => week.indexes[key] / base * 100);
  let min = Math.min(...values, 96), max = Math.max(...values, 104); const pad = Math.max(2, (max - min) * .14); min -= pad; max += pad;
  const W=900,H=290,L=48,R=18,T=18,B=38,x=i=>L+i*(W-L-R)/Math.max(1,values.length-1),y=v=>T+(max-v)*(H-T-B)/(max-min);
  let svg = [min,(min+max)/2,max,100].map(v=>`<line x1="${L}" y1="${y(v)}" x2="${W-R}" y2="${y(v)}" stroke="#edf0f4"/><text x="${L-8}" y="${y(v)+4}" text-anchor="end" font-size="10" fill="#94a0b1">${v.toFixed(0)}</text>`).join("");
  const path=values.map((v,i)=>`${i?"L":"M"}${x(i)},${y(v)}`).join(" ");
  svg += `<path class="showcaseLine" d="${path}" fill="none" stroke="#2f6fe4" stroke-width="2.6"/>`;
  slice.forEach((week,i)=>{ if(week.event) svg += `<line x1="${x(i)}" y1="${T}" x2="${x(i)}" y2="${H-B}" stroke="#ef9b3a" stroke-dasharray="3 4"/><circle class="eventPulse" cx="${x(i)}" cy="${T+7}" r="4" fill="#ef9b3a"/>`; svg += `<circle cx="${x(i)}" cy="${y(values[i])}" r="4" fill="#fff" stroke="#2f6fe4" stroke-width="2"/>`; });
  return { svg, sub: `所选区间 ${slice.length} 周 · 相对左侧所选周 · ${values[0].toFixed(1)} → ${values.at(-1).toFixed(1)}` };
}

function cognitionVisual(unit) {
  const session = unit.sessions[0], actual = new Set(session.actualSteps);
  const steps = session.expectedSteps.map((step, index) => `<span class="taskNode ${actual.has(step) ? "done" : "miss"}" style="--i:${index}"><i>${index+1}</i>${step.replaceAll("_", " ")}</span>`).join("");
  const events = session.events.length ? session.events.map(event => `<em>${event.label || event.type}</em>`).join("") : "<em>路径完整</em>";
  return `<div class="taskPath">${steps}</div><div class="eventTags">${events}</div><div class="miniStats"><span>启动 <b>${fmt(session.result.startupLatencySec)}s</b></span><span>顺序 <b>${fmt(session.result.orderIntegrityPct)}%</b></span><span>提示 <b>${fmt(session.result.promptPerStep)}</b></span></div>`;
}

function sleepVisual(unit) {
  const night = unit.nights.find(item => item.date === unit.representativeNightDate) || unit.nights[0];
  const onset = ((night.sleepOnsetMin - 360 + 1440) % 1440) / 1440 * 360, duration = night.sleepWindowMin / 1440 * 360;
  const ticks = night.awakenings.map(a => `<i style="transform:rotate(${((a.startMin-360+1440)%1440)/4}deg)"></i>`).join("");
  return `<div class="sleepScene"><div class="sleepRing" style="--start:${onset}deg;--end:${onset+duration}deg">${ticks}<div><b>${fmt(night.estimatedSleepMin/60)}h</b><span>估计睡眠</span></div></div><div class="sleepLegend"><span>入睡 <b>${Math.floor(night.sleepOnsetMin/60)%24}:${String(Math.round(night.sleepOnsetMin%60)).padStart(2,"0")}</b></span><span>起床 <b>${Math.floor(night.finalRiseMin/60)%24}:${String(Math.round(night.finalRiseMin%60)).padStart(2,"0")}</b></span><span>夜醒 <b>${night.awakenings.length} 次</b></span></div></div>`;
}

function participationVisual(unit) {
  const day = unit.days.find(item => item.date === unit.representativeDay) || unit.days[0];
  const zones = Object.entries(day.zoneMinutes).sort((a,b)=>b[1]-a[1]).slice(0,5);
  return `<div class="routeScene"><svg viewBox="0 0 320 125"><path class="routePath" d="M30 94 C70 30 120 108 158 56 S245 28 294 75"/><circle cx="30" cy="94" r="8"/><circle cx="158" cy="56" r="8"/><circle cx="294" cy="75" r="8"/></svg><div class="zoneBars">${zones.map(([name,value])=>`<span style="--w:${Math.max(8,value/Math.max(...zones.map(x=>x[1]))*100)}%"><i>${name.replace("_"," ")}</i><b>${fmt(value)}m</b></span>`).join("")}</div></div><div class="miniStats"><span>外出 <b>${day.outingCount} 次</b></span><span>互动 <b>${day.interactionEpisodes} 次</b></span><span>有效活动 <b>${fmt(day.meaningfulActivityMinutes)}m</b></span></div>`;
}

function evidenceCard(domain, evidence, week) {
  const visual = domain === "cognition" ? cognitionVisual(evidence) : domain === "sleep" ? sleepVisual(evidence) : participationVisual(evidence);
  return `<div class="showcaseCardHead"><b>${weekText(week)}</b><span>${week.phase || "长期基线"}</span></div><div class="showcaseVisual">${visual}</div>`;
}

export function mountShowcaseView({ main, domain, weeks, evidenceWeeks, metricMapping, clock, initialEvidenceOpen=false, onEvidenceChange=()=>{} }) {
  const config=CONFIG[domain], evidenceById=new Map(evidenceWeeks.map(week=>[week.weekId,week]));
  const view={metric:config.metric,open:initialEvidenceOpen,token:0,removeClock:null};
  main.innerHTML=`<section class="panel hero showcaseEnter"><div class="heroRow"><div class="weekBox"><div class="weekLabel">历史周</div><select id="showLeft" class="weekSelect"></select><div id="showLeftMeta" class="weekMeta"></div></div><div class="vs">VS</div><div class="weekBox"><div class="weekLabel">比较周</div><select id="showRight" class="weekSelect"></select><div id="showRightMeta" class="weekMeta"></div></div></div><div class="summaryLine"><div class="summaryText"><b>${config.title}</b> · 个人长期基线对比</div><div class="summaryPills" id="showPills"></div></div></section><div class="metricGrid showcaseEnter" id="showMetrics"></div><div class="contentGrid showcaseEnter"><section class="panel chartPanel"><div class="panelHeader"><div><div class="panelTitle" id="showChartTitle"></div><div class="panelSub" id="showChartSub"></div></div><div class="legend"><span><i style="background:#2f6fe4"></i>周指数</span><span><i style="background:#ef9b3a"></i>关键事件</span></div></div><div class="chartWrap"><svg id="showChart" viewBox="0 0 900 290"></svg></div><div class="timelineFooter"><div class="phaseBar" id="showPhases"></div><button class="videoButton" id="showEvidenceButton"><span>▶</span></button></div></section><aside class="panel detailPanel"><div class="detailTitle" id="showDetailTitle"></div><div class="detailExplain">由可解释原始量聚合后，相对该人物前五周基线归一化。</div><div id="showEvidenceList"></div><div class="noteBox">${config.note}</div></aside></div><section class="panel autoEvidence" id="showAutoEvidence" ${view.open?"":"hidden"}><div class="evidenceHead"><div><div class="evidenceTitle">${config.evidenceTitle}</div><div class="evidenceSub" id="showEvidenceSub"></div></div><span class="clockBadge">核心数据</span></div><div class="progressTrack"><span id="showProgress"></span></div><div class="showcaseEvidenceGrid" id="showEvidenceGrid"></div></section>`;
  const left=document.getElementById("showLeft"),right=document.getElementById("showRight");
  weeks.forEach((week,index)=>{const option=new Option(selectorText(week),index);left.add(option.cloneNode(true));right.add(option)}); left.value=config.defaults[0];right.value=config.defaults[1];

  function update(){const li=+left.value,ri=+right.value,lw=weeks[li],rw=weeks[ri];document.getElementById("showLeftMeta").innerHTML=`<span>有效单元 ${lw.validUnits}/${lw.expectedUnits}</span><span>可信度 ${fmt(lw.confidencePct)}%</span>`;document.getElementById("showRightMeta").innerHTML=`<span>有效单元 ${rw.validUnits}/${rw.expectedUnits}</span><span>可信度 ${fmt(rw.confidencePct)}%</span>`;let good=0,bad=0,stable=0;Object.keys(config.labels).forEach(key=>{const css=classify(lw.indexes[key],rw.indexes[key])[1];css==="good"?good++:css==="bad"?bad++:stable++});document.getElementById("showPills").innerHTML=`<span class="pill good">${good} 项改善</span><span class="pill bad">${bad} 项下降</span><span class="pill neutral">${stable} 项稳定</span>`;document.getElementById("showMetrics").innerHTML=Object.entries(config.labels).map(([key,label])=>{const [status,css,delta]=classify(lw.indexes[key],rw.indexes[key]);return `<article class="metric ${key===view.metric?"selected":""}" data-show-metric="${key}"><div class="metricLabel">${label}</div><div class="metricValue">${fmt(rw.indexes[key]/lw.indexes[key]*100)}<small>相对值</small></div><div class="metricDelta ${css}">${delta>=0?"+":""}${fmt(delta)}% · ${status}</div><div class="indexRail"><i style="width:${Math.min(100,Math.max(8,rw.indexes[key]-65))}%"></i></div></article>`}).join("");document.querySelectorAll("[data-show-metric]").forEach(card=>card.onclick=()=>{view.metric=card.dataset.showMetric;update()});const chart=chartSvg(weeks,view.metric,li,ri);document.getElementById("showChart").innerHTML=chart.svg;document.getElementById("showChartTitle").textContent=`${config.labels[view.metric]} · 40 周变化`;document.getElementById("showChartSub").textContent=chart.sub;document.getElementById("showPhases").innerHTML=[...new Set(weeks.slice(li,ri+1).map(w=>w.phase))].map(x=>`<span class="phaseChip">${x}</span>`).join("")+weeks.slice(li,ri+1).filter(w=>w.event).map(w=>`<span class="phaseChip event">${w.event}</span>`).join("");const fields=metricMapping.indexes[view.metric].rawMetrics;document.getElementById("showDetailTitle").textContent=`${config.labels[view.metric]} · 变化依据`;document.getElementById("showEvidenceList").innerHTML=fields.map(key=>{const def=metricMapping.rawMetrics[key],l=lw.metrics[key],r=rw.metrics[key],delta=l?100*r/l-100:0,improved=def.higherIsBetter?delta>0:delta<0,css=Math.abs(delta)<2?"neutral":improved?"good":"bad";return `<div class="evidence"><div class="evRow"><div class="evName">${def.label}</div><div><div class="evVals">${fmt(l)}${def.unit} → ${fmt(r)}${def.unit}</div><div class="evDelta ${css}">${delta>=0?"+":""}${fmt(delta)}%</div></div></div></div>`}).join("");if(view.open)loadEvidence(li,ri)}
  async function loadEvidence(li,ri){const token=++view.token,selected=[weeks[li],weeks[ri]],grid=document.getElementById("showEvidenceGrid");grid.innerHTML=selected.map(w=>`<article class="showcaseCard loading" data-show-week="${w.weekId}"><div class="showcaseCardHead"><b>${weekText(w)}</b><span>准备核心数据</span></div><div class="emotionLoading"><span class="spinner"></span><span>核心数据 loading</span></div></article>`).join("");document.getElementById("showEvidenceSub").textContent="正在对齐两周核心数据";await wait(1000);for(const week of selected){if(token!==view.token)return;const card=grid.querySelector(`[data-show-week="${week.weekId}"]`);card.classList.remove("loading");card.innerHTML=evidenceCard(domain,evidenceById.get(week.weekId),week);await wait(180)}document.getElementById("showEvidenceSub").textContent="历史周与比较周 · 同源证据对齐完成";clock.restart()}
  left.onchange=()=>{if(+left.value>+right.value)right.value=left.value;update()};right.onchange=()=>{if(+right.value<+left.value)left.value=right.value;update()};document.getElementById("showEvidenceButton").onclick=()=>{view.open=!view.open;onEvidenceChange(view.open);document.getElementById("showAutoEvidence").hidden=!view.open;if(view.open){loadEvidence(+left.value,+right.value);document.getElementById("showAutoEvidence").scrollIntoView({behavior:"smooth",block:"start"})}else view.token++};view.removeClock=clock.add({renderAt(phase){const bar=document.getElementById("showProgress");if(bar)bar.style.width=`${phase*100}%`}});update();return()=>{view.token++;view.removeClock?.()};
}
