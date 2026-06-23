/* FERC range -> Project / expense type — UI port of ferc/classifier.py (electric USoA default).
   Lets the project pages derive each account's functional Project live from its FERC number. */
const FERC_RANGES = [
  [101,101,"Plant in service (control)","Capital"],
  [105,105,"Plant held for future use","Capital"],
  [106,107,"CWIP — capital projects","Capital"],
  [108,115,"Accumulated depreciation & plant adj","Capital"],
  [151,174,"Materials, inventory & current assets","Balance sheet"],
  [181,191,"Deferred debits / regulatory assets","Balance sheet"],
  [201,253,"Liabilities & equity","Balance sheet"],
  [301,303,"Intangible plant","Capital"],
  [310,347,"Production plant","Capital"],
  [350,359,"Transmission plant","Capital"],
  [360,374,"Distribution plant","Capital"],
  [380,388,"Regional transmission & market plant","Capital"],
  [389,399,"General plant","Capital"],
  [400,432,"Income accounts","Income"],
  [440,457,"Operating revenues","Revenue"],
  [500,557,"Production O&M","O&M"],
  [560,576,"Transmission O&M","O&M"],
  [580,598,"Distribution O&M","O&M"],
  [901,905,"Customer accounts","O&M"],
  [907,910,"Customer service & information","O&M"],
  [911,917,"Sales","O&M"],
  [920,935,"Administrative & general (A&G)","O&M"],
];
function fercNumber(code){
  const m = String(code).match(/(?<!\d)(\d{3})(?!\d)/);
  if(!m) return null;
  const n = +m[1];
  return (n>=100 && n<=999) ? n : null;
}
function fercClassify(code){
  const n = fercNumber(code);
  if(n!==null){ for(const [lo,hi,proj,et] of FERC_RANGES){ if(n>=lo && n<=hi) return {ferc:n, project:proj, expense_type:et}; } }
  return {ferc:n, project:"Unmapped — review", expense_type:""};
}
function fercProject(code){ return fercClassify(code).project; }
