exec(open('georef.py').read())
def mk(im):
    m=(im.sum(2)<170)
    m[:45,:]=0;m[800:,:]=0;m[:,:140]=0;m[:,1185:]=0
    m[585:,440:]=0      # district name list
    m[480:580,840:1060]=0  # legend
    m[:150,:120]=0
    # remove numbered label circles: white circles with dark outline -> keep (small effect)
    return m
bk=[f for f in D if f['properties']['pro_code']=='10']
p,m=fit('hazard_src.png',mk,bk,(146,49,1110,806),step=.0015)
json.dump(list(p),open('hazard_affine.json','w'));print(p)
# overlay check
im=Image.open('hazard_src.png').convert('RGB');from PIL import ImageDraw;d=ImageDraw.Draw(im)
for f in bk:
    for r in rings(f['geometry']):
        xy=[(p[0]*x+p[1]*y+p[2],p[3]*x+p[4]*y+p[5]) for x,y in r];d.line(xy,fill=(0,255,255),width=2)
im.save('/tmp/claude-0/hz_check.png')
