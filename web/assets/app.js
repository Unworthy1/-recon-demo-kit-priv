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

/* ───────── Teams: a collaboration grouping orthogonal to the org-role hierarchy ─────────
   org-role (junior→director) gates access + segregation of duties; a *team* is the function a
   person speaks for in a reconciliation thread. A user can sit on more than one team. */
RECON.teams = [
  {id:"accounting", name:"Accounting",       descr:"Owns the reconciliations — prepares, reviews & approves the close"},
  {id:"treasury",   name:"Treasury",         descr:"Bank relationships, statements, wires & balance confirmations"},
  {id:"audit",      name:"Audit & Controls", descr:"Internal audit / SOX — reviews evidence and attests to controls"},
  {id:"operations", name:"Operations",       descr:"Project & business-unit owners — explain variances, supply WO/PO/invoices"},
];
// existing accountants are Accounting; add cross-functional counterparts so the thread is multi-team
RECON.team.push(
  {name:"Tara V.", init:"TV", role:"senior",    email:"tara.v@meridianpower.example"},
  {name:"Nina O.", init:"NO", role:"principal", email:"nina.o@meridianpower.example"},
  {name:"Glen M.", init:"GM", role:"senior",    email:"glen.m@meridianpower.example"},
);
const _TEAM_OF = {
  "Sam R.":["accounting"], "Priya N.":["accounting"], "Joe B.":["accounting"],
  "Dana P.":["accounting"], "Maria L.":["accounting"], "Robert K.":["accounting","audit"],
  "Tara V.":["treasury"], "Nina O.":["audit"], "Glen M.":["operations"],
};
RECON.team.forEach(t=>{ t.teams = _TEAM_OF[t.name] || ["accounting"]; });
function teamById(id){ return RECON.teams.find(t=>t.id===id) || {id, name:id}; }
function teamLabel(id){ return teamById(id).name; }
function teamsOf(name){ const u=RECON.team.find(t=>t.name===name); return u? (u.teams||["accounting"]) : ["accounting"]; }
function primaryTeam(name){ return teamsOf(name)[0]; }
function membersOf(teamId){ return RECON.team.filter(t=>(t.teams||[]).includes(teamId)); }
const TEAM_COLOR = {accounting:"#185FA5", treasury:"#0E8A6B", audit:"#534AB7", operations:"#C9790B"};
function teamColor(id){ return TEAM_COLOR[id] || "#5A6385"; }

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

/* ───────── Reconciliation discussion thread — multi-team comments, attachments & cross-team requests ─────────
   Client-side only (localStorage) for this showcase. The deployable stack persists every comment to the
   recon_comment table and the immutable audit trail — GET/POST /api/thread/{entity_type}/{entity_id}
   (stack/api/app.py), with the same "request → awaiting <team> → response clears it" semantics. */
const SEED_THREADS = {
  "reconciliation:2020": [
    {id:1, ts:"Jun 2, 09:12", author:"Joe B.", team:"accounting", kind:"comment",
     body:"GL shows -$58,740.21 but the Amex statement is -$61,240.21 — a $2,500 gap. Looks like a late-posted card charge."},
    {id:2, ts:"Jun 2, 09:15", author:"Joe B.", team:"accounting", kind:"request", toTeam:"treasury",
     body:"Can Treasury confirm the May closing balance and send the statement PDF? Want to verify the $2,500 before I book it."},
    {id:3, ts:"Jun 2, 14:40", author:"Tara V.", team:"treasury", kind:"response", resolvesId:2,
     body:"Confirmed — $61,240.21 closing. The $2,500 is a 5/31 fuel charge that posted 6/1. Statement attached.",
     attach:{name:"Amex_May2026_statement.pdf", ref:"DMS-88421"}},
  ],
  "project:PRJ-IT-0526": [
    {id:1, ts:"Jun 3, 10:05", author:"Sam R.", team:"accounting", kind:"comment",
     body:"Allocations tie to $31,050 but the invoice is $31,500 — a $450 variance. Missing a line?"},
    {id:2, ts:"Jun 3, 10:07", author:"Sam R.", team:"accounting", kind:"request", toTeam:"operations",
     body:"Ops — can you confirm the scope on the Managed IT invoice? Which cost center absorbs the extra $450?"},
  ],
};
function _threadKey(etype, eid){ return "or_thread_"+etype+":"+eid; }
function loadThread(etype, eid){
  const k=_threadKey(etype,eid);
  try{ const s=localStorage.getItem(k); if(s) return JSON.parse(s); }catch(e){}
  return (SEED_THREADS[etype+":"+eid]||[]).map(function(c){ return Object.assign({}, c); });
}
function saveThread(etype, eid, list){ try{ localStorage.setItem(_threadKey(etype,eid), JSON.stringify(list)); }catch(e){} }
// open requests = a request with no response that resolves it
function openRequests(list){ return list.filter(function(c){ return c.kind==='request' && !list.some(function(x){ return x.resolvesId===c.id; }); }); }

