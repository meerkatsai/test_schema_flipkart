/* Dashboard demo — faithful vanilla port of the design handoff:
   ReportCard anatomy verbatim (drag handle · title+question · INLINE controls:
   metric select, D/W/M, Compare TOGGLE, calendar date-range dropdown · synced ·
   download CSV · pin) per components/cards/ReportCard.jsx + core/{Toggle,DateRange}.jsx;
   card sets/order per ui_kits/dashboard/App.jsx; crosshair trend hover per
   guidelines/interaction.html. In-place drill with breadcrumbs is the one
   extension. Seeded demo data, no LLM, no build step. */
"use strict";

const GRAINS=["date","week","month"];
const NON_ADDITIVE=new Set(["roas","roi","direct_roi","indirect_roi","acos","ctr","cvr","cpc","avg_cpc","cpm","cpi","aov","reach","frequency","conv_rate","cost_per_conv","cost_per_purchase","conv_value_per_cost","mer","spend_share","ntb_share","budget_utilization_pct"]);
const SERIES=["var(--series-1)","var(--series-2)","var(--series-3)","var(--series-4)","var(--series-5)","var(--series-6)","var(--series-7)","var(--series-8)"];
const HEAT=["var(--heat-1)","var(--heat-2)","var(--heat-3)","var(--heat-4)","var(--heat-5)"];
/* inlined lucide icons (core/Icon.jsx inlines lucide) */
const IC=(p,s=14)=>`<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${p}</svg>`;
const ICON_PIN=IC('<path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1z"/>');
const ICON_PIN_OFF=IC('<path d="M12 17v5"/><path d="M15 9.34V6h1a2 2 0 0 0 0-4H7.89"/><path d="m2 2 20 20"/><path d="M9 9v1.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h11"/>');
const ICON_GRIP=IC('<circle cx="9" cy="12" r="1"/><circle cx="9" cy="5" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="19" r="1"/>');
const ICON_DL=IC('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>');
const ICON_CAL=IC('<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',13);
const ICON_CHEV=IC('<path d="m6 9 6 6 6-6"/>',12);

const FACTS={
  spend:{label:"Spend",unit:"inr"}, sales:{label:"Sales",unit:"inr"}, revenue:{label:"Revenue",unit:"inr"},
  conv_value:{label:"Conv. value",unit:"inr"}, orders:{label:"Orders",unit:"num"}, units:{label:"Units",unit:"num"},
  clicks:{label:"Clicks",unit:"num"}, views:{label:"Views",unit:"num"}, impressions:{label:"Impressions",unit:"num"},
  purchases:{label:"Purchases",unit:"num"}, conversions:{label:"Conversions",unit:"num"},
  roas:{label:"ROAS",unit:"x"}, roi:{label:"ROI",unit:"x"}, conv_value_per_cost:{label:"Conv. value / cost",unit:"x"},
  acos:{label:"ACOS",unit:"pct",invert:true}, ctr:{label:"CTR",unit:"pct"}, cvr:{label:"CVR",unit:"pct"},
  conv_rate:{label:"Conv. rate",unit:"pct"}, cpc:{label:"CPC",unit:"inr",invert:true},
  avg_cpc:{label:"Avg CPC",unit:"inr",invert:true}, cpm:{label:"CPM",unit:"inr",invert:true},
  cpi:{label:"CPI",unit:"inr",invert:true}, cost_per_conv:{label:"Cost / conversion",unit:"inr",invert:true},
  mer:{label:"MER",unit:"x"}
};
const MEMBERS={
  campaign:["Always-On | Exact","Festive Push","NTB Broad","Retarget Cart","Category Defense","Hero SKU Boost","Generic Terms","Competitor Conquest"],
  placement:["Top of Search","Rest of Search","Product Pages"],
  device:["Mobile","Desktop","Tablet"],
  os:["Android","iOS"],
  platform:["Amazon","Flipkart","Google","Meta"]
};
const CFG={
  amazon:{ eff:"roas", effAlt:"acos", grid:"placement",
    metrics:["spend","sales","roas","acos","ctr","cpc","orders"],
    kpis:["spend","sales","roas","acos","ctr","cpc"] },
  flipkart:{ eff:"roi", effAlt:"roi", grid:"placement",
    metrics:["spend","revenue","roi","ctr","cpc","orders","views"],
    kpis:["spend","revenue","roi","views","ctr","cpc"] },
  google:{ eff:"conv_value_per_cost", effAlt:"cost_per_conv", grid:"device",
    metrics:["spend","conv_value","conv_value_per_cost","conversions","conv_rate","cost_per_conv","avg_cpc"],
    kpis:["spend","conversions","conv_value","conv_value_per_cost","conv_rate","cost_per_conv"] },
  meta:{ eff:"roas", effAlt:"cpi", grid:"os",
    metrics:["spend","purchases","roas","cpi","cpm","cpc","ctr","cvr"],
    kpis:["spend","purchases","roas","cpi","ctr","cvr"] }
};
const SPEND_LABEL={google:"Cost"};
/* DateRange presets — verbatim from components/core/DateRange.jsx */
const PRESETS=[{value:"7d",label:"Last 7 days",range:"24 – 30 Aug 2026",days:7},
  {value:"30d",label:"Last 30 days",range:"1 – 30 Aug 2026",days:30},
  {value:"mtd",label:"Month to date",range:"1 – 10 Sep 2026",days:10},
  {value:"90d",label:"Last 90 days",range:"2 Jun – 30 Aug 2026",days:90},
  {value:"custom",label:"Custom range…",range:"Custom",days:30}];
const preset=v=>PRESETS.find(p=>p.value===v)||PRESETS[1];

