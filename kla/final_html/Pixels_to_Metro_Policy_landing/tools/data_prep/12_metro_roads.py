"""Expressways and highways for the metropolitan map (bkk.metro.roads).

Source: Natural Earth 10m roads (public domain), https://github.com/nvkelso/natural-earth-vector (geojson/ne_10m_roads.geojson).
Clipped to 99.75-102.05 E, 13.3-14.45 N; classes: 2 = expressway, 1 = main highway (scalerank <= 5), 0 = other highway.
Coarse (about 1:10M); good for showing how the provinces connect, not for routing.
"""
import json,sys
src=sys.argv[1] if len(sys.argv)>1 else 'ne_10m_roads.geojson'
W,E,S,N=99.75,102.05,13.3,14.45
inb=lambda q:W<=q[0]<=E and S<=q[1]<=N
out=[]
for f in json.load(open(src))['features']:
    p,g=f['properties'],f['geometry']
    if not g:continue
    for ln in (g['coordinates'] if g['type']=='MultiLineString' else [g['coordinates']]):
        seg=[]
        for q in ln+[[999,999]]:
            if inb(q):seg.append([round(q[0],3),round(q[1],3)])
            else:
                if len(seg)>1:out.append([2 if p.get('expressway') else (1 if p['scalerank']<=5 else 0),seg])
                seg=[]
b=json.load(open('data/bkk.json'));b['metro']['roads']=out
json.dump(b,open('data/bkk.json','w'),ensure_ascii=False,separators=(',',':'))
print(len(out),'road lines')
