import re,json,numpy as np
s=open('x/ppt/slides/slide3.xml').read()
sps=re.findall(r'<p:sp>.*?</p:sp>',s,re.S)
def fill(sp):
    m=re.search(r'<p:spPr>(.*?)</p:spPr>',sp,re.S).group(1)
    f=re.search(r'^(?:<a:xfrm>.*?</a:xfrm>)?(?:<a:custGeom>.*?</a:custGeom>|<a:prstGeom.*?</a:prstGeom>)?\s*<a:solidFill><a:srgbClr val="(\w+)"',m,re.S)
    return f.group(1) if f else None
def xfrm(sp):
    o=re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"/><a:ext cx="(\d+)" cy="(\d+)"/>',sp)
    return [int(v) for v in o.groups()]
def rings(sp):
    ox,oy,cx,cy=xfrm(sp);out=[]
    for pm in re.finditer(r'<a:path w="(\d+)" h="(\d+)"[^>]*>(.*?)</a:path>',sp,re.S):
        w,h=int(pm.group(1)),int(pm.group(2));body=pm.group(3)
        cur=[]
        for cmd in re.finditer(r'<a:(moveTo|lnTo|close)\b[^>]*?(?:/>|>(.*?)</a:\1>)',body,re.S):
            if cmd.group(1)=='close':
                if len(cur)>2:out.append(cur)
                cur=[];continue
            pt=re.search(r'x="(-?\d+)" y="(-?\d+)"',cmd.group(2));x,y=int(pt.group(1)),int(pt.group(2))
            P=(ox+x*cx/max(w,1),oy+y*cy/max(h,1))
            if cmd.group(1)=='moveTo':
                if len(cur)>2:out.append(cur)
                cur=[P]
            else:cur.append(P)
        if len(cur)>2:out.append(cur)
    return out
D={};comm=[];pts=[]
for sp in sps:
    name=re.search(r'name="([^"]*)"',sp).group(1);f=fill(sp)
    if 'custGeom' in sp and f=='EBEEE8':D[name.replace('ขอบเขตเขต','')]=rings(sp)
    elif 'custGeom' in sp and f in('DED5C5','F2C8AD'):comm.append((name,f=='F2C8AD',rings(sp)))
    elif 'ellipse' in sp and f in('217E86','BD481D'):
        ox,oy,cx,cy=xfrm(sp);pts.append((f=='BD481D',ox+cx/2,oy+cy/2,name))
print(len(D),len(comm),len(pts),sum(1 for c in comm if c[1]))
dist=json.load(open('/root/geo/ogd/districts.geojson'))
bk={f['properties']['amp_th']:f for f in dist['features'] if f['properties']['pro_code']=='10'}
def cen(rs):
    a=np.concatenate([np.array(r) for r in rs]);return a.mean(0)
def gcen(f):
    g=f['geometry'];polys=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
    a=np.concatenate([np.array(p[0]) for p in polys]);return a.mean(0)
A=[];B=[];miss=[]
for n,rs in D.items():
    if n in bk:A.append(cen(rs));B.append(gcen(bk[n]))
    else:miss.append(n)
print('matched',len(A),'miss',miss)
A=np.array(A);B=np.array(B)
X=np.c_[A,np.ones(len(A))]
M,res,_,_=np.linalg.lstsq(X,B,rcond=None)
pred=X@M;err=np.abs(pred-B).max(0);print('max err deg',err,'mean',np.abs(pred-B).mean(0))
tf=lambda p:(np.array([p[0],p[1],1])@M).round(5).tolist()
out={'comm':[[c[0],1 if c[1] else 0,[[tf(p) for p in r] for r in c[2]]] for c in comm],
     'bm':[tf((x,y)) for r,x,y,n in pts if not r],'fire':[tf((x,y)) for r,x,y,n in pts if r]}
json.dump(out,open('bkk_layers.json','w'),ensure_ascii=False)
import os;print(os.path.getsize('bkk_layers.json'))