/* ── seeded executor ────────────────────────────────────────────────────── */
function hash(str){let h=2166136261;for(const c of String(str)){h^=c.charCodeAt(0);h=Math.imul(h,16777619)}return (h>>>0)/4294967295;}
function baseVal(metric,member,pk){
  const r=hash(pk+"|"+metric+"|"+member);
  const bases={spend:9e5,sales:32e5,revenue:28e5,conv_value:26e5,orders:2400,units:3100,purchases:1900,conversions:2100,clicks:52000,views:8.6e5,impressions:2.1e6};
  if(metric in bases)return bases[metric]*(0.25+r);
  if(metric==="roas")return 2.2+3.4*r; if(metric==="roi")return 1.8+3.8*r;
  if(metric==="conv_value_per_cost")return 2+3.5*r;
  if(metric==="acos")return 14+26*r; if(metric==="ctr")return .3+.9*r;
  if(metric==="cvr"||metric==="conv_rate")return 4+9*r;
  if(metric==="cpc"||metric==="avg_cpc")return 6+22*r;
  if(metric==="cpm")return 40+180*r; if(metric==="cpi")return 18+60*r;
  if(metric==="cost_per_conv")return 120+500*r; if(metric==="mer")return 1.6+2.6*r;
  return 100*r;
}
function seriesFor(metric,member,pk,n,compare){
  const b=baseVal(metric,member,pk)/(NON_ADDITIVE.has(metric)?1:30); // per-day base
  const cur=[],prev=[];
  for(let t=0;t<n;t++){
    const wave=1+0.18*Math.sin((t/7)*Math.PI*2)+0.25*(hash(pk+member+metric+t)-0.5)+(0.25*t/n);
    cur.push(b*wave); if(compare)prev.push(b*wave*(0.82+0.14*hash(metric+t)));
  }
  return {cur,prev:compare?prev:null};
}
function totalFor(metric,member,pk,days=30){
  const s=seriesFor(metric,member,pk,days,true);
  const red=a=>NON_ADDITIVE.has(metric)?a.reduce((x,y)=>x+y,0)/a.length:a.reduce((x,y)=>x+y,0);
  return {cur:red(s.cur),prev:red(s.prev)};
}
function labels(gr,n){ const out=[]; for(let t=0;t<n;t++){ const d=new Date("2026-08-30");
  if(gr==="D"){d.setDate(d.getDate()-(n-1-t));out.push(`${d.getDate()} ${d.toLocaleString("en",{month:"short"})}`);}
  else if(gr==="W"){d.setDate(d.getDate()-7*(n-1-t));out.push(`wk ${d.getDate()}/${d.getMonth()+1}`);}
  else {d.setMonth(d.getMonth()-(n-1-t));out.push(d.toLocaleString("en",{month:"short"}));}} return out;}
function nPeriods(gr,days){ return gr==="D"?Math.min(days,60):gr==="W"?Math.max(2,Math.ceil(days/7)):Math.max(2,Math.ceil(days/30)); }

/* ── formatting ─────────────────────────────────────────────────────────── */
function fmt(v,unit){ if(v==null||isNaN(v))return "—";
  if(unit==="pct")return v.toFixed(1)+"%"; if(unit==="x")return v.toFixed(1)+"×";
  const inr=unit==="inr"; const a=Math.abs(v);
  const s=a>=1e7?(v/1e7).toFixed(1)+" Cr":a>=1e5?(v/1e5).toFixed(1)+" L":a>=1e3?(v/1e3).toFixed(1)+"K":Math.round(v).toLocaleString("en-IN");
  return inr?"₹"+s:s; }
const esc=t=>String(t).replace(/&/g,"&amp;").replace(/</g,"&lt;");
const U=k=>(FACTS[k]||{}).unit||"num";
const L=(k,pk)=>k==="spend"&&SPEND_LABEL[pk]?SPEND_LABEL[pk]:(FACTS[k]||{}).label||k;
const dHtml=(d,inv)=>{ if(d==null)return ""; const good=(d>=0)!==!!inv;
  return `<span class="${good?"up":"down"}">${d>=0?"+":"−"}${Math.abs(d).toFixed(1)}%</span>`; };
const pct=(c,p)=>p?((c-p)/Math.abs(p))*100:null;

