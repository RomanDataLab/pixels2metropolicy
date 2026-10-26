exec(open('georef.py').read())
def mk(im):
    m=(im.sum(2)<200)
    m[:95,:]=0;m[455:,:]=0;m[:,:95]=0
    for (x0,y0,x1,y1) in [(290,255,345,300),(380,315,480,340),(380,380,460,400),(185,405,260,430),(135,270,195,292),(415,195,470,215),(340,310,370,335)]:
        m[y0:y1,x0:x1]=0
    return m
codes=['10','12','13','11','74','73']
feat=[f for f in P if f['properties']['pro_code'] in codes]
bk=[f for f in P if f['properties']['pro_code']=='10']
# init from Bangkok bbox
import numpy as np
exec_init=True
p,m=fit('density_src.png',mk,bk,(253,232,528,447),step=.004)
# refine with all provinces from p
pts_all=feat
def refit(p0):
    im=np.array(Image.open('density_src.png').convert('RGB')).astype(int);mm=mk(im);dt=ndimage.distance_transform_edt(~mm)
    pts=np.concatenate([densify(r,.004) for f in feat for r in rings(f['geometry'])])
    H,Wd=dt.shape
    def cost(p):
        px=p[0]*pts[:,0]+p[1]*pts[:,1]+p[2];py=p[3]*pts[:,0]+p[4]*pts[:,1]+p[5]
        inside=(px>95)&(px<Wd)&(py>95)&(py<455)
        d=ndimage.map_coordinates(dt,[np.clip(py,0,H-1),np.clip(px,0,Wd-1)],order=1)
        return np.mean(np.minimum(d[inside],10)) if inside.sum()>100 else 99
    r=optimize.minimize(cost,p0,method='Powell',options={'maxiter':20000});r=optimize.minimize(cost,r.x,method='Nelder-Mead',options={'maxiter':20000})
    print('refit',cost(p0),r.fun);return r.x
p=refit(p)
json.dump(list(p),open('density_affine.json','w'));print(p)
im=Image.open('density_src.png').convert('RGB').resize((1108,1108));from PIL import ImageDraw;d=ImageDraw.Draw(im)
for f in feat+[x for x in D if x['properties']['pro_code']=='10']:
    for r in rings(f['geometry']):
        xy=[(2*(p[0]*x+p[1]*y+p[2]),2*(p[3]*x+p[4]*y+p[5])) for x,y in r];d.line(xy,fill=(0,255,0),width=2)
im.save('/tmp/claude-0/d_check.png')
