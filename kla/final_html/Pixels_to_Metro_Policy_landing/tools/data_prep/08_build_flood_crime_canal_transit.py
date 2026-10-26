import json,math,numpy as np,re
from shapely.geometry import shape,Point,LineString,MultiLineString,Polygon
from shapely.ops import unary_union,transform
from shapely.strtree import STRtree
D=json.load(open('/root/geo/ogd/districts.geojson'))['features']
bkD=[f for f in D if f['properties']['pro_code']=='10']
th2en={f['properties']['amp_th']:f['properties']['amp_en'] for f in bkD}
BKK=unary_union([shape(f['geometry']).buffer(0) for f in bkD])
OUT={}
norm=lambda s:s.replace('ษฏ','ษฎ').strip()
T={norm(k):v for k,v in th2en.items()}
def en(th):
    th=norm(th)
    if th in T:return T[th]
    raise KeyError(th)
# ---- flood 2569 (BMA via Rocket Media Lab) and 2554
F69={'high':'คลองสามวา คันนายาว จตุจักร บางกะปิ บางเขน บึงกุ่ม ประเวศ มีนบุรี ลาดกระบัง วังทองหลาง สวนหลวง สะพานสูง สายไหม หนองจอก หลักสี่',
     'med':'ดอนเมือง ดินแดง ดุสิต ทวีวัฒนา ทุ่งครุ บางซื่อ บางนา บางบอน บางพลัด พญาไท พระโขนง ราชเทวี วัฒนา ห้วยขวาง'}
F54={'high':'คลองสามวา จตุจักร ดอนเมือง ตลิ่งชัน ทวีวัฒนา บางเขน บางแค บางพลัด ภาษีเจริญ สายไหม หนองแขม หลักสี่',
     'med':'คลองเตย คันนายาว จอมทอง ดินแดง ดุสิต ธนบุรี บางกอกน้อย บางกอกใหญ่ บางกะปิ บางขุนเทียน บางคอแหลม บางซื่อ บางบอน บางรัก บึงกุ่ม ประเวศ พระโขนง พระนคร มีนบุรี ยานนาวา ลาดกระบัง ลาดพร้าว สะพานสูง สัมพันธวงศ์ หนองจอก ห้วยขวาง'}
def lvl(F):
    r={f['properties']['amp_en']:0 for f in bkD}
    for k,v in F.items():
        for t in v.split():r[en(t)]=2 if k=='high' else 1
    return r
OUT['flood69']=lvl(F69);OUT['flood54']=lvl(F54)
print('2569 high',sum(v==2 for v in OUT['flood69'].values()),'med',sum(v==1 for v in OUT['flood69'].values()))
# ---- crime risk spots (BMA 2564 via Rocket Media Lab), partial
CR={'บางรัก':23,'คลองสาน':22,'หนองจอก':20,'ดอนเมือง':18,'บางบอน':17,'ห้วยขวาง':3,'ธนบุรี':3,'ทวีวัฒนา':4,'มีนบุรี':4,'วังทองหลาง':4,'สาทร':4,'สายไหม':4,'ดุสิต':5,'บางกอกใหญ่':5,'พญาไท':5,'สวนหลวง':5,'วัฒนา':2}
OUT['crime']={en(k):v for k,v in CR.items()}
# ---- canals & rivers (OSM via waterway-bkk)
WW=json.load(open('/root/geo/wx_waterway-bkk/public/data/waterways-bkk.json'))['features']
def simp(coords,tol=.00025):
    g=LineString(coords).simplify(tol);return [[round(x,4),round(y,4)] for x,y in g.coords]
can=[];riv=[]
for f in WW:
    t=f['properties'].get('t');c=f['geometry']['coordinates']
    if len(c)<2:continue
    L=LineString(c)
    if t=='canal' and L.length>0.004:can.append(simp(c))
    elif t=='river':riv.append(simp(c,.0002))
OUT['canals']=can;OUT['rivers']=riv
print('canals',len(can),'rivers',len(riv))
# ---- mass transit from metro-fare stations (order by station id within line)
import subprocess
st=json.load(open('/root/geo/metro-fare/src/data/station.json'))
from collections import defaultdict
lines=defaultdict(list)
for s in st:lines[s['lineType']].append(s)
def keyf(s):
    m=re.match(r'([A-Z]*)(\d+)',s['id']);return (m.group(1),int(m.group(2))) if m else (s['id'],0)
TR={}
for lt,ss in lines.items():
    ss=sorted(ss,key=keyf)
    if lt=='BTS_SUKHUMVIT':
        n=[s for s in ss if s['id'].startswith('N')];e=[s for s in ss if s['id'].startswith('E')];cen=[s for s in ss if s['id']=='CEN']
        ss=list(reversed(n))+cen+e
    if lt=='BTS_SILOM':
        w=[s for s in ss if s['id'].startswith('W')];s_=[s for s in ss if s['id'].startswith('S')];cen=[s for s in st if s['id']=='CEN'][:1]
        ss=w+cen+s_
    TR[lt]=[[round(s['position'][1],5),round(s['position'][0],5),s['nameEN']] for s in ss]
OUT['transit']=TR
print({k:len(v) for k,v in TR.items()})
# ---- mainline rail (Natural Earth 10m)
NR=json.load(open('/root/geo/ne_10m_railroads.geojson'))['features']
W,E,S,N=100.2,101.2,13.4,14.2
rail=[]
for f in NR:
    g=shape(f['geometry']);gs=[g] if g.geom_type=='LineString' else list(g.geoms)
    for l in gs:
        c=[[round(x,4),round(y,4)] for x,y in l.coords if W<x<E and S<y<N]
        if len(c)>1:rail.append(c)
OUT['rail']=rail;print('rail parts',len(rail))
json.dump(OUT,open('layers_vec.json','w'),ensure_ascii=False,separators=(',',':'))
