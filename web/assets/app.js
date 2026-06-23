/* OpenRecon showcase — shared data + helpers (no backend; all client-side) */
const RECON = {
  period: "May 2026 close",
  asOf: "as of May 31, 2026",
  currentUser: "Joe B.",
  // representative slice of a much larger book (see scale stats on the landing page)
  accounts: [
    {id:"1010", grp:"Cash & equivalents", name:"Operating cash — Wells Fargo", code:"1010", mask:"••4471", bank:"Wells Fargo", dot:"#D71E2B", gl:2840114.22, stmt:2840114.22, status:"reconciled", assigned:"Joe B.", work:"resolved", as_of:"2026-05-31", tol:25, ocr_acct:"…4471", ocr_date:"2026-05-31"},
    {id:"1020", grp:"Cash & equivalents", name:"Payroll cash — Chase", code:"1020", mask:"••8810", bank:"JPMorgan Chase", dot:"#117ACA", gl:486220.00, stmt:483220.00, status:"variance", assigned:"Joe B.", work:"progress", as_of:"2026-05-31", tol:50, ocr_acct:"…8810", ocr_date:"2026-05-31"},
    {id:"1030", grp:"Cash & equivalents", name:"Money market — Fidelity", code:"1030", mask:"••2093", bank:"Fidelity", dot:"#3A7D44", gl:1200000.00, stmt:1200000.00, status:"reconciled", assigned:"Dana P.", work:"resolved", as_of:"2026-05-31", tol:25, ocr_acct:"…2093", ocr_date:"2026-05-31"},
    {id:"1040", grp:"Cash & equivalents", name:"FBO escrow — Mercury", code:"1040", mask:"••5567", bank:"Mercury", dot:"#5B3DF5", gl:75500.00, stmt:null, status:"unreconciled", assigned:"Sam R.", work:"assigned", as_of:"2026-05-31", tol:25, ocr_acct:null, ocr_date:null},

    {id:"1210", grp:"Accounts receivable", name:"Trade AR — domestic", code:"1210", mask:"sub-ledger", bank:"AR aging", dot:"#11A150", gl:1894220.10, stmt:1894220.10, status:"reconciled", assigned:"Dana P.", work:"resolved", as_of:"2026-05-31", tol:100, ocr_acct:"AR-DOM", ocr_date:"2026-05-31"},
    {id:"1220", grp:"Accounts receivable", name:"Trade AR — international", code:"1220", mask:"sub-ledger", bank:"AR aging", dot:"#11A150", gl:642118.55, stmt:648618.55, status:"variance", assigned:"Dana P.", work:"ack", as_of:"2026-05-31", tol:100, ocr_acct:"AR-INTL", ocr_date:"2026-05-31"},
    {id:"1250", grp:"Accounts receivable", name:"Credit-card clearing — Stripe", code:"1250", mask:"••0091", bank:"Stripe", dot:"#635BFF", gl:118402.33, stmt:118402.33, status:"reconciled", assigned:"Joe B.", work:"resolved", as_of:"2026-05-31", tol:25, ocr_acct:"…0091", ocr_date:"2026-05-31"},

    {id:"1410", grp:"Prepaid & other assets", name:"Prepaid insurance", code:"1410", mask:"schedule", bank:"Amortization", dot:"#5A6385", gl:88333.34, stmt:88333.34, status:"reconciled", assigned:"Sam R.", work:"resolved", as_of:"2026-05-31", tol:10, ocr_acct:"PPD-INS", ocr_date:"2026-05-31"},
    {id:"1420", grp:"Prepaid & other assets", name:"Prepaid software (SaaS)", code:"1420", mask:"schedule", bank:"Amortization", dot:"#5A6385", gl:46210.00, stmt:null, status:"unreconciled", assigned:"Sam R.", work:"assigned", as_of:"2026-05-31", tol:10, ocr_acct:null, ocr_date:null},

    {id:"2010", grp:"Accounts payable", name:"Trade AP — domestic", code:"2010", mask:"sub-ledger", bank:"AP aging", dot:"#E0413F", gl:-934118.00, stmt:-934118.00, status:"reconciled", assigned:"Dana P.", work:"resolved", as_of:"2026-05-31", tol:100, ocr_acct:"AP-DOM", ocr_date:"2026-05-31"},
    {id:"2020", grp:"Accounts payable", name:"Corporate cards — Amex", code:"2020", mask:"••3008", bank:"American Express", dot:"#2671B9", gl:-58740.21, stmt:-61240.21, status:"variance", assigned:"Joe B.", work:"progress", as_of:"2026-05-31", tol:50, ocr_acct:"…3008", ocr_date:"2026-05-31"},

    {id:"2310", grp:"Accrued liabilities", name:"Accrued payroll", code:"2310", mask:"schedule", bank:"Payroll accrual", dot:"#C9790B", gl:-212004.00, stmt:-212004.00, status:"reconciled", assigned:"Joe B.", work:"resolved", as_of:"2026-05-31", tol:50, ocr_acct:"ACR-PAY", ocr_date:"2026-05-31"},
    {id:"2320", grp:"Accrued liabilities", name:"Accrued sales tax", code:"2320", mask:"schedule", bank:"Tax accrual", dot:"#C9790B", gl:-77410.50, stmt:-77410.50, status:"reconciled", assigned:"Sam R.", work:"resolved", as_of:"2026-05-31", tol:25, ocr_acct:"ACR-TAX", ocr_date:"2026-05-31"},

    {id:"2710", grp:"Intercompany", name:"Due to/from — UK subsidiary", code:"2710", mask:"IC ledger", bank:"Intercompany", dot:"#8B2FF6", gl:412900.00, stmt:401400.00, status:"variance", assigned:"Dana P.", work:"ack", as_of:"2026-05-31", tol:100, ocr_acct:"IC-UK", ocr_date:"2026-05-31"},
    {id:"2720", grp:"Intercompany", name:"Due to/from — Canada subsidiary", code:"2720", mask:"IC ledger", bank:"Intercompany", dot:"#8B2FF6", gl:96120.00, stmt:96120.00, status:"reconciled", assigned:"Joe B.", work:"resolved", as_of:"2026-05-31", tol:100, ocr_acct:"IC-CA", ocr_date:"2026-05-31"}
  ],
  // people for the director dashboard — email drives send-back notifications (demo domain, .example is reserved/never real)
  team:[
    {name:"Sam R.", init:"SR", role:"junior", email:"sam.r@meridianpower.example"},
    {name:"Priya N.", init:"PN", role:"junior", email:"priya.n@meridianpower.example"},
    {name:"Joe B.", init:"JB", role:"senior", email:"joe.b@meridianpower.example"},
    {name:"Dana P.", init:"DP", role:"senior", email:"dana.p@meridianpower.example"},
    {name:"Maria L.", init:"ML", role:"principal", email:"maria.l@meridianpower.example"},
    {name:"Robert K.", init:"RK", role:"director", email:"robert.k@meridianpower.example"}
  ]
};

