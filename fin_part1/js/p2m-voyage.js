/* Pixels to Metro Policy · scroll voyage (globe → Asia → Thailand → Bangkok). Needs d3 v7, topojson-client v3 and window.P2M_DATA (p2m-data.js). */
(()=>{
'use strict';
const RM=matchMedia('(prefers-reduced-motion: reduce)');
const $=id=>document.getElementById(id);
const J=id=>window.P2M_DATA[id];
const LAND=J('landdots');const POP=J('popbars');const loadT=performance.now();const w110=J('w110');const world=topojson.feature(w110,w110.objects.countries).features;const SEA=J('sea10').features;const B=J('bkk');
// units grid
(()=>{const u=$('units');const cols=[[120,'#ffb547'],[120,'#9a7bff'],[60,'#2fd5a5']];cols.forEach(([n,c])=>{for(let i=0;i<n;i++){const e=document.createElement('i');e.style.background=c;e.style.opacity=.85;u.appendChild(e)}})})();
const heatImg=new Image();heatImg.src=B.heat;const hzImg=new Image();hzImg.src=B.hz;const theosImg=new Image();theosImg.src=B.seg;window.__B=B;
const BB={w:100.32788911328558,e:100.9379578268588,s:13.48698924474914,n:13.954553421857204};
const CSA=new Set(['398','417','762','795','860','004','050','064','356','364','462','524','586','144']);
const ESA=new Set(['156','158','392','496','408','410','096','116','360','418','458','104','608','702','764','626','704']);
const BEAMS_UNUSED=[[110,22,362,'E & SE ASIA · 362 M'],[76,24,334,'C & S ASIA · 334 M'],[20,3,265,'SUB-SAHARAN AFRICA · 265 M']];
const CITIES=[['Chiang Mai',98.99,18.79],['Khon Kaen',102.83,16.44],['Nakhon Ratchasima',102.10,14.97],['Udon Thani',102.79,17.41],['Hat Yai',100.47,7.01],['Phuket',98.39,7.88],['Chon Buri',100.98,13.36],['Phitsanulok',100.26,16.82],['Ubon Ratchathani',104.85,15.24],['Surat Thani',99.33,9.14]];
const STEPS=[['ORBIT',0],['PLANET',.055],['ASIA',.165],['THAILAND',.275],['CANALS & RAIL',.385],['BANGKOK',.495],['RECORDS',.595],['SCREENING',.685],['AUDIT',.775],['SEA RISK',.855],['AERIAL',.935],['VALIDATION',.978]];
// Display order: part A (orbit to audit) | analytics section | part B (aerial, validation, then SEA risk).
// q = content progress (timeline below), g = display progress. Part A shows q 0-.85; part B shows .925-1, then .85-.935.
const QA=.85,SB=.47;
const g2q=g=>{if(g<=QA)return g;const s=(g-QA)/(1-QA);return s<SB?.925+(s/SB)*.075:.85+((s-SB)/(1-SB))*.085};
const DSTEPS=[...STEPS.slice(0,9),['AERIAL',QA+1e-4],['VALIDATION',QA+(1-QA)*(.053/.075*SB)],['SEA RISK',QA+(1-QA)*(SB+(.005/.085)*(1-SB))]];
const stepsEl=$('steps');STEPS.forEach(()=>{const li=document.createElement('li');li.innerHTML='<i></i>';stepsEl.appendChild(li)});
// camera keys: p, lon, lat, zoom (number) or ['B',k] = Bangkok-fit × k
const KEYS=[[0,15,18,.82],[.05,25,15,.9],[.14,55,12,1.0],[.17,92,20,1.8],[.25,96,18,1.95],[.28,101,13,7],[.36,101,13.1,7.4],[.39,100.8,13.5,8.5],[.46,100.7,13.7,11],
 [.50,100.635,13.72,['B',1]],[.58,100.635,13.72,['B',1]],[.66,100.63,13.72,['B',1.04]],[.75,100.6,13.73,['B',1.1]],[.83,100.58,13.73,['B',1.12]],[.86,100.55,13.73,['B',1.28]],[.92,100.54,13.73,['B',1.32]],[.95,100.52,13.73,['B',7]],[.972,100.52,13.73,['B',7.4]],[.99,100.635,13.72,['B',1]],[1,100.635,13.72,['B',1]]];
const ease=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
const win=(p,a,b,f=.02)=>Math.max(0,Math.min(1,Math.min((p-a)/f,(b-p)/f)));
const ramp=(p,a,b)=>Math.max(0,Math.min(1,(p-a)/(b-a)));
const cv=$('globe'),ctx=cv.getContext('2d');
let W=0,H=0,dpr=1,base=1,bkZ=150,mobile=false;
function size(){dpr=Math.min(devicePixelRatio||1,2);const r=cv.getBoundingClientRect();W=r.width;H=r.height;cv.width=Math.round(W*dpr);cv.height=Math.round(H*dpr);mobile=W<760;base=Math.min(W,H)*(mobile?.40:.44);
  const fitW=mobile?W*.94:W*.5;const fitH=mobile?H*.52:H*.8;const pxkm=Math.min(fitW/66,fitH/52);bkZ=pxkm*6371/base}
const zv=z=>Array.isArray(z)?bkZ*z[1]:z;
function cam(p){let i=0;while(i<KEYS.length-2&&p>KEYS[i+1][0])i++;const a=KEYS[i],b=KEYS[i+1];const t=ease(Math.max(0,Math.min(1,(p-a[0])/(b[0]-a[0]))));const za=zv(a[3]),zb=zv(b[3]);
  return{lon:a[1]+(b[1]-a[1])*t,lat:a[2]+(b[2]-a[2])*t,z:Math.exp(Math.log(za)+(Math.log(zb)-Math.log(za))*t)}}
const stars=Array.from({length:500},()=>[Math.random(),Math.random(),Math.random()*1.3+.2,Math.random()]);
const proj=d3.geoOrthographic().clipAngle(90).precision(.3);const path=d3.geoPath(proj,ctx);
const sphere={type:'Sphere'};const grat=d3.geoGraticule10();
let prog=0,t0=performance.now(),offCur=null,offY=null;
const vis=(lo,la)=>{const r=proj.rotate();if(d3.geoDistance([lo,la],[-r[0],-r[1]])>Math.PI/2-.02)return null;return proj([lo,la])};
function geoPathRings(rings){ctx.beginPath();rings.forEach(r=>{r.forEach((q,i)=>{const s=proj(q);i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1])});ctx.closePath()})}
function draw(now){
  const p=prog;let c=cam(p);
  // part B seam: glide from the validation framing into the SEA-risk camera instead of cutting
  {const sg=QA+(1-QA)*SB;if(gprog>sg){const f=Math.max(0,Math.min(1,(gprog-sg)/.022));if(f<1){const a=cam(1),e=ease(f);c={lon:a.lon+(c.lon-a.lon)*e,lat:a.lat+(c.lat-a.lat)*e,z:Math.exp(Math.log(a.z)+(Math.log(c.z)-Math.log(a.z))*e)}}}}
  const spin=RM.matches?0:Math.max(0,1-p/.05)*((now-t0)/1000*2.5%360);
  const R=base*c.z;
  let k=0;STEPS.forEach((s,i)=>{if(p>=s[1])k=i});
  const panelLeft=k>0&&document.querySelectorAll('.panel')[k-1]?.classList.contains('l');
  const target=mobile?0:(k===0?W*.2:(panelLeft?1:-1)*W*.17);
  const ty=mobile?(k===0?0:-H*.16):0;
  offCur=RM.matches||offCur==null?target:offCur+(target-offCur)*.07;offY=RM.matches||offY==null?ty:offY+(ty-offY)*.07;
  const cx=W/2+offCur,cy=H/2+offY;
  proj.scale(R).translate([cx,cy]).rotate([-(c.lon+spin),-c.lat,0]);
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.globalCompositeOperation='source-over';ctx.globalAlpha=1;
  ctx.fillStyle='#030507';ctx.fillRect(0,0,W,H);
  const zf=Math.min(1,Math.max(0,(c.z-2)/4));
  ctx.globalAlpha=1-zf;stars.forEach(([x,y,r,a])=>{ctx.fillStyle=`rgba(220,232,240,${.2+a*.6})`;ctx.fillRect(x*W,y*H,r,r)});ctx.globalAlpha=1;
  // sphere
  ctx.beginPath();path(sphere);const og=ctx.createRadialGradient(cx-R*.35,cy-R*.4,R*.05,cx,cy,R);og.addColorStop(0,'#1a2026');og.addColorStop(1,'#07090b');ctx.fillStyle=c.z>5?'#05080b':og;ctx.fill();
  if(c.z<4){ctx.save();ctx.shadowColor='rgba(255,255,255,.9)';ctx.shadowBlur=26*(1-zf);ctx.strokeStyle=`rgba(255,255,255,${.85*(1-zf)})`;ctx.lineWidth=2.5;ctx.beginPath();path(sphere);ctx.stroke();ctx.restore()}
  ctx.beginPath();path(grat);ctx.strokeStyle=`rgba(120,150,170,${.07*(1-zf)})`;ctx.lineWidth=.6;ctx.stroke();
  // globe: faint land dots + population bars split by slum share
  const asiaHL=win(p,.16,.27,.03);
  if(c.z<7){const dA=1-ramp(c.z,4,7);const ds=Math.max(1,R*.004);
    if(asiaHL>0){world.forEach(f=>{if(!(CSA.has(f.id)||ESA.has(f.id)))return;ctx.beginPath();path(f);ctx.fillStyle=`rgba(255,181,71,${.10*asiaHL})`;ctx.fill()})}
    ctx.fillStyle=`rgba(63,162,255,${.32*dA})`;
    for(const [lo,la] of LAND){const s=vis(lo,la);if(!s)continue;ctx.fillRect(s[0]-ds/2,s[1]-ds/2,ds,ds)}
    const barA=dA*(1-ramp(c.z,2.4,4.6));
    if(barA>0){const grow=RM.matches?1:ease(Math.min(1,(now-loadT)/2600));const hs=.62*grow;const lw=Math.max(1.4,R*.0062);
      ctx.save();ctx.globalCompositeOperation='lighter';ctx.lineCap='butt';
      const cool=`rgba(63,162,255,${.42*barA})`;
      for(const [lo,la,m,sh] of POP){const sp=vis(lo,la);if(!sp)continue;const h=Math.sqrt(m)*hs;const dx=sp[0]-cx,dy=sp[1]-cy;
        const tx=cx+dx*(1+h),ty=cy+dy*(1+h);const f=sh<0?0:sh/100;const mx=sp[0]+(tx-sp[0])*f,my=sp[1]+(ty-sp[1])*f;
        ctx.lineWidth=lw;ctx.strokeStyle=cool;ctx.beginPath();ctx.moveTo(mx,my);ctx.lineTo(tx,ty);ctx.stroke();
        if(f>0){ctx.strokeStyle=f>=.4?`rgba(255,60,130,${barA})`:f>=.15?`rgba(255,120,90,${.9*barA})`:`rgba(255,181,71,${.75*barA})`;ctx.beginPath();ctx.moveTo(sp[0],sp[1]);ctx.lineTo(mx,my);ctx.stroke()}
        if(f>=.4&&m>.03){ctx.fillStyle=`rgba(255,200,230,${barA})`;ctx.beginPath();ctx.arc(mx,my,lw*.9,0,7);ctx.fill()}}
      ctx.restore()}
    $('globeKey').style.opacity=barA;
  }else $('globeKey').style.opacity=0;
  // country outlines when nearer
  const outA=ramp(c.z,2.2,5)*(1-ramp(c.z,60,120));
  if(outA>0){ctx.strokeStyle=`rgba(63,210,240,${.22*outA})`;ctx.lineWidth=.7;world.forEach(f=>{if(c.z>4&&['764','116','418','104','458','704'].includes(f.id))return;ctx.beginPath();path(f);ctx.stroke()});
    if(c.z>4)SEA.forEach(f=>{if(f.id==='764')return;ctx.beginPath();path(f);ctx.fillStyle='rgba(20,30,36,.55)';ctx.fill();ctx.strokeStyle=`rgba(63,210,240,${.3*outA})`;ctx.stroke()})}
  // Thailand: dots + provinces
  const thA=ramp(c.z,3.5,6.5);
  if(thA>0&&c.z<400){
    const dotA=thA*(1-ramp(c.z,30,80));const ds=Math.max(1.2,Math.min(3.2,R*.0006));
    ctx.fillStyle=`rgba(47,213,165,${.55*dotA})`;for(const [lo,la] of B.thdots){const s=vis(lo,la);if(s)ctx.fillRect(s[0]-ds/2,s[1]-ds/2,ds,ds)}
    ctx.save();ctx.shadowColor='rgba(63,210,240,.9)';ctx.shadowBlur=6;
    B.prov.forEach(pv=>{ctx.beginPath();path(pv.g);const bkk=pv.n==='Bangkok';if(bkk){ctx.fillStyle=`rgba(154,123,255,${.45*thA*(1-ramp(c.z,40,90))})`;ctx.fill()}ctx.strokeStyle=bkk?`rgba(196,176,255,${thA})`:`rgba(63,210,240,${.55*thA*(1-ramp(c.z,40,120))})`;ctx.lineWidth=bkk?1.6:.8;ctx.stroke()});
    ctx.restore();
    const cityA=win(p,.27,.47,.03);
    if(cityA>0){ctx.font='500 11px "IBM Plex Mono",monospace';ctx.textBaseline='middle';CITIES.forEach(([n,lo,la])=>{const s=vis(lo,la);if(!s)return;ctx.globalAlpha=cityA;ctx.strokeStyle='#e8eef2';ctx.lineWidth=1;ctx.beginPath();ctx.arc(s[0],s[1],4,0,7);ctx.stroke();if(!mobile){ctx.fillStyle='#93a3ad';ctx.fillText(n.toUpperCase()+(p>.385?' · DATA PENDING':''),s[0]+9,s[1])}ctx.globalAlpha=1});
      const s=vis(100.52,13.75);if(s){ctx.globalAlpha=cityA;const r=(now/28)%50;ctx.strokeStyle=`rgba(154,123,255,${1-r/50})`;ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(s[0],s[1],6+r,0,7);ctx.stroke();ctx.fillStyle='#c4b0ff';ctx.font='600 12px "IBM Plex Mono",monospace';ctx.fillText('BANGKOK',s[0]+12,s[1]-12);ctx.globalAlpha=1}}
  }
  // Bangkok
  const bA=ramp(c.z,bkZ*.35,bkZ*.8);
  if(bA>0) drawBangkok(p,c,bA,now);
  // aerial frame
  const aA=ramp(p,.925,.95)*(1-ramp(p,.968,.982));
  if(aA>0) drawAerial(aA,p,now);else $('aerialCap').style.opacity=0;
  // HUD
  const alt=Math.round(36000/c.z);const kmPerPx=6371/R;
  const nice=[1,2,5,10,20,50,100,200,500,1000,2000];const tgt=110*kmPerPx;const nv=nice.filter(v=>v<=tgt).pop()||1;
  $('sbi').style.width=(nv/kmPerPx).toFixed(0)+'px';$('sbt').textContent=nv+' km';$('sbw').style.opacity=c.z>3?1:0;
  const mode=k<5?'GLOBAL':(k===10?'AERIAL':'METRO');
  $('rd').innerHTML=`<span>LAT</span><b>${c.lat.toFixed(3)}°N</b><span>LON</span><b>${((c.lon+spin)%360).toFixed(3)}°E</b><span>VIEW ALT</span><b>≈ ${alt.toLocaleString()} km</b><span>MODE</span><b>${mode}</b>`;
}
function drawBangkok(p,c,bA,now){
  const R=proj.scale();
  ctx.save();ctx.globalAlpha=bA;
  // dark land plate for Bangkok
  ctx.lineJoin='round';
  // districts
  B.dist.forEach(d=>{ctx.beginPath();path(d.g);ctx.fillStyle='rgba(9,16,22,.85)';ctx.fill()});
  // SEA stage: 2569 flood impact by district (BMA) + hazard raster + canals
  const seaA=win(p,.85,.93,.02);
  if(seaA>0){
    ctx.save();ctx.globalAlpha=bA*seaA;
    if(hzImg.complete){const a=proj([BB.w,BB.n]),b=proj([BB.e,BB.s]);ctx.globalAlpha=bA*seaA*.28;ctx.drawImage(hzImg,a[0],a[1],b[0]-a[0],b[1]-a[1]);ctx.globalAlpha=bA*seaA}
    B.dist.forEach(d=>{const v=B.flood69[d.n]||0;if(!v)return;ctx.beginPath();path(d.g);ctx.fillStyle=v===2?'rgba(63,162,255,.72)':'rgba(63,162,255,.36)';ctx.fill()});
    ctx.strokeStyle='rgba(110,200,255,.55)';ctx.lineWidth=.8;ctx.beginPath();B.canals.forEach(l=>{l.forEach((q,i)=>{const s=proj(q);i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1])})});ctx.stroke();
    ctx.strokeStyle='rgba(120,190,255,.9)';ctx.lineWidth=2.2;ctx.beginPath();B.rivers.forEach(l=>{l.forEach((q,i)=>{const s=proj(q);i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1])})});ctx.stroke();
    ctx.restore();
  }
  // communities
  const cA=ramp(p,.49,.52)*(1-.75*ramp(p,.68,.71))*(1-.4*win(p,.85,.93,.02));
  if(cA>0){
    ctx.lineWidth=.7;
    const other=new Path2D(),cong=new Path2D();
    B.comm.forEach(([cg,rings])=>{const P=cg?cong:other;rings.forEach(r=>{r.forEach((q,i)=>{const s=proj(q);i?P.lineTo(s[0],s[1]):P.moveTo(s[0],s[1])});P.closePath()})});
    ctx.globalAlpha=bA*cA;ctx.fillStyle='rgba(93,127,140,.28)';ctx.fill(other);ctx.strokeStyle='rgba(120,160,175,.55)';ctx.stroke(other);
    const recA=win(p,.585,.67,.02);
    ctx.fillStyle=`rgba(255,181,71,${.38+.3*recA})`;ctx.fill(cong);ctx.strokeStyle='rgba(255,200,110,.9)';ctx.stroke(cong);
    ctx.globalAlpha=bA;
  }
  const hA=Math.max(ramp(p,.675,.705)*(1-ramp(p,.94,.96)),ramp(p,.975,.995));
  if(hA>0&&heatImg.complete){const a=proj([BB.w,BB.n]),b=proj([BB.e,BB.s]);ctx.save();ctx.globalCompositeOperation='lighter';ctx.imageSmoothingEnabled=true;ctx.globalAlpha=bA*hA;ctx.drawImage(heatImg,a[0],a[1],b[0]-a[0],b[1]-a[1]);ctx.globalAlpha=bA*hA*.8;ctx.filter='blur(3px)';ctx.drawImage(heatImg,a[0],a[1],b[0]-a[0],b[1]-a[1]);ctx.filter='none';ctx.restore()}
  // district lines
  ctx.save();ctx.shadowColor='rgba(63,210,240,.8)';ctx.shadowBlur=5;ctx.strokeStyle='rgba(63,210,240,.65)';ctx.lineWidth=1;B.dist.forEach(d=>{ctx.beginPath();path(d.g);ctx.stroke()});ctx.restore();
  // outer boundary
  const prov=B.prov.find(x=>x.n==='Bangkok');ctx.beginPath();path(prov.g);ctx.strokeStyle='rgba(232,238,242,.9)';ctx.lineWidth=1.6;ctx.stroke();
  // district labels
  if(!mobile&&p<.93){ctx.font='500 9.5px "IBM Plex Mono",monospace';ctx.fillStyle='rgba(147,163,173,.75)';ctx.textAlign='center';B.dist.forEach(d=>{const s=proj(d.c);ctx.fillText(d.n.toUpperCase(),s[0],s[1])});ctx.textAlign='left'}
  // Baan Mankong
  const bmA=win(p,.49,.68,.02);
  if(bmA>0){ctx.globalAlpha=bA*bmA;ctx.strokeStyle='#2fd5a5';ctx.lineWidth=1.3;B.bm.forEach(q=>{const s=proj(q);ctx.beginPath();ctx.arc(s[0],s[1],3.2,0,7);ctx.stroke()});ctx.globalAlpha=bA}
  // candidates
  const caA=win(p,.70,.85,.02);
  if(caA>0){ctx.globalAlpha=bA*caA;const pulse=RM.matches?0:(Math.sin(now/400)+1)/2;ctx.strokeStyle='#ff8a3d';ctx.lineWidth=1.6;ctx.shadowColor='#ff8a3d';ctx.shadowBlur=8;B.cand.forEach(q=>{const s=proj(q);ctx.beginPath();ctx.arc(s[0],s[1],5+pulse*2,0,7);ctx.stroke()});ctx.shadowBlur=0;ctx.globalAlpha=bA}
  // fire risk
  const fA=win(p,.85,.93,.02);
  if(fA>0){ctx.globalAlpha=bA*fA;ctx.font='600 11px "IBM Plex Mono",monospace';const r0=RM.matches?0:(now/25)%40;
    B.fire.forEach((q,i)=>{const s=proj(q);ctx.strokeStyle=`rgba(255,90,78,${1-r0/40})`;ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(s[0],s[1],7+r0,0,7);ctx.stroke();ctx.fillStyle='#ff5a4e';ctx.beginPath();ctx.arc(s[0],s[1],5,0,7);ctx.fill()});ctx.globalAlpha=bA}
  ctx.restore();
}
function drawAerial(aA,p,now){
  const t=ease(aA);const fw=Math.min(W*.9,H*1.15,1044),fh=fw*798/1044;
  const w=fw*(.25+.75*t),h=fh*(.25+.75*t);const x=(W-w)/2+(mobile?0:(offCur||0)*.4),y=(H-h)/2-(mobile?H*.12:0);
  ctx.save();ctx.fillStyle=`rgba(3,5,7,${.55*t})`;ctx.fillRect(0,0,W,H);
  ctx.globalAlpha=t;if(theosImg.complete)ctx.drawImage(theosImg,x,y,w,h);
  // scan line + grid
  const sy=y+((now/14)%h);ctx.fillStyle='rgba(63,210,240,.18)';ctx.fillRect(x,sy,w,2);
  ctx.strokeStyle='rgba(63,210,240,.85)';ctx.lineWidth=1;ctx.strokeRect(x,y,w,h);
  const L=18;ctx.lineWidth=2;[[x,y,1,1],[x+w,y,-1,1],[x,y+h,1,-1],[x+w,y+h,-1,-1]].forEach(([a,b,sx,sy2])=>{ctx.beginPath();ctx.moveTo(a,b+sy2*L);ctx.lineTo(a,b);ctx.lineTo(a+sx*L,b);ctx.stroke()});
  ctx.restore();
  $('aerialCap').style.opacity=t;
}
// panels/ui
const panels=[...document.querySelectorAll('.panel')].map(el=>({el,a:+el.dataset.in,b:+el.dataset.out}));
const intro=$('intro'),legend=$('legend');
const LV={fl69:[.85,.93],hzl:[.85,.93],dist:[.49,1.1],comm:[.49,1.1],cong:[.49,1.1],bm:[.49,.68],heat:[.68,1.1],cand:[.70,.85],fire:[.85,.93]};
function ui(p){
  const io=1-Math.min(1,p/.04);intro.style.opacity=io;intro.style.visibility=io<=0?'hidden':'visible';intro.style.transform=`translateY(${-(1-io)*40}px)`;
  panels.forEach(({el,a,b})=>{const o=win(p,a,b,.015);el.classList.toggle('on',o>0);el.style.opacity=o;const base=innerWidth<760?'':'translateY(-50%) ';el.style.transform=`${base}translateY(${(1-o)*22}px)`});
  const lA=win(p,.49,1.2,.02)*(1-win(p,.93,.975,.01))*(1-ramp(p,.972,.982));legend.style.opacity=lA;
  // dock the legend on the side without a card, so it never covers the map
  {let best=null,bo=0;panels.forEach(q=>{const o=win(p,q.a,q.b,.015);if(o>bo){bo=o;best=q}});if(best)legend.classList.toggle('dock-r',best.el.classList.contains('l'))}
  const zc=$('zoomCap');if(zc){const zo=win(p,.9235,.944,.006);zc.style.opacity=zo;zc.style.transform=`translate(-50%,-50%) scale(${1+.06*ramp(p,.925,.944)})`}
  legend.querySelectorAll('[data-l]').forEach(d=>{const r=LV[d.dataset.l];d.classList.toggle('off',!(p>=r[0]&&p<=r[1]))});
  let cur=0;DSTEPS.forEach((s,i)=>{if(gprog>=s[1])cur=i});
  [...stepsEl.children].forEach((li,i)=>{const s=DSTEPS[i][1],e=(DSTEPS[i+1]||[0,1])[1];li.firstChild.style.transform=`scaleX(${Math.max(0,Math.min(1,(gprog-s)/(e-s)))})`});
  $('stepL').textContent=`${String(cur).padStart(2,'0')} / ${DSTEPS.length-1} · ${DSTEPS[cur][0]}`;
}
const vy=$('voyage'),vy2=$('voyage2'),stageEl=$('stage');let gprog=0;
const clamp01=x=>Math.max(0,Math.min(1,x));
function readScroll(){const a=vy.getBoundingClientRect(),ih=innerHeight;
  if(!vy2||a.bottom>0){if(stageEl.parentNode!==vy)vy.insertBefore(stageEl,vy.firstChild);gprog=QA*clamp01(-a.top/(a.height-ih))}
  else{if(stageEl.parentNode!==vy2)vy2.appendChild(stageEl);const b=vy2.getBoundingClientRect();gprog=QA+(1-QA)*clamp01(-b.top/(b.height-ih))}
  prog=g2q(gprog)}
let raf=0,running=false;function loop(now){readScroll();ui(prog);draw(now);raf=requestAnimationFrame(loop)}
const visSet=new Set();const io=new IntersectionObserver(es=>{es.forEach(e=>e.isIntersecting?visSet.add(e.target):visSet.delete(e.target));const v=visSet.size>0;if(v&&!running){running=true;raf=requestAnimationFrame(loop)}else if(!v&&running){running=false;cancelAnimationFrame(raf)}});io.observe(vy);if(vy2)io.observe(vy2);
addEventListener('resize',()=>{size();readScroll();ui(prog);draw(performance.now())});
size();readScroll();ui(prog);draw(performance.now());
})();