/* ── chart primitives ───────────────────────────────────────────────────── */
const W=1160;
let TRENDS={}, TSEQ=0; // per-chart hover geometry, rebuilt every render
function spark(data,w=88,h=26,color="var(--series-1)"){
  const mx=Math.max(...data),mn=Math.min(...data);
  const pts=data.map((v,i)=>`${(i/(data.length-1))*w},${h-2-((v-mn)/((mx-mn)||1))*(h-4)}`).join(" ");
  return `<svg width="${w}" height="${h}" style="display:block"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5"/></svg>`;
}
function lineChart(defs,xs,unit){
  const H=240,pad=52; let maxV=0; defs.forEach(s=>s.data.forEach(d=>{if(d!=null)maxV=Math.max(maxV,d);}));
  const px=i=>pad+i*(W-pad-16)/Math.max(xs.length-1,1), py=v=>H-28-(v/maxV)*(H-52);
  const tid="t"+(++TSEQ);
  TRENDS[tid]={xs,defs,px,py,pad,H,unit};
  let out=`<svg class="trend" data-tid="${tid}" viewBox="0 0 ${W} ${H}" width="100%">`;
  for(let g=0;g<=4;g++){const y=py(maxV*g/4);out+=`<line x1="${pad}" x2="${W-16}" y1="${y}" y2="${y}" stroke="var(--rule-grid)"/><text x="${pad-8}" y="${y+3}" text-anchor="end">${fmt(maxV*g/4,unit)}</text>`;}
  defs.forEach(s=>{out+=`<path class="tline" data-sid="${esc(s.id)}" data-color="${s.color}" fill="none" stroke="${s.color}" stroke-width="${s.dashed?1.5:2}" ${s.dashed?'stroke-dasharray="4 4"':""} stroke-linejoin="round" stroke-linecap="round" style="transition:stroke 120ms" d="${s.data.map((d,i)=>d==null?"":(i&&s.data[i-1]!=null?"L":"M")+px(i).toFixed(1)+","+py(d).toFixed(1)).join("")}"/>`;});
  xs.forEach((x,i)=>{const st=Math.ceil(xs.length/8); if(xs.length<=8||i===xs.length-1||(i%st===0&&xs.length-1-i>=st/2)) out+=`<text x="${px(i)}" y="${H-6}" text-anchor="${i===0?"start":i===xs.length-1?"end":"middle"}">${esc(x)}</text>`;});
  out+=`<line class="xhair" x1="0" x2="0" y1="12" y2="${H-28}" stroke="var(--chart-crosshair)" stroke-width="1" stroke-dasharray="2 3" style="display:none"/>`;
  out+=`<circle class="xpt" r="4.5" fill="var(--surface-card)" stroke-width="2" style="display:none;pointer-events:none"/>`;
  out+="</svg>";
  out+=`<div class="tooltip"><div class="tl"></div><div style="display:flex;gap:8px;align-items:baseline"><span class="tlab" style="color:var(--ink-300)"></span><strong class="num tval" style="font-weight:600;font-size:13px"></strong></div></div>`;
  out+=`<div class="legend">${defs.map(s=>`<span><span style="width:14px;border-top:${s.dashed?"1.5px dashed":"2px solid"} ${s.color};display:inline-block"></span>${esc(s.label)}</span>`).join("")}</div>`;
  return out;
}
function wireTrends(root){
  root.querySelectorAll("svg.trend").forEach(svg=>{
    const g=TRENDS[svg.dataset.tid]; if(!g)return;
    const body=svg.closest(".body"); const tip=svg.nextElementSibling; // .tooltip
    const xh=svg.querySelector(".xhair"), xp=svg.querySelector(".xpt");
    svg.addEventListener("mousemove",e=>{
      const r=svg.getBoundingClientRect();
      const vx=(e.clientX-r.left)*(W/r.width), vy=(e.clientY-r.top)*(g.H/r.height);
      if(vx<g.pad||vx>W-16){tip.style.display="none";xh.style.display="none";xp.style.display="none";return;}
      const i=Math.max(0,Math.min(g.xs.length-1,Math.round((vx-g.pad)/((W-g.pad-16)/Math.max(g.xs.length-1,1)))));
      let best=null,bd=1e9;
      g.defs.forEach(s=>{const d=s.data[i]; if(d==null)return; const dy=Math.abs(g.py(d)-vy); if(dy<bd){bd=dy;best=s;}});
      if(!best){tip.style.display="none";return;}
      const cx=g.px(i), cy=g.py(best.data[i]);
      xh.setAttribute("x1",cx); xh.setAttribute("x2",cx); xh.style.display="";
      xp.setAttribute("cx",cx); xp.setAttribute("cy",cy); xp.style.stroke=best.color; xp.style.display="";
      svg.querySelectorAll(".tline").forEach(p=>{p.style.stroke=(p.dataset.sid===best.id)?p.dataset.color:"var(--series-dim)";});
      tip.querySelector(".tl").textContent=g.xs[i];
      tip.querySelector(".tlab").textContent=best.label;
      tip.querySelector(".tval").textContent=fmt(best.data[i],best.unit||g.unit);
      const br=body.getBoundingClientRect();
      tip.style.left=Math.min(e.clientX-br.left+14,br.width-180)+"px";
      tip.style.top=Math.max(0,e.clientY-br.top-48)+"px";
      tip.style.display="block";
    });
    svg.addEventListener("mouseleave",()=>{tip.style.display="none";xh.style.display="none";xp.style.display="none";
      svg.querySelectorAll(".tline").forEach(p=>p.style.stroke=p.dataset.color);});
  });
}
function vBars(groups,unit){
  const H=250,pad=52; let maxV=0; groups.forEach(g=>g.bars.forEach(b=>maxV=Math.max(maxV,b.value)));
  const gw=(W-pad-30)/groups.length;
  let out=`<svg class="barsv" viewBox="0 0 ${W} ${H}" width="100%">`;
  for(let g=0;g<=4;g++){const y=H-44-(g/4)*(H-84);out+=`<line x1="${pad}" x2="${W-16}" y1="${y}" y2="${y}" stroke="var(--rule-grid)"/><text x="${pad-8}" y="${y+3}" text-anchor="end">${fmt(maxV*g/4,unit)}</text>`;}
  groups.forEach((g,gi)=>{ const n=g.bars.length, bw=Math.min(64,(gw-24)/n);
    g.bars.forEach((b,bi)=>{ const x=pad+16+gi*gw+bi*(bw+6), h=(b.value/maxV)*(H-84), y=H-44-h;
      out+=`<rect class="bridge" data-m="${esc(g.label)}" x="${x}" y="${y}" width="${bw}" height="${h}" rx="1" fill="${b.dim?"var(--series-dim)":b.color||"var(--series-1)"}" style="cursor:pointer"><title>${esc(g.label)}${b.label?" · "+esc(b.label):""}: ${fmt(b.value,unit)} — click to drill in place</title></rect>`;
      out+=`<text class="val" x="${x+bw/2}" y="${y-6}" text-anchor="middle">${fmt(b.value,unit)}</text>`;});
    out+=`<text x="${pad+16+gi*gw+(Math.min(64,(gw-24)/n)*n+6*(n-1))/2}" y="${H-28}" text-anchor="middle" class="val">${esc(g.label)}</text>`;});
  return out+"</svg>";
}
function hBars(rows,nameKey,mk,pk,extraKey){
  const rh=30,H=rows.length*rh+12,lw=260; const maxV=Math.max(...rows.map(r=>r[mk]||0));
  let out=`<svg viewBox="0 0 ${W} ${H}" width="100%">`;
  rows.forEach((r,i)=>{ const y=6+i*rh,w=((r[mk]||0)/maxV)*(W-lw-140);
    out+=`<text x="${lw-8}" y="${y+13}" text-anchor="end" class="val">${esc(String(r[nameKey]).slice(0,36))}</text>`;
    out+=`<rect x="${lw}" y="${y}" width="${W-lw-140}" height="${rh-11}" rx="1" fill="var(--bar-track)"/>`;
    out+=`<rect class="bridge" data-m="${esc(r[nameKey])}" data-m2="${esc(r[nameKey])}" x="${lw}" y="${y}" width="${w}" height="${rh-11}" rx="1" fill="var(--series-1)" style="cursor:pointer"><title>${esc(r[nameKey])} — click to drill in place</title></rect>`;
    out+=`<text x="${lw+(W-lw-140)+8}" y="${y+13}">${fmt(r[mk],U(mk))}${extraKey?` · ${esc(L(extraKey,pk))} ${fmt(r[extraKey],U(extraKey))}`:""}</text>`;});
  return out+"</svg>";
}
function heat(cols,rowsY,val,unit,inv){
  const flat=[]; rowsY.forEach(yv=>cols.forEach(x=>flat.push(val(x,yv))));
  const mn=Math.min(...flat),mx=Math.max(...flat);
  const cw=Math.min(150,(W-250)/cols.length),ch=36,H=rowsY.length*ch+44;
  let out=`<svg viewBox="0 0 ${W} ${H}" width="100%">`;
  cols.forEach((x,i)=>out+=`<text x="${240+i*cw+cw/2}" y="14" text-anchor="middle">${esc(x)}</text>`);
  rowsY.forEach((yv,j)=>{ out+=`<text x="232" y="${26+j*ch+ch/2+4}" text-anchor="end" class="val">${esc(String(yv).slice(0,30))}</text>`;
    cols.forEach((x,i)=>{ const v=val(x,yv); let t=(v-mn)/((mx-mn)||1); if(inv)t=1-t;
      const step=Math.min(4,Math.floor(t*5));
      out+=`<rect class="bridge" data-hx="${esc(x)}" data-hy="${esc(String(yv))}" x="${240+i*cw}" y="${26+j*ch}" width="${cw-4}" height="${ch-4}" rx="1" fill="${HEAT[step]}" style="cursor:pointer"><title>click to drill in place — ${esc(String(yv))} × ${esc(x)}</title></rect><text pointer-events="none" x="${240+i*cw+cw/2-2}" y="${26+j*ch+ch/2+2}" text-anchor="middle" fill="${step>=3?"var(--surface-card)":"var(--ink-900)"}">${fmt(v,unit)}</text>`;});});
  return out+`</svg><div class="note">5-step scale, ${inv?"darker = better (lower)":"darker = higher"}</div>`;
}