RECON.accounts.forEach(a=>{ a.variance = (a.stmt===null) ? null : Math.round((a.gl - a.stmt)*100)/100; });

/* ---- project reconciliations: one supporting document settles many FERC accounts ----
   (one expense allocated across accounts; the lines must tie to the source within tolerance) */
RECON.projects = [
  {id:"PRJ-TX4471", name:"Substation 7 transmission upgrade", wo:"WO# TX-4471", assigned:"Joe B.", work:"progress", period:"May 2026", tol:100,
   source:{amount:2412800.00, vendor:"Burns & McDonnell", doc:"EPC_invoice_TX-4471.pdf", doc_ref:"INV-TX-4471"},
   lines:[
     {code:"352", name:"Structures & improvements", allocated:412800.00},
     {code:"353", name:"Station equipment", allocated:1480000.00},
     {code:"355", name:"Poles & fixtures", allocated:240000.00},
     {code:"356", name:"Overhead conductors & devices", allocated:280000.00},
   ]},
  {id:"PRJ-FUEL-0526", name:"Fleet fuel — May allocation", wo:"Alloc# FUEL-0526", assigned:"Dana P.", work:"ack", period:"May 2026", tol:100,
   source:{amount:48250.00, vendor:"Regional Fuel Co.", doc:"fuel_invoice_May2026.pdf", doc_ref:"INV-FUEL-0526"},
   lines:[
     {code:"560", name:"Transmission — operation supervision", allocated:14200.00},
     {code:"580", name:"Distribution — operation supervision", allocated:22050.00},
     {code:"588", name:"Distribution — miscellaneous expenses", allocated:6000.00},
     {code:"920", name:"Administrative & general salaries", allocated:6000.00},
   ]},
  {id:"PRJ-IT-0526", name:"IT shared services — May", wo:"Alloc# IT-0526", assigned:"Sam R.", work:"assigned", period:"May 2026", tol:100,
   source:{amount:31500.00, vendor:"Managed IT Partners", doc:"it_services_invoice_May.pdf", doc_ref:"INV-IT-0526"},
   lines:[
     {code:"921", name:"Office supplies & expenses", allocated:12000.00},
     {code:"923", name:"Outside services employed", allocated:14250.00},
     {code:"935", name:"Maintenance of general plant", allocated:4800.00},
   ]},  // ties to 31,050 vs 31,500 source -> $450 variance (exception)
];
function projectSummary(p){
  const allocated = Math.round(p.lines.reduce((s,l)=>s+l.allocated,0)*100)/100;
  const variance = Math.round((p.source.amount - allocated)*100)/100;
  const status = Math.abs(variance) <= p.tol ? "tied" : "variance";
  const functions = (typeof fercProject==="function") ? [...new Set(p.lines.map(l=>fercProject(l.code)))] : [];
  return {allocated, variance, status, accounts:p.lines.length, functions};
}
function projectKpis(){
  const P=RECON.projects;
  const tied = P.filter(p=>projectSummary(p).status==="tied").length;
  return {count:P.length, tied, variance:P.length-tied,
          total:P.reduce((s,p)=>s+p.source.amount,0),
          accounts:P.reduce((s,p)=>s+p.lines.length,0)};
}

