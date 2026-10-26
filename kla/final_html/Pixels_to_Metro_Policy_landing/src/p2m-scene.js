/* Pixels to Metro Policy · bird's-eye evidence scene + analytics charts. Runs after p2m-voyage.js (uses window.__B). */
(()=>{
'use strict';
const B=window.__B;if(!B)return;
const $=id=>document.getElementById(id);
const RM=matchMedia('(prefers-reduced-motion: reduce)');
const W0=100.32788911328558,E0=100.9379578268588,S0=13.48698924474914,N0=13.954553421857204;
const VW=6595,VH=5172,KX=VW/(E0-W0),KY=VH/(N0-S0);
const X=lo=>(lo-W0)*KX,Y=la=>(N0-la)*KY;
const PW=1000,PH=784,U=VW/PW;
const pathD=rings=>rings.map(r=>'M'+r.map(q=>X(q[0]).toFixed(1)+' '+Y(q[1]).toFixed(1)).join('L')+'Z').join('');
const geomD=g=>(g.type==='MultiPolygon'?g.coordinates:[g.coordinates]).map(pathD).join('');
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* ---------- scene build ---------- */
const svg=$('scSvg'),plane=$('scPlane'),view=$('scView'),card=$('scCard');
$('gDist').innerHTML=B.dist.map((d,i)=>`<path d="${geomD(d.g)}" data-d="${i}"/>`).join('')+`<path class="edge" d="${geomD(B.prov.find(p=>p.n==='Bangkok').g)}"/>`;
$('gLbl').innerHTML=B.dist.map(d=>`<text x="${X(d.c[0]).toFixed(0)}" y="${Y(d.c[1]).toFixed(0)}">${esc(d.n)}</text>`).join('');
let ho='',hc='';B.comm.forEach(([cg,rings],i)=>{const s=`<path d="${pathD(rings)}" data-i="${i}"/>`;if(cg)hc+=s;else ho+=s});
$('gOther').innerHTML=ho;$('gCong').innerHTML=hc;
$('gCand').innerHTML=B.cand.map((q,i)=>`<circle cx="${X(q[0]).toFixed(0)}" cy="${Y(q[1]).toFixed(0)}" r="40" data-c="${i}"/>`).join('');
$('gBM').innerHTML=B.bm.map(q=>`<circle cx="${X(q[0]).toFixed(0)}" cy="${Y(q[1]).toFixed(0)}" r="20"/>`).join('');
$('scHeat').src=B.heat;$('scHz').src=B.hz;
(()=>{const [bw,be,bs,bn]=B.densBox,im=$('scDens');im.src=B.dens;im.style.left=(X(bw)/U)+'px';im.style.top=(Y(bn)/U)+'px';im.style.width=((X(be)-X(bw))/U)+'px';im.style.height=((Y(bs)-Y(bn))/U)+'px'})();
const lineD=ls=>ls.map(l=>'M'+l.map(q=>X(q[0]).toFixed(0)+' '+Y(q[1]).toFixed(0)).join('L')).join('');
$('gFlood').innerHTML=B.dist.map(d=>{const v=B.flood69[d.n]||0;return v?`<path d="${geomD(d.g)}" fill="${v===2?'rgba(63,162,255,.42)':'rgba(63,162,255,.18)'}"/>`:''}).join('');
$('gCanal').innerHTML=`<path d="${lineD(B.canals)}"/>`;$('gRiver').innerHTML=`<path d="${lineD(B.rivers)}"/>`;
$('gRail').innerHTML=`<path d="${lineD(B.rail)}"/>`;
const TCOL={BTS_SUKHUMVIT:'#7ac943',BTS_SILOM:'#0f9d76',MRT_BLUE:'#2f6fe0',MRT_PURPLE:'#8a52d6',ARL:'#e0384a',BRT:'#f4b400'};
$('gTransit').innerHTML=Object.entries(B.transit).map(([k,v])=>`<path stroke="${TCOL[k]}" d="${lineD([v])}"/>`+v.map(s=>`<circle cx="${X(s[0]).toFixed(0)}" cy="${Y(s[1]).toFixed(0)}" r="14" fill="${TCOL[k]}"/>`).join('')).join('');
$('gCrime').innerHTML=B.dist.filter(d=>B.crime[d.n]!=null).map(d=>{const v=B.crime[d.n];return `<circle cx="${X(d.c[0]).toFixed(0)}" cy="${Y(d.c[1]).toFixed(0)}" r="${(40+Math.sqrt(v)*34).toFixed(0)}"/><text x="${X(d.c[0]).toFixed(0)}" y="${Y(d.c[1]).toFixed(0)}">${v}</text>`}).join('');
// analytics card
(()=>{const P=B.an.prox,rows=[['Within 100 m of a canal or river','canal100'],['Within 800 m of a rail-transit station','station800'],['Within 300 m of mainline rail','rail300']];
  const col={congested:'var(--amber)',other:'#5d8a9b',random:'#4b5a64'},lab={congested:'Congested',other:'Other reg.',random:'Random'};
  $('scStats').innerHTML=rows.map(([t,k])=>{const mx=Math.max(...['congested','other','random'].map(g=>P[g][k]));return `<div class="r"><b>${t}</b><div class="bars">${['congested','other','random'].map(g=>`<span>${lab[g]}</span><i><em style="width:${(P[g][k]/mx*100).toFixed(0)}%;background:${col[g]}"></em></i><span>${P[g][k].toFixed(0)}%</span>`).join('')}</div></div>`}).join('')+`<div class="r"><b>2569 flood · high-impact districts</b><div class="bars"><span>East bank</span><i><em style="width:100%;background:var(--blue)"></em></i><span>${B.an.eastwest.east.high69}</span><span>West bank</span><i><em style="width:1%;background:var(--blue)"></em></i><span>${B.an.eastwest.west.high69}</span></div></div>`})();
const FIRE_SVG='<svg width="14" height="16" viewBox="0 0 14 16" aria-hidden="true"><path d="M7 1c1 3 4 4.5 4 8.2A4 4 0 0 1 3 9.5C3 7.6 4.3 6.6 5 5c.4 1.2 1 2 2 2.3C6.6 5 6.5 3 7 1Z" fill="currentColor"/></svg>';
const DROP_SVG='<svg width="12" height="16" viewBox="0 0 12 16" aria-hidden="true"><path d="M6 1C4 5 1.5 7.4 1.5 10.2a4.5 4.5 0 0 0 9 0C10.5 7.4 8 5 6 1Z" fill="currentColor"/></svg>';
const pins=[];
function addPin(cls,q,tag,data){const an=document.createElement('i');an.style.left=(X(q[0])/U)+'px';an.style.top=(Y(q[1])/U)+'px';$('scPins').appendChild(an);const el=document.createElement('div');el.className='pin '+cls;el._an=an;
  el.innerHTML=`<button type="button" aria-label="${esc(tag)}"><span class="tag">${esc(tag)}</span><span class="head">${cls==='fire'?FIRE_SVG:DROP_SVG}</span><span class="stem"></span><span class="ring"></span></button>`;
  el.querySelector('button').addEventListener('click',e=>{e.stopPropagation();showPin(data)});$('scPinsUI').appendChild(el);pins.push(el)}
const sceneEl=$('scene');function placePins(){const o=sceneEl.getBoundingClientRect();pins.forEach(p=>{const r=p._an.getBoundingClientRect();p.style.transform=`translate(${(r.left-o.left).toFixed(1)}px,${(r.top-o.top).toFixed(1)}px)`})}
let pinRaf=0;function pinLoop(){placePins();pinRaf=requestAnimationFrame(pinLoop)}
B.fireN.forEach(([n,d,lv,q],i)=>addPin('fire',q,`${i+1} · ${n} · ${lv}`,{t:'fire',n,d,lv,q}));
pins.forEach((p,i)=>{p.querySelector('.stem').style.height=(40+[0,0,0,34,0,68,0,0,30,0,0,0][i]||40)+'px'});
B.flood.forEach(([n,q])=>addPin('flood',q,`${n} · outside river flood wall`,{t:'flood',n,q}));
const dc=n=>B.dist.find(d=>d.n===n).c;
Object.entries(B.claims69).forEach(([n,v])=>addPin('claim',dc(n),`${n} · ${v.toLocaleString()} flood claims${B.stillFlooded.includes(n)?' · still flooded 21 Oct':''}`,{t:'claim',n,v,q:dc(n)}));
B.stillFlooded.filter(n=>!(n in B.claims69)).forEach(n=>addPin('claim',dc(n),`${n} · still flooded 21 Oct 2569`,{t:'claim',n,v:null,q:dc(n)}));
$('gFireD').innerHTML=B.dist.map(d=>{const f=B.fire68[d.n];if(!f)return '';const r=(26+Math.sqrt(f[2])*30).toFixed(0);return `<circle cx="${X(d.c[0]).toFixed(0)}" cy="${Y(d.c[1]).toFixed(0)}" r="${r}"/><text x="${X(d.c[0]).toFixed(0)}" y="${Y(d.c[1]).toFixed(0)}">${f[2]}</text>`}).join('');

/* ---------- view state ---------- */
const st={s:1,ox:0,oy:0,tilt:0,rz:0};let fitS=1;
function fit(){const r=view.getBoundingClientRect();fitS=st.tilt>10?Math.min(r.width/PW*.8,r.height/PH*1.15):Math.min(r.width/PW,r.height/PH)*.88}
function apply(){
  const k=fitS*st.s;
  plane.style.transform=`translate(-50%,-50%) rotateX(${st.tilt}deg) rotateZ(${st.rz}deg) scale(${k}) translate(${st.ox}px,${st.oy}px)`;
  const upx=U/k;
  svg.style.setProperty('--sw',(1.1*upx).toFixed(2));svg.style.setProperty('--fs',(9.5*upx).toFixed(1)+'px');
  $('gLbl').style.opacity=st.s<1.6&&innerWidth<760?0:1;
  const rc=Math.max(30,5*upx).toFixed(0),rb=Math.max(14,2.6*upx).toFixed(0);
  $('gCand').querySelectorAll('circle').forEach(c=>c.setAttribute('r',rc));$('gBM').querySelectorAll('circle').forEach(c=>c.setAttribute('r',rb));
}
function anim(on){plane.classList.toggle('anim',on&&!RM.matches)}
function flyTo(lo,la,s){anim(true);st.ox=PW/2-X(lo)/U;st.oy=PH/2-Y(la)/U;st.s=s;apply();setTimeout(()=>anim(false),1150)}
function zoomBy(f){anim(true);st.s=Math.max(.8,Math.min(16,st.s*f));apply();setTimeout(()=>anim(false),1150)}
$('scIn').onclick=()=>zoomBy(1.6);$('scOut').onclick=()=>zoomBy(1/1.6);
$('scReset').onclick=()=>{anim(true);st.s=1;st.ox=0;st.oy=0;fit();apply();setTimeout(()=>anim(false),1150)};
const tiltBtn=$('scTilt');
function setTilt(on){anim(true);st.tilt=on?56:0;st.rz=on?-16:0;tiltBtn.textContent=on?'2D':'3D';fit();apply();setTimeout(()=>anim(false),1150)}
tiltBtn.onclick=()=>setTilt(st.tilt<10);
const sel=$('scDist');B.dist.slice().sort((a,b)=>a.n.localeCompare(b.n)).forEach(d=>{const o=document.createElement('option');o.value=d.n;o.textContent=`${d.n} · ${d.th}`;sel.appendChild(o)});
sel.onchange=()=>{const d=B.dist.find(x=>x.n===sel.value);if(d)flyTo(d.c[0],d.c[1],3.6)};
// drag / pinch / ctrl-wheel
const ptr=new Map();let moved=0,pinch=0;
view.addEventListener('pointerdown',e=>{if(e.target.closest('.pin'))return;view.setPointerCapture(e.pointerId);ptr.set(e.pointerId,[e.clientX,e.clientY]);moved=0;if(ptr.size===2){const[a,b]=[...ptr.values()];pinch=Math.hypot(a[0]-b[0],a[1]-b[1])}view.classList.add('drag')});
view.addEventListener('pointermove',e=>{if(!ptr.has(e.pointerId))return;const p=ptr.get(e.pointerId);const dx=e.clientX-p[0],dy=e.clientY-p[1];ptr.set(e.pointerId,[e.clientX,e.clientY]);
  if(ptr.size===2){const[a,b]=[...ptr.values()];const d=Math.hypot(a[0]-b[0],a[1]-b[1]);if(pinch){st.s=Math.max(.8,Math.min(16,st.s*d/pinch));apply()}pinch=d;moved+=10;return}
  moved+=Math.abs(dx)+Math.abs(dy);const a=-st.rz*Math.PI/180,dy2=dy/Math.max(.35,Math.cos(st.tilt*Math.PI/180)),k=fitS*st.s;
  st.ox+=(dx*Math.cos(a)-dy2*Math.sin(a))/k;st.oy+=(dx*Math.sin(a)+dy2*Math.cos(a))/k;apply()});
const up=e=>{ptr.delete(e.pointerId);if(ptr.size<2)pinch=0;if(!ptr.size)view.classList.remove('drag');
  if(e.type==='pointerup'&&moved<6){const el=document.elementFromPoint(e.clientX,e.clientY);handleTap(el)}};
view.addEventListener('pointerup',up);view.addEventListener('pointercancel',up);
view.addEventListener('wheel',e=>{if(!(e.ctrlKey||e.metaKey))return;e.preventDefault();st.s=Math.max(.8,Math.min(16,st.s*Math.exp(-e.deltaY*.002)));apply()},{passive:false});
view.addEventListener('dblclick',()=>zoomBy(1.6));
// hover + tap
let selEl=null;
function handleTap(el){if(!el)return;if(el.closest&&el.closest('.pin'))return;
  if(el.matches&&el.matches('#gOther path,#gCong path')){mark(el);showComm(+el.dataset.i)}
  else if(el.matches&&el.matches('#gCand circle')){mark(el);showCand(+el.dataset.c)}
  else{mark(null);card.hidden=true}}
function mark(el){if(selEl)selEl.classList.remove('sel');selEl=el;if(el)el.classList.add('sel')}
if(matchMedia('(hover:hover)').matches){svg.addEventListener('pointerover',e=>{if(ptr.size)return;const t=e.target;if(t.matches('#gOther path,#gCong path'))showComm(+t.dataset.i);else if(t.matches('#gCand circle'))showCand(+t.dataset.c)})}
const near=(lo,la)=>{let b=null,bd=1e9;B.dist.forEach(d=>{const dd=Math.hypot((d.c[0]-lo)*1.05,d.c[1]-la);if(dd<bd){bd=dd;b=d}});return b};
function li(c,t){return `<li><i style="background:${c}"></i><span>${t}</span></li>`}
function openCard(h){card.innerHTML=`<button class="x" type="button" aria-label="Close">×</button>`+h;card.hidden=false;card.querySelector('.x').onclick=()=>{card.hidden=true;mark(null)}}
function showComm(i){const [name,dist,f]=B.info[i];const cg=B.comm[i][0];
  let L='';if(f&4){const fr=B.fireN.find(x=>Math.hypot(x[3][0]-B.info[i][3],x[3][1]-B.info[i][4])<.004);L+=li('var(--red)',`Fire risk assessed ${fr?fr[2].toLowerCase():'high'} (2568)`)}
  if(f&8)L+=li('var(--blue)','On the outside-flood-wall list (Nov 2568)');
  if(f&1)L+=li('var(--teal)','Baan Mankong project within 300 m');
  if(f&2)L+=li('#ff4d8c','Model candidate area within 600 m');
  if(!(f&15))L+=li('#4b5a64','No fire, flood-wall, Baan Mankong or candidate flag nearby');
  const e=B.ext[i],fl=['not affected','medium','high'][e[0]],hz=['high','moderate','low'][e[1]];
  L+=li('var(--blue)',`2569 flood impact of district: <b>${fl}</b>`);
  if(e[1]>=0)L+=li(['#ff4848','#ffaa3c','#3cc88c'][e[1]],`Modelled flood hazard at site: <b>${hz}</b>`);
  L+=li('#6ec8ff',`Nearest canal or river: <b>${e[2].toLocaleString()} m</b>`);
  L+=li('#7ac943',`Nearest rail-transit station: <b>${e[3]>=1000?(e[3]/1000).toFixed(1)+' km':e[3]+' m'}</b>`);
  const dc=B.densByDist[dist];if(dc)L+=li('#fcb76b',`District density 2564: <b>${dc[0].toLocaleString()}–${dc[1].toLocaleString()}</b> per km²`);
  const fd=B.fire68[dist];if(fd)L+=li('#ff7a3d',`Fire incidents in district 2568: <b>${fd[2]}</b> (${fd[1]} building fires)`);
  L+=li('#e05cff',B.crime[dist]!=null?`BMA crime risk spots in district: <b>${B.crime[dist]}</b> (2564)`:'Crime risk spots: district count not published');
  openCard(`<span class="ty" style="color:${cg?'var(--amber)':'#8fb7c6'}">${cg?'Registered slum · congested community':'Registered community · other type'}</span><h4>${esc(name)}</h4><span class="src">${esc(dist)} district · BMA community register</span><ul>${L}</ul>`)}
function showCand(i){const q=B.cand[i];const d=near(q[0],q[1]);
  openCard(`<span class="ty" style="color:#ff4d8c">Potential informal · candidate area</span><h4>Unverified screening output</h4><span class="src">Near ${esc(d.n)} district · position digitised from the project map</span><ul>${li('#ff4d8c','Building-pattern cluster outside registered community polygons')}${li('var(--amber)','Needs field verification before any claim about the community')}${li('#2d3b45','Name withheld: candidates are not identified communities')}</ul>`)}
function showPin(d){if(d.t==='claim'){openCard(`<span class="ty" style="color:#7fd0ff">SEA · 2569 flood · ${esc(d.n)}</span><h4>${d.v?d.v.toLocaleString()+' damage claims':'Still flooded'}</h4><span class="src">Claim Bangkok registrations to 20 Oct 2569 · BMA</span><ul>${d.v?li('#2f8fff','One of the five districts with the most flood-damage registrations'):''}${B.stillFlooded.includes(d.n)?li('var(--amber)','Still flooded on 21 Oct 2569, almost four weeks after the rain'):''}${li('var(--blue)',`BMA impact level: <b>${['not affected','medium','high'][B.flood69[d.n]||0]}</b>`)}</ul>`);flyTo(d.q[0],d.q[1],Math.max(st.s,3));return}
  if(d.t==='fire')openCard(`<span class="ty" style="color:var(--red)">SEA · fire risk · ${esc(d.lv)}</span><h4>${esc(d.n)}</h4><span class="src">${esc(d.d)} district · assessment year 2568</span><ul>${li('var(--red)','Risk classification, not a recorded fire')}${li('var(--amber)','Priority for a risk-first field visit')}</ul>`);
  else openCard(`<span class="ty" style="color:var(--blue)">SEA · outside flood walls</span><h4>${esc(d.n)}</h4><span class="src">Registered informal community · list of Nov 2568</span><ul>${li('var(--blue)','One of 11 communities (320 households, ~1,070 people) outside the walls')}${li('#2d3b45','6 of 11 matched to coordinates; 5 remain unlocated')}</ul>`);
  flyTo(d.q[0],d.q[1],Math.max(st.s,5))}
// layers
const tog=(id,fn)=>{const el=$(id);el.addEventListener('change',()=>fn(el.checked))};
tog('lyCong',v=>$('gCong').style.display=v?'':'none');tog('lyOther',v=>$('gOther').style.display=v?'':'none');
tog('lyCand',v=>$('gCand').style.display=v?'':'none');tog('lyBM',v=>$('gBM').style.display=v?'':'none');$('gBM').style.display='none';
tog('lyFire',v=>pins.forEach(p=>{if(p.classList.contains('fire'))p.hidden=!v}));tog('lyFlood',v=>pins.forEach(p=>{if(p.classList.contains('flood'))p.hidden=!v}));tog('lyClaim',v=>pins.forEach(p=>{if(p.classList.contains('claim'))p.hidden=!v}));
tog('lyHeat',v=>$('scHeat').style.opacity=v?'':'0');$('scHeat').style.opacity='0';
const show=(id,on)=>{$(id).style.display=on?'':'none'};
[['lyFl69','gFlood',1],['lyCanal','gCanal',1],['lyCanal','gRiver',1],['lyRail','gRail',1],['lyTransit','gTransit',1],['lyCrime','gCrime',0],['lyFireD','gFireD',1]].forEach(([c,g,d])=>{show(g,d);$(c).addEventListener('change',e=>show(g,e.target.checked))});
tog('lyHz',v=>$('scHz').style.opacity=v?'.75':'0');$('scHz').style.opacity='0';
tog('lyDens',v=>$('scDens').style.opacity=v?'.85':'0');$('scDens').style.opacity='0';
// entrance: top-down → bird's-eye
fit();apply();
let entered=false;
new IntersectionObserver(es=>{if(es[0].isIntersecting){if(!pinRaf)pinLoop()}else{cancelAnimationFrame(pinRaf);pinRaf=0}},{threshold:0}).observe(sceneEl);
new IntersectionObserver(es=>{if(es[0].isIntersecting&&!entered){entered=true;setTimeout(()=>setTilt(true),RM.matches?0:250)}},{threshold:.45}).observe(view);
addEventListener('resize',()=>{fit();apply()});

/* ---------- analytics ---------- */
const tt=document.createElement('div');tt.className='tt';document.body.appendChild(tt);
const tip=(e,h)=>{tt.innerHTML=h;tt.style.opacity=1;const x=Math.min(e.clientX+14,innerWidth-tt.offsetWidth-8);tt.style.left=x+'px';tt.style.top=(e.clientY+14)+'px'};
const untip=()=>tt.style.opacity=0;
const AM='#ffb547',BL='#3fa2ff';
// separation
(()=>{const rows=[['Surrounding-ring density',.69,1,''],['Distance to canal, median',.60,0,''],['Model mean probability',.56,1,'M'],['Nearest-neighbour distance',.54,0,''],['Model high-score share',.54,1,'M'],['Orientation concentration',.50,0,''],['Rectangularity, median',.47,0,'A'],['Density inside the frame',.44,1,''],['Building count',.43,1,''],['Building area, median',.40,0,''],['Building elongation',.39,1,'A'],['Edge gap between buildings',.25,0,''],['Share of touching buildings',.16,1,''],['Variability of building size',.12,1,''],['Spacing regularity',.11,1,''],['Orientation entropy',.10,1,''],['Inside-to-outside ratio',.09,1,''],['Share aligned within 10°',.03,1,'']];
  const w=1000,lw=270,rh=26,top=26,h=top+rows.length*rh+10,x=v=>lw+v/.8*(w-lw-60);
  let s=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Separation by descriptor"><defs><filter id="bg1"><feGaussianBlur stdDeviation="3"/></filter><linearGradient id="ga" x1="0" x2="1"><stop offset="0" stop-color="${AM}" stop-opacity=".25"/><stop offset="1" stop-color="${AM}"/></linearGradient><linearGradient id="gb" x1="0" x2="1"><stop offset="0" stop-color="${BL}" stop-opacity=".25"/><stop offset="1" stop-color="${BL}"/></linearGradient></defs>`;
  [0,.2,.4,.6,.8].forEach(v=>{s+=`<line x1="${x(v)}" x2="${x(v)}" y1="${top-8}" y2="${h-6}" stroke="#1f2a31"/><text x="${x(v)}" y="${top-12}" font-size="10" text-anchor="middle">${v.toFixed(1)}</text>`});
  rows.forEach(([n,v,hi,t],i)=>{const y=top+i*rh;const g=hi?'url(#ga)':'url(#gb)',c=hi?AM:BL;const dens=/density|count/i.test(n);
    s+=`<text x="${lw-34}" y="${y+15}" font-size="12" text-anchor="end" style="fill:${dens?'#e8eef2':'#a9b7bf'}">${n}</text>${t?`<text x="${lw-14}" y="${y+15}" font-size="11" text-anchor="middle" style="fill:${AM}">${t}</text>`:''}
    <rect x="${lw}" y="${y+6}" width="${x(v)-lw}" height="12" fill="${c}" opacity=".5" filter="url(#bg1)"/><rect x="${lw}" y="${y+6}" width="${x(v)-lw}" height="12" fill="${g}"/><rect x="${x(v)-2}" y="${y+4}" width="2" height="16" fill="#fff"/><text x="${x(v)+8}" y="${y+16}" font-size="11.5" style="fill:#e8eef2">${v.toFixed(2)}</text>`});
  $('chSep').innerHTML=s+'</svg>'})();
// correlation
(()=>{const lab=['buildings','density in','density ring','spacing','orientation','rectangularity','canal distance','model prob','model share'];
  const P={'0,1':.98,'0,2':.66,'0,3':-.68,'1,2':.68,'1,3':-.69,'3,8':-.53,'7,8':.88};
  const col=d3.scaleLinear().domain([-1,0,1]).range([BL,'#10171c',AM]);const cs=40,ox=118,oy=14,n=9,w=ox+n*cs+10,h=oy+n*cs+92;
  let s=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Correlation matrix"><defs><filter id="cg"><feGaussianBlur stdDeviation="4"/></filter></defs>`;
  for(let i=0;i<n;i++){s+=`<text x="${ox-8}" y="${oy+i*cs+cs/2+4}" font-size="11" text-anchor="end">${i+1} ${lab[i]}</text><text x="${ox+i*cs+cs/2}" y="${oy+n*cs+16}" font-size="11" text-anchor="middle">${i+1}</text>`;
    for(let j=0;j<n;j++){const k=i<j?i+','+j:j+','+i;const v=i===j?1:P[k];const x=ox+j*cs,y=oy+i*cs;
      if(v==null)s+=`<rect x="${x+2}" y="${y+2}" width="${cs-4}" height="${cs-4}" fill="none" stroke="#1f2a31" stroke-dasharray="2 3"/>`;
      else if(i===j)s+=`<rect x="${x+2}" y="${y+2}" width="${cs-4}" height="${cs-4}" fill="#1a2329"/><text x="${x+cs/2}" y="${y+cs/2+4}" font-size="10" text-anchor="middle" style="fill:#5f6f79">1</text>`;
      else s+=`<rect x="${x+2}" y="${y+2}" width="${cs-4}" height="${cs-4}" fill="${col(v)}" opacity=".7" filter="url(#cg)"/><rect x="${x+2}" y="${y+2}" width="${cs-4}" height="${cs-4}" fill="${col(v)}" data-t="${lab[i]} × ${lab[j]}: ρ = ${v.toFixed(2)}"/><text x="${x+cs/2}" y="${y+cs/2+4}" font-size="10.5" text-anchor="middle" style="fill:#03141a;font-weight:600">${v.toFixed(2)}</text>`}}
  const ly=oy+n*cs+40;s+=`<defs><linearGradient id="lg"><stop offset="0" stop-color="${BL}"/><stop offset=".5" stop-color="#10171c"/><stop offset="1" stop-color="${AM}"/></linearGradient></defs><rect x="${ox}" y="${ly}" width="${n*cs}" height="8" fill="url(#lg)"/><text x="${ox}" y="${ly+24}" font-size="10">−1</text><text x="${ox+n*cs/2}" y="${ly+24}" font-size="10" text-anchor="middle">0</text><text x="${ox+n*cs}" y="${ly+24}" font-size="10" text-anchor="end">+1</text><rect x="${ox}" y="${ly+34}" width="12" height="12" fill="none" stroke="#2d3b45" stroke-dasharray="2 3"/><text x="${ox+18}" y="${ly+44}" font-size="10">not published</text>`;
  const el=$('chCorr');el.innerHTML=s+'</svg>';el.addEventListener('pointermove',e=>{const t=e.target.dataset&&e.target.dataset.t;t?tip(e,t):untip()});el.addEventListener('pointerleave',untip)})();
// rings
(()=>{const ring=(parts,center,sub,gate)=>{const r=52,c=2*Math.PI*r;let s=`<svg viewBox="0 0 140 140"><circle cx="70" cy="70" r="${r}" fill="none" stroke="#1a2329" stroke-width="12"/>`;let off=0;
    parts.forEach(([v,col])=>{s+=`<circle cx="70" cy="70" r="${r}" fill="none" stroke="${col}" stroke-width="12" stroke-dasharray="${v*c} ${c}" stroke-dashoffset="${-off*c}" transform="rotate(-90 70 70)" style="filter:drop-shadow(0 0 6px ${col})"/>`;off+=v});
    if(gate!=null){const a=gate*2*Math.PI-Math.PI/2;s+=`<line x1="${70+(r-11)*Math.cos(a)}" y1="${70+(r-11)*Math.sin(a)}" x2="${70+(r+11)*Math.cos(a)}" y2="${70+(r+11)*Math.sin(a)}" stroke="#fff" stroke-width="2.5"/>`}
    return s+`<text x="70" y="72" text-anchor="middle" font-size="22" style="fill:#e8eef2;font-family:Archivo,sans-serif;font-weight:800">${center}</text><text x="70" y="90" text-anchor="middle" font-size="9" style="fill:#93a3ad">${sub}</text></svg>`};
  $('chRings').innerHTML=`<figure>${ring([[.733,'#9a7bff']],'0.733','SPATIAL AUC',.8)}<p>Below the white 0.80 gate: not used to classify</p></figure><figure>${ring([[1135/1588,AM],[325/1588,'#b07a2a'],[128/1588,'#5a4a30']],'71%','NHA OUTSIDE BMA')}<p>1,135 of 1,588 NHA points outside every BMA polygon</p></figure><figure>${ring([[154/244,'#ff4d8c'],[90/244,'#2fd5a5']],'244','CANDIDATES')}<p>154 no register overlap · 90 overlap</p></figure>`})();
// district heatmap + rank
(()=>{const st=new Map(B.dstat.map(r=>[r[0],{cg:r[1],ot:r[2],bm:r[3],ca:r[4]}]));const max=d3.max(B.dstat,r=>r[1]);
  const col=d3.scaleSequential(t=>d3.interpolateRgbBasis(['#0f1a21','#3a2a80','#9a7bff','#ffb547','#fff1c9'])(t)).domain([0,max]);
  const w=620,h=Math.round(w*VH/VW),k=w/VW;let s=`<svg viewBox="0 0 ${w} ${h+40}" role="img" aria-label="Congested communities by district">`;
  B.dist.forEach(d=>{const v=(st.get(d.n)||{cg:0}).cg;const dd=(d.g.type==='MultiPolygon'?d.g.coordinates:[d.g.coordinates]).map(p=>p.map(r=>'M'+r.map(q=>(X(q[0])*k).toFixed(1)+' '+(Y(q[1])*k).toFixed(1)).join('L')+'Z').join('')).join('');
    s+=`<path d="${dd}" fill="${col(v)}" stroke="#03141a" stroke-width=".8" data-n="${esc(d.n)}" style="cursor:pointer"/>`});
  s+=`<defs><linearGradient id="hl">${[0,.25,.5,.75,1].map(t=>`<stop offset="${t}" stop-color="${col(t*max)}"/>`).join('')}</linearGradient></defs><rect x="10" y="${h+12}" width="200" height="8" fill="url(#hl)"/><text x="10" y="${h+34}" font-size="10">0</text><text x="210" y="${h+34}" font-size="10" text-anchor="end">${max} congested communities</text>`;
  const m=$('chMap');m.innerHTML=s+'</svg>';
  m.addEventListener('pointermove',e=>{const n=e.target.dataset&&e.target.dataset.n;if(!n)return untip();const v=st.get(n)||{cg:0,ot:0,bm:0,ca:0};tip(e,`<b>${n.toUpperCase()}</b><br>Congested ${v.cg} · Other ${v.ot}<br>Baan Mankong ${v.bm} · Candidates ~${v.ca}`)});m.addEventListener('pointerleave',untip);
  const top=B.dstat.slice(0,12),rw=400,rh=27,lw=120,xm=d3.max(top,r=>r[1]+r[2]);let r=`<svg viewBox="0 0 ${rw} ${top.length*rh+30}" role="img" aria-label="Top districts">`;
  top.forEach((d,i)=>{const y=i*rh+8,sx=v=>v/xm*(rw-lw-40);r+=`<text x="${lw-8}" y="${y+13}" font-size="11" text-anchor="end" style="fill:#c8d3da">${d[0]}</text><rect x="${lw}" y="${y+3}" width="${sx(d[1])}" height="13" fill="${AM}" style="filter:drop-shadow(0 0 4px rgba(255,181,71,.6))"/><rect x="${lw+sx(d[1])}" y="${y+3}" width="${sx(d[2])}" height="13" fill="#2d4652"/><text x="${lw+sx(d[1]+d[2])+6}" y="${y+14}" font-size="10.5" style="fill:#e8eef2">${d[1]}</text>`});
  r+=`<rect x="${lw}" y="${top.length*rh+12}" width="10" height="8" fill="${AM}"/><text x="${lw+16}" y="${top.length*rh+20}" font-size="10">congested</text><rect x="${lw+100}" y="${top.length*rh+12}" width="10" height="8" fill="#2d4652"/><text x="${lw+116}" y="${top.length*rh+20}" font-size="10">other registered</text>`;
  $('chRank').innerHTML=r+'</svg>'})();
// scatter
(()=>{const D=B.dstat.map(r=>({n:r[0],x:r[1],y:r[4],b:r[3]}));const w=1000,h=380,m={l:60,r:30,t:20,b:50};
  const xs=d3.scaleLinear().domain([0,d3.max(D,d=>d.x)*1.05]).range([m.l,w-m.r]),ys=d3.scaleLinear().domain([0,d3.max(D,d=>d.y)*1.15]).range([h-m.b,m.t]),rs=d3.scaleSqrt().domain([0,d3.max(D,d=>d.b)]).range([3,13]);
  const rank=a=>{const s=a.map((v,i)=>[v,i]).sort((p,q)=>p[0]-q[0]);const r=new Array(a.length);let i=0;while(i<s.length){let j=i;while(j+1<s.length&&s[j+1][0]===s[i][0])j++;for(let k=i;k<=j;k++)r[s[k][1]]=(i+j)/2+1;i=j+1}return r};
  const rx=rank(D.map(d=>d.x)),ry=rank(D.map(d=>d.y)),mx=d3.mean(rx),my=d3.mean(ry);const rho=d3.sum(rx.map((v,i)=>(v-mx)*(ry[i]-my)))/Math.sqrt(d3.sum(rx.map(v=>(v-mx)**2))*d3.sum(ry.map(v=>(v-my)**2)));
  let s=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Districts: congested communities vs candidate areas">`;
  xs.ticks(6).forEach(t=>s+=`<line x1="${xs(t)}" x2="${xs(t)}" y1="${m.t}" y2="${h-m.b}" stroke="#16202a"/><text x="${xs(t)}" y="${h-m.b+18}" font-size="10" text-anchor="middle">${t}</text>`);
  ys.ticks(5).forEach(t=>s+=`<line x1="${m.l}" x2="${w-m.r}" y1="${ys(t)}" y2="${ys(t)}" stroke="#16202a"/><text x="${m.l-10}" y="${ys(t)+4}" font-size="10" text-anchor="end">${t}</text>`);
  s+=`<text x="${(m.l+w-m.r)/2}" y="${h-8}" font-size="11" text-anchor="middle" style="fill:#c8d3da">Registered congested communities per district</text><text transform="translate(16 ${(m.t+h-m.b)/2}) rotate(-90)" font-size="11" text-anchor="middle" style="fill:#c8d3da">Candidate markers (digitised)</text>`;
  D.forEach(d=>{s+=`<circle cx="${xs(d.x)}" cy="${ys(d.y)}" r="${rs(d.b)}" fill="rgba(255,77,140,.35)" stroke="#ff4d8c" style="filter:drop-shadow(0 0 5px rgba(255,77,140,.8))" data-t="${esc(d.n)} · congested ${d.x} · candidates ~${d.y} · Baan Mankong ${d.b}"/>`;if(d.x>=30||d.y>=5)s+=`<text x="${xs(d.x)+rs(d.b)+5}" y="${ys(d.y)+4}" font-size="10.5" style="fill:#e8eef2">${esc(d.n)}</text>`});
  const el=$('chScat');el.innerHTML=s+'</svg>';el.addEventListener('pointermove',e=>{const t=e.target.dataset&&e.target.dataset.t;t?tip(e,t):untip()});el.addEventListener('pointerleave',untip);
  $('scatCap').textContent=`Each dot is a district; size shows Baan Mankong projects. Spearman ρ = ${rho.toFixed(2)} across 50 districts. Candidate locations were digitised from the project map, so overlapping markers merge and counts are approximate. Correlation is not causation.`})();

/* ---------- added analytics ---------- */
const GC={congested:'#ffb547',other:'#5d8a9b',random:'#4b5a64'},GL={congested:'Congested (626)',other:'Other registered (1,368)',random:'Random points (3,000)'};
const hoverTip=el=>{el.addEventListener('pointermove',e=>{const t=e.target.dataset&&e.target.dataset.t;t?tip(e,t):untip()});el.addEventListener('pointerleave',untip)};
(()=>{const P=B.an.prox,M=[['canal100','Within 100 m of canal / river'],['station800','Within 800 m of a rail-transit station'],['rail300','Within 300 m of mainline rail']];
  const w=1000,h=300,l=330,r=60,bh=16,gap=6,grp=3*(bh+gap)+22,top=26,xs=v=>l+v/50*(w-l-r);
  let s=`<svg viewBox="0 0 ${w} ${top+M.length*grp+30}" role="img" aria-label="Share of communities near canals, transit and rail">`;
  [0,10,20,30,40,50].forEach(v=>s+=`<line x1="${xs(v)}" x2="${xs(v)}" y1="${top-8}" y2="${top+M.length*grp-12}" stroke="#16202a"/><text x="${xs(v)}" y="${top-12}" font-size="10" text-anchor="middle">${v}%</text>`);
  M.forEach(([k,t],i)=>{const y0=top+i*grp;s+=`<text x="${l-16}" y="${y0+bh*1.5+gap+4}" font-size="12.5" text-anchor="end" style="fill:#e8eef2">${t}</text>`;
    ['congested','other','random'].forEach((g,j)=>{const v=P[g][k],y=y0+j*(bh+gap);s+=`<rect x="${l}" y="${y}" width="${xs(v)-l}" height="${bh}" fill="${GC[g]}" ${g==='congested'?'style="filter:drop-shadow(0 0 6px rgba(255,181,71,.6))"':''} data-t="${GL[g]}: ${v}%"/><text x="${xs(v)+6}" y="${y+12}" font-size="11" style="fill:#e8eef2">${v.toFixed(1)}%</text>`});
    const ratio=P.congested[k]/P.random[k];s+=`<text x="${w-r+50}" y="${y0+bh+8}" font-size="18" text-anchor="end" style="fill:#ffb547;font-family:Archivo,sans-serif;font-weight:800">${ratio.toFixed(1)}×</text>`});
  const ly=top+M.length*grp+8;let lx=l;['congested','other','random'].forEach(g=>{s+=`<rect x="${lx}" y="${ly}" width="12" height="10" fill="${GC[g]}"/><text x="${lx+18}" y="${ly+9}" font-size="11">${GL[g]}</text>`;lx+=230});
  s+=`<text x="${w-r+50}" y="${top-12}" font-size="10" text-anchor="end" style="fill:#ffb547">× VS RANDOM</text>`;
  const el=$('chProx');el.innerHTML=s+'</svg>';hoverTip(el)})();
(()=>{const col=[ '#1a2730','rgba(63,162,255,.45)','#3fa2ff'],w=460,mapW=215,k=mapW/VW,h=Math.round(VH*k);
  const m=(F,ox,title)=>{let s=`<text x="${ox+mapW/2}" y="14" font-size="12" text-anchor="middle" style="fill:#e8eef2">${title}</text>`;
    B.dist.forEach(d=>{const v=F[d.n]||0;const dd=(d.g.type==='MultiPolygon'?d.g.coordinates:[d.g.coordinates]).map(p=>p.map(r=>'M'+r.map(q=>(ox+X(q[0])*k).toFixed(1)+' '+(22+Y(q[1])*k).toFixed(1)).join('L')+'Z').join('')).join('');
      s+=`<path d="${dd}" fill="${col[v]}" stroke="#03141a" stroke-width=".6" data-t="${esc(d.n)}: ${['not affected','medium','high'][v]}"/>`});return s};
  const c54=Object.values(B.flood54),c69=Object.values(B.flood69),n=(a,v)=>a.filter(x=>x===v).length;
  let s=`<svg viewBox="0 0 ${w} ${h+90}" role="img" aria-label="Flood impact by district 2554 and 2569">`+m(B.flood54,0,'2554 (news compilation)')+m(B.flood69,w-mapW,'2569 (BMA, 29 Sept)');
  const ly=h+40;[[2,'High'],[1,'Medium'],[0,'Not affected']].forEach(([v,t],i)=>{s+=`<rect x="${i*150}" y="${ly}" width="12" height="10" fill="${col[v]}"/><text x="${i*150+18}" y="${ly+9}" font-size="11">${t}: ${n(c54,v)} → ${n(c69,v)}</text>`});
  s+=`<text x="0" y="${ly+32}" font-size="10.5" style="fill:#93a3ad">Districts per level, 2554 → 2569. High-impact 2569: ${B.an.eastwest.east.high69} east bank, ${B.an.eastwest.west.high69} west bank.</text>`;
  const el=$('chFlood');el.innerHTML=s+'</svg>';hoverTip(el)})();
(()=>{const H=B.an.hazard,w=460,l=150,bh=26,top=10,cols=['#ff4848','#ffaa3c','#3cc88c'],labs=['High','Moderate','Low'];
  let s=`<svg viewBox="0 0 ${w} ${top+3*(bh+18)+40}" role="img" aria-label="Flood hazard class at community locations">`;
  ['congested','other','random'].forEach((g,i)=>{const y=top+i*(bh+18);let x=l;s+=`<text x="${l-10}" y="${y+bh/2+4}" font-size="11.5" text-anchor="end" style="fill:#e8eef2">${GL[g].replace(/ \(.*/,'')}</text>`;
    H[g].forEach((v,j)=>{const ww=v/100*(w-l-10);s+=`<rect x="${x}" y="${y}" width="${ww}" height="${bh}" fill="${cols[j]}" opacity=".9" data-t="${GL[g]} · ${labs[j]} hazard: ${v}%"/>`;if(ww>34)s+=`<text x="${x+ww/2}" y="${y+bh/2+4}" font-size="11" text-anchor="middle" style="fill:#03141a;font-weight:600">${v.toFixed(0)}%</text>`;x+=ww})});
  const ly=top+3*(bh+18)+6;labs.forEach((t,j)=>{s+=`<rect x="${l+j*95}" y="${ly}" width="12" height="10" fill="${cols[j]}"/><text x="${l+j*95+18}" y="${ly+9}" font-size="11">${t}</text>`});
  const el=$('chHz');el.innerHTML=s+'</svg>';hoverTip(el)})();
(()=>{const st=new Map(B.dstat.map(r=>[r[0],r[1]]));const D=B.dist.map(d=>{const c=B.densByDist[d.n];return c?{n:d.n,x:Math.sqrt(c[0]*c[1]),lo:c[0],hi:c[1],y:st.get(d.n)||0,f:B.flood69[d.n]||0}:null}).filter(Boolean);
  const w=1000,h=360,m={l:60,r:30,t:16,b:50};const xs=d3.scaleLog().domain([500,30000]).range([m.l,w-m.r]),ys=d3.scaleLinear().domain([0,d3.max(D,d=>d.y)*1.12]).range([h-m.b,m.t]);
  let s=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="District density against congested communities">`;
  [500,1000,2000,5000,10000,20000].forEach(t=>s+=`<line x1="${xs(t)}" x2="${xs(t)}" y1="${m.t}" y2="${h-m.b}" stroke="#16202a"/><text x="${xs(t)}" y="${h-m.b+18}" font-size="10" text-anchor="middle">${t.toLocaleString()}</text>`);
  ys.ticks(5).forEach(t=>s+=`<line x1="${m.l}" x2="${w-m.r}" y1="${ys(t)}" y2="${ys(t)}" stroke="#16202a"/><text x="${m.l-10}" y="${ys(t)+4}" font-size="10" text-anchor="end">${t}</text>`);
  s+=`<text x="${(m.l+w-m.r)/2}" y="${h-8}" font-size="11" text-anchor="middle" style="fill:#c8d3da">Population density class, people per km² (log scale, class midpoint)</text><text transform="translate(16 ${(m.t+h-m.b)/2}) rotate(-90)" font-size="11" text-anchor="middle" style="fill:#c8d3da">Congested communities</text>`;
  const rk=a=>{const s2=a.map((v,i)=>[v,i]).sort((p,q)=>p[0]-q[0]),r=new Array(a.length);let i=0;while(i<s2.length){let j=i;while(j+1<s2.length&&s2[j+1][0]===s2[i][0])j++;for(let k=i;k<=j;k++)r[s2[k][1]]=(i+j)/2+1;i=j+1}return r};
  const rx=rk(D.map(d=>d.x)),ry=rk(D.map(d=>d.y)),mx=d3.mean(rx),my=d3.mean(ry),rho=d3.sum(rx.map((v,i)=>(v-mx)*(ry[i]-my)))/Math.sqrt(d3.sum(rx.map(v=>(v-mx)**2))*d3.sum(ry.map(v=>(v-my)**2)));
  const jit=n=>((n.charCodeAt(0)*7+n.length*13)%11-5)*.012;
  D.forEach(d=>{const cx=xs(d.x)*(1+jit(d.n)),cy=ys(d.y);s+=`<line x1="${xs(d.lo)}" x2="${xs(d.hi)}" y1="${cy}" y2="${cy}" stroke="rgba(252,183,107,.25)"/><circle cx="${cx}" cy="${cy}" r="6" fill="${['#fcb76b','#7fb8ff','#3fa2ff'][d.f]}" fill-opacity=".85" stroke="#03141a" data-t="${esc(d.n)} · density ${d.lo.toLocaleString()}–${d.hi.toLocaleString()} /km² · congested ${d.y} · flood 2569 ${['none','medium','high'][d.f]}"/>`;if(d.y>=40||(d.y>=26&&d.x>9000))s+=`<text x="${cx+9}" y="${cy+4}" font-size="10.5" style="fill:#e8eef2">${esc(d.n)}</text>`});
  const el=$('chDen');el.innerHTML=s+'</svg>';hoverTip(el);
  $('denCap').textContent=`Each dot is a district: population density class (registered residents, 2564, read from the Urban TH map) against congested communities. Bars show the class range; colour shows 2569 flood impact (blue = affected). Spearman ρ = ${rho.toFixed(2)} across ${D.length} districts. Association only.`})();
/* ---------- two scales ---------- */
(()=>{$('segTheos').src=B.seg;$('segGoogle').src=B.segGoogle;
  const cv=$('cityCv'),img=new Image();img.src=B.heat;
  const draw=()=>{const r=cv.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);cv.width=r.width*dpr;cv.height=r.height*dpr;const g=cv.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);
    g.fillStyle='#03070a';g.fillRect(0,0,r.width,r.height);const sc=Math.min(r.width/VW,r.height/VH)*.94,ox=(r.width-VW*sc)/2,oy=(r.height-VH*sc)/2;
    const P=(q)=>[ox+X(q[0])*sc,oy+Y(q[1])*sc];
    g.lineJoin='round';B.dist.forEach(d=>{(d.g.type==='MultiPolygon'?d.g.coordinates:[d.g.coordinates]).forEach(p=>p.forEach(rg=>{g.beginPath();rg.forEach((q,i)=>{const s=P(q);i?g.lineTo(s[0],s[1]):g.moveTo(s[0],s[1])});g.closePath();g.fillStyle='rgba(12,22,30,.9)';g.fill()}))});
    if(img.complete){g.save();g.globalCompositeOperation='lighter';g.drawImage(img,ox,oy,VW*sc,VH*sc);g.filter='blur(2px)';g.globalAlpha=.7;g.drawImage(img,ox,oy,VW*sc,VH*sc);g.restore()}
    g.strokeStyle='rgba(63,210,240,.45)';g.lineWidth=.7;B.dist.forEach(d=>{(d.g.type==='MultiPolygon'?d.g.coordinates:[d.g.coordinates]).forEach(p=>p.forEach(rg=>{g.beginPath();rg.forEach((q,i)=>{const s=P(q);i?g.lineTo(s[0],s[1]):g.moveTo(s[0],s[1])});g.closePath();g.stroke()}))});
    g.strokeStyle='#ff4d8c';g.lineWidth=1.3;g.shadowColor='#ff4d8c';g.shadowBlur=6;B.cand.forEach(q=>{const s=P(q);g.beginPath();g.arc(s[0],s[1],4,0,7);g.stroke()});g.shadowBlur=0;
    g.font='500 10.5px "IBM Plex Mono",monospace';g.fillStyle='#e8eef2';g.fillText('MODEL PATTERN SCORE + 244 CANDIDATE AREAS',12,r.height-12)};
  img.onload=draw;new ResizeObserver(draw).observe(cv);draw()})();
/* ---------- metropolitan ---------- */
(()=>{const M=B.metro,svgEl=$('mtSvg');let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;
  const each=(g,f)=>(g.type==='MultiPolygon'?g.coordinates:[g.coordinates]).forEach(p=>p.forEach(r=>r.forEach(f)));
  M.prov.forEach(p=>each(p.g,([x,y])=>{x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y)}));
  const kx=Math.cos(13.75*Math.PI/180),w=1000,sc=w/((x1-x0)*kx),h=Math.round((y1-y0)*sc)+10;
  const px=x=>((x-x0)*kx*sc).toFixed(1),py=y=>((y1-y)*sc+5).toFixed(1);
  const gd=g=>(g.type==='MultiPolygon'?g.coordinates:[g.coordinates]).map(p=>p.map(r=>'M'+r.map(q=>px(q[0])+' '+py(q[1])).join('L')+'Z').join('')).join('');
  const [bw,be,bs,bn]=B.densBox;
  let s=`<defs><pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="7" stroke="rgba(63,210,240,.35)" stroke-width="2"/></pattern><clipPath id="bmrClip">${M.prov.map(p=>`<path d="${gd(p.g)}"/>`).join('')}</clipPath></defs>`;
  s+=`<image href="${B.dens}" x="${px(bw)}" y="${py(bn)}" width="${(be-bw)*kx*sc}" height="${(bn-bs)*sc}" preserveAspectRatio="none" opacity=".75" clip-path="url(#bmrClip)"/>`;
  M.prov.filter(p=>p.c!=='10').forEach(p=>s+=`<path d="${gd(p.g)}" fill="url(#hatch)" class="scanp" pointer-events="none"/>`);
  if(M.roads){const rd=c=>M.roads.filter(r=>r[0]===c).map(r=>'M'+r[1].map(q=>px(q[0])+' '+py(q[1])).join('L')).join('');
    s+=`<g clip-path="url(#bmrClip)" pointer-events="none"><path class="rd0" d="${rd(0)}"/><path class="rd1" d="${rd(1)}"/><path class="rd2" d="${rd(2)}"/></g>`}
  s+=`<path class="dl" d="${M.dist.map(d=>gd(d.g)).join('')}"/>`;
  s+=`<path class="dl" style="stroke:rgba(63,210,240,.4)" d="${B.dist.map(d=>gd(d.g)).join('')}"/>`;
  let cg='';B.comm.forEach(([c,rings])=>{if(c)cg+=rings.map(r=>'M'+r.map(q=>px(q[0])+' '+py(q[1])).join('L')+'Z').join('')});
  s+=`<path d="${cg}" fill="#ffb547" stroke="#ffd28a" stroke-width=".4" style="filter:drop-shadow(0 0 3px rgba(255,181,71,.8))" pointer-events="none"/>`;
  s+=B.cand.map(q=>`<circle cx="${px(q[0])}" cy="${py(q[1])}" r="2.6" fill="none" stroke="#ff4d8c" stroke-width="1" pointer-events="none"/>`).join('');
  M.prov.forEach((p,i)=>s+=`<path d="${gd(p.g)}" class="pv${p.c==='10'?' bkk':''}" data-i="${i}"/>`);
  M.prov.forEach(p=>{let sx=0,sy=0,n=0;each(p.g,([x,y])=>{sx+=x;sy+=y;n++});const cx=+px(sx/n),cy=+py(sy/n);s+=`<text class="lbl" x="${cx}" y="${cy}">${p.n.toUpperCase()}</text><text class="lbl s" x="${cx}" y="${cy+14}">${p.c==='10'?'ANALYSED':'READY TO RUN'}</text>`});
  svgEl.setAttribute('viewBox',`-16 -16 ${w+32} ${h+32}`);svgEl.innerHTML=s;
  const info=p=>p.c==='10'?{st:'Analysed · validation pending',ch:[['do','626 congested'],['do','244 candidates'],['','Footprints'],['','THEOS-2'],['','Density 2564']]}:{st:'Ready to run',ch:[['','Footprints'],['','THEOS-2'],[p.c==='24'?'no':'',p.c==='24'?'Density · outside source map':'Density 2564'],['','Road links'],['no','Local register needed']]};
  const list=$('mtList');list.innerHTML=M.prov.slice().sort((a,b)=>(a.c==='10'?-1:b.c==='10'?1:a.n.localeCompare(b.n))).map(p=>{const f=info(p);return `<div class="mt-row" data-c="${p.c}"><b>${p.n} <span style="font-weight:400;color:var(--muted)">${p.th}</span></b><em>${p.a.toLocaleString()} km² · ${p.nd} districts</em><div class="ch">${f.ch.map(([c,t])=>`<span class="${c}">${t}</span>`).join('')}</div></div>`}).join('');
  const tipEl=$('mtTip'),fig=svgEl.parentNode;
  const hl=c=>{svgEl.querySelectorAll('.pv').forEach(e=>e.classList.toggle('on',M.prov[+e.dataset.i].c===c));list.querySelectorAll('.mt-row').forEach(e=>e.classList.toggle('on',e.dataset.c===c))};
  svgEl.addEventListener('pointermove',e=>{const t=e.target.closest('.pv');if(!t){tipEl.hidden=true;hl(null);return}const p=M.prov[+t.dataset.i],f=info(p);hl(p.c);
    const r=fig.getBoundingClientRect();tipEl.hidden=false;tipEl.innerHTML=`<b>${p.n}</b><span>${p.th} · ${p.a.toLocaleString()} km² · ${p.nd} districts</span>${M.pop64&&M.pop64[p.c]?`<span>${M.pop64[p.c].toLocaleString()} registered residents, 2564</span>`:''}<span style="color:${p.c==='10'?'var(--amber)':'var(--cyan)'}">${f.st}</span>`;
    tipEl.style.left=Math.min(e.clientX-r.left+14,r.width-270)+'px';tipEl.style.top=(e.clientY-r.top+14)+'px'});
  svgEl.addEventListener('pointerleave',()=>{tipEl.hidden=true;hl(null)});
  list.addEventListener('pointerover',e=>{const r=e.target.closest('.mt-row');hl(r?r.dataset.c:null)});list.addEventListener('pointerleave',()=>hl(null));
  if(!RM.matches){let o=0;const pt=svgEl.querySelector('#hatch');(function an(){o=(o+.25)%7;pt.setAttribute('patternTransform',`rotate(45) translate(${o} 0)`);requestAnimationFrame(an)})()}})();

/* ---------- footage ---------- */
document.querySelectorAll('.vid').forEach(v=>{const id=v.dataset.yt,t0=+v.dataset.start||0,fr=v.querySelector('.vid-frame');
  const url=`https://www.youtube.com/watch?v=${id}&t=${t0}s`,ttl=v.querySelector('h3').textContent;
  fr.innerHTML=`<video muted loop playsinline preload="metadata" poster="${v.dataset.poster}" aria-label="${ttl}, muted news footage"><source src="${v.dataset.webm}" type="video/webm"><source src="${v.dataset.src}" type="video/mp4"></video><span class="vid-tag">FOOTAGE</span><div class="vid-ov"><button class="vid-btn vb-play" type="button">❚❚ Pause</button><a class="vid-btn" href="${url}" target="_blank" rel="noopener">Full report with sound ↗</a></div>`;
  const vd=fr.querySelector('video'),pb=fr.querySelector('.vb-play');let user=false;
  const sync=()=>{pb.textContent=vd.paused?'▶ Play':'❚❚ Pause'};vd.addEventListener('play',sync);vd.addEventListener('pause',sync);
  pb.onclick=()=>{user=true;vd.paused?vd.play().catch(()=>{}):vd.pause()};
  if(RM.matches){sync();return}
  new IntersectionObserver(es=>{if(user&&vd.paused)return;es[0].isIntersecting?vd.play().catch(sync):vd.pause()},{threshold:.4}).observe(vd);sync()});
/* ---------- zoom lens + lightbox ---------- */
(()=>{const lens=document.createElement('div');lens.className='zlens';document.body.appendChild(lens);const Z=3;
  const lb=$('lb'),li=$('lbImg'),lc=$('lbCap');let last=null;
  const srcOf=el=>{const im=el.querySelector('img');if(im)return [im.currentSrc||im.src,im.alt];const cv=el.querySelector('canvas');return cv?[cv.toDataURL('image/png'),cv.getAttribute('aria-label')]:[null,'']};
  const fine=matchMedia('(hover:hover) and (pointer:fine)');
  document.querySelectorAll('.zoomable').forEach(el=>{
    el.addEventListener('pointermove',e=>{if(!fine.matches)return;const r=el.getBoundingClientRect(),im=el.querySelector('img');let src,w=r.width,h=r.height,bx,by;
      if(im){src=im.currentSrc||im.src;const nw=im.naturalWidth,nh=im.naturalHeight,s=Math.max(w/nw,h/nh),dw=nw*s,dh=nh*s,ox=(w-dw)/2,oy=(h-dh)/2;w=dw;h=dh;bx=e.clientX-r.left-ox;by=e.clientY-r.top-oy}
      else{const cv=el.querySelector('canvas');if(!el._u||el._t<Date.now()-2000){el._u=cv.toDataURL('image/png');el._t=Date.now()}src=el._u;bx=e.clientX-r.left;by=e.clientY-r.top}
      lens.style.display='block';lens.style.left=(e.clientX-115)+'px';lens.style.top=(e.clientY-115)+'px';
      lens.style.backgroundImage=`url("${src}")`;lens.style.backgroundSize=`${w*Z}px ${h*Z}px`;lens.style.backgroundPosition=`${-(bx*Z-115)}px ${-(by*Z-115)}px`});
    el.addEventListener('pointerleave',()=>lens.style.display='none');
    el.addEventListener('click',()=>{const [src,alt]=srcOf(el);if(!src)return;last=el;lens.style.display='none';li.src=src;li.alt=alt||'';lc.textContent=alt||'';lb.hidden=false;lb.querySelector('.lb-x').focus()})});
  const close=()=>{lb.hidden=true;li.removeAttribute('src');if(last)last.focus&&last.focus()};
  lb.addEventListener('click',close);addEventListener('keydown',e=>{if(e.key==='Escape'&&!lb.hidden)close()})})();

/* ---------- map-grid labels + pixel bands ---------- */
(()=>{const secs=[...document.querySelectorAll('section.s,.next')];const cols='ABCDEFGHJKLMNPQRSTUV';
  secs.forEach((el,i)=>{const lat=(13.95-i*0.021).toFixed(3),lon=(100.33+i*0.031).toFixed(3);el.dataset.grid=`GRID ${cols[i%cols.length]}-${String(i+1).padStart(2,'0')} · ${lat}°N ${lon}°E`});
  const targets=[document.getElementById('scene'),...secs.filter(e=>e.id!=='footage'&&e.id!=='pipeline'&&e.id!=='method'&&e.id!=='structure')];
  const PAL=['#3fd2f0','#9a7bff','#ffb547','#2fd5a5'];const bands=[];
  targets.forEach((el,k)=>{if(!el)return;const b=document.createElement('div');b.className='pxb';b.setAttribute('aria-hidden','true');const cv=document.createElement('canvas');b.appendChild(cv);el.parentNode.insertBefore(b,el);
    let seed=k*9301+49297;const rnd=()=>(seed=(seed*9301+49297)%233280)/233280;const n=400,cells=[];for(let i=0;i<n;i++)cells.push([rnd(),rnd(),rnd()<.06?PAL[Math.floor(rnd()*4)]:null]);bands.push({b,cv,cells,acc:PAL[k%4]})});
  const draw=B0=>{const r=B0.b.getBoundingClientRect();if(r.bottom<0||r.top>innerHeight)return;const dpr=Math.min(devicePixelRatio||1,2);const W=r.width,H=r.height;
    if(B0.cv.width!==Math.round(W*dpr)){B0.cv.width=Math.round(W*dpr);B0.cv.height=Math.round(H*dpr)}const g=B0.cv.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);g.clearRect(0,0,W,H);
    const cs=W<760?12:16,nx=Math.ceil(W/cs),ny=Math.ceil(H/cs);const p=RM.matches?.5:Math.max(0,Math.min(1,1-(r.top+H/2)/innerHeight));
    for(let y=0;y<ny;y++)for(let x=0;x<nx;x++){const c=B0.cells[(x*7+y*13)%B0.cells.length];const edge=y/(ny-1);const th=c[0]*.7+edge*.3;
      if(th>p*1.25)continue;const a=Math.max(0,Math.min(1,(p*1.25-th)*3))*(.25+.75*(1-edge));
      g.fillStyle=c[2]?c[2]:`rgba(63,210,240,${(.06+c[1]*.14).toFixed(3)})`;g.globalAlpha=c[2]?a*.9:a;g.fillRect(x*cs+1,y*cs+1,cs-2,cs-2)}
    g.globalAlpha=1;g.fillStyle='rgba(63,210,240,.35)';g.font='500 10px "IBM Plex Mono",monospace';g.fillText('+',W*.5-3,H*.5+4)};
  let tk=0;const loop=()=>{tk=0;bands.forEach(draw)};addEventListener('scroll',()=>{if(!tk)tk=requestAnimationFrame(loop)},{passive:true});addEventListener('resize',loop);loop()})();
})();
