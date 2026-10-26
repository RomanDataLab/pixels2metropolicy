import re,json,numpy as np,collections
exec(open('parse.py').read().split("D={};comm=[];pts=[]")[0])  # reuse helpers fill,xfrm,rings
dist=json.load(open('/root/geo/ogd/districts.geojson'))
bk={f['properties']['amp_th']:f for f in dist['features'] if f['properties']['pro_code']=='10'}
def gcen(f):
    g=f['geometry'];polys=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
    a=np.concatenate([np.array(p[0]) for p in polys]);return a.mean(0)
out={}
for n in [7,8]:
    s=open(f'x/ppt/slides/slide{n}.xml').read()
    sps=re.findall(r'<p:sp>.*?</p:sp>',s,re.S)
    A=[];B=[];ovals=[];texts=[]
    for sp in sps:
        name=re.search(r'name="([^"]*)"',sp).group(1)
        nm=name.replace('เขต','',1)
        if 'custGeom' in sp and nm in bk:
            rs=rings(sp);a=np.concatenate([np.array(r) for r in rs]).mean(0);A.append(a);B.append(gcen(bk[nm]))
        elif 'ellipse' in sp:
            ox,oy,cx,cy=xfrm(sp);t=''.join(re.findall(r'<a:t>([^<]*)</a:t>',sp));ovals.append((fill(sp),cx,ox+cx/2,oy+cy/2,t))
        elif '<a:t>' in sp:
            ox,oy,cx,cy=xfrm(sp);t=''.join(re.findall(r'<a:t>([^<]*)</a:t>',sp));texts.append((t,ox+cx/2,oy+cy/2))
    A=np.array(A);B=np.array(B);X=np.c_[A,np.ones(len(A))];M=np.linalg.lstsq(X,B,rcond=None)[0]
    print('slide',n,'districts',len(A),'max err',np.abs(X@M-B).max())
    tf=lambda x,y:(np.array([x,y,1])@M).round(5).tolist()
    print(collections.Counter((o[0],o[1]) for o in ovals).most_common(8))
    big=[o for o in ovals if o[1]>ovals[0][1]*1.5 or o[4]]
    for o in sorted(ovals,key=lambda o:-o[1])[:16]:print(o[0],o[1],o[4],tf(o[2],o[3]))
    out[n]={'big':[(o[0],o[4],tf(o[2],o[3])) for o in sorted(ovals,key=lambda o:-o[1])[:16]],'texts':[(t,tf(x,y)) for t,x,y in texts if re.fullmatch(r'\d{1,2}',t.strip())]}
    print('digit texts',out[n]['texts'])
json.dump(out,open('risk.json','w'),ensure_ascii=False)