function _frThreadCss(){
  if(typeof document==='undefined' || document.getElementById('fr-thread-css')) return;
  const s=document.createElement('style'); s.id='fr-thread-css';
  s.textContent=`
  .thread{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin-top:18px;box-shadow:var(--shadow)}
  .thread .th{display:flex;align-items:baseline;gap:10px;margin-bottom:6px;flex-wrap:wrap}
  .thread .th b{font-size:15px;font-weight:700}.thread .th span{font-size:12.5px;color:var(--muted)}
  .await{display:flex;align-items:center;gap:9px;background:#FBF0DA;border:1px solid #F3D9A6;border-radius:11px;padding:9px 13px;margin:12px 0;font-size:13px;color:#8A5A00;font-weight:600}
  .await .dot{width:8px;height:8px;border-radius:50%;background:#C9790B;animation:frPulse 1.6s ease-in-out infinite}
  @keyframes frPulse{0%,100%{opacity:.4}50%{opacity:1}}
  .cmt{display:flex;gap:12px;padding:13px 0;border-top:1px solid var(--line)}
  .cmt .cav{width:36px;height:36px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:12.5px}
  .cmt .cb{flex:1;min-width:0}
  .cmt .cm{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:3px}
  .cmt .cm b{font-size:13.5px;font-weight:700}
  .tbadge{font-size:10.5px;font-weight:700;letter-spacing:.3px;text-transform:uppercase;border-radius:9px;padding:2px 8px;color:#fff}
  .cmt .cm .role{font-size:11.5px;color:var(--muted)}.cmt .cm .when{font-size:11.5px;color:var(--muted);margin-left:auto}
  .cmt .body{font-size:14px;line-height:1.55;color:var(--text)}
  .reqpill{font-size:11px;font-weight:700;border-radius:9px;padding:2px 8px;background:#FBF0DA;color:#8A5A00}
  .reqpill.done{background:#E7F7EE;color:#11823F}
  .attach{display:inline-flex;align-items:center;gap:8px;margin-top:8px;border:1px solid var(--line);border-radius:10px;padding:7px 11px;background:#FAFBFE;font-size:12.5px;font-weight:600;color:var(--text);text-decoration:none}
  .attach .ai{width:24px;height:24px;border-radius:6px;background:#EEF1F8;display:flex;align-items:center;justify-content:center;color:var(--slate);font-size:9px;font-weight:800}
  .respond{margin-left:auto;font-size:12px;font-weight:700;color:var(--pink);background:none;border:none;cursor:pointer}
  .compose{border-top:1px solid var(--line);margin-top:6px;padding-top:15px}
  .compose textarea{width:100%;min-height:64px;border:1px solid var(--line);border-radius:11px;padding:11px 13px;font:inherit;font-size:14px;resize:vertical;box-sizing:border-box}
  .compose textarea:focus{outline:none;border-color:var(--pink);box-shadow:0 0 0 3px rgba(255,45,120,.12)}
  .cbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:11px}
  .cbar select{font:inherit;font-size:13px;font-weight:600;border:1px solid var(--line);border-radius:9px;padding:8px 10px;background:#fff;cursor:pointer}
  .cbar .lbl{font-size:12px;color:var(--muted);font-weight:600}
  .cbar .chipbtn{font:inherit;font-size:13px;font-weight:600;border:1px solid var(--line);border-radius:9px;padding:8px 11px;background:#fff;cursor:pointer;display:inline-flex;align-items:center;gap:6px;color:var(--text)}
  .cbar .chipbtn svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:2}
  .cbar .chipbtn.on{border-color:var(--green);background:var(--greenbg);color:var(--green)}
  .cbar .post{margin-left:auto;font:inherit;font-size:13.5px;font-weight:700;border:none;border-radius:9px;padding:9px 16px;background:var(--grad);color:#fff;cursor:pointer}
  .respctx{font-size:12.5px;color:#8A5A00;background:#FBF0DA;border-radius:9px;padding:7px 11px;margin-top:10px;display:none;align-items:center;gap:8px}
  .respctx.on{display:flex}`;
  document.head.appendChild(s);
}