/* ---- year-end / close periods: monthly, quarterly, annual; lock when closed ---- */
RECON.fiscalYear = "FY 2026";
RECON.periods = [
  {key:"2026-01", label:"January 2026", type:"monthly", status:"locked", closed_by:"Dana P.", closed:"2026-02-05"},
  {key:"2026-02", label:"February 2026", type:"monthly", status:"locked", closed_by:"Dana P.", closed:"2026-03-05"},
  {key:"2026-03", label:"March 2026", type:"monthly", status:"locked", closed_by:"Joe B.", closed:"2026-04-06"},
  {key:"2026-04", label:"April 2026", type:"monthly", status:"locked", closed_by:"Joe B.", closed:"2026-05-05"},
  {key:"2026-05", label:"May 2026", type:"monthly", status:"open", progress:60},
  {key:"2026-Q1", label:"Q1 2026 (Jan–Mar)", type:"quarterly", status:"locked", closed_by:"Sam R.", closed:"2026-04-10"},
  {key:"2026-Q2", label:"Q2 2026 (Apr–Jun)", type:"quarterly", status:"open", progress:33},
  {key:"2026-FY", label:"FY 2026 — annual close", type:"annual", status:"open", progress:62},
];
function periodKpis(){
  const P=RECON.periods;
  return {total:P.length, locked:P.filter(p=>p.status==='locked').length, open:P.filter(p=>p.status==='open').length,
          annual:P.find(p=>p.type==='annual')};
}

/* ---- year-end roll-forward (continuity): opening + activity = closing, then tie to evidence ---- */
RECON.rollforward = [
  {code:"101", name:"Electric plant in service", opening:842000000, activity:2412800, evidence:844412800},
  {code:"107", name:"Construction work in progress (CWIP)", opening:18400000, activity:-2412800, evidence:15987200},
  {code:"108", name:"Accumulated depreciation", opening:-310000000, activity:-28500000, evidence:-338500000},
  {code:"232", name:"Long-term debt", opening:-420000000, activity:0, evidence:-420000000},
  {code:"216", name:"Retained earnings", opening:-95000000, activity:-12400000, evidence:-107000000},
];
RECON.rollforward.forEach(r=>{ r.closing = Math.round((r.opening+r.activity)*100)/100; r.tie = Math.round((r.closing - r.evidence)*100)/100; });
const ROLLFWD_TOL = 1000;  // $1k tolerance at year-end (utility-scale balances)
function rollforwardSummary(){
  const R=RECON.rollforward;
  const tied = R.filter(r=>Math.abs(r.tie)<=ROLLFWD_TOL).length;
  return {count:R.length, tied, variance:R.length-tied, tol:ROLLFWD_TOL,
          closing:R.reduce((s,r)=>s+r.closing,0)};
}