/* ── per-card state + header controls (design core components) ──────────── */
let STATE={};
const key=(pk,id)=>pk+":"+id;
function st(pk,id,defaults){ const k=key(pk,id); if(!STATE[k])STATE[k]={range:"30d",...defaults}; return STATE[k]; }
function days(pk,id){ return preset(st(pk,id,{}).range||"30d").days; }
function selCtl(pk,id,name,value,options){
  return `<select data-card="${id}" data-ctl="${name}">${options.map(o=>`<option value="${o.value}" ${o.value===value?"selected":""}>${esc(o.label)}</option>`).join("")}</select>`;
}
function segCtl(pk,id,name,value,options){
  return `<span class="seg">${options.map(o=>`<button data-card="${id}" data-ctl="${name}" data-val="${o}" class="${o===value?"on":""}">${o}</button>`).join("")}</span>`;
}
function tglCtl(pk,id,on){
  return `<span class="tgl ${on?"on":""}" data-card="${id}" data-ctl="compare" role="switch" aria-checked="${on}"><span class="sw"><span class="kn"></span></span><span>Compare</span></span>`;
}
function drCtl(pk,id){
  const v=st(pk,id,{}).range||"30d"; const cur=preset(v);
  return `<span class="dr" data-card="${id}"><button data-drbtn="${id}">${ICON_CAL}<span class="num">${esc(cur.range)}</span>${ICON_CHEV}</button>
    <span class="menu" hidden>${PRESETS.map(p=>`<span class="opt ${p.value===v?"sel":""}" data-card="${id}" data-ctl="range" data-val="${p.value}"><span>${esc(p.label)}</span><span class="rng num">${esc(p.range)}</span></span>`).join("")}</span></span>`;
}
function metricOpts(pk,keys){ return keys.map(k=>({value:k,label:L(k,pk)})); }

