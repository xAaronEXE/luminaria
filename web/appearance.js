/* Semantic appearance tokens. Loaded synchronously in <head> so the saved look applies before first paint.
   CSS reads the custom properties; the spatial renderer receives the same values through `studio-appearance`. */
(()=>{
 const BASE={
  dark:{bg:'#000000',sidebar:'#050505',panel:'#0A0A0A',raised:'#141414',hover:'#1D1D1D',line:'#2A2A2A','control-line':'#5C5C5C',text:'#F5F5F2',muted:'#C2C2BD',dim:'#9E9E99',
   success:'#86D9A3',warning:'#EBC57E',danger:'#F59D94',info:'#9CC0F2',entity:'#F5F5F2',lattice:'#8A8A86',pathway:'#B4B4AF',particle:'#FFFFFF',glow:'#ECECE7'},
  light:{bg:'#FFFFFF',sidebar:'#F7F7F5',panel:'#FCFCFB',raised:'#F0F0ED',hover:'#E6E6E2',line:'#D5D5D0','control-line':'#85857F',text:'#0A0A0A',muted:'#3A3A37',dim:'#575753',
   success:'#1C6A38',warning:'#7A5200',danger:'#A3242C',info:'#1D4D94',entity:'#0A0A0A',lattice:'#7A7A75',pathway:'#4E4E4A',particle:'#000000',glow:'#1A1A1A'}
 };
 const EDITABLE=[
  ['Surfaces',[['bg','Background'],['sidebar','Sidebar'],['panel','Panels and composer'],['raised','Raised controls'],['hover','Hover'],['line','Borders'],['control-line','Field borders']]],
  ['Text',[['text','Primary text'],['muted','Secondary text'],['dim','Tertiary text']]],
  ['States',[['success','Success'],['warning','Warning'],['danger','Error'],['info','Information']]],
  ['Spatial workspace',[['entity','Entity'],['particle','Particles'],['lattice','Lattice'],['pathway','Pathways'],['glow','Lighting']]]
 ];
 const KEYS=new Set(EDITABLE.flatMap(([,items])=>items.map(([k])=>k)));
 const DEFAULT={mode:'light',accent:'',modes:{dark:{},light:{}},version:1};
 const hex=v=>typeof v==='string'&&/^#[0-9a-f]{6}$/i.test(v);
 const rgb=h=>h.slice(1,7).match(/../g).map(x=>parseInt(x,16));
 const toHex=a=>'#'+a.map(v=>Math.round(Math.max(0,Math.min(255,v))).toString(16).padStart(2,'0')).join('').toUpperCase();
 const mix=(a,b,t)=>{const x=rgb(a),y=rgb(b);return toHex(x.map((v,i)=>v+(y[i]-v)*t))};
 const lum=h=>{const [r,g,b]=rgb(h).map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*r+.7152*g+.0722*b};
 const contrast=(a,b)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
 function normalize(a){
  const out={...DEFAULT,...(a&&typeof a==='object'?a:{})};
  if(!['dark','light','system'].includes(out.mode))out.mode='light';
  if(!hex(out.accent))out.accent='';
  out.modes={dark:{...(out.modes?.dark||{})},light:{...(out.modes?.light||{})}};
  for(const m of ['dark','light']){const s=out.modes[m];s.colors=Object.fromEntries(Object.entries(s.colors||{}).filter(([k,v])=>KEYS.has(k)&&hex(v)));if(s.accent!=null&&!hex(s.accent))delete s.accent}
  return out
 }
 const system=matchMedia('(prefers-color-scheme: dark)');
 const resolveMode=a=>a.mode==='system'?(system.matches?'dark':'light'):a.mode;
 function accentFor(a,mode){
  return a.modes[mode].accent||a.accent||null
 }
 function tokens(input,forceMode){
  const a=normalize(input),mode=forceMode||resolveMode(a),t={...BASE[mode],...a.modes[mode].colors};
  const chosen=accentFor(a,mode),accent=chosen||t.text;
  const onAccent=contrast(accent,'#000000')>=contrast(accent,'#FFFFFF')?'#000000':'#FFFFFF';
  Object.assign(t,{
   accent,'accent-dark':onAccent,'accent-contrast':onAccent,
   'accent-hover':mix(accent,mode==='dark'?'#FFFFFF':'#000000',.14),
   'accent-soft':mix(t.bg,accent,mode==='dark'?.16:.1),
   focus:accent,progress:accent,selection:mix(t.bg,accent,mode==='dark'?.34:.22),
   'line-strong':mix(t.line,t.text,.18),
   'code-bg':mix(t.bg,t.text,mode==='dark'?.045:.03),'code-inline-bg':mix(t.bg,t.text,mode==='dark'?.1:.07),'code-text':t.text,
   'syntax-keyword':mode==='dark'?'#C9B8FF':'#5B2A86','syntax-string':mode==='dark'?'#A9DDB4':'#1E5E33','syntax-number':mode==='dark'?'#EBC88F':'#7A4A00','syntax-comment':t.dim,
   'node-active':chosen||t.entity,'node-done':t.pathway,'node-failed':t.danger,'node-planned':t.lattice,'node-waiting':t.warning,
   scrim:mode==='dark'?'#000000B8':'#0000004D',shadow:mode==='dark'?'#000000A6':'#00000029'
  });
  return {mode,accented:!!chosen,tokens:t,appearance:a}
 }
 function warnings(t){
  const out=[],check=(fg,bg,min,what)=>{const r=contrast(t[fg],t[bg]);if(r<min)out.push({fg,bg,ratio:Math.round(r*10)/10,min,what})};
  check('text','bg',4.5,'Primary text on the background');check('text','panel',4.5,'Primary text on panels');check('muted','bg',4.5,'Secondary text on the background');
  check('dim','panel',4.5,'Tertiary text on panels');check('accent','bg',3,'Accent controls against the background');check('accent-contrast','accent',4.5,'Button labels on the accent');
  check('danger','bg',4.5,'Error text');check('warning','bg',4.5,'Warning text');check('success','bg',4.5,'Success text');check('line','bg',1.25,'Borders against the background');
  return out
 }
 let current=null;
 function apply(input,{persist=true}={}){
  const r=tokens(input),root=document.documentElement;
  for(const [k,v] of Object.entries(r.tokens))root.style.setProperty('--'+k,v);
  root.dataset.theme=r.mode;root.dataset.accent=r.accented?'on':'off';root.style.colorScheme=r.mode;
  if(persist)try{localStorage.setItem('luminaria-appearance',JSON.stringify(r.appearance));localStorage.setItem('luminaria-theme',r.mode)}catch{}
  current=r;window.dispatchEvent(new CustomEvent('studio-appearance',{detail:r}));
  return r
 }
 function fromPreferences(p){return normalize(p?.appearance||{mode:['dark','light','system'].includes(p?.theme_mode)?p.theme_mode:'light'})}
 system.addEventListener('change',()=>{if(current?.appearance.mode==='system')apply(current.appearance)});
 let cached=null;try{cached=JSON.parse(localStorage.getItem('luminaria-appearance')||'null')}catch{}
 if(!cached){let legacy=null;try{legacy=localStorage.getItem('luminaria-theme')}catch{}cached={mode:legacy==='dark'?'dark':'light'}}
 apply(cached);
 window.luminariaAppearance={BASE,EDITABLE,DEFAULT,normalize,tokens,warnings,contrast,apply,fromPreferences,mix,get current(){return current}};
})();