/* ---- RBAC: org-role hierarchy (access) + workflow-role capabilities (assignment) ---- */
RECON.roles = [
  {key:"junior",    label:"Junior Accountant",  tier:1},
  {key:"senior",    label:"Senior Accountant",  tier:2},
  {key:"principal", label:"Principal Accountant",tier:3},
  {key:"director",  label:"Manager / Director",  tier:4},
];
// which org roles may hold each workflow role (configurable — this is the org's policy).
// Default: anyone prepares; seniors+ approve OTHERS' work; only principals/directors review.
RECON.capabilities = {
  prepare: ["junior","senior","principal","director"],
  approve: ["senior","principal","director"],
  review:  ["principal","director"],
};
function roleKey(name){ const u=RECON.team.find(t=>t.name===name); return u?u.role:"senior"; }
function emailOf(name){ const u=RECON.team.find(t=>t.name===name); return u&&u.email ? u.email
  : (String(name||'user').toLowerCase().replace(/[^a-z]+/g,'.').replace(/(^\.|\.$)/g,'')||'user')+"@meridianpower.example"; }
function roleLabel(key){ const r=RECON.roles.find(x=>x.key===key); return r?r.label:key; }
function tierOf(key){ const r=RECON.roles.find(x=>x.key===key); return r?r.tier:0; }
function can(role, action){ return (RECON.capabilities[action]||[]).includes(role); }
// segregation of duties: an item's approver is a DIFFERENT person whose tier >= the preparer's
function approverFor(item){
  const prep = item.assigned, pt = tierOf(roleKey(prep));
  const cands = RECON.team.filter(t=>t.name!==prep && can(t.role,'approve') && tierOf(t.role)>=pt);
  const pool = cands.length ? cands : RECON.team.filter(t=>can(t.role,'approve'));
  const n = parseInt(String(item.id).replace(/\D/g,''))||0;
  return (pool[n%pool.length]||RECON.team[0]).name;
}
function reviewerFor(item){ return (RECON.team.find(t=>t.role==='director')||RECON.team.find(t=>t.role==='principal')).name; }
function workloadFor(name){
  const prepares = RECON.accounts.filter(a=>a.assigned===name).length + RECON.projects.filter(p=>p.assigned===name).length;
  const approves = RECON.accounts.filter(a=>approverFor(a)===name).length;
  const reviews  = can(roleKey(name),'review') ? RECON.accounts.length + RECON.projects.length : 0;
  return {prepares, approves, reviews};
}
/* "viewing as" — the effective current user; gates actions on the detail pages */
RECON.viewer = (typeof localStorage!=='undefined' && localStorage.getItem('fr_viewer')) || RECON.currentUser;
function setViewer(name){ RECON.viewer = name; try{ localStorage.setItem('fr_viewer', name); }catch(e){} }
function viewerRole(){ return roleKey(RECON.viewer); }

/* per-account review decision by the approver: pending | approved | sent_back */
const REVIEW_LABELS = {pending:"Pending review", approved:"Approved", sent_back:"Sent back"};
const _sentBack=["1220"], _awaitingApproval=["1030","2320"];
RECON.accounts.forEach(a=>{
  a.review = _sentBack.includes(a.id) ? 'sent_back'
           : (a.work==='resolved' ? (_awaitingApproval.includes(a.id) ? 'pending' : 'approved') : 'pending');
});
function prepStats(name){
  const mine = RECON.accounts.filter(a=>a.assigned===name);
  return {assigned:mine.length, prepared:mine.filter(a=>a.work==='resolved').length, accounts:mine};
}
function reviewStats(name){
  const q = RECON.accounts.filter(a=>approverFor(a)===name);
  return {queue:q.length, approved:q.filter(a=>a.review==='approved').length,
          sent_back:q.filter(a=>a.review==='sent_back').length,
          pending:q.filter(a=>a.review==='pending').length, accounts:q};
}