/* ── the design file's cards (PlatformCards.jsx, ported) ────────────────── */
const CARDS={
  kpi:{ title:()=>"Account KPIs", q:()=>"How is the account performing this period versus last period and plan?",
    ctl:(pk)=>{st(pk,"kpi",{gr:"D"});return segCtl(pk,"kpi","gr",st(pk,"kpi",{}).gr,["D","W","M"])+drCtl(pk,"kpi");},
    body:(pk)=>{ const c=CFG[pk]; const dys=days(pk,"kpi");
      return `<div class="kpis">`+c.kpis.map(k=>{ const t=totalFor(k,"account",pk,dys);
        const d=pct(t.cur,t.prev), target=(hash(pk+k+"t")-0.5)*24, inv=(FACTS[k]||{}).invert;
        const s=seriesFor(k,"account",pk,14,false).cur;
        return `<div class="kpi"><div class="lab">${esc(L(k,pk))}</div><div class="v num">${fmt(t.cur,U(k))}</div><div class="d">${dHtml(d,inv)} vs prev · ${dHtml(target,inv)} vs target</div><div style="margin-top:6px">${spark(s)}</div></div>`;}).join("")+`</div>`; } },
  trend:{ title:(pk)=>L(st(pk,"trend",{mk:"spend",gr:"D",cmp:true}).mk,pk)+" over time",
    q:(pk)=>{const s=st(pk,"trend",{});return "How is "+L(s.mk,pk).toLowerCase()+" changing "+(s.gr==="D"?"day on day":s.gr==="W"?"week on week":"month on month")+"?";},
    ctl:(pk)=>{const s=st(pk,"trend",{});return selCtl(pk,"trend","mk",s.mk,metricOpts(pk,CFG[pk].metrics))+segCtl(pk,"trend","gr",s.gr,["D","W","M"])+tglCtl(pk,"trend",s.cmp)+drCtl(pk,"trend");},
    body:(pk)=>{const s=st(pk,"trend",{}); const n=nPeriods(s.gr,days(pk,"trend")); const sr=seriesFor(s.mk,"account",pk,n,s.cmp);
      const defs=[{id:s.mk,label:L(s.mk,pk),color:SERIES[0],unit:U(s.mk),data:sr.cur}];
      if(sr.prev)defs.push({id:"__prev",label:"Previous period",color:"var(--series-compare)",dashed:true,unit:U(s.mk),data:sr.prev});
      return lineChart(defs,labels(s.gr,n),U(s.mk)); } },
  rank:{ title:(pk)=>"Top campaigns by "+L(st(pk,"rank",{mk:CFG[pk].eff}).mk,pk),
    q:(pk)=>{const m=st(pk,"rank",{}).mk;return "Which campaigns "+((FACTS[m]||{}).invert?"are most efficient on ":"lead on ")+L(m,pk)+"?";},
    ctl:(pk)=>{const s=st(pk,"rank",{});return selCtl(pk,"rank","mk",s.mk,metricOpts(pk,CFG[pk].metrics))+drCtl(pk,"rank");},
    body:(pk)=>{const s=st(pk,"rank",{}); const inv=(FACTS[s.mk]||{}).invert; const dys=days(pk,"rank");
      const rows=MEMBERS.campaign.map(c=>({name:c,[s.mk]:totalFor(s.mk,c,pk,dys).cur,spend:totalFor("spend",c,pk,dys).cur}))
        .sort((a,b)=>inv?a[s.mk]-b[s.mk]:b[s.mk]-a[s.mk]);
      return hBars(rows,"name",s.mk,pk,s.mk!=="spend"?"spend":null); } },
  ctrend:{ title:(pk)=>"Campaign "+L(st(pk,"ctrend",{mk:"spend",c:MEMBERS.campaign[0],gr:"D",cmp:true}).mk,pk)+" over time",
    q:(pk)=>{const s=st(pk,"ctrend",{});return "How is "+esc(s.c)+" trending on "+L(s.mk,pk)+"?";},
    ctl:(pk)=>{const s=st(pk,"ctrend",{});return selCtl(pk,"ctrend","c",s.c,MEMBERS.campaign.map(c=>({value:c,label:c})))+selCtl(pk,"ctrend","mk",s.mk,metricOpts(pk,CFG[pk].metrics))+segCtl(pk,"ctrend","gr",s.gr,["D","W","M"])+tglCtl(pk,"ctrend",s.cmp)+drCtl(pk,"ctrend");},
    body:(pk)=>{const s=st(pk,"ctrend",{}); const n=nPeriods(s.gr,days(pk,"ctrend")); const sr=seriesFor(s.mk,s.c,pk,n,s.cmp);
      const defs=[{id:"c",label:s.c,color:SERIES[0],unit:U(s.mk),data:sr.cur}];
      if(sr.prev)defs.push({id:"__prev",label:"Previous period",color:"var(--series-compare)",dashed:true,unit:U(s.mk),data:sr.prev});
      return lineChart(defs,labels(s.gr,n),U(s.mk)); } },
  table:{ title:()=>"Campaign performance table", q:()=>"What are the exact numbers for every campaign?",
    ctl:(pk)=>{st(pk,"table",{});return drCtl(pk,"table");},
    body:(pk)=>{ const cols=["campaign"].concat(CFG[pk].metrics); const dys=days(pk,"table");
      const rows=MEMBERS.campaign.map(c=>{const r={campaign:c};CFG[pk].metrics.forEach(k=>r[k]=totalFor(k,c,pk,dys).cur);return r;})
        .sort((a,b)=>b.spend-a.spend);
      let out="<table><tr>"+cols.map(c=>`<th>${c==="campaign"?"Campaign":esc(L(c,pk))}${c==="spend"?' <span style="color:var(--ink-400)">↓</span>':""}</th>`).join("")+"</tr>";
      rows.forEach(r=>{out+=`<tr class="num bridge" data-m="${esc(r.campaign)}" style="cursor:pointer" title="click to drill in place">`+cols.map(c=>`<td>${c==="campaign"?esc(r[c]):fmt(r[c],U(c))}</td>`).join("")+"</tr>";});
      return out+"</table>"; } },
  dod:{}, wow:{}, mom:{},
  grid:{ title:(pk)=>"Campaign × "+({placement:"placement",device:"device",os:"OS"})[CFG[pk].grid]+" · "+L(CFG[pk].effAlt,pk),
    q:(pk)=>({amazon:"Where on Amazon are ads performing best?",flipkart:"Which retail-media placements are most effective?",google:"Are mobile, desktop and tablet users behaving differently?",meta:"Is there a meaningful gap between Android and iOS?"})[pk],
    ctl:(pk)=>{st(pk,"grid",{});return drCtl(pk,"grid");},
    body:(pk)=>{ const dim=CFG[pk].grid, mk=CFG[pk].effAlt, inv=(FACTS[mk]||{}).invert;
      return heat(MEMBERS[dim],MEMBERS.campaign.slice(0,6),(x,y)=>baseVal(mk,y+"|"+x,pk),U(mk),inv); } },
  pbars:{ title:(pk)=>L(CFG[pk].eff,pk)+" by "+CFG[pk].grid,
    q:(pk)=>"Which "+CFG[pk].grid+" delivers the best return?",
    ctl:(pk)=>{st(pk,"pbars",{});return drCtl(pk,"pbars");},
    body:(pk)=>{ const dim=CFG[pk].grid, mk=CFG[pk].eff;
      return vBars(MEMBERS[dim].map(m=>({label:m,bars:[{value:baseVal(mk,m,pk),color:"var(--series-1)"}]})),U(mk)); } },
  os:{ title:(pk)=>"Android vs iOS · "+L(st(pk,"os",{mk:"cpi"}).mk,pk).toUpperCase(),
    q:()=>"Is there a meaningful CPI/CVR gap between operating systems?",
    ctl:(pk)=>{const s=st(pk,"os",{});return segCtl(pk,"os","mkseg",s.mk==="cpi"?"CPI":"CVR",["CPI","CVR"])+drCtl(pk,"os");},
    body:(pk)=>{const s=st(pk,"os",{});
      return vBars(MEMBERS.os.map(o=>({label:o,bars:[{value:baseVal(s.mk,o,pk),color:"var(--series-1)"}]})),U(s.mk)); } },
  bkpi:{ title:()=>"Blended KPIs · all platforms", q:()=>"How is total ad investment translating into sales across Amazon, Flipkart, Google and Meta?",
    ctl:(pk)=>{st(pk,"bkpi",{});return drCtl(pk,"bkpi");},
    body:(pk)=>{ const dys=days(pk,"bkpi");
      const items=[["spend","Total ad spend","inr"],["sales","Attributed revenue","inr"],["mer","MER (with formula)","x"],["clicks","Clicks","num"]];
      return `<div class="kpis">`+items.map(([k,lab,u])=>{ let cur=0,prev=0;
        MEMBERS.platform.forEach(p=>{const t=totalFor(k,"account",p.toLowerCase(),dys);cur+=t.cur;prev+=t.prev;});
        if(NON_ADDITIVE.has(k)){cur/=4;prev/=4;}
        return `<div class="kpi"><div class="lab">${esc(lab)}</div><div class="v num">${fmt(cur,u)}</div><div class="d">${dHtml(pct(cur,prev),false)} vs prev</div></div>`;}).join("")+
        `</div><div class="note">additive facts only across platforms; mer = revenue ÷ ad spend, always printed with its formula</div>`; } },
  ptrend:{ title:()=>"Spend over time by platform", q:()=>"How does spend move day on day on each platform?",
    ctl:(pk)=>{const s=st(pk,"ptrend",{gr:"D"});return segCtl(pk,"ptrend","gr",s.gr,["D","W","M"])+drCtl(pk,"ptrend");},
    body:(pk)=>{const s=st(pk,"ptrend",{}); const n=nPeriods(s.gr,days(pk,"ptrend"));
      const defs=MEMBERS.platform.map((p,i)=>({id:p,label:p,color:SERIES[i%8],unit:"inr",data:seriesFor("spend","account",p.toLowerCase(),n,false).cur}));
      return lineChart(defs,labels(s.gr,n),"inr"); } },
  pspend:{ title:()=>"Spend by platform vs previous period", q:()=>"Where did the budget go this period compared with last?",
    ctl:(pk)=>{st(pk,"pspend",{});return drCtl(pk,"pspend");},
    body:(pk)=>{ const dys=days(pk,"pspend");
      return vBars(MEMBERS.platform.map(p=>{const t=totalFor("spend","account",p.toLowerCase(),dys);
        return {label:p,bars:[{label:"previous",value:t.prev,dim:true},{label:"current",value:t.cur,color:"var(--series-1)"}]};}),"inr"); } },
  proas:{ title:()=>"ROAS by platform", q:()=>"Which platform returns the most per rupee?",
    ctl:(pk)=>{st(pk,"proas",{});return drCtl(pk,"proas");},
    body:()=>vBars(MEMBERS.platform.map(p=>({label:p,bars:[{value:baseVal(p==="Google"?"conv_value_per_cost":p==="Flipkart"?"roi":"roas","account",p.toLowerCase()),color:"var(--series-1)"}]})),"x")+
      `<div class="note">each platform reports on its own basis (roi includes halo on flipkart; conv. value / cost on google) — never a blended roas</div>` },
  ptable:{ title:()=>"Platform comparison table", q:()=>"What are the exact totals per platform?",
    ctl:(pk)=>{st(pk,"ptable",{});return drCtl(pk,"ptable");},
    body:(pk)=>{ const dys=days(pk,"ptable");
      let out=`<table><tr><th>Platform</th><th>Spend</th><th>Clicks</th><th>Orders</th><th>Return (native basis)</th></tr>`;
      MEMBERS.platform.forEach(p=>{const k=p.toLowerCase();
        const effK=p==="Google"?"conv_value_per_cost":p==="Flipkart"?"roi":"roas";
        out+=`<tr class="num"><td>${p}</td><td>${fmt(totalFor("spend","account",k,dys).cur,"inr")}</td><td>${fmt(totalFor("clicks","account",k,dys).cur,"num")}</td><td>${fmt(totalFor("orders","account",k,dys).cur,"num")}</td><td>${fmt(baseVal(effK,"account",k),"x")} <span style="color:var(--ink-400)">${esc(L(effK,k))}</span></td></tr>`;});
      return out+"</table>"; } }
};
function periodCard(gr){
  const name=gr==="D"?"Day on day":gr==="W"?"Week on week":"Month on month";
  const id=gr==="D"?"dod":gr==="W"?"wow":"mom";
  return {
    title:(pk)=>name+" · campaign "+L(st(pk,id,{mk:"spend"}).mk,pk),
    q:(pk)=>"How did each campaign's "+L(st(pk,id,{}).mk,pk).toLowerCase()+" move "+name.toLowerCase()+"?",
    ctl:(pk)=>selCtl(pk,id,"mk",st(pk,id,{}).mk,metricOpts(pk,CFG[pk].metrics))+drCtl(pk,id),
    body:(pk)=>{ const s=st(pk,id,{}); const n=Math.min(gr==="D"?7:6,nPeriods(gr,days(pk,id))); const xs=labels(gr,n);
      const inv=(FACTS[s.mk]||{}).invert;
      let out=`<table><tr><th>Campaign</th>${xs.map(x=>`<th>${esc(x)}</th>`).join("")}</tr>`;
      MEMBERS.campaign.slice(0,6).forEach(c=>{ const sr=seriesFor(s.mk,c,pk,n,false).cur;
        out+=`<tr class="num"><td>${esc(c)}</td>`+sr.map((v,i)=>{ const d=i?pct(v,sr[i-1]):null;
          return `<td>${fmt(v,U(s.mk))}<div style="font-family:var(--font-mono);font-size:var(--fs-micro)">${d==null?"—":dHtml(d,inv)}</div></td>`;}).join("")+"</tr>";});
      return out+"</table>"; } };
}
CARDS.dod=periodCard("D"); CARDS.wow=periodCard("W"); CARDS.mom=periodCard("M");