function renderThread(hostId, etype, eid){
  _frThreadCss();
  const host=document.getElementById(hostId); if(!host) return;
  const list=loadThread(etype, eid);
  const open=openRequests(list);
  const viewer=RECON.viewer, vteams=teamsOf(viewer);

  const awaitBanner = open.map(function(r){
    const mine=vteams.includes(r.toTeam);
    const ask=r.body.length>70?r.body.slice(0,70)+'…':r.body;
    return '<div class="await"><span class="dot"></span>Awaiting <b style="margin:0 3px">'+teamLabel(r.toTeam)+'</b> — '+r.author+' asked: “'+ask+'”'
      + (mine?'<button class="respond" onclick="frRespond(\''+hostId+'\',\''+etype+'\',\''+eid+'\','+r.id+')">Respond &amp; resolve ↩</button>':'')
      + '</div>';
  }).join('');

  const rows=list.map(function(c){
    const u=RECON.team.find(function(t){ return t.name===c.author; });
    const init=u?u.init:initials(c.author), role=u?roleLabel(u.role):'';
    const reqDone = c.kind==='request' && list.some(function(x){ return x.resolvesId===c.id; });
    const tag='<span class="tbadge" style="background:'+teamColor(c.team)+'">'+teamLabel(c.team)+'</span>';
    let kindPill='';
    if(c.kind==='request') kindPill='<span class="reqpill '+(reqDone?'done':'')+'">'+(reqDone?'✓ answered by ':'→ asked ')+teamLabel(c.toTeam)+'</span>';
    if(c.kind==='response' && c.resolvesId) kindPill='<span class="reqpill done">✓ resolved request</span>';
    const attach=c.attach?'<a class="attach" href="documents.html" onclick="return false"><span class="ai">PDF</span>'+c.attach.name+(c.attach.ref?' · '+c.attach.ref:'')+'</a>':'';
    return '<div class="cmt">'
      + '<div class="cav" style="background:'+teamColor(c.team)+'">'+init+'</div>'
      + '<div class="cb">'
      + '<div class="cm"><b>'+c.author+'</b>'+tag+'<span class="role">'+role+'</span>'+kindPill+'<span class="when">'+c.ts+'</span></div>'
      + '<div class="body">'+c.body+'</div>'+attach
      + '</div></div>';
  }).join('');

  const postAsSel = vteams.length>1
    ? '<span class="lbl">as</span><select id="cm-team">'+vteams.map(function(t){ return '<option value="'+t+'">'+teamLabel(t)+'</option>'; }).join('')+'</select>'
    : '<input type="hidden" id="cm-team" value="'+vteams[0]+'">';
  const otherTeams=RECON.teams.filter(function(t){ return !vteams.includes(t.id); });
  const reqSel='<span class="lbl">request from</span><select id="cm-to"><option value="">— no one —</option>'+otherTeams.map(function(t){ return '<option value="'+t.id+'">'+t.name+'</option>'; }).join('')+'</select>';

  const emptyMsg='<p class="note" style="color:var(--muted);font-size:13.5px;padding:10px 0">No comments yet — start the conversation.</p>';
  host.innerHTML='<div class="thread">'
    + '<div class="th"><b>Discussion</b><span>multi-team thread on this reconciliation — comments, attachments &amp; cross-team requests · audited</span></div>'
    + awaitBanner
    + '<div id="cmts">'+(rows||emptyMsg)+'</div>'
    + '<div class="compose">'
    + '<div class="respctx" id="respctx"></div>'
    + '<textarea id="cm-body" placeholder="Add a comment, or request something from another team…"></textarea>'
    + '<div class="cbar">'
    + postAsSel + reqSel
    + '<button class="chipbtn" id="cm-attach" onclick="frToggleAttach()"><svg viewBox="0 0 24 24"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.2-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>Attach</button>'
    + '<button class="post" onclick="frPostComment(\''+hostId+'\',\''+etype+'\',\''+eid+'\')">Post</button>'
    + '</div></div></div>';
}
let _frAttach=null, _frRespondTo=null;
function frToggleAttach(){
  const b=document.getElementById('cm-attach');
  if(_frAttach){ _frAttach=null; b.classList.remove('on'); b.lastChild.textContent='Attach'; return; }
  const name=(prompt('Attachment filename','supporting_document.pdf')||'').trim();
  if(!name) return;
  _frAttach={name:name, ref:'DMS-'+Math.floor(10000+Math.random()*89999)};
  b.classList.add('on'); b.lastChild.textContent=name.length>18?name.slice(0,18)+'…':name;
}
function frRespond(hostId, etype, eid, reqId){
  _frRespondTo=reqId;
  const list=loadThread(etype,eid), r=list.find(function(c){ return c.id===reqId; });
  const ctx=document.getElementById('respctx');
  if(ctx){ ctx.classList.add('on'); ctx.innerHTML='↩ Responding to '+(r?r.author:'')+': “'+(r?r.body.slice(0,60):'')+'…” — your reply will clear the wait. <button class="respond" style="margin-left:auto" onclick="frCancelRespond()">cancel</button>'; }
  const ta=document.getElementById('cm-body'); if(ta) ta.focus();
}
function frCancelRespond(){ _frRespondTo=null; const ctx=document.getElementById('respctx'); if(ctx){ctx.classList.remove('on');ctx.innerHTML='';} }
function frPostComment(hostId, etype, eid){
  const ta=document.getElementById('cm-body'); const body=(ta.value||'').trim();
  if(!body){ ta.focus(); return; }
  const team=document.getElementById('cm-team').value;
  const toTeam=document.getElementById('cm-to').value;
  const list=loadThread(etype, eid);
  const nid=(list.reduce(function(m,c){ return Math.max(m,c.id); },0)||0)+1;
  const ts=new Date().toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
  const c={id:nid, ts:ts, author:RECON.viewer, team:team, body:body, kind:'comment'};
  if(_frRespondTo){ c.kind='response'; c.resolvesId=_frRespondTo; }
  else if(toTeam){ c.kind='request'; c.toTeam=toTeam; }
  if(_frAttach) c.attach=_frAttach;
  list.push(c); saveThread(etype, eid, list);
  _frAttach=null; _frRespondTo=null;
  renderThread(hostId, etype, eid);
}
if(typeof window!=='undefined'){ window.renderThread=renderThread; window.frPostComment=frPostComment; window.frToggleAttach=frToggleAttach; window.frRespond=frRespond; window.frCancelRespond=frCancelRespond; }