/* ───────── Email notifications — alert the preparer when an account is sent back ─────────
   Demographics carry an email (RECON.team[].email). When a reviewer sends an account back,
   the assigned preparer is notified by email. In this static showcase the email is composed
   and "dispatched" visibly (a preview/compose modal + a confirmation toast); the deployable
   stack actually sends it over SMTP (stack/api/notify.py + POST /api/account/{id}/send-back). */
const FR_PERIOD_LABEL = "May 2026";
function _frNotifyCss(){
  if(typeof document==='undefined' || document.getElementById('fr-notify-css')) return;
  const s=document.createElement('style'); s.id='fr-notify-css';
  s.textContent=`
  .fr-ov{position:fixed;inset:0;background:rgba(14,19,48,.55);display:flex;align-items:center;justify-content:center;z-index:60;padding:20px}
  .fr-modal{background:#fff;border-radius:16px;max-width:560px;width:100%;box-shadow:0 24px 60px rgba(14,19,48,.4);overflow:hidden;font-size:14px}
  .fr-modal .mh{padding:16px 20px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:11px}
  .fr-modal .mh .em{width:34px;height:34px;border-radius:9px;background:var(--grad);display:flex;align-items:center;justify-content:center;font-size:17px;color:#fff}
  .fr-modal .mh b{font-size:15px;display:block} .fr-modal .mh span{font-size:12px;color:var(--muted)}
  .fr-mail{margin:16px 20px;border:1px solid var(--line);border-radius:11px;overflow:hidden}
  .fr-mail .hdr{padding:11px 14px;background:#F6F8FC;border-bottom:1px solid var(--line);font-size:12.5px;line-height:1.7}
  .fr-mail .hdr b{color:var(--muted);font-weight:600} .fr-mail .hdr .to{color:var(--text);font-weight:600}
  .fr-mail .bdy{padding:14px;color:var(--text);line-height:1.55;white-space:pre-wrap}
  .fr-rsn{margin:0 20px 14px;display:block}
  .fr-rsn label{font-size:12px;font-weight:600;color:var(--muted);display:block;margin-bottom:5px}
  .fr-rsn textarea{width:100%;min-height:62px;border:1px solid var(--line);border-radius:9px;padding:9px 11px;font:inherit;font-size:13.5px;resize:vertical;box-sizing:border-box}
  .fr-mf{padding:14px 20px;border-top:1px solid var(--line);display:flex;gap:10px;justify-content:flex-end;align-items:center}
  .fr-mf .gh{margin-right:auto;font-size:12px;color:var(--muted)}
  .fr-b{font:inherit;font-size:13.5px;font-weight:700;border-radius:9px;padding:9px 15px;cursor:pointer;border:1px solid var(--line);background:#fff;color:var(--text)}
  .fr-b.pri{border:none;background:var(--grad);color:#fff}
  .fr-toast{position:fixed;right:20px;bottom:20px;z-index:70;background:#fff;border:1px solid var(--line);border-left:4px solid #11A150;border-radius:12px;box-shadow:0 14px 40px rgba(14,19,48,.25);padding:13px 16px;font-size:13.5px;max-width:360px;display:flex;gap:11px;align-items:flex-start;animation:frIn .25s ease}
  .fr-toast .ti{font-size:18px;line-height:1.1} .fr-toast b{display:block;margin-bottom:2px}
  .fr-toast .tm{color:var(--muted);font-size:12.5px}
  @keyframes frIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}`;
  document.head.appendChild(s);
}
function frToast(title, msg){
  _frNotifyCss();
  const t=document.createElement('div'); t.className='fr-toast';
  t.innerHTML=`<div class="ti">📧</div><div><b>${title}</b><div class="tm">${msg}</div></div>`;
  document.body.appendChild(t);
  setTimeout(()=>{ t.style.transition='opacity .4s'; t.style.opacity='0'; setTimeout(()=>t.remove(),400); }, 5200);
}
// Compose the send-back notification email for an account (recipient = its preparer).
function sendBackEmail(acct, reviewer){
  const prep=acct.assigned, code=acct.code||acct.id, nm=acct.name||'';
  return {
    toName:prep, to:emailOf(prep), fromName:reviewer, from:emailOf(reviewer),
    subject:`[OpenRecon] Account ${code} — ${nm}: sent back for rework (${FR_PERIOD_LABEL})`,
    greeting:`Hi ${prep},`,
    line:`${reviewer} has sent account ${code} — ${nm} back to you for rework as part of the ${FR_PERIOD_LABEL} close.`,
    cta:`Open it in OpenRecon → account.html?id=${acct.id}`,
  };
}
// Open the send-back composer; on confirm, toast the dispatch and call onSend(reason).
function notifySendBack(acct, reviewer, onSend){
  _frNotifyCss();
  const m=sendBackEmail(acct, reviewer);
  const ov=document.createElement('div'); ov.className='fr-ov';
  ov.innerHTML=`<div class="fr-modal" role="dialog" aria-label="Send back and notify">
    <div class="mh"><div class="em">↩</div><div><b>Send back &amp; notify ${m.toName}</b><span>an email goes to the preparer when you send this back</span></div></div>
    <div class="fr-mail">
      <div class="hdr">
        <div><b>To</b> &nbsp;<span class="to">${m.toName} &lt;${m.to}&gt;</span></div>
        <div><b>From</b> &nbsp;${m.fromName} &lt;${m.from}&gt; · OpenRecon notifications</div>
        <div><b>Subject</b> &nbsp;${m.subject}</div>
      </div>
      <div class="bdy">${m.greeting}\n\n${m.line}\n\n${m.cta}</div>
    </div>
    <div class="fr-rsn"><label>Reason for rework (added to the email)</label><textarea id="fr-reason" placeholder="e.g. Supporting wire confirmation is missing — please attach and re-submit."></textarea></div>
    <div class="fr-mf"><span class="gh">🔒 Sent to the address on file · ${m.to}</span>
      <button class="fr-b" id="fr-cancel">Cancel</button>
      <button class="fr-b pri" id="fr-send">Send back &amp; notify</button></div>
  </div>`;
  document.body.appendChild(ov);
  const close=()=>ov.remove();
  ov.addEventListener('click', e=>{ if(e.target===ov) close(); });
  ov.querySelector('#fr-cancel').onclick=close;
  ov.querySelector('#fr-send').onclick=()=>{
    const reason=(ov.querySelector('#fr-reason').value||'').trim();
    close();
    frToast(`Email sent to ${m.toName}`, `${m.to} — account ${acct.code||acct.id} sent back for rework`);
    if(typeof onSend==='function') onSend(reason);
  };
}