const PLATFORM_CARDS=["kpi","trend","rank","ctrend","table","dod","wow","mom","grid","pbars"];
const META_CARDS=["kpi","trend","rank","ctrend","table","dod","wow","mom","os","grid"];
const ALL_CARDS=["bkpi","ptrend","pspend","proas","ptable"];

/* ── in-place drill (extension; breadcrumb undoes) ──────────────────────── */
const PRODUCT_DIM={amazon:"advertised_asin",flipkart:"fsn",google:"keyword",meta:"creative"};
const PRODUCT_MEMBERS={amazon:["AreoVeda Baby Lotion","AreoVeda Stretch Marks Cream","AreoVeda Baby Wash","AreoVeda Massage Oil","AreoVeda Rash Cream","AreoVeda Bathing Bar","AreoVeda Belly Oil","AreoVeda Nipple Butter"],
  flipkart:["Baby Lotion 200ml","Stretch Cream 100g","Baby Wash 250ml","Massage Oil 150ml","Rash Cream 50g","Bathing Bar 75g"],
  google:["baby diaper cream","stretch marks cream","baby wash","natural baby lotion","baby massage oil","diaper rash"],
  meta:["UGC Testimonial","Product Demo","Before/After","Founder Story"]};
const DIM_LABEL={advertised_asin:"Advertised ASIN",fsn:"FSN (product)",keyword:"Keyword",creative:"Creative",campaign:"Campaign",placement:"Placement",device:"Device",os:"OS"};
const DIM_PLURAL={advertised_asin:"advertised ASINs (products)",fsn:"products (FSN)",keyword:"keywords",creative:"creatives",campaign:"campaigns",placement:"placements",device:"devices",os:"operating systems"};
function nextDim(pk,dim){ if(dim==="campaign")return PRODUCT_DIM[pk];
  if(dim==="placement"||dim==="device"||dim==="os")return "campaign"; return null; }
