// Safe helpers — prevent undefined leaks, XSS via escape
function safeDisplay(v, fallback='--'){ if(v===null||v===undefined||v===''||String(v).toUpperCase()==='N/A'||String(v).toUpperCase()==='UNDEFINED') return fallback; return String(v); }
function esc(s){ if(typeof s!=='string') return s; return s.replace(/[&<>'"]/g, c=> ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function toast(msg, type='info'){ if(window.showToast) return window.showToast(msg,type); const el=document.createElement('div'); el.textContent=msg; el.style.cssText='position:fixed;bottom:20px;right:20px;background:#111214;color:#fff;padding:10px 14px;border-radius:8px;border:1px solid #1e1f23;z-index:9999;font-size:12px'; document.body.appendChild(el); setTimeout(()=>el.remove(),3000); }

// StockerAI - Rebuilt Dashboard - Minimal, FCF/DCF focus, live prices
const TICK = typeof TICKER!=='undefined'?TICKER: window.location.pathname.split('/').pop().toUpperCase();
let DATA=null;
const $=id=>document.getElementById(id);
const fmt=(v,d=2)=>{const n=Number(v);return Number.isFinite(n)?n.toFixed(d):'--'};
const money=v=>{const n=Number(v);return Number.isFinite(n)?`$${n.toFixed(2)}`:'--'};
const pct=v=>{const n=Number(v);return Number.isFinite(n)?`${(Math.abs(n)<=1&&n!==0?n*100:n).toFixed(1)}%`:'--'};
const badge=(v)=>{v=(v||'HOLD').toUpperCase(); if(v.includes('BUY')) return 'badge-buy'; if(v.includes('SELL')) return 'badge-sell'; return 'badge-hold';};

function set(id,txt){const e=$(id); if(e) e.innerText=txt;}
function html(id,h){const e=$(id); if(e) e.innerHTML=h;}

function tabInit(){
  document.querySelectorAll('.tab').forEach(b=>{
    b.onclick=()=>{
      document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
      b.classList.add('active');
      const p=document.getElementById('panel-'+b.dataset.tab);
      if(p) p.classList.add('active');
    };
  });
}

async function fetchData(){
  const maxRetries=2;
  for(let attempt=0; attempt<=maxRetries; attempt++){
    try{
      const r=await fetch(`/api/stock/${TICK}?t=${Date.now()}`);
      if(r.status===429 && attempt<maxRetries){ await new Promise(res=>setTimeout(res, 1000*(attempt+1))); continue; }
      if(!r.ok){
        const j=await r.json().catch(()=>({error:r.statusText}));
        throw new Error(j.error || `HTTP ${r.status}`);
      }
      DATA=await r.json();
      if(!DATA || !DATA.ticker) throw new Error('Empty response');
      render();
      try{ pollLive(); setInterval(pollLive,30000);}catch(e){}
      return;
    }catch(e){
      if(attempt===maxRetries){
        html('exec-summary', `<div style="color:var(--red);padding:12px;border:1px solid var(--red);border-radius:8px">FAILED to load ${TICK}: ${e.message}. <button onclick="location.reload()" class="btn" style="margin-left:8px">Retry</button></div>`);
        toast('Failed to load '+TICK+': '+e.message, 'error');
        console.error(e);
      } else {
        await new Promise(res=>setTimeout(res, 600*(attempt+1)));
      }
    }
  }
}

function render(){
  const m=DATA.key_metrics||{}, dcf=DATA.dcf_data||{}, sc=DATA.financial_scores||{}, an=DATA.analysis||{}, val=an.valuation_assessment||{};
  const curr=Number(m.current_price||m.currentPrice||0);
  const fair=Number(val.fair_value_mid||dcf.implied_price||curr);
  const upside=curr?((fair-curr)/curr*100):0;
  const pe=`${fmt(m.trailingPE)} / ${fmt(m.forwardPE)}`;
  const eps=`$${fmt(m.trailingEps)} / $${fmt(m.forwardEps)}`;
  const target=Number(m.targetMeanPrice||0);
  const verdict=(an.verdict||'HOLD').toUpperCase();
  const conf=an.verdict_confidence||0;

  set('hero-company', DATA.company_name||TICK);
  set('hero-summary', (an.executive_summary||'').split('.').slice(0,2).join('.')||'AI verdict and valuation below.');
  set('hero-verdict', verdict); set('hero-confidence', conf+'%'); set('hero-upside', `${upside>=0?'+':''}${upside.toFixed(1)}%`);
  set('hero-price', money(curr)); set('hero-fair', money(fair)); set('hero-risk', (an.risk_assessment?.risk_reward_ratio||'Balanced'));
  set('s-price', money(curr)); set('s-price-sub', `${(Number(m.price_change_1d)||0).toFixed(2)}% today`);
  set('s-fair', money(fair)); set('s-fair-sub', `${upside>=0?'+':''}${upside.toFixed(1)}% vs price`);
  set('s-pe', pe); set('s-eps', eps); set('s-target', money(target)); set('s-target-sub', `${m.numberOfAnalystOpinions||'?'} analysts`);

  try{ renderQuote(m); }catch(eq){ console.log(eq); }
  try{ renderStats(); }catch(es){ console.log(es); }
  // verdict
  const vb=$('verdict-badge'); if(vb){ vb.innerText=verdict; vb.className='badge '+badge(verdict); }
  set('conf-badge', conf+'% confidence');
  html('exec-summary', `<div style="white-space:pre-wrap">${esc(an.executive_summary||'--')}</div>`);
  html('why-list', (()=>{
    const items=[];
    if(curr&&fair) items.push(`Price ${money(curr)} vs fair ${money(fair)} (${upside>=0?'+':''}${upside.toFixed(1)}%).`);
    if(m.revenueGrowth_pct!=null) items.push(`Revenue growth ${pct(m.revenueGrowth_pct)}.`);
    if(m.freeCashflow) items.push(`FCF ${money(m.freeCashflow)} (base for DCF).`);
    items.push(`AI verdict ${verdict} ${conf}%.`);
    return items.map(i=>`<li>${i}</li>`).join('');
  })());
  html('thesis', esc(an.investment_thesis||'--')); html('position', esc(an.position_sizing||'--')); html('reasoning', esc(an.verdict_reasoning||'--'));

  // valuation
  const fcf=dcf.fcf_base||m.freeCashflow;
  html('dcf-box', `
    <div>FCF base <b>${money(fcf)}</b> • WACC <b>${dcf.wacc_used||'--'}%</b> • Terminal <b>${dcf.terminal_growth||'--'}%</b></div>
    <div style="margin-top:6px">Fair <b>${money(fair)}</b> • Spot <b>${money(curr)}</b> • Upside <b style="color:${upside>=0?'var(--green)':'var(--red)'}">${upside.toFixed(1)}%</b></div>
    <div style="margin-top:6px;color:var(--muted)">Basis: ${dcf.valuation_basis||'FCF DCF'}</div>
  `);
  const range=$('dcf-range'); if(range) range.style.width = `${Math.min(90, Math.max(10, 50+upside))}%`;
  // targets
  html('targets', `
    <div style="display:flex;justify-content:space-between;border:1px solid var(--border);border-radius:10px;padding:10px"><span>Bear</span><b>${money(an.bear_case_target||val.fair_value_low)}</b></div>
    <div style="display:flex;justify-content:space-between;border:1px solid var(--green);border-radius:10px;padding:10px;background:rgba(52,199,89,.06)"><span>12m Target</span><b>${money(an.price_target_12m||fair)}</b></div>
    <div style="display:flex;justify-content:space-between;border:1px solid var(--border);border-radius:10px;padding:10px"><span>Bull</span><b>${money(an.bull_case_target||val.fair_value_high)}</b></div>
  `);
  const adv=DATA.advanced_models||{};
  html('adv-models', `
    <div>Monte Carlo p10/p50/p90: $${adv.monte_carlo?.p10||'--'} / $${adv.monte_carlo?.p50||'--'} / $${adv.monte_carlo?.p90||'--'}</div>
    <div>CCA median: $${adv.cca?.implied_pe_price||adv.cca?.implied_fwd_pe_price||'--'}</div>
    <div>DDM: ${adv.ddm?.implied_price? money(adv.ddm.implied_price): adv.ddm?.message||'--'}</div>
    <div>Regression fair: $${adv.regression?.fair_price||'--'} (${adv.regression?.deviation_pct||'--'}% vs trend)</div>
  `);
  html('reconcile', val.current_valuation||'Model-weighted fair value reconciles DCF, peers, analyst target, regression.');

  // peers
  const peers=DATA.peers_data||[];
  const tbody=document.querySelector('#peers-table tbody');
  if(tbody){
    tbody.innerHTML = peers.length? peers.map(p=> `<tr><td>${esc(safeDisplay(p.ticker))}</td><td>${fmt(p.pe)}</td><td>${fmt(p.fwd_pe)}</td><td>${fmt(p.ps)}</td><td>${fmt(p.pb)}</td></tr>`).join('') : `<tr><td colspan="5" style="color:var(--muted)">No peers</td></tr>`;
  }

  // risks
  const risks=(an.risk_assessment?.risk_factors||[]).map(r=> `<li><b>${r.risk}</b> — ${r.impact} <span style="color:var(--muted)">[${r.severity}/${r.probability}]</span></li>`).join('');
  html('risk-list', risks||'<li>No risks</li>');
  const cats=(an.catalysts||[]).map(c=> `<li><b>${c.catalyst}</b> <span style="color:var(--muted)">(${c.timeline}, ${c.impact})</span></li>`).join('');
  html('catalyst-list', cats||'<li>No catalysts</li>');

  // notion
  const notion=DATA.notion_data||{};
  const subpages=notion.subpages||{};
  const notionNav=$('notion-subnav'), notionContent=$('notion-content'), notionPage=$('notion-page');
  if(notionPage) notionPage.innerText = notion.company_title||'';
  if(notionNav && notionContent){
    const keys=Object.keys(subpages);
    if(keys.length){
      notionNav.innerHTML = keys.map((k,i)=> `<button class="notion-btn ${i===0?'active':''}" data-k="${k}">${subpages[k].title||k}</button>`).join('');
      const renderNotion=(k)=>{
        const html=subpages[k]?.html||'<div style="color:var(--muted)">No content</div>';
        notionContent.innerHTML=html;
        notionNav.querySelectorAll('.notion-btn').forEach(b=> b.classList.toggle('active', b.dataset.k===k));
      };
      notionNav.querySelectorAll('.notion-btn').forEach(b=> b.onclick=()=> renderNotion(b.dataset.k));
      renderNotion(keys[0]);
    }else{
      notionNav.innerHTML='<span style="color:var(--muted);font-size:12px">No Notion research — will auto-generate on next analyze</span>';
      notionContent.innerHTML='<div style="color:var(--muted)">Notion workspace not linked or empty for '+TICK+'</div>';
    }
  }

  // financials
  loadStmt('income');
  loadCharts();
}

let stmtType='income', stmtFreq='annual';
function setFreq(f,btn){
  stmtFreq=f;
  document.querySelectorAll('#panel-financials .freq-btn').forEach(b=>b.classList.remove('active'));
  if(btn)btn.classList.add('active');
  loadStmt(stmtType,null);
}
const STMT_PRIORITY={
income:["total revenue","cost of revenue","gross profit","operating expense","selling general","research development","operating income","ebit ","ebitda","interest expense","pretax","tax provision","net income","basic eps","diluted eps","weighted average shares","shares outstanding"],
balance:["cash and cash equivalents","total cash","short term investments","net receivables","inventory","total current assets","property plant","goodwill","intangible","total assets","accounts payable","total current liabilities","long term debt","total liabilities","retained earnings","stockholders equity","total equity","shares issued","ordinary shares"],
cashflow:["operating cash flow","investing cash flow","financing cash flow","capital expenditure","payments to acquire property","free cash flow","dividends paid","repurchase","buyback","issuance of debt","repayment of debt","net change in cash","ending cash","beginning cash"]
};
function stmtMoney(name,v){
  if(v==null||v===""||isNaN(Number(v)))return {t:"--",neg:false};
  const n=Number(v);
  if(/eps|per share/i.test(name||""))return {t:"$"+n.toFixed(2),neg:n<0};
  const a=Math.abs(n);
  const s=a>=1e12?"$"+(n/1e12).toFixed(2)+"T":a>=1e9?"$"+(n/1e9).toFixed(2)+"B":a>=1e6?"$"+(n/1e6).toFixed(2)+"M":a>=1e3?"$"+(n/1e3).toFixed(1)+"K":"$"+n.toFixed(0);
  return {t:s,neg:n<0};
}
function loadStmt(type,btn){
  if(type)stmtType=type;
  if(btn){document.querySelectorAll('#panel-financials .stmt-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');}
  const src={income:[DATA.financials,DATA.q_financials],balance:[DATA.balance_sheet,DATA.q_balance_sheet],cashflow:[DATA.cashflow,DATA.q_cashflow]}[stmtType];
  const df=stmtFreq==="quarterly"?src[1]:src[0];
  const tbl=$('stmt-table'),note=$('stmt-note');
  if(!df||!df.columns||!df.rows||!df.rows.length){tbl.innerHTML='<tr><td style="color:var(--muted)">No '+(stmtFreq)+' '+stmtType+' data in this analysis run.</td></tr>';if(note)note.innerText='';return;}
  const cols=df.columns;
  const periods=cols.slice(1,5);
  const prio=STMT_PRIORITY[stmtType]||[];
  const rank=n=>{const l=String(n).toLowerCase();for(let i=0;i<prio.length;i++){if(l.includes(prio[i]))return i;}return 999;};
  const rows=df.rows.slice().sort((a,b)=>{const ra=rank(a[cols[0]]),rb=rank(b[cols[0]]);return ra!==rb?ra-rb:String(a[cols[0]]).localeCompare(String(b[cols[0]]));});
  let h='<thead><tr><th style="text-align:left">Breakdown</th>'+periods.map(c=>`<th style="text-align:right">${c}</th>`).join('')+'<th style="text-align:right">YoY</th></tr></thead><tbody>';
  rows.forEach(r=>{
    const name=r[cols[0]]||'--';
    h+=`<tr><td style="font-weight:600;text-align:left">${name}</td>`;
    const vals=periods.map(c=>Number(r[c]));
    vals.forEach(v=>{
      const f=stmtMoney(name,isNaN(v)?null:v);
      h+=`<td style="text-align:right;font-family:JetBrains Mono,monospace;color:${f.neg?'var(--red)':'inherit'}">${f.t}</td>`;
    });
    const last=vals[vals.length-1],prev=vals[vals.length-2];
    let yoy='--',yc='var(--muted)';
    if(Number.isFinite(last)&&Number.isFinite(prev)&&prev!==0){const p=(last-prev)/Math.abs(prev)*100;yoy=(p>=0?'+':'')+p.toFixed(1)+'%';yc=p>=0?'var(--green)':'var(--red)';}
    h+=`<td style="text-align:right;font-family:JetBrains Mono,monospace;color:${yc}">${yoy}</td></tr>`;
  });
  h+='</tbody>';
  tbl.innerHTML=h;
  if(note)note.innerText=`${rows.length} rows - ${stmtFreq} - latest ${periods[periods.length-1]||''} - values in $B/$M, YoY = latest vs prior period`;
}

function loadCharts(){
  const c=$('charts');
  if(!c) return;
  c.innerHTML = '<div class="skeleton" style="height:180px"></div>';
  // simple placeholder - actual charts are generated server side as png, but we can list available
  setTimeout(()=>{
    const hist=DATA.price_history_compact;
    if(!hist){ c.innerHTML='<div style="color:var(--muted);font-size:12px">No price history</div>'; return; }
    if (typeof Chart === 'undefined'){ c.innerHTML='<div style="color:var(--muted);font-size:12px">Charts unavailable — check connection and reload</div>'; return; }
    c.innerHTML = `<canvas id="priceChart" height="180"></canvas>`;
    try{
      const labels=Object.keys(hist).slice(-60);
      const vals=labels.map(k=>hist[k]);
      new Chart(document.getElementById('priceChart'), {
        type:'line',
        data:{labels, datasets:[{data:vals, borderColor:'#34c759', backgroundColor:'rgba(52,199,89,.1)', fill:true, tension:.3, pointRadius:0}]},
        options:{responsive:true, plugins:{legend:{display:false}}, scales:{x:{display:false}, y:{grid:{color:'#1e1f23'}}}}
      });
    }catch(e){ c.innerHTML='<div style="color:var(--muted);font-size:12px">Chart unavailable</div>'; }
  },300);
}

async function pollLive(){
  try{
    const r=await fetch(`/api/stock/${TICK}/live-quote`);
    if(!r.ok) return;
    const j=await r.json();
    if(j.price && Number.isFinite(Number(j.price))){
      const priceEl=$('hero-price'), sPriceEl=$('s-price');
      const prevPrice = priceEl ? parseFloat(priceEl.innerText.replace('$','')) : NaN;
      const newPrice = Number(j.price);
      set('hero-price', `$${newPrice.toFixed(2)}`);
      set('s-price', `$${newPrice.toFixed(2)}`);
      if(Number.isFinite(prevPrice) && prevPrice!==newPrice){
        [priceEl, sPriceEl].forEach(el=>{
          if(!el) return;
          el.style.transition='background 0.2s';
          el.style.background = newPrice>prevPrice ? 'rgba(52,199,89,0.18)' : 'rgba(255,59,48,0.18)';
          setTimeout(()=> el.style.background='', 600);
        });
      }
      const chg=Number(j.change||0), pct=Number(j.pct||0);
      set('hero-price-sub', `${chg>=0?'+':''}${chg.toFixed(2)} (${(pct*100).toFixed(2)}% live)`);
      const el=$('s-price-sub'); if(el){ el.innerText=`${chg>=0?'+':''}${chg.toFixed(2)} today`; el.style.color = chg>=0?'var(--green)':'var(--red)'; }
      set('q-price', '$'+newPrice.toFixed(2)); set('q-chg', (chg>=0?'+':'')+chg.toFixed(2)+' ('+(chg>=0?'+':'')+(pct*100).toFixed(2)+'% today)');
    }
  }catch(e){}
}

function applyPreset(which){
  const p={bear:{wacc:11,g15:5,g610:3,term:1.5}, base:{wacc:9,g15:15,g610:10,term:2.5}, bull:{wacc:7.5,g15:20,g610:12,term:3}};
  const v=p[which]; if(!v) return;
  $('wacc').value=v.wacc; $('g15').value=v.g15; $('g610').value=v.g610; $('term').value=v.term;
}
async function recalc(){
  const wacc=Number($('wacc').value), g15=Number($('g15').value), g610=Number($('g610').value), term=Number($('term').value);
  if(![wacc,g15,g610,term].every(Number.isFinite)){ toast('Invalid inputs','error'); return; }
  if(wacc <= term){ toast('WACC must be > terminal growth','error'); return; }
  const body={wacc, growth_1_5:g15, growth_6_10:g610, terminal_growth:term};
  toast('Recalculating...','info');
  const r=await fetch(`/api/stock/${TICK}/recalculate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();
  if(j.error){ toast(j.error,'error'); return; } toast('Recalculated','success');
  DATA=j; render();
}

// live clock
function tick(){
  const e=$('live-clock'); if(e) e.innerText=new Date().toLocaleTimeString('en-GB',{hour12:false})+' UTC';
  const s=$('session'); if(s){ const h=new Date().getUTCHours(); s.innerText=(h>=13&&h<=20)?'OPEN':'CLOSED'; s.style.color=(h>=13&&h<=20)?'var(--green)':'var(--muted)'; }
}
setInterval(tick,1000); tick();
tabInit();
fetchData().catch(e=>{document.body.innerHTML=`<div style="padding:40px;text-align:center"><h2>Error loading ${TICK}</h2><p>${e}</p><a href="/">Hub</a></div>`;});
let QCHART=null, QRANGE=30;
function qNum(v){ const n=Number(v); return Number.isFinite(n)?n:null; }
function qMoney(v){ const n=qNum(v); return n==null?'--':'$'+n.toFixed(2); }
function qBig(v){ const n=qNum(v); if(n==null) return '--'; const a=Math.abs(n); if(a>=1e12) return '$'+(n/1e12).toFixed(2)+'T'; if(a>=1e9) return '$'+(n/1e9).toFixed(2)+'B'; if(a>=1e6) return '$'+(n/1e6).toFixed(1)+'M'; return '$'+n.toFixed(2); }
function qInt(v){ const n=qNum(v); if(n==null) return '--'; return Math.round(n).toLocaleString('en-US'); }
function qDate(v){ if(!v) return '--'; const t=Number(v); const d=t>1e12?new Date(t):(t>1e9?new Date(t*1000):new Date(v)); return isNaN(d)?'--':d.toISOString().slice(0,10); }
function qSlice(hist, range){
  const keys=Object.keys(hist||{}).sort();
  if(!keys.length) return [];
  if(range==='MAX') return keys;
  const last=new Date(keys[keys.length-1]);
  let cutoff;
  if(range==='YTD'){ cutoff=new Date(last.getFullYear(),0,1); }
  else { cutoff=new Date(last.getTime()-Number(range)*864e5); }
  const out=keys.filter(k=>new Date(k)>=cutoff);
  return out.length>1?out:keys.slice(-60);
}
function drawQChart(){
  const cv=document.getElementById('qchart'); if(!cv) return;
  const hist=DATA&&DATA.price_history_compact; if(!hist) return;
  let keys=qSlice(hist, QRANGE); if(keys.length<2) return;
  const pairs=keys.map(k=>{const v=hist[k];return [k,(v&&typeof v==="object")?Number(v.Close):Number(v)]}).filter(p=>Number.isFinite(p[1])); if(pairs.length<2){const nc=cv.getContext("2d");nc.fillStyle="#8a8d93";nc.font="12px Inter,sans-serif";nc.fillText("Not enough history for this range - try MAX.",12,20);return;} keys=pairs.map(p=>p[0]); const vals=pairs.map(p=>p[1]);
  const up=vals[vals.length-1]>=vals[0];
  const col=up?'#34c759':'#ff453a';
  const W=cv.clientWidth||600, H=230, dpr=window.devicePixelRatio||1;
  cv.width=W*dpr; cv.height=H*dpr;
  const ctx=cv.getContext('2d'); ctx.scale(dpr,dpr); ctx.clearRect(0,0,W,H);
  let lo=Math.min.apply(null,vals), hi=Math.max.apply(null,vals);
  if(hi<=lo){ hi=lo*1.01; lo=lo*0.99; }
  const pad=8, X=i=>pad+i*(W-pad-46)/(vals.length-1), Y=v=>6+(1-(v-lo)/(hi-lo))*(H-40);
  ctx.strokeStyle='#1b1d25'; ctx.fillStyle='#8a8d93'; ctx.font='10px JetBrains Mono,monospace'; ctx.lineWidth=1;
  for(let g=0; g<4; g++){ const gy=10+g*(H-44)/3; ctx.beginPath(); ctx.moveTo(0,gy); ctx.lineTo(W-44,gy); ctx.stroke(); const gv=hi-(hi-lo)*g/3; ctx.fillText('$'+gv.toFixed(0), W-40, gy+3); }
  const grad=ctx.createLinearGradient(0,0,0,H);
  grad.addColorStop(0, up?'rgba(52,199,89,.30)':'rgba(255,69,58,.30)'); grad.addColorStop(1,'rgba(0,0,0,0)');
  ctx.beginPath(); ctx.moveTo(X(0),Y(vals[0]));
  for(let i=1;i<vals.length;i++){ const xm=(X(i-1)+X(i))/2; ctx.bezierCurveTo(xm,Y(vals[i-1]),xm,Y(vals[i]),X(i),Y(vals[i])); }
  ctx.strokeStyle=col; ctx.lineWidth=2; ctx.stroke();
  ctx.lineTo(X(vals.length-1),H-24); ctx.lineTo(X(0),H-24); ctx.closePath(); ctx.fillStyle=grad; ctx.fill();
  ctx.fillStyle=col; ctx.beginPath(); ctx.arc(X(vals.length-1),Y(vals[vals.length-1]),3.5,0,7); ctx.fill();
  ctx.fillStyle='#c9cdd6'; ctx.fillText(keys[0], 2, H-8);
  const le=keys[keys.length-1]; ctx.fillText(le, Math.max(2,W-110), H-8);
  cv.onmousemove=function(ev){ const r=cv.getBoundingClientRect(); const i=Math.round((ev.clientX-r.left-pad)/(W-pad-46)*(vals.length-1)); if(i<0||i>=vals.length) return; drawQChart(); const c2=cv.getContext('2d'); c2.strokeStyle='rgba(255,255,255,.35)'; c2.beginPath(); c2.moveTo(X(i),4); c2.lineTo(X(i),H-24); c2.stroke(); c2.fillStyle='#fff'; c2.beginPath(); c2.arc(X(i),Y(vals[i]),4,0,7); c2.fill(); c2.fillStyle='#0a84ff'; const t='$'+vals[i].toFixed(2)+'  '+keys[i]; c2.fillText(t, Math.min(Math.max(2,X(i)-40),W-120), 12); };
  cv.onmouseleave=function(){ drawQChart(); };
}
function sPct2(m, base){ const p=qNum(m[base+"_pct"]); if(p!=null) return p.toFixed(2)+"%"; const v=qNum(m[base]); if(v!=null) return (v*100).toFixed(2)+"%"; return "--"; }
function sRawPct(v){ const n=qNum(v); return n==null?"--":n.toFixed(2)+"%"; }
function sMult(v){ const n=qNum(v); return n==null?"--":n.toFixed(2); }
function stmtVal(df, cands){ try{ if(!df||!df.rows||!df.rows.length||!df.columns||!df.columns.length) return null; const col=df.columns[df.columns.length-1]; const labK=Object.keys(df.rows[0])[0]; for(const pass of [0,1]){ for(const c of cands){ const r=df.rows.find(function(r){ const L=String(r[labK]||"").toLowerCase(); return pass===0?L===c:L.includes(c); }); if(r&&r[col]!=null&&r[col]!==""&&Number.isFinite(Number(r[col]))) return Number(r[col]); } } }catch(e){} return null; }
function statCard(title, rows, sub){ return "<div class=\"card\"><div class=\"card-title\">"+title+(sub?"<span style=\"margin-left:auto;font-size:10px;text-transform:none\">"+sub+"</span>":"")+"</div>"+rows.map(function(r){ return "<div class=\"qkv\"><span>"+r[0]+"</span><b>"+r[1]+"</b></div>"; }).join("")+"</div>"; }
function renderStats(){
  const root=document.getElementById("stats-root"); if(!root) return;
  const m=DATA.key_metrics||{};
  const curr=qNum(m.current_price!=null?m.current_price:m.currentPrice)||0;
  const med=qNum(m.targetMedianPrice), mean=qNum(m.targetMeanPrice), hi=qNum(m.targetHighPrice), lo=qNum(m.targetLowPrice);
  const medUp=(med!=null&&curr)?(((med-curr)/curr*100).toFixed(1)+"%"):"--";
  let bar="";
  if(lo!=null&&hi!=null&&hi>lo&&curr){ const p=Math.min(96,Math.max(4,((curr-lo)/(hi-lo))*100));
    bar="<div class=\"qr-h\" style=\"display:flex;justify-content:space-between;font-size:11px;color:var(--muted);font-family:JetBrains Mono,monospace;margin:10px 0 5px\"><span>LOW "+qMoney(lo)+"</span><span>CURRENT "+qMoney(curr)+"</span><span>HIGH "+qMoney(hi)+"</span></div><div class=\"qbar\" style=\"position:relative;height:6px;border-radius:99px;background:#1c1e26\"><i style=\"position:absolute;top:-3px;width:12px;height:12px;border-radius:50%;background:var(--blue);border:2px solid #0a0a0b;left:calc("+p.toFixed(1)+"% - 6px)\"></i></div>"; }
  const eCard="<div class=\"card\"><div class=\"card-title\">Earnings Preview</div><div id=\"earn-prev\"><div class=\"skeleton\" style=\"width:60%\"></div></div></div>";
  const tCard="<div class=\"card\"><div class=\"card-title\">Analyst Price Targets<span style=\"margin-left:auto;font-size:10px;text-transform:none\">"+(qInt(m.numberOfAnalystOpinions)==="--"?"":"based on "+qInt(m.numberOfAnalystOpinions)+" analysts")+"</span></div>"+"<div style=\"display:flex;gap:18px;flex-wrap:wrap;align-items:baseline\"><div><div style=\"font-size:11px;color:var(--muted)\">MEDIAN TARGET</div><div style=\"font-family:JetBrains Mono,monospace;font-size:26px;font-weight:700\">"+qMoney(med)+"</div></div><div><div style=\"font-size:11px;color:var(--muted)\">VS CURRENT</div><div style=\"font-family:JetBrains Mono,monospace;font-size:16px;font-weight:700;color:"+(String(medUp).charAt(0)==="-"?"var(--red)":"var(--green)")+"\">"+(medUp==="--"?"--":((String(medUp).charAt(0)==="-"?"":"+")+medUp))+"</div></div><div><div style=\"font-size:11px;color:var(--muted)\">MEAN / HIGH / LOW</div><div style=\"font-family:JetBrains Mono,monospace;font-size:13px\">"+qMoney(mean)+" / "+qMoney(hi)+" / "+qMoney(lo)+"</div></div></div>"+bar+"</div>";
  const vCard=statCard("Valuation Measures", [
    ["Market Cap", qBig(m.marketCap)], ["Enterprise Value", qBig(m.enterpriseValue)],
    ["Trailing P/E", sMult(m.trailingPE)], ["Forward P/E", sMult(m.forwardPE)], ["PEG Ratio", sMult(m.pegRatio)],
    ["Price/Sales (TTM)", sMult(m.priceToSalesTrailing12Months)], ["Price/Book", sMult(m.priceToBook)],
    ["Enterprise/Revenue", sMult(m.enterpriseToRevenue)], ["Enterprise/EBITDA", sMult(m.enterpriseToEbitda)]]);
  const pCard=statCard("Profitability", [
    ["Profit Margin", sPct2(m,"profitMargins")], ["Operating Margin", sPct2(m,"operatingMargins")], ["EBITDA Margin", sPct2(m,"ebitdaMargins")],
    ["Return on Assets", sPct2(m,"returnOnAssets")], ["Return on Equity", sPct2(m,"returnOnEquity")],
    ["Revenue (TTM)", qBig(m.totalRevenue)], ["Revenue Per Share", qMoney(m.revenuePerShare)],
    ["Revenue Growth (YoY)", sPct2(m,"revenueGrowth")], ["Quarterly Revenue Growth", sPct2(m,"earningsQuarterlyGrowth")],
    ["Earnings Growth", sPct2(m,"earningsGrowth")], ["Diluted EPS (TTM)", qMoney(m.trailingEps)], ["Forward EPS", qMoney(m.forwardEps)]]);
  const inc=DATA.financials, bal=DATA.balance_sheet, cf=DATA.cashflow;
  const incCol=(inc&&inc.columns&&inc.columns.length)?inc.columns[inc.columns.length-1]:null;
  const iRows=[["Total Revenue",stmtVal(inc,["total revenue"])],["Gross Profit",stmtVal(inc,["gross profit"])],["Operating Income",stmtVal(inc,["operating income","total operating income as reported"])],["Net Income",stmtVal(inc,["net income"])],["EBITDA",stmtVal(inc,["ebitda","normalized ebitda"])],["Diluted EPS",stmtVal(inc,["diluted eps"] )]];
  const iShow=iRows.some(function(r){return r[1]!=null;});
  const iCard=iShow?statCard("Income Statement", iRows.filter(function(r){return r[1]!=null;}).map(function(r){ return [r[0], (r[0].indexOf("EPS")>=0?("$"+r[1].toFixed(2)):qBig(r[1]))]; }), incCol?("latest: "+incCol):""):"";
  const bCard=statCard("Balance Sheet & Cash Flow", [
    ["Total Cash", qBig(m.totalCash)], ["Cash Per Share", qMoney(m.totalCashPerShare)], ["Total Debt", qBig(m.totalDebt)],
    ["Debt/Equity", sMult(m.debtToEquity)], ["Current Ratio", sMult(m.currentRatio)], ["Quick Ratio", sMult(m.quickRatio)],
    ["Book Value / Share", qMoney(m.bookValue)], ["Operating Cash Flow", qBig(m.operatingCashflow)], ["Free Cash Flow", qBig(m.freeCashflow)]]);
  const sCard=statCard("Share Statistics", [
    ["Shares Outstanding", qInt(m.sharesOutstanding)], ["Beta (5Y monthly)", sMult(m.beta)],
    ["% Held by Insiders", sPct2(m,"heldPercentInsiders")], ["% Held by Institutions", sPct2(m,"heldPercentInstitutions")],
    ["Short % of Float", sPct2(m,"shortPercentOfFloat")], ["Short Ratio", sMult(m.shortRatio)],
    ["52-Week High / Low", qMoney(m.high_52w)+" / "+qMoney(m.low_52w)], ["1-Year Return", sRawPct(m.return_1y)]]);
  const dCard=statCard("Dividends", [
    ["Forward Dividend", qMoney(m.dividendRate)], ["Dividend Yield", sPct2(m,"dividendYield")],
    ["Payout Ratio", sPct2(m,"payoutRatio")], ["5-Year Avg Yield", sRawPct(m.fiveYearAvgDividendYield)]]);
  const rCard="<div class=\"card\"><div class=\"card-title\">Analyst Ratings Trend</div><div id=\"ratings-prev\"><div class=\"skeleton\" style=\"width:55%\"></div></div></div>";
  const os=DATA.options_sentiment||{};
  let oCard="";
  if(os&&(os.put_call_volume_ratio!=null||os.avg_implied_volatility!=null)){
    const pcv=qNum(os.put_call_volume_ratio), pco=qNum(os.put_call_oi_ratio), iv=qNum(os.avg_implied_volatility);
    const bias=(pcv==null)?"--":(pcv<0.7?"BULLISH":(pcv>1?"BEARISH":"NEUTRAL"));
    const bcol=bias==="BULLISH"?"var(--green)":(bias==="BEARISH"?"var(--red)":"var(--orange)");
    oCard=statCard("Options Sentiment", [
      ["Bias (P/C vol)", "<span style=\"color:"+bcol+"\">"+bias+"</span>"],
      ["Put/Call Volume", pcv==null?"--":pcv.toFixed(3)],
      ["Put/Call Open Interest", pco==null?"--":pco.toFixed(3)],
      ["Avg Implied Volatility", iv==null?"--":(iv*100).toFixed(1)+"%"],
      ["Front Expiry", esc(os.expiration||"--")]], "options chain");
  }
  const estCard="<div class=\"card\"><div class=\"card-title\">Earnings & Revenue Estimates<span style=\"margin-left:auto;font-size:10px;text-transform:none\">analyst consensus</span></div><div id=\"est-prev\"><div class=\"skeleton\" style=\"width:55%\"></div></div></div>";
  root.innerHTML=tCard+eCard+rCard+"<div class=\"grid2\">"+vCard+pCard+"</div>"+estCard+(iCard?"<div class=\"grid2\">"+iCard+bCard+"</div>":bCard)+"<div class=\"grid2\">"+sCard+dCard+oCard+"</div>";
  try{ renderEarnPrev(); }catch(ee){ console.log(ee); }
  try{ renderRatings(); }catch(er){ console.log(er); }
  try{ renderEstimates(); }catch(ee2){ console.log(ee2); }
}
function qSeries(df, label){ try{ if(!df||!df.rows||!df.rows.length||!df.columns||!df.columns.length) return []; const labK=Object.keys(df.rows[0])[0]; const row=df.rows.find(function(r){ return String(r[labK]||"").toLowerCase()===label; }); if(!row) return []; return df.columns.slice(1).map(function(c){ const v=Number(row[c]); return [c, Number.isFinite(v)?v:null]; }).filter(function(p){ return p[1]!=null; }); }catch(e){ return []; } }
function qShortQ(dstr){ const m=/^(\d{4})-(\d{2})/.exec(dstr||""); if(!m) return dstr||""; return "Q"+Math.ceil(Number(m[2])/3)+" '"+m[1].slice(2); }
function drawQRev(){
  const cv=document.getElementById("qrev"), cap=document.getElementById("qrev-cap"); if(!cv) return;
  const rev=qSeries(DATA&&DATA.q_financials,"total revenue").slice(-8);
  const ni=qSeries(DATA&&DATA.q_financials,"net income").slice(-8);
  if(rev.length<2){ cv.style.display="none"; if(cap) cap.style.display="none"; return; }
  cv.style.display=""; if(cap) cap.style.display="";
  const W=cv.clientWidth||600, H=96, dpr=window.devicePixelRatio||1;
  cv.width=W*dpr; cv.height=H*dpr;
  const ctx=cv.getContext("2d"); ctx.scale(dpr,dpr); ctx.clearRect(0,0,W,H);
  const niv=ni.map(function(p){return p[1];}).filter(Number.isFinite);
  const re=(typeof window!=="undefined"&&window._revEst)?window._revEst:null;
  const estAvg=re?qNum(re.avg):null;
  const estHi=re?qNum(re.hi):null;
  const est=(estAvg&&estAvg>0)?{avg:estAvg,hi:estHi}:null;
  const mx=Math.max.apply(null, rev.map(function(p){return p[1];}).concat(niv.length?niv:[0]).concat(est?[est.avg,est.hi||0]:[]))||1;
  const bars=rev.map(function(p){ return {d:p[0],v:p[1],est:false}; });
  if(est) bars.push({d:"EST",v:est.avg,est:true});
  const base=H-18, top=16, n=bars.length, slot=W/n, bw=Math.min(34,slot*0.5);
  ctx.font="9px JetBrains Mono,monospace";
  bars.forEach(function(b,i){
    const h=Math.max(2,(b.v/mx)*(base-top)); const x=slot*i+(slot-bw)/2;
    if(b.est){ ctx.save(); ctx.setLineDash([4,3]); ctx.strokeStyle="rgba(191,90,242,.95)"; ctx.lineWidth=1.5; ctx.fillStyle="rgba(191,90,242,.16)"; ctx.fillRect(x,base-h,bw,h); ctx.strokeRect(x,base-h,bw,h); ctx.restore(); ctx.fillStyle="#bf5af2"; ctx.fillText("EST",slot*i+2,H-5); }
    else { ctx.fillStyle="rgba(10,132,255,.8)"; ctx.fillRect(x,base-h,bw,h); ctx.fillStyle="#8a8d93"; ctx.fillText(qShortQ(b.d),slot*i+2,H-5); }
  });
  const niByDate={}; ni.forEach(function(p){ niByDate[p[0]]=p[1]; });
  ctx.fillStyle="#34c759";
  rev.forEach(function(p,i){ const v=niByDate[p[0]]; if(v==null) return; const y=base-(v/mx)*(base-top); ctx.beginPath(); ctx.arc(slot*i+slot/2,y,3,0,7); ctx.fill(); });
  if(cap){ const last=rev[rev.length-1][1], prev=rev[rev.length-2][1]; const qoq=prev?(((last-prev)/Math.abs(prev)*100).toFixed(1)+"% QoQ"):""; let yoy=""; if(rev.length>=5){ const y=rev[rev.length-5][1]; if(y) yoy=" / "+(((last-y)/Math.abs(y)*100).toFixed(1)+"% YoY"); } cap.textContent="QUARTERLY REVENUE $"+(last/1e9).toFixed(1)+"B ("+qoq+yoy+") \u2022 dots = net income"+(est?" \u2022 dashed = next-qtr consensus $"+(est.avg/1e9).toFixed(1)+"B":""); }
}
function renderEarnPrev(){
  const el=document.getElementById("earn-prev"); if(!el) return;
  fetch("/api/stock/"+TICK+"/earnings-preview").then(function(r){ return r.json(); }).then(function(d){
    let cd=""; if(d.next_date){ const t=new Date(); t.setHours(0,0,0,0); const days=Math.round((new Date(d.next_date+"T12:00:00")-t)/864e5); cd=days<0?"reported "+Math.abs(days)+"d ago":(days===0?"expected TODAY":"in "+days+"d"); }
        const st=(d.surprises||[]).map(function(x){ const sp=qNum(x.surprise_pct); const col=sp==null?"var(--muted)":(sp>=0?"var(--green)":"var(--red)"); const spt=sp==null?"--":((sp>=0?"+":"")+sp.toFixed(2)+"%"); const es=qNum(x.estimate), rp=qNum(x.reported); return "<tr><td>"+qShortQ(x.date)+"</td><td>"+(es==null?"--":"$"+es.toFixed(2))+"</td><td>"+(rp==null?"--":"$"+rp.toFixed(2))+"</td><td style=\"color:"+col+"\">"+spt+"</td></tr>"; }).join("");
    const stHtml=st?"<div style=\"font-size:11px;color:var(--muted);margin:10px 0 4px\">EPS SURPRISE HISTORY</div><div style=\"overflow:auto\"><table class=\"table\"><thead><tr><th>Quarter</th><th>Estimate</th><th>Reported</th><th>Surprise</th></tr></thead><tbody>"+st+"</tbody></table></div>":"";
    const qrows=(d.quarters||[]).map(function(q,i,arr){ let chg=""; if(i>0&&arr[i-1].revenue){ chg=" ("+(((q.revenue-arr[i-1].revenue)/Math.abs(arr[i-1].revenue)*100).toFixed(1)+"％").replace("％","%")+")"; } return "<div class=\"qkv\"><span>"+qShortQ(q.date)+"</span><b>"+qBig(q.revenue)+" rev \u2022 "+qBig(q.net_income)+" NI"+chg+"</b></div>"; }).join("");
    el.innerHTML="<div style=\"display:flex;gap:18px;flex-wrap:wrap;align-items:baseline;margin-bottom:6px\">"+"<div><div style=\"font-size:11px;color:var(--muted)\">NEXT REPORT "+(d.next_date||"--")+(cd?" ("+cd+")":"")+"</div><div style=\"font-family:JetBrains Mono,monospace;font-size:13px;font-weight:700\">EPS est $"+(qNum(d.eps_avg)==null?"--":qNum(d.eps_avg).toFixed(2))+" <span style=\"color:var(--muted);font-weight:400\">("+((qNum(d.eps_low)==null)?"--":"$"+qNum(d.eps_low).toFixed(2))+" \u2013 "+((qNum(d.eps_high)==null)?"--":"$"+qNum(d.eps_high).toFixed(2))+")</span></div></div>"+"<div><div style=\"font-size:11px;color:var(--muted)\">REVENUE EST</div><div style=\"font-family:JetBrains Mono,monospace;font-size:13px;font-weight:700\">"+qBig(d.rev_avg)+" <span style=\"color:var(--muted);font-weight:400\">("+qBig(d.rev_low)+" \u2013 "+qBig(d.rev_high)+")</span></div></div>"+(d.analysts?"<div><div style=\"font-size:11px;color:var(--muted)\">ESTIMATES FROM</div><div style=\"font-family:JetBrains Mono,monospace;font-size:13px\">"+d.analysts+" analysts</div></div>":"")+"</div>"+(qrows||"<div style=\"color:var(--muted);font-size:12px\">No recent quarters stored.</div>")+stHtml;
  }).catch(function(){ el.innerHTML="<div style=\"color:var(--muted);font-size:12px\">Earnings preview unavailable.</div>"; });
}
function rPeriodLabel(p){ if(p==="0m") return "Now"; const m=/^-(\d+)m$/.exec(p||""); return m?m[1]+" mo ago":p; }
function renderRatings(){
  const el=document.getElementById("ratings-prev"); if(!el) return;
  fetch("/api/stock/"+TICK+"/ratings-trend").then(function(r){ return r.json(); }).then(function(d){
    const ps=d.periods||[];
    if(!ps.length){ el.innerHTML="<div style=\"color:var(--muted);font-size:12px\">No ratings trend available.</div>"; return; }
    const segs=[["strongBuy","STRONG BUY","#0a7d33"],["buy","BUY","#34c759"],["hold","HOLD","#ff9f0a"],["sell","SELL","#ff6b62"],["strongSell","STRONG SELL","#ff453a"]];
    const rows=ps.map(function(p){ const tot=segs.reduce(function(a,x){ return a+(Number(p[x[0]])||0); },0)||1;
      const bar=segs.map(function(x){ const v=Number(p[x[0]])||0, w=(v/tot*100); return w<=0?"":'<div title="'+x[1]+': '+v+'" style="width:'+w.toFixed(1)+'%;background:'+x[2]+'"></div>'; }).join("");
      return '<div style="display:grid;grid-template-columns:78px 1fr 34px;gap:10px;align-items:center;margin:7px 0;font-size:11.5px"><span style="color:var(--muted);font-family:JetBrains Mono,monospace">'+rPeriodLabel(p.period)+'</span><div style="display:flex;height:14px;border-radius:7px;overflow:hidden;background:#1c1e26">'+bar+'</div><b style="font-family:JetBrains Mono,monospace;text-align:right">'+tot+'</b></div>'; });
    const leg=segs.map(function(x){ return '<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px;font-size:11px;color:var(--muted)"><i style="width:9px;height:9px;border-radius:3px;background:'+x[2]+';display:inline-block"></i>'+x[1]+'</span>'; }).join("");
    el.innerHTML="<div style=\"margin-bottom:8px\">"+leg+"</div>"+rows.join("");
  }).catch(function(){ el.innerHTML="<div style=\"color:var(--muted);font-size:12px\">Ratings trend unavailable.</div>"; });
}
function estPeriodLabel(p){ return {"0q":"Current Qtr","+1q":"Next Qtr","0y":"Current Year","+1y":"Next Year"}[p]||p; }
function estTable(rows, money){
  const head="<thead><tr><th></th><th>Avg Est</th><th>Low</th><th>High</th><th># Anl</th><th>Growth</th></tr></thead>";
  const body=rows.map(function(r){
    const g=qNum(r.growth), gc=g==null?"":(g>=0?"var(--green)":"var(--red)");
    const f=money?function(v){ return qBig(v); }:function(v){ const n=qNum(v); return n==null?"--":"$"+n.toFixed(2); };
    return "<tr><td>"+estPeriodLabel(r.period)+"</td><td>"+f(r.avg)+"</td><td>"+f(r.low)+"</td><td>"+f(r.high)+"</td><td>"+(qNum(r.analysts)==null?"--":Math.round(qNum(r.analysts)))+"</td><td style=\"color:"+gc+"\">"+(g==null?"--":((g>=0?"+":"")+(g*100).toFixed(1)+"%"))+"</td></tr>";
  }).join("");
  return "<div style=\"overflow:auto\"><table class=\"table\">"+head+"<tbody>"+body+"</tbody></table></div>";
}
function renderEstimates(){
  const el=document.getElementById("est-prev"); if(!el) return;
  fetch("/api/stock/"+TICK+"/estimates").then(function(r){ return r.json(); }).then(function(d){
    const er=d.earnings||[], rv=d.revenue||[], gr=d.growth||[];
    if(!er.length&&!rv.length){ el.innerHTML="<div style=\"color:var(--muted);font-size:12px\">No analyst estimates available.</div>"; return; }
    let h="";
    if(er.length) h+="<div style=\"font-size:11px;color:var(--muted);margin:10px 0 4px\">EARNINGS ESTIMATE (EPS)</div>"+estTable(er,false);
    if(rv.length) h+="<div style=\"font-size:11px;color:var(--muted);margin:10px 0 4px\">REVENUE ESTIMATE</div>"+estTable(rv,true);
    if(gr.length){
      const gl={"0q":"Current Qtr","+1q":"Next Qtr","0y":"Current Year","+1y":"Next Year","LTG":"Long-Term Growth"};
      h+="<div style=\"font-size:11px;color:var(--muted);margin:10px 0 4px\">GROWTH ESTIMATES (STOCK VS INDUSTRY)</div>"+gr.map(function(g){
        const s=qNum(g.stock), ix=qNum(g.index);
        return "<div class=\"qkv\"><span>"+(gl[g.period]||g.period)+"</span><b>"+(s==null?"--":((s>=0?"+":"")+(s*100).toFixed(1)+"%"))+" vs "+(ix==null?"--":((ix>=0?"+":"")+(ix*100).toFixed(1)+"%"))+"</b></div>";
      }).join("");
    }
    el.innerHTML=h;
    try{
      const rq=(rv||[]).find(function(r){ return r.period==="0q"; })||rv[0];
      if(typeof window!=="undefined"&&rq&&qNum(rq.avg)) window._revEst={avg:qNum(rq.avg),lo:qNum(rq.low),hi:qNum(rq.high)};
      if(typeof drawQRev==="function") drawQRev();
    }catch(ee3){ console.log(ee3); }
  }).catch(function(){ el.innerHTML="<div style=\"color:var(--muted);font-size:12px\">Estimates unavailable.</div>"; });
}
function qMarker(id, labId, lo, hi, val, fmtF){
  const lab=document.getElementById(labId), bar=document.getElementById(id);
  if(lo==null||hi==null||!(hi>lo)){ if(lab) lab.innerText='--'; if(bar) bar.style.display='none'; return; }
  if(lab) lab.innerText=fmtF(lo)+' - '+fmtF(hi);
  if(bar){ bar.style.display=''; const p=Math.min(96,Math.max(4,((val-lo)/(hi-lo))*100)); bar.style.left='calc('+p.toFixed(1)+'% - 6px)'; }
}
function renderQuote(m){
  m=m||{};
  const curr=qNum(m.current_price!=null?m.current_price:m.currentPrice)||0;
  const prev=qNum(m.previousClose)!=null?qNum(m.previousClose):curr;
  const chg=curr-prev, chgP=prev?chg/prev*100:0;
  const cls=chg>0?'up':(chg<0?'dn':'flat');
  const col=chg>0?'var(--green)':(chg<0?'var(--red)':'var(--muted)');
  const setT=function(id,t){ const e=document.getElementById(id); if(e) e.innerText=t; };
  setT('q-name', DATA.company_name||TICK);
  setT('q-tick', TICK);
  setT('q-sector', (m.sector||'')+((m.sector&&m.industry)?' • ':'')+(m.industry||''));
  setT('q-price', curr?('$'+curr.toFixed(2)):'--');
  const ce=document.getElementById('q-chg');
  if(ce){ ce.innerText=(chg>=0?'+':'')+chg.toFixed(2)+' ('+(chg>=0?'+':'')+chgP.toFixed(2)+'%) today'; ce.style.color=col; }
  const eh=DATA.extended_hours, ahe=document.getElementById('q-ah');
  if(ahe){ const ehp=eh&&(eh.price||eh.postMarketPrice||eh.afterHoursPrice); ahe.innerText=(ehp!=null&&Number.isFinite(Number(ehp)))?('After hours $'+Number(ehp).toFixed(2)):''; }
  qMarker('q-daybar','q-daylab',qNum(m.dayLow),qNum(m.dayHigh),curr,function(v){return '$'+v.toFixed(2)});
  qMarker('q-wkbar','q-wklab',qNum(m.low_52w!=null?m.low_52w:m.fiftyTwoWeekLow),qNum(m.high_52w!=null?m.high_52w:m.fiftyTwoWeekHigh),curr,function(v){return '$'+v.toFixed(2)});
  const dy=qNum(m.dividendYield), dyT=dy==null?'--':((dy>1?dy:dy*100).toFixed(2)+'%');
  const rows=[
    ['Prev Close', (prev?qMoney(prev):'--')],['Open', (qNum(m.open)?qMoney(m.open):'--')],
    ['Day Low / High', (qNum(m.dayLow)!=null?qMoney(m.dayLow):'--')+' / '+(qNum(m.dayHigh)!=null?qMoney(m.dayHigh):'--')],
    ['52W Low / High', (qNum(m.low_52w)!=null?qMoney(m.low_52w):'--')+' / '+(qNum(m.high_52w)!=null?qMoney(m.high_52w):'--')],
    ['Volume', qInt(m.volume)],['Avg Volume', qInt(m.averageVolume)],
    ['Mkt Cap', qBig(m.marketCap)],['Beta', (qNum(m.beta)!=null?qNum(m.beta).toFixed(2):'--')],
    ['Trailing P/E', (qNum(m.trailingPE)!=null?qNum(m.trailingPE).toFixed(2):'--')],['Forward P/E', (qNum(m.forwardPE)!=null?qNum(m.forwardPE).toFixed(2):'--')],
    ['Trailing EPS', qMoney(m.trailingEps)],['Forward EPS', qMoney(m.forwardEps)],
    ['Div Yield', dyT],['Ex-Div Date', qDate(m.exDividendDate)],
    ['Earnings Date', qDate(m.earningsTimestamp||m.earningsDate)],['Target (mean)', qMoney(m.targetMeanPrice)],
    ['Analysts', (m.numberOfAnalystOpinions!=null?m.numberOfAnalystOpinions:'--')]
  ];
  const se=document.getElementById('q-stats');
  if(se) se.innerHTML=rows.map(function(r){return '<div class="qkv"><span>'+r[0]+'</span><b>'+r[1]+'</b></div>'}).join('');
  drawQChart();
  try{ drawQRev(); }catch(eq2){ console.log(eq2); }
}
document.querySelectorAll('#q-iv button').forEach(function(b){ b.onclick=function(){ document.querySelectorAll('#q-iv button').forEach(function(x){x.classList.remove('on')}); b.classList.add('on'); QRANGE=(b.getAttribute('data-r')==='MAX'||b.getAttribute('data-r')==='YTD')?b.getAttribute('data-r'):Number(b.getAttribute('data-r')); drawQChart(); }; });




window.addEventListener('resize', function(){ try{ if(DATA){ drawQChart(); drawQRev(); } }catch(e){} });
