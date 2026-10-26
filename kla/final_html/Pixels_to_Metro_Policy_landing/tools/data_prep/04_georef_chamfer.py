import json,numpy as np,math
from PIL import Image
from scipy import ndimage,optimize
from shapely.geometry import shape
D=json.load(open('/root/geo/ogd/districts.geojson'))['features']
P=json.load(open('/root/geo/ogd/provinces.geojson'))['features']
def rings(g):
    g=shape(g).buffer(0);polys=[g] if g.geom_type=='Polygon' else list(g.geoms)
    out=[]
    for p in polys:
        c=np.array(p.exterior.coords);out.append(c)
    return out
def densify(r,step):
    pts=[]
    for a,b in zip(r[:-1],r[1:]):
        n=max(1,int(np.hypot(*(b-a))/step));pts+= [a+(b-a)*t for t in np.arange(n)/n]
    return np.array(pts)
def fit(img_path,line_mask_fn,features,bbox_px,step=.002,crop=None):
    im=np.array(Image.open(img_path).convert('RGB')).astype(int)
    m=line_mask_fn(im)
    if crop is not None:
        x0,y0,x1,y1=crop;mm=np.zeros_like(m);mm[y0:y1,x0:x1]=m[y0:y1,x0:x1];m=mm
    dt=ndimage.distance_transform_edt(~m)
    pts=np.concatenate([densify(r,step) for f in features for r in rings(f['geometry'])])
    lo0,la0=pts[:,0].min(),pts[:,1].max();lo1,la1=pts[:,0].max(),pts[:,1].min()
    X0,Y0,X1,Y1=bbox_px
    # params: px = a*lon + b*lat + c ; py = d*lon + e*lat + f
    a=(X1-X0)/(lo1-lo0);e=(Y1-Y0)/(la1-la0)
    p0=np.array([a,0,X0-a*lo0,0,e,Y0-e*la0])
    H,Wd=dt.shape
    def cost(p):
        px=p[0]*pts[:,0]+p[1]*pts[:,1]+p[2];py=p[3]*pts[:,0]+p[4]*pts[:,1]+p[5]
        ix=np.clip(px,0,Wd-1);iy=np.clip(py,0,H-1)
        d=ndimage.map_coordinates(dt,[iy,ix],order=1)
        return np.mean(np.minimum(d,12))
    best=None
    for s in [1.0]:
        r=optimize.minimize(cost,p0,method='Powell',options={'maxiter':20000,'xtol':1e-3,'ftol':1e-4})
        r=optimize.minimize(cost,r.x,method='Nelder-Mead',options={'maxiter':20000,'xatol':1e-3,'fatol':1e-5})
        best=r
    print(img_path,'cost init',round(cost(p0),2),'final',round(best.fun,2))
    return best.x,m
