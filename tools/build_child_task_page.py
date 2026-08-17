#!/usr/bin/env python3
import json
import math
import random
import re
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "person/P-1047/longitudinal-function/index.html"
OUTPUT = ROOT / "person/C-2308/task-longitudinal/index.html"


TASK_CONFIGS = [
    ("homework", "课后作业", "首次注意力不集中", 11.2, 31),
    ("piano", "钢琴练习", "首次无序敲击", 8.8, 47),
    ("reading", "独立阅读", "首次离开阅读内容", 14.0, 59),
    ("writing", "汉字书写", "首次停笔或转移任务", 7.6, 71),
    ("building", "益智拼搭", "首次放弃当前步骤", 16.5, 83),
    ("tidying", "房间整理", "首次需要额外提示", 5.1, 97),
]


EVENTS = {
    "homework": {8: "期中作业量增加", 14: "开始使用分段计时提示"},
    "piano": {9: "更换练习曲", 15: "开始分段慢练"},
    "reading": {10: "阅读材料难度提升", 17: "固定安静阅读时段"},
    "writing": {12: "书写任务量增加", 19: "调整桌椅与握笔提示"},
    "building": {7: "引入更复杂的拼搭套件", 16: "开始独立规划拼搭步骤"},
    "tidying": {11: "整理步骤增加", 18: "开始使用图示清单"},
}


def progression(key, week):
    if key == "homework":
        return 0.45 * min(week - 1, 7) - 0.95 * max(0, min(week - 8, 5)) + 0.72 * max(0, week - 13)
    if key == "piano":
        return 0.18 * min(week - 1, 8) - 0.82 * max(0, min(week - 9, 4)) + 0.58 * max(0, week - 13)
    if key == "reading":
        return 0.39 * (week - 1) - 2.2 * math.exp(-((week - 11) / 2.2) ** 2)
    if key == "writing":
        return 0.23 * (week - 1) - 2.0 * math.exp(-((week - 16) / 2.5) ** 2)
    if key == "building":
        return 0.20 * (week - 1) - 2.8 * math.exp(-((week - 8) / 2.0) ** 2) + 0.8 * math.sin(week * 0.5)
    return 0.22 * (week - 1) - 1.4 * math.exp(-((week - 12) / 2.4) ** 2)


def phase(key, week):
    boundaries = {
        "homework": [(7, "逐步适应期"), (13, "任务压力波动期"), (24, "策略支持恢复期")],
        "piano": [(8, "稳定练习期"), (14, "新曲适应期"), (24, "分段训练改善期")],
        "reading": [(9, "稳定阅读期"), (16, "难度适应期"), (24, "持续改善期")],
        "writing": [(11, "书写适应期"), (18, "疲劳波动期"), (24, "姿势调整恢复期")],
        "building": [(6, "稳定完成期"), (15, "复杂任务适应期"), (24, "独立规划期")],
        "tidying": [(10, "提示依赖期"), (17, "多步骤适应期"), (24, "清单支持改善期")],
    }[key]
    return next(label for end, label in boundaries if week <= end)