function membersOf(pk,dim){ return dim===PRODUCT_DIM[pk]?PRODUCT_MEMBERS[pk]:(MEMBERS[dim]||[]); }
function drillOf(pk,id){ const s=STATE[key(pk,id)]; return (s&&s.drill)||null; }
function setDrill(pk,id,drill){ const k=key(pk,id); if(!STATE[k])STATE[k]={range:"30d"}; STATE[k].drill=drill; render(); }
function pushDrill(pk,id,dim,value){
  const cur=drillOf(pk,id)||{filters:[]};
  const to=nextDim(pk,dim); if(!to)return;
  setDrill(pk,id,{filters:cur.filters.concat([{dim,value}]),toDim:to});
}
function drilledBody(pk,id,mk){
  const d=drillOf(pk,id); const seed=d.filters.map(f=>f.dim+"="+f.value).join("&");
  const scale=Math.pow(0.42,d.filters.length);
  const rows=membersOf(pk,d.toDim).map(m=>({name:m,
      [mk]:NON_ADDITIVE.has(mk)?baseVal(mk,m+"|"+seed,pk):baseVal(mk,m+"|"+seed,pk)*scale,
      spend:baseVal("spend",m+"|"+seed,pk)*scale}))
    .sort((a,b)=>((FACTS[mk]||{}).invert?a[mk]-b[mk]:b[mk]-a[mk])).slice(0,10);
  const deeper=nextDim(pk,d.toDim);
  return hBars(rows,"name",mk,pk,mk!=="spend"?"spend":null)
    +`<div class="note">${DIM_PLURAL[d.toDim]} ranked by ${L(mk,pk).toLowerCase()} within the selection · ${deeper?`click a bar to drill into its ${DIM_PLURAL[nextDim(pk,d.toDim)]}`:"edge of the hierarchy"}</div>`;
}
function crumbsHtml(pk,id){
  const d=drillOf(pk,id); if(!d)return "";
  return `<div class="crumbs">drilled: ${d.filters.map((f,i)=>`<span class="crumb" data-crumb="${i}" title="remove">${esc(DIM_LABEL[f.dim]||f.dim)} = ${esc(f.value)} ✕</span>`).join("")}</div>`;
}

/* ── CSV download (design: CSV per card) ────────────────────────────────── */
function csvFor(pk,id){
  const dys=days(pk,id); const rows=[];
  const push=r=>rows.push(r.map(v=>typeof v==="number"?v:'"'+String(v).replace(/"/g,'""')+'"').join(","));
  if(id==="kpi"||id==="bkpi"){ push(["metric","value","previous"]);
    (id==="kpi"?CFG[pk].kpis:["spend","sales","mer","clicks"]).forEach(k=>{
      if(id==="kpi"){const t=totalFor(k,"account",pk,dys);push([L(k,pk),t.cur,t.prev]);}
      else{let c=0,p=0;MEMBERS.platform.forEach(pl=>{const t=totalFor(k,"account",pl.toLowerCase(),dys);c+=t.cur;p+=t.prev;});
        if(NON_ADDITIVE.has(k)){c/=4;p/=4;} push([L(k,pk),c,p]);}});}
  else if(id==="trend"||id==="ctrend"){ const s=st(pk,id,{}); const n=nPeriods(s.gr,dys);
    const member=id==="ctrend"?s.c:"account"; const sr=seriesFor(s.mk,member,pk,n,true); const xs=labels(s.gr,n);
    push(["period",L(s.mk,pk),"previous"]); xs.forEach((x,i)=>push([x,sr.cur[i],sr.prev[i]]));}
  else if(id==="ptrend"){ const s=st(pk,id,{}); const n=nPeriods(s.gr,dys); const xs=labels(s.gr,n);
    push(["period"].concat(MEMBERS.platform));
    const ser=MEMBERS.platform.map(p=>seriesFor("spend","account",p.toLowerCase(),n,false).cur);
    xs.forEach((x,i)=>push([x].concat(ser.map(sr=>sr[i]))));}
  else if(id==="rank"||id==="table"){ const cols=CFG[pk].metrics;
    push(["campaign"].concat(cols.map(k=>L(k,pk))));
    MEMBERS.campaign.forEach(c=>push([c].concat(cols.map(k=>totalFor(k,c,pk,dys).cur))));}
  else if(id==="dod"||id==="wow"||id==="mom"){ const s=st(pk,id,{}); const gr=id==="dod"?"D":id==="wow"?"W":"M";
    const n=Math.min(gr==="D"?7:6,nPeriods(gr,dys)); const xs=labels(gr,n);
    push(["campaign"].concat(xs));
    MEMBERS.campaign.slice(0,6).forEach(c=>push([c].concat(seriesFor(s.mk,c,pk,n,false).cur)));}
  else if(id==="grid"){ const dim=CFG[pk].grid, mk=CFG[pk].effAlt;
    push(["campaign"].concat(MEMBERS[dim]));
    MEMBERS.campaign.slice(0,6).forEach(c=>push([c].concat(MEMBERS[dim].map(x=>baseVal(mk,c+"|"+x,pk)))));}
  else if(id==="pbars"||id==="os"){ const dim=id==="os"?"os":CFG[pk].grid; const mk=id==="os"?st(pk,"os",{}).mk:CFG[pk].eff;
    push([dim,L(mk,pk)]); MEMBERS[dim].forEach(m=>push([m,baseVal(mk,m,pk)]));}
  else if(id==="pspend"){ push(["platform","previous","current"]);
    MEMBERS.platform.forEach(p=>{const t=totalFor("spend","account",p.toLowerCase(),dys);push([p,t.prev,t.cur]);});}
  else if(id==="proas"){ push(["platform","return (native basis)"]);
    MEMBERS.platform.forEach(p=>push([p,baseVal(p==="Google"?"conv_value_per_cost":p==="Flipkart"?"roi":"roas","account",p.toLowerCase())]));}
  else if(id==="ptable"){ push(["platform","spend","clicks","orders"]);
    MEMBERS.platform.forEach(p=>{const k=p.toLowerCase();push([p,totalFor("spend","account",k,dys).cur,totalFor("clicks","account",k,dys).cur,totalFor("orders","account",k,dys).cur]);});}
  return rows.join("\n");
}
function downloadCsv(pk,id){
  const blob=new Blob(["﻿"+csvFor(pk,id)],{type:"text/csv;charset=utf-8"});
  const a=document.createElement("a"); a.href=URL.createObjectURL(blob);
  a.download=`${pk}-${id}.csv`; a.click(); URL.revokeObjectURL(a.href);
}

/* ── shell ──────────────────────────────────────────────────────────────── */
const $=s=>document.querySelector(s);
const store={get:(k,d)=>{try{const v=localStorage.getItem(k);return v?JSON.parse(v):d;}catch(e){return d;}},
             set:(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v));}catch(e){}}};
let UNPINNED=store.get("mk-dash-unpinned",{});

