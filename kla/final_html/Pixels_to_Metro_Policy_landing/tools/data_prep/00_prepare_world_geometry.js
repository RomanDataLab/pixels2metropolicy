const tc=require('./tc/package/dist/topojson-client.js');
const fs=require('fs');
const t10=JSON.parse(fs.readFileSync('wa/package/countries-10m.json'));
const fc=tc.feature(t10,t10.objects.countries);
const ids=new Set(['764','116','418','104','458','704']);
const r=x=>Math.round(x*500)/500;
function simp(ring){const o=[];let last=null;for(const p of ring){const q=[r(p[0]),r(p[1])];if(!last||q[0]!==last[0]||q[1]!==last[1]){o.push(q);last=q}}return o}
const out=fc.features.filter(f=>ids.has(f.id)).map(f=>{const g=f.geometry;const polys=g.type==='Polygon'?[g.coordinates]:g.coordinates;
 const keep=polys.map(p=>p.map(simp).filter(r=>r.length>3)).filter(p=>p.length&&p[0].some(q=>q[1]<24&&q[1]>-2&&q[0]>90&&q[0]<112));
 return {type:'Feature',id:f.id,properties:{name:f.properties.name},geometry:{type:'MultiPolygon',coordinates:keep}}});
fs.writeFileSync('sea10.json',JSON.stringify({type:'FeatureCollection',features:out}));
fs.copyFileSync('wa/package/countries-110m.json','w110.json');
const t110=JSON.parse(fs.readFileSync('w110.json'));
console.log(t110.objects.countries.geometries.slice(0,3).map(g=>[g.id,g.properties]));
