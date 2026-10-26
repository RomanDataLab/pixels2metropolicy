import json,math,numpy as np
from shapely.geometry import shape,Point,LineString,Polygon,MultiLineString
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely.prepared import prep
B=json.load(open('/home/claude/voyage/bkk.json'));V=json.load(open('layers_vec.json'));R=json.load(open('layers_raster.json'))
KX,KY=108.1*1000,110.6*1000
def m(x,y):return (x*KX,y*KY)
def L(c):return LineString([m(*p) for p in c])
canal=unary_union([L(c) for c in V['canals']]+[L(c) for c in V['rivers']])
rail=unary_union([L(c) for c in V['rail']])
stations=[Point(m(s[0],s[1])) for v in V['transit'].values() for s in v]
st_tree=STRtree(stations)
D=json.load(open('/root/geo/ogd/districts.geojson'))['features']
bkD=[f for f in D if f['properties']['pro_code']=='10']
BKK=unary_union([shape(f['geometry']).buffer(0) for f in bkD])
# unique communities
seen={};
for i,(cg,rings) in enumerate(B['comm']):
    name,dist=B['info'][i][0],B['info'][i][1]
    key=(name,dist)
    if key in seen:continue
    poly=Polygon(rings[0]);c=poly.representative_point() if poly.is_valid and not poly.is_empty else Point(rings[0][0])
    seen[key]=(cg,c.x,c.y,dist)
comm=list(seen.values());print('unique',len(comm),'congested',sum(c[0] for c in comm))
rng=np.random.default_rng(7);pb=prep(BKK);x0,y0,x1,y1=BKK.bounds;rand=[]
while len(rand)<3000:
    x,y=rng.uniform(x0,x1),rng.uniform(y0,y1)
    if pb.contains(Point(x,y)):rand.append((x,y))
cb=prep(canal.buffer(100));rb=prep(rail.buffer(300))
def stats(pts):
    P=[Point(m(x,y)) for x,y in pts]
    c=np.mean([cb.contains(p) for p in P])*100
    r=np.mean([rb.contains(p) for p in P])*100
    s=np.mean([p.distance(stations[st_tree.nearest(p)])<800 for p in P])*100
    dc=np.median([p.distance(canal) for p in P])
    return dict(canal100=round(c,1),rail300=round(r,1),station800=round(s,1),medCanal=round(dc))
G={'congested':[(c[1],c[2]) for c in comm if c[0]],'other':[(c[1],c[2]) for c in comm if not c[0]],'random':rand}
PROX={k:stats(v) for k,v in G.items()};print(json.dumps(PROX,indent=0))
# flood 2569 by type
f69=V['flood69'];f54=V['flood54']
def fl(sel,F):
    v=[F.get(c[3],0) for c in comm if c[0]==sel];return [round(np.mean(np.array(v)==k)*100,1) for k in (2,1,0)]
FLD={'cong69':fl(1,f69),'other69':fl(0,f69),'cong54':fl(1,f54)}
# counts of congested communities by flood69 level
cnt69=[sum(1 for c in comm if c[0] and f69.get(c[3],0)==k) for k in (2,1,0)]
FLD['cong69n']=cnt69;print('flood',FLD)
# east vs west of Chao Phraya: use river? approximate by district list (Thonburi side)
thon=set('Bangkok Noi,Bangkok Yai,Bang Phlat,Thon Buri,Khlong San,Chom Thong,Rat Burana,Thung Khru,Bang Khun Thian,Bang Bon,Bang Khae,Phasi Charoen,Nong Khaem,Taling Chan,Thawi Watthana'.split(','))
side=lambda d:'west' if d in thon else 'east'
ew={s:{'districts':0,'high69':0,'med69':0} for s in ('east','west')}
for d,v in f69.items():
    s=side(d);ew[s]['districts']+=1;ew[s]['high69']+=v==2;ew[s]['med69']+=v==1
print('east/west',ew)
# hazard class at community points
W0,E0,S0,N0=100.32788911328558,100.9379578268588,13.48698924474914,13.954553421857204
from PIL import Image;import io,base64
hz=Image.open(io.BytesIO(base64.b64decode(R['hazard'].split(',')[1]))).convert('RGBA');H=np.array(hz)
def hcls(x,y):
    i=int((N0-y)/(N0-S0)*H.shape[0]);j=int((x-W0)/(E0-W0)*H.shape[1])
    if not(0<=i<H.shape[0] and 0<=j<H.shape[1]):return None
    r,g,b,a=H[i,j]
    if a==0:return None
    return 0 if r>230 and g<120 else (1 if r>200 else 2)
HZ={}
for k,v in G.items():
    cl=[hcls(x,y) for x,y in v];cl=[c for c in cl if c is not None]
    HZ[k]=[round(np.mean(np.array(cl)==i)*100,1) for i in range(3)]
print('hazard',HZ)
# density class by type
den=R['densityByDist'];
def dmid(d):
    v=den.get(d);return None if v is None else (v[0]+v[1])/2
DEN={'congested':np.median([dmid(c[3]) for c in comm if c[0] and dmid(c[3])]),'other':np.median([dmid(c[3]) for c in comm if not c[0] and dmid(c[3])])}
print('density median class mid',DEN)
json.dump({'prox':PROX,'flood':FLD,'eastwest':ew,'hazard':HZ,'nComm':[sum(c[0] for c in comm),sum(1-c[0] for c in comm)]},open('analytics.json','w'))
# ---- per-polygon extras for cards
ext=[]
for i,(cg,rings) in enumerate(B['comm']):
    x,y=B['info'][i][3],B['info'][i][4];p=Point(m(x,y))
    ext.append([f69.get(B['info'][i][1],0),hcls(x,y) if hcls(x,y) is not None else -1,int(round(p.distance(canal))),int(round(p.distance(stations[st_tree.nearest(p)])))])
json.dump(ext,open('ext.json','w'),separators=(',',':'))
print('ext',len(ext),ext[:3])