const WORK_LABELS = {ack:"Acknowledged", assigned:"Assigned", progress:"In progress", resolved:"Resolved"};

function money(n){
  if(n===null||n===undefined) return "—";
  const neg = n<0; const v = Math.abs(n).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
  return (neg?"-$":"$")+v;
}
function kpis(){
  const A=RECON.accounts;
  const inScope=A.length;
  const reconciled=A.filter(a=>a.status==='reconciled').length;
  const variance=A.filter(a=>a.status==='variance').length;
  const unreconciled=A.filter(a=>a.status==='unreconciled').length;
  const varTotal=A.filter(a=>a.status==='variance').reduce((s,a)=>s+Math.abs(a.variance),0);
  return {inScope,reconciled,variance,unreconciled,varTotal,
    progress:Math.round(reconciled/inScope*100),
    exceptions:variance+unreconciled};
}

/* shared navy sidebar — `active` = page key */
function renderSidebar(active){
  const k=kpis();
  const item=(key,href,label,svg,badge)=>`<a class="${active===key?'on':''}" href="${href}">${svg}${label}${badge?`<span class="badge">${badge}</span>`:''}</a>`;
  const html=`
  <a class="brand" href="index.html"><div class="mark">OR</div><div><div class="nm">OpenRecon</div><div class="sub">FINANCIAL CLOSE</div></div></a>
  <nav class="nav">
    ${item('home','home.html','My dashboard','<svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/></svg>')}
    ${item('overview','workspace.html','Overview','<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>')}
    ${item('exceptions','workspace.html?f=exceptions','Exceptions','<svg viewBox="0 0 24 24"><path d="M12 9v4m0 4h.01M10.3 4.3 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0Z"/></svg>',k.exceptions)}
    ${item('docs','documents.html','Documents','<svg viewBox="0 0 24 24"><path d="M14 3v5h5M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-5Z"/></svg>')}
    ${item('accounts','workspace.html','Accounts','<svg viewBox="0 0 24 24"><path d="M3 3v18h18M8 16l3.5-4 3 2.5L20 8"/></svg>')}
    ${item('projects','projects.html','Projects','<svg viewBox="0 0 24 24"><path d="M3 7l9-4 9 4-9 4-9-4Z"/><path d="M3 12l9 4 9-4M3 17l9 4 9-4"/></svg>')}
    ${item('periods','periods.html','Year-end close','<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>')}
    ${item('audit','audit.html','Audit package','<svg viewBox="0 0 24 24"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>')}
    <div class="navsep"></div>
    ${item('team','team.html','Team & roles','<svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>')}
    ${item('dashboard','dashboard.html','Director dashboard','<svg viewBox="0 0 24 24"><path d="M4 4h16v12H4zM2 20h20M9 8v4m3-6v6m3-3v3"/></svg>')}
    ${item('how','how-it-works.html','How it works','<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 16v-4m0-4h.01"/></svg>')}
  </nav>
  <div class="who"><div class="av">${initials(RECON.viewer)}</div><div><div class="nm">${RECON.viewer}</div><div class="rl">${roleLabel(viewerRole())}</div></div></div>`;
  const el=document.getElementById('side'); if(el) el.innerHTML=html;
  _mountMobileNav();
}
// mobile: a top bar with a hamburger that slides the sidebar in as an off-canvas drawer
function _mountMobileNav(){
  if(typeof document==='undefined' || document.getElementById('mobtop')) return;
  const bar=document.createElement('div'); bar.className='mobtop'; bar.id='mobtop';
  bar.innerHTML=`<button class="mobburger" aria-label="Open menu" onclick="toggleSidebar()"><svg viewBox="0 0 24 24"><path d="M3 6h18M3 12h18M3 18h18"/></svg></button>`
    +`<a class="mobbrand" href="index.html"><span class="mark">OR</span><b>OpenRecon</b></a>`;
  const bd=document.createElement('div'); bd.className='mobbd'; bd.id='mobbd'; bd.onclick=closeSidebar;
  document.body.insertBefore(bar, document.body.firstChild);
  document.body.appendChild(bd);
  const side=document.getElementById('side');
  if(side) side.addEventListener('click', e=>{ if(e.target.closest('a')) closeSidebar(); });
}
function toggleSidebar(){ document.getElementById('side')?.classList.toggle('open'); document.getElementById('mobbd')?.classList.toggle('on'); }
function closeSidebar(){ document.getElementById('side')?.classList.remove('open'); document.getElementById('mobbd')?.classList.remove('on'); }
if(typeof window!=='undefined'){ window.toggleSidebar=toggleSidebar; window.closeSidebar=closeSidebar; }
function initials(n){return n.split(' ').map(x=>x[0]).join('').slice(0,2).toUpperCase();}

/* derive the document repository (faux Paperless / Laserfiche) from the dataset */
function buildDocuments(){
  const docs=[];
  RECON.accounts.forEach(a=>{
    const nid = parseInt(a.id,10)||0;
    if(a.stmt!==null){
      docs.push({
        id:"STMT-"+a.id, kind:"statement", type:"Bank statement",
        title:a.bank+" — statement — May 2026",
        correspondent:a.bank, acctId:a.id, acctName:a.name, acctMask:a.mask, grp:a.grp,
        created:"2026-06-01", asn:100000+nid, pages:2,
        tags:["Bank statement", a.grp], balance:a.stmt,
        ocr_acct:a.ocr_acct, ocr_date:a.ocr_date
      });
    }
    if(a.status==='variance'){
      docs.push({
        id:"SUP-"+a.id, kind:"support", type:"Supporting document",
        title:"Treasury wire confirmation — ref #88"+a.id,
        correspondent:"Treasury ops", acctId:a.id, acctName:a.name, acctMask:a.mask, grp:a.grp,
        created:"2026-06-02", asn:200000+nid, pages:1,
        tags:["Supporting", "Wire confirmation"], amount:Math.abs(a.variance)
      });
    }
  });
  return docs;
}