function cardHtml(pk,id){
  const c=CARDS[id];
  const d=(["rank","table","pbars","grid"].includes(id))?drillOf(pk,id):null;
  // evaluation order matters: title() initializes the card's default state, q/ctl/body read it
  let titleHtml=c.title(pk), qHtml=c.q(pk);
  const ctlHtml=c.ctl(pk);
  let body;
  if(d){ const mk=(st(pk,id,{}).mk)||(id==="grid"?CFG[pk].effAlt:CFG[pk].eff);
    body=drilledBody(pk,id,mk);
    // drilled: say exactly what the card now shows — selection · target level · ranking metric
    const last=d.filters[d.filters.length-1];
    qHtml=`inside ${d.filters.map(f=>`${esc(DIM_LABEL[f.dim]||f.dim)} “${esc(f.value)}”`).join(" › ")} — drilled from ${titleHtml}`;
    titleHtml=`${esc(last.value)} · ${DIM_PLURAL[d.toDim]} by ${esc(L(mk,pk))}`;
  }
  else body=c.body(pk);
  return `<section class="card" data-cid="${id}">
    <header class="card-h">
      <span class="grip" title="Drag to reorder">${ICON_GRIP}</span>
      <div class="tw"><h3 class="t">${titleHtml}</h3><div class="q">${qHtml}</div></div>
      <div class="ctls">${ctlHtml}</div>
      <div class="tail">
        <span class="synced">synced 2m ago</span>
        <button class="iconbtn" data-dl="${id}" title="Download CSV">${ICON_DL}</button>
        <button class="iconbtn active" data-unpin="${id}" title="Unpin from dashboard">${ICON_PIN}</button>
      </div>
    </header>
    ${crumbsHtml(pk,id)}
    <div class="body">${body}</div>
    <div class="foot"><span>data as of 2026-09-10 06:30 ist · last 2 days provisional</span><span>one visualization per card</span></div>
  </section>`;
}
function render(){
  TRENDS={}; TSEQ=0;
  const pk=store.get("mk-dash-platform","amazon");
  $("#platform").value=pk;
  const list=pk==="all"?ALL_CARDS:pk==="meta"?META_CARDS:PLATFORM_CARDS;
  const hidden=list.filter(id=>UNPINNED[key(pk,id)]);
  const shown=list.filter(id=>!UNPINNED[key(pk,id)]);
  let html=shown.map(id=>cardHtml(pk,id)).join("");
  if(hidden.length) html+=`<div class="restore"><span>${hidden.length} card${hidden.length>1?"s":""} unpinned — available in Reports.</span><button id="restoreAll">Restore all</button></div>`;
  html+=`<div class="mono" style="padding:8px 0 24px">sample data · figures in inr · one visualization per card · pin order: newest last</div>`;
  $("#stack").innerHTML=html;
  wireTrends($("#stack"));
  document.querySelectorAll("[data-unpin]").forEach(b=>b.addEventListener("click",()=>{
    UNPINNED[key(pk,b.dataset.unpin)]=true; store.set("mk-dash-unpinned",UNPINNED); render();}));
  document.querySelectorAll("[data-dl]").forEach(b=>b.addEventListener("click",()=>downloadCsv(pk,b.dataset.dl)));
  const ra=$("#restoreAll"); if(ra) ra.addEventListener("click",()=>{ list.forEach(id=>delete UNPINNED[key(pk,id)]); store.set("mk-dash-unpinned",UNPINNED); render();});
  document.querySelectorAll("select[data-ctl]").forEach(s=>s.addEventListener("change",()=>{
    st(pk,s.dataset.card,{})[s.dataset.ctl]=s.value; render();}));
  document.querySelectorAll("button[data-ctl]").forEach(b=>b.addEventListener("click",()=>{
    const s=st(pk,b.dataset.card,{});
    if(b.dataset.ctl==="mkseg") s.mk=b.dataset.val==="CPI"?"cpi":"cvr";
    else s[b.dataset.ctl]=b.dataset.val;
    render();}));
  document.querySelectorAll(".tgl[data-ctl='compare']").forEach(t=>t.addEventListener("click",()=>{
    const s=st(pk,t.dataset.card,{}); s.cmp=!s.cmp; render();}));
  document.querySelectorAll("[data-drbtn]").forEach(b=>b.addEventListener("click",e=>{
    e.stopPropagation();
    const dr=b.closest(".dr"); const menu=dr.querySelector(".menu");
    document.querySelectorAll(".dr .menu").forEach(m=>{if(m!==menu)m.hidden=true;});
    document.querySelectorAll(".dr").forEach(d=>{if(d!==dr)d.classList.remove("open");});
    menu.hidden=!menu.hidden; dr.classList.toggle("open",!menu.hidden);}));
  document.querySelectorAll(".dr .opt").forEach(o=>o.addEventListener("click",()=>{
    st(pk,o.dataset.card,{}).range=o.dataset.val; render();}));
}
document.addEventListener("click",e=>{
  // close open date-range menus on outside click
  if(!e.target.closest||!e.target.closest(".dr")) document.querySelectorAll(".dr .menu").forEach(m=>m.hidden=true);
  const pk=store.get("mk-dash-platform","amazon");
  const card=e.target.closest?e.target.closest(".card"):null; if(!card)return;
  const cid=card.dataset.cid; if(!cid)return;
  const crumb=e.target.closest(".crumb");
  if(crumb){ const i=parseInt(crumb.dataset.crumb); const d=drillOf(pk,cid);
    const filters=d.filters.slice(0,i);
    if(!filters.length) setDrill(pk,cid,null);
    else setDrill(pk,cid,{filters,toDim:nextDim(pk,filters[filters.length-1].dim)});
    return; }
  const t=e.target.closest(".bridge"); if(!t)return;
  if(pk==="all")return;
  const d=drillOf(pk,cid);
  if(d&&t.dataset.m2!==undefined){ pushDrill(pk,cid,d.toDim,t.dataset.m2); return; }
  if(cid==="rank"&&t.dataset.m) pushDrill(pk,cid,"campaign",t.dataset.m);
  else if(cid==="table"&&t.dataset.m) pushDrill(pk,cid,"campaign",t.dataset.m);
  else if(cid==="pbars"&&t.dataset.m) pushDrill(pk,cid,CFG[pk].grid,t.dataset.m);
  else if(cid==="grid"&&t.dataset.hx){ const dim=CFG[pk].grid;
    setDrill(pk,cid,{filters:[{dim:"campaign",value:t.dataset.hy},{dim,value:t.dataset.hx}],toDim:PRODUCT_DIM[pk]}); }
});
const sel=$("#platform");
[{v:"all",l:"All platforms"},{v:"amazon",l:"Amazon Ads"},{v:"flipkart",l:"Flipkart Ads"},{v:"google",l:"Google Ads"},{v:"meta",l:"Meta Ads"}]
  .forEach(o=>{const el=document.createElement("option");el.value=o.v;el.textContent=o.l;sel.appendChild(el);});
sel.addEventListener("change",()=>{store.set("mk-dash-platform",sel.value);render();});
render();
