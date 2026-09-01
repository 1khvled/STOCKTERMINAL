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
  const r=await fetch(`/api/stock/${TICK}?t=${Date.now()}`);
  if(!r.ok) throw new Error('no data');
  DATA=await r.json();
  render();
  // live poll
  try{ pollLive(); setInterval(pollLive,30000);}catch(e){}
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
  
  // verdict
  const vb=$('verdict-badge'); if(vb){ vb.innerText=verdict; vb.className='badge '+badge(verdict); }
  set('conf-badge', conf+'% confidence');
  html('exec-summary', `<div style="white-space:pre-wrap">${an.executive_summary||'--'}</div>`);
  html('why-list', (()=>{
    const items=[];
    if(curr&&fair) items.push(`Price ${money(curr)} vs fair ${money(fair)} (${upside>=0?'+':''}${upside.toFixed(1)}%).`);
    if(m.revenueGrowth_pct!=null) items.push(`Revenue growth ${pct(m.revenueGrowth_pct)}.`);
    if(m.freeCashflow) items.push(`FCF ${money(m.freeCashflow)} (base for DCF).`);
    items.push(`AI verdict ${verdict} ${conf}%.`);
    return items.map(i=>`<li>${i}</li>`).join('');
  })());
  html('thesis', an.investment_thesis||'--'); html('position', an.position_sizing||'--'); html('reasoning', an.verdict_reasoning||'--');

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
    tbody.innerHTML = peers.length? peers.map(p=> `<tr><td>${p.ticker}</td><td>${fmt(p.pe)}</td><td>${fmt(p.fwd_pe)}</td><td>${fmt(p.ps)}</td><td>${fmt(p.pb)}</td></tr>`).join('') : `<tr><td colspan="5" style="color:var(--muted)">No peers</td></tr>`;
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

function loadStmt(type, btn){
  if(btn){ document.querySelectorAll('#panel-financials .btn').forEach(b=>b.classList.remove('active')); btn.classList.add('active'); }
  const map={income: DATA.financials, balance: DATA.balance_sheet, cashflow: DATA.cashflow};
  const df=map[type];
  const tbl=$('stmt-table');
  if(!df || !df.columns){ tbl.innerHTML='<tr><td>No data</td></tr>'; return; }
  let h='<thead><tr><th>Breakdown</th>'+df.columns.slice(0,6).map(c=>`<th>${c}</th>`).join('')+'</tr></thead><tbody>';
  const idx=df.index||[];
  // df is stored as {columns, rows}? handle both
  // Our stored financials is _df_to_json_ready output: need to render generic
  // Fallback simple: iterate rows if available
  try{
    const cols=df.columns||[];
    const rows=df.rows||df.data||[];
    // rows is array of dicts
    rows.slice(0,15).forEach(r=>{
      h+=`<tr><td style="font-weight:600">${r[cols[0]]||r.index||''}</td>`;
      cols.slice(1,6).forEach(c=>{ const v=r[c]; h+=`<td style="font-family:JetBrains Mono,monospace">${v==null?'--': (Number(v).toLocaleString())}</td>`; });
      h+='</tr>';
    });
  }catch(e){ h+=`<tr><td>Error ${e}</td></tr>`; }
  h+='</tbody>';
  tbl.innerHTML=h;
}

function loadCharts(){
  const c=$('charts');
  if(!c) return;
  c.innerHTML = '<div class="skeleton" style="height:180px"></div>';
  // simple placeholder - actual charts are generated server side as png, but we can list available
  setTimeout(()=>{
    const hist=DATA.price_history_compact;
    if(!hist){ c.innerHTML='<div style="color:var(--muted);font-size:12px">No price history</div>'; return; }
    c.innerHTML = `<canvas id="priceChart" height="180"></canvas>`;
    try{
      const labels=Object.keys(hist).slice(-60);
      const vals=labels.map(k=>hist[k]);
      new Chart(document.getElementById('priceChart'), {
        type:'line',
        data:{labels, datasets:[{data:vals, borderColor:'#34c759', backgroundColor:'rgba(52,199,89,.1)', fill:true, tension:.3, pointRadius:0}]},
        options:{responsive:true, plugins:{legend:{display:false}}, scales:{x:{display:false}, y:{grid:{color:'#1e1f23'}}}}
      });
    }catch(e){ c.innerHTML='Chart error '+e; }
  },300);
}

async function pollLive(){
  try{
    const r=await fetch(`/api/stock/${TICK}/live-quote`);
    const j=await r.json();
    if(j.price){
      set('hero-price', `$${Number(j.price).toFixed(2)}`);
      set('s-price', `$${Number(j.price).toFixed(2)}`);
      const chg=Number(j.change||0), pct=Number(j.pct||0);
      set('hero-price-sub', `${chg>=0?'+':''}${chg.toFixed(2)} (${(pct*100).toFixed(2)}% live)`);
      const el=$('s-price-sub'); if(el) el.innerText=`${chg>=0?'+':''}${chg.toFixed(2)} today`;
      el && (el.style.color = chg>=0?'var(--green)':'var(--red)');
    }
  }catch(e){}
}

function applyPreset(which){
  const p={bear:{wacc:11,g15:5,g610:3,term:1.5}, base:{wacc:9,g15:15,g610:10,term:2.5}, bull:{wacc:7.5,g15:20,g610:12,term:3}};
  const v=p[which]; if(!v) return;
  $('wacc').value=v.wacc; $('g15').value=v.g15; $('g610').value=v.g610; $('term').value=v.term;
}
async function recalc(){
  const body={wacc: Number($('wacc').value), growth_1_5: Number($('g15').value), growth_6_10: Number($('g610').value), terminal_growth: Number($('term').value)};
  const r=await fetch(`/api/stock/${TICK}/recalculate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();
  if(j.error){ alert(j.error); return; }
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
