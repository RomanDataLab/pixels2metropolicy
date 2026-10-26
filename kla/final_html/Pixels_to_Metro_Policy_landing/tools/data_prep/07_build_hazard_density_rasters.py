import json,math,numpy as np,io,base64,re
from PIL import Image,ImageDraw
from shapely.geometry import shape,Point,LineString,MultiLineString,mapping
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree
from scipy import ndimage
OUT={}
D=json.load(open('/root/geo/ogd/districts.geojson'))['features']
P=json.load(open('/root/geo/ogd/provinces.geojson'))['features']
bkD=[f for f in D if f['properties']['pro_code']=='10']
BKK=unary_union([shape(f['geometry']).buffer(0) for f in bkD])
W0,E0,S0,N0=100.32788911328558,100.9379578268588,13.48698924474914,13.954553421857204
def b64(im,fmt='WEBP',q=82):
    buf=io.BytesIO();im.save(buf,fmt,quality=q,method=6) if fmt=='WEBP' else im.save(buf,fmt,optimize=True);return f'data:image/{fmt.lower()};base64,'+base64.b64encode(buf.getvalue()).decode()
def clipmask(geom,bbox,w,h):
    w0,e0,s0,n0=bbox;m=Image.new('L',(w,h),0);d=ImageDraw.Draw(m)
    polys=[geom] if geom.geom_type=='Polygon' else list(geom.geoms)
    for pg in polys:d.polygon([((x-w0)/(e0-w0)*w,(n0-y)/(n0-s0)*h) for x,y in pg.exterior.coords],fill=255)
    return np.array(m)>0
# ---------- 1. hazard raster (Sawangnate et al. 2022) ----------
src=np.array(Image.open('hazard_src.png').convert('RGB')).astype(int);p=json.load(open('hazard_affine.json'))
Wo,Ho=1100,843
lon=W0+(np.arange(Wo)+.5)/Wo*(E0-W0);lat=N0-(np.arange(Ho)+.5)/Ho*(N0-S0);LO,LA=np.meshgrid(lon,lat)
px=np.clip(np.round(p[0]*LO+p[1]*LA+p[2]).astype(int),0,src.shape[1]-1);py=np.clip(np.round(p[3]*LO+p[4]*LA+p[5]).astype(int),0,src.shape[0]-1)
c=src[py,px]
ref=np.array([[160,10,10],[235,160,20],[90,140,60]]);  # high, moderate, low
d=((c[:,:,None,:]-ref[None,None])**2).sum(3);k=d.argmin(2);sat=(c.max(2)-c.min(2))>70;ok=(d.min(2)<90**2)&sat
wh=ndimage.binary_dilation((src.min(2)>170),iterations=4)
ok&=~wh[py,px]
inb=clipmask(BKK,(W0,E0,S0,N0),Wo,Ho)
# fill line/label pixels by nearest valid class
k=np.where(ok,k,-1)
from scipy import ndimage
idx=ndimage.distance_transform_edt(k<0,return_distances=False,return_indices=True)
k=k[idx[0],idx[1]]
k=ndimage.median_filter(k,size=5)
pal=np.array([[255,72,72,210],[255,170,60,150],[60,200,140,110]],dtype=np.uint8)
rgba=pal[k];rgba[~inb]=0
OUT['hazard']=b64(Image.fromarray(rgba,'RGBA'),'WEBP',85)
Image.fromarray(rgba,'RGBA').save('/tmp/claude-0/hz_out.png')
# per-district shares
hz={}
for f in bkD:
    m=clipmask(shape(f['geometry']).buffer(0),(W0,E0,S0,N0),Wo,Ho)&inb
    v=k[m];n=len(v)
    hz[f['properties']['amp_en']]=[round((v==i).mean()*100,1) for i in range(3)] if n else None
OUT['hazardByDist']=hz
tot=k[inb];print('hazard share H/M/L',[round((tot==i).mean()*100,1) for i in range(3)],'(paper: 50.32/35.41/14.27)')
HZK=k
# ---------- 2. density raster BMR (Urban TH, DOPA 2564) ----------
src=np.array(Image.open('density_src.png').convert('RGB')).astype(float);p=json.load(open('density_affine.json'))
ys=[322,336,350,364,378,392,406,420,434,448,462,476,490,504,518]
sw=np.array([np.median(src[y-1:y+2,19:27].reshape(-1,3),0) for y in ys])
BMRc=['10','12','13','11','74','73']
BMR=unary_union([shape(f['geometry']).buffer(0) for f in P if f['properties']['pro_code'] in BMRc])
bw,bs,be,bn=BMR.bounds;MB=(round(bw,4),round(be,4),round(bs,4),round(bn,4));OUT['bmrBox']=MB
Wd=900;Hd=int(Wd*(bn-bs)/(be-bw))
lon=bw+(np.arange(Wd)+.5)/Wd*(be-bw);lat=bn-(np.arange(Hd)+.5)/Hd*(bn-bs);LO,LA=np.meshgrid(lon,lat)
fx=p[0]*LO+p[1]*LA+p[2];fy=p[3]*LO+p[4]*LA+p[5]
c=ndimage.map_coordinates(src.transpose(2,0,1),[np.stack([fy]*3),np.stack([fx]*3)] if False else [fy,fx],order=0) if False else src[np.clip(np.round(fy).astype(int),0,src.shape[0]-1),np.clip(np.round(fx).astype(int),0,src.shape[1]-1)]
d=((c[:,:,None,:]-sw[None,None])**2).sum(3);k=d.argmin(2);ok=d.min(2)<40**2
k=np.where(ok,k,-1);idx=ndimage.distance_transform_edt(k<0,return_distances=False,return_indices=True);k=k[idx[0],idx[1]]
k=ndimage.median_filter(k,size=5)
inb=clipmask(BMR,(bw,be,bs,bn),Wd,Hd)
import matplotlib
ramp=(np.array(matplotlib.colormaps['magma'](np.linspace(.12,.98,15)))*255).astype(np.uint8)
ramp[:,3]=np.linspace(70,235,15).astype(np.uint8)
rgba=ramp[k];rgba[~inb]=0
OUT['density']=b64(Image.fromarray(rgba,'RGBA'),'WEBP',85)
OUT['densityRamp']=[ '#%02x%02x%02x'%tuple(r[:3]) for r in ramp]
Image.fromarray(rgba,'RGBA').save('/tmp/claude-0/dn_out.png')
OUT['densityClasses']=[[31,300],[301,400],[401,500],[501,600],[601,700],[701,800],[801,900],[901,1000],[1001,2000],[2001,3000],[3001,4000],[4001,5000],[5001,10000],[10001,15000],[15001,23000]]
OUT['densityByDist']=json.load(open('density_by_district.json'))
json.dump(OUT,open('layers_raster.json','w'))
print('ok', {k:len(v) if isinstance(v,str) else '' for k,v in OUT.items()})