def build_task(key, label, first_label, base, seed):
    rng = random.Random(seed)
    start = date(2026, 2, 23)
    rows = []
    for week in range(1, 25):
        first = max(2.2, base + progression(key, week) + rng.uniform(-0.75, 0.75))
        focus = min(94.0, max(48.0, 58 + first * 1.65 + rng.uniform(-2.2, 2.2)))
        prompts = max(0.2, 5.8 - first * 0.23 + rng.uniform(-0.45, 0.45))
        completion = min(99.0, max(55.0, 70 + first * 1.2 + rng.uniform(-2.5, 2.5)))
        variability = max(3.0, 16.5 - first * 0.45 + rng.uniform(-1.0, 1.0))
        continuous = max(1.5, first * 0.72 + rng.uniform(-0.4, 0.4))
        switches = max(0.2, 6.2 - first * 0.18 + rng.uniform(-0.5, 0.5))
        off_task = max(0.4, 8.0 - first * 0.22 + rng.uniform(-0.5, 0.5))
        beginning = start + timedelta(days=(week - 1) * 7)
        event = EVENTS[key].get(week)
        rows.append({
            "周序号": week,
            "周开始": beginning.isoformat(),
            "周结束": (beginning + timedelta(days=6)).isoformat(),
            "周状态": "完整周",
            "有效任务数": rng.randint(4, 8),
            "基线可信度_%": round(rng.uniform(92.5, 97.8), 1),
            "首次事件分钟": round(first, 2),
            "持续专注率_%": round(focus, 1),
            "提示次数": round(prompts, 1),
            "任务完成率_%": round(completion, 1),
            "周内波动_CV_%": round(variability, 1),
            "平均连续专注段_min": round(continuous, 2),
            "任务切换次数": round(switches, 1),
            "偏离任务累计_min": round(off_task, 2),
            "阶段解释": phase(key, week),
            "事件标注": event,
            "数据备注": "模拟观察数据，仅用于界面与分析流程验证",
        })
    return {
        "label": label,
        "firstEventLabel": first_label,
        "rows": rows,
    }


def main():
    source = SOURCE.read_text(encoding="utf-8")
    style = re.search(r"<style>([\s\S]*?)</style>", source).group(1)
    style += """
.taskEventGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:13px}
.taskEvent{padding:12px;border:1px solid var(--line);border-radius:12px;background:#fbfcfe}
.taskEventWeek{font-size:10px;color:#8290a2}.taskEventValue{font-size:22px;font-weight:850;margin:8px 0 4px;color:#243a59}
.taskEventValue small{font-size:10px;color:#8a96a6;margin-left:3px}.taskEventName{font-size:11px;color:#58677b;line-height:1.5}
@media(max-width:1250px){.taskEventGrid{grid-template-columns:repeat(3,minmax(0,1fr))}}
"""
    tasks = {key: build_task(key, label, event, base, seed) for key, label, event, base, seed in TASK_CONFIGS}
    html = TEMPLATE.replace("__STYLE__", style).replace("__TASKS__", json.dumps(tasks, ensure_ascii=False, separators=(",", ":")))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(OUTPUT)


TEMPLATE = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>192.168.50.154:5173 · C-2308</title><style>__STYLE__</style></head><body>
<script>if(location.protocol==='file:')location.replace('http://192.168.50.154:5173/person/C-2308/task-longitudinal/')</script>
<div class="app"><div class="pageHead"><div><h1>SISP</h1><p>Child task longitudinal baseline · weekly comparison</p><div class="personMeta" aria-label="匿名儿童观察档案"><span class="personId">CH-2308</span><span>9 岁零 146 天</span><span>四川省</span><span>观察周期 24 周</span><span>中断 4 天</span></div></div><div class="status">192.168.50.154:5173</div></div>
<div class="shell"><aside class="sidebar"><div class="sideTitle">观察任务</div>
<div class="place active" data-place="homework"><span class="placeDot"></span>课后作业</div>
<div class="place" data-place="piano"><span class="placeDot"></span>钢琴练习</div>
<div class="place" data-place="reading"><span class="placeDot"></span>独立阅读</div>
<div class="place" data-place="writing"><span class="placeDot"></span>汉字书写</div>
<div class="place" data-place="building"><span class="placeDot"></span>益智拼搭</div>
<div class="place" data-place="tidying"><span class="placeDot"></span>房间整理</div>
<div class="sideNote">匿名纵向模拟数据<br/>各任务独立建模，不用于诊断。</div></aside><main class="main" id="main"></main></div></div>
<script>
const TASKS=__TASKS__;
let activeTask='homework',activeMetric='first',eventLoadTimer=null;
const sharedMetrics={
 first:{field:'首次事件分钟',unit:'min',higher:true,dec:1},focus:{label:'持续专注率',field:'持续专注率_%',unit:'%',higher:true,dec:1},
 prompts:{label:'提示次数',field:'提示次数',unit:'次',higher:false,dec:1},completion:{label:'任务完成率',field:'任务完成率_%',unit:'%',higher:true,dec:1},
 variability:{label:'周内波动',field:'周内波动_CV_%',unit:'%',higher:false,dec:1}};
function currentTask(){return TASKS[activeTask]} function rows(){return currentTask().rows}
function metricDefs(){return{...sharedMetrics,first:{...sharedMetrics.first,label:currentTask().firstEventLabel}}}
function d(s){return new Date(s+'T00:00:00')} function fmt(s){const x=d(s);return x.getFullYear()+'.'+String(x.getMonth()+1).padStart(2,'0')+'.'+String(x.getDate()).padStart(2,'0')}
function weekText(r){return fmt(r['周开始'])+' — '+fmt(r['周结束'])} function rel(a,b){return 100*b/a}
function classify(def,a,b){const p=(b/a-1)*100;if(Math.abs(p)<2)return['稳定','neutral'];const good=def.higher?p>0:p<0;return[good?'改善':'下降',good?'good':'bad']}
function delta(a,b){const p=(b/a-1)*100;return(p>=0?'+':'')+p.toFixed(1)+'%'}
function sparkSVG(data,def,li,ri){const vals=data.slice(li,ri+1).map(x=>+x[def.field]),w=180,h=34,p=2;let mn=Math.min(...vals),mx=Math.max(...vals);if(mx-mn<.1){mn-=.5;mx+=.5}const path=vals.map((v,i)=>`${i?'L':'M'}${p+i*(w-2*p)/Math.max(1,vals.length-1)},${p+(mx-v)*(h-2*p)/(mx-mn)}`).join(' ');return `<svg viewBox="0 0 ${w} ${h}"><path d="${path}" fill="none" stroke="#2f6fe4" stroke-width="2.1" stroke-linecap="round"/><line x1="0" y1="${h/2}" x2="${w}" y2="${h/2}" stroke="#e9edf3"/></svg>`}
function render(){const data=rows(),task=currentTask();document.getElementById('main').innerHTML=`
<section class="panel hero"><div class="heroRow"><div class="weekBox"><div class="weekLabel">历史周</div><select id="leftWeek" class="weekSelect"></select><div id="leftMeta" class="weekMeta"></div></div><div class="vs">VS</div><div class="weekBox"><div class="weekLabel">比较周</div><select id="rightWeek" class="weekSelect"></select><div id="rightMeta" class="weekMeta"></div></div></div><div class="summaryLine"><div class="summaryText"><b>${task.label}</b> · 各项变化相对左侧所选周</div><div class="summaryPills" id="summaryPills"></div></div></section>
<div class="metricGrid" id="metricGrid"></div><div class="contentGrid"><section class="panel chartPanel"><div class="panelHeader"><div><div class="panelTitle" id="chartTitle"></div><div class="panelSub" id="chartSub"></div></div><div class="legend"><span><i style="background:#2f6fe4"></i>周观察值</span><span><i style="background:#8ea9db"></i>4周趋势</span><span><i style="background:#ef9b3a"></i>任务事件</span></div></div><div class="chartWrap"><svg id="chart"></svg></div><div class="timelineFooter"><div class="phaseBar" id="phaseBar"></div><button class="videoButton" type="button" aria-label="查看周任务事件" title="查看周任务事件" onclick="openEvents()"><span>▶</span></button></div></section>
<aside class="panel detailPanel"><div class="detailTitle" id="detailTitle"></div><div class="detailExplain" id="detailExplain"></div><div id="evidenceList"></div><div class="noteBox">本页为匿名模拟纵向数据，用于研究不同任务中的注意与行为变化曲线，不构成儿童发展或医学诊断。</div></aside></div>
<section class="panel videoSection" id="eventSection" hidden><div class="videoSectionTitle">周任务事件</div><div class="videoSectionSub" id="eventSectionSub"></div><div id="taskEvents"></div></section>`;
const L=document.getElementById('leftWeek'),R=document.getElementById('rightWeek');data.forEach((r,i)=>{const o=document.createElement('option');o.value=i;o.textContent=weekText(r);L.appendChild(o.cloneNode(true));R.appendChild(o)});L.value=0;R.value=data.length-1;L.onchange=()=>{if(+L.value>+R.value)R.value=L.value;update()};R.onchange=()=>{if(+R.value<+L.value)L.value=R.value;update()};update()}
function update(){const data=rows(),defs=metricDefs(),li=+leftWeek.value,ri=+rightWeek.value,l=data[li],r=data[ri];leftMeta.innerHTML=`<span>${l['有效任务数']} 次有效任务</span><span>可信度 ${l['基线可信度_%']}%</span><span>${l['周状态']}</span>`;rightMeta.innerHTML=`<span>${r['有效任务数']} 次有效任务</span><span>可信度 ${r['基线可信度_%']}%</span><span>${r['周状态']}</span>`;let good=0,bad=0,stable=0;Object.values(defs).forEach(def=>{const c=classify(def,l[def.field],r[def.field])[1];c==='good'?good++:c==='bad'?bad++:stable++});summaryPills.innerHTML=`<span class="pill good">${good} 项改善</span><span class="pill bad">${bad} 项下降</span><span class="pill neutral">${stable} 项稳定</span>`;metricGrid.innerHTML=Object.entries(defs).map(([k,def])=>{const [label,cls]=classify(def,l[def.field],r[def.field]),value=+r[def.field];return `<div class="metric ${k===activeMetric?'selected':''}" data-key="${k}"><div class="metricLabel">${def.label}</div><div class="metricValue">${value.toFixed(def.dec)}<small>${def.unit}</small></div><div class="metricDelta ${cls}">${delta(l[def.field],r[def.field])} · ${label}</div><div class="spark">${sparkSVG(data,def,li,ri)}</div></div>`}).join('');document.querySelectorAll('.metric').forEach(x=>x.onclick=()=>{activeMetric=x.dataset.key;update()});renderEvidence(l,r);renderChart(li,ri)}
function renderEvidence(l,r){const def=metricDefs()[activeMetric],items=[[def.label,def.field,def.unit,def.higher],['平均连续专注段','平均连续专注段_min','min',true],['任务切换次数','任务切换次数','次',false],['偏离任务累计','偏离任务累计_min','min',false]];detailTitle.textContent=def.label+' · 变化依据';detailExplain.textContent=activeMetric==='first'?`每周多次${currentTask().label}观察中，首次出现“${currentTask().firstEventLabel}”的时间中位数。`:'结合任务过程事件与有效参与情况形成的周级观察指标。';evidenceList.innerHTML=items.map(([name,field,unit,higher])=>{const a=+l[field],b=+r[field],p=(b/a-1)*100,good=higher?p>2:p<-2,stable=Math.abs(p)<=2,cls=stable?'neutral':good?'good':'bad',txt=stable?'稳定':good?'改善':'下降';return `<div class="evidence"><div class="evRow"><div class="evName">${name}</div><div><div class="evVals">${a.toFixed(1)}${unit} → ${b.toFixed(1)}${unit}</div><div class="evDelta ${cls}">${p>=0?'+':''}${p.toFixed(1)}% · ${txt}</div></div></div><div class="evBar"><span style="width:${Math.min(100,Math.max(7,Math.abs(p)*3))}%;background:${cls==='good'?'#1c8b62':cls==='bad'?'#d45454':'#c79a54'}"></span></div></div>`}).join('')}
function renderChart(li,ri){const data=rows(),def=metricDefs()[activeMetric],slice=data.slice(li,ri+1),vals=slice.map(x=>+x[def.field]),ma=vals.map((v,i)=>{let s=0,n=0;for(let j=Math.max(0,i-3);j<=i;j++){s+=vals[j];n++}return s/n});let mn=Math.min(...vals,...ma),mx=Math.max(...vals,...ma),pad=(mx-mn)*.14||1;mn-=pad;mx+=pad;const W=900,H=290,L=48,R=18,T=17,B=38,x=i=>L+i*(W-L-R)/Math.max(1,slice.length-1),y=v=>T+(mx-v)*(H-T-B)/(mx-mn);let h='';[mn,(mn+mx)/2,mx].forEach(v=>h+=`<line x1="${L}" y1="${y(v)}" x2="${W-R}" y2="${y(v)}" stroke="#edf0f4"/><text x="${L-8}" y="${y(v)+4}" text-anchor="end" font-size="10" fill="#94a0b1">${v.toFixed(1)}</text>`);const p=vals.map((v,i)=>`${i?'L':'M'}${x(i)},${y(v)}`).join(' '),pm=ma.map((v,i)=>`${i?'L':'M'}${x(i)},${y(v)}`).join(' ');h+=`<path d="${p}" fill="none" stroke="#2f6fe4" stroke-width="2.4"/><path d="${pm}" fill="none" stroke="#8ea9db" stroke-width="1.7" stroke-dasharray="6 5"/>`;slice.forEach((r,i)=>{if(r['事件标注'])h+=`<line x1="${x(i)}" y1="${T}" x2="${x(i)}" y2="${H-B}" stroke="#ef9b3a" stroke-dasharray="3 4"/><circle cx="${x(i)}" cy="${T+7}" r="4" fill="#ef9b3a"><title>${r['事件标注']}</title></circle>`;h+=`<circle cx="${x(i)}" cy="${y(vals[i])}" r="4" fill="#fff" stroke="#2f6fe4" stroke-width="2"><title>${weekText(r)} · ${def.label} ${vals[i].toFixed(1)}${def.unit}</title></circle>`});const step=Math.max(1,Math.ceil(slice.length/6));for(let i=0;i<slice.length;i+=step)h+=`<text x="${x(i)}" y="${H-14}" text-anchor="middle" font-size="10" fill="#8e9aac">${fmt(slice[i]['周开始']).slice(2,7)}</text>`;chart.setAttribute('viewBox',`0 0 ${W} ${H}`);chart.innerHTML=h;chartTitle.textContent=def.label+' · 长期变化曲线';chartSub.textContent=`${slice.length} 周 · 最低 ${Math.min(...vals).toFixed(1)} / 最高 ${Math.max(...vals).toFixed(1)} / 当前 ${vals.at(-1).toFixed(1)} ${def.unit}`;const phases=[];slice.forEach(r=>{if(r['阶段解释']&&phases.at(-1)!==r['阶段解释'])phases.push(r['阶段解释'])});const events=slice.filter(r=>r['事件标注']).map(r=>fmt(r['周开始']).slice(5)+' · '+r['事件标注']);phaseBar.innerHTML=phases.map(p=>`<span class="phaseChip">${p}</span>`).join('')+events.map(e=>`<span class="phaseChip event">${e}</span>`).join('')}
function openEvents(){eventSection.hidden=!eventSection.hidden;if(eventSection.hidden)return;const data=rows(),li=+leftWeek.value,ri=+rightWeek.value,slice=data.slice(li,ri+1);eventSectionSub.textContent=`${currentTask().label} · 所选区间 ${slice.length} 周 · ${currentTask().firstEventLabel}`;taskEvents.innerHTML=`<div class="taskEventGrid">${slice.map(r=>`<article class="taskEvent"><div class="taskEventWeek">第 ${r['周序号']} 周 · ${fmt(r['周开始'])}</div><div class="taskEventValue">${r['首次事件分钟'].toFixed(1)}<small>min</small></div><div class="taskEventName">${currentTask().firstEventLabel}${r['事件标注']?`<br><b>${r['事件标注']}</b>`:''}</div></article>`).join('')}</div>`;eventSection.scrollIntoView({behavior:'smooth',block:'start'})}
document.querySelectorAll('.place').forEach(el=>el.onclick=()=>{document.querySelectorAll('.place').forEach(x=>x.classList.remove('active'));el.classList.add('active');activeTask=el.dataset.place;activeMetric='first';render()});render();
</script></body></html>'''


if __name__ == "__main__":
    main()
