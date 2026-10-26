from PIL import Image
import numpy as np, json, math, io, base64
from scipy import ndimage
from shapely.geometry import shape, mapping
import matplotlib
W0,E0,S0,N0=100.32788911328558,100.9379578268588,13.48698924474914,13.954553421857204
my=lambda la: math.log(math.tan(math.pi/4+math.radians(la)/2))
MS,MN=my(S0),my(N0)
def geo(px,py,bb):
    x0,x1,y0,y1=bb
    lon=W0+(px-x0)/(x1-x0)*(E0-W0)
    m=MN-(py-y0)/(y1-y0)*(MN-MS)
    lat=math.degrees(2*math.atan(math.exp(m))-math.pi/2)
    return round(lon,5),round(lat,5)
out={}
# heat
a=np.array(Image.open('x/ppt/media/image5.png').convert('RGB')).astype(np.int32)
bb=(413,2398,257,1824)
crop=a[bb[2]:bb[3]+1,bb[0]:bb[1]+1]
dark=(crop.sum(2)<260)&(np.abs(crop[:,:,0]-crop[:,:,2])<45)
lab,k=ndimage.label(dark,structure=np.ones((3,3)));sizes=ndimage.sum(dark,lab,range(1,k+1))
outline=ndimage.binary_dilation(lab==(np.argmax(sizes)+1),iterations=3)
lut=(np.array(matplotlib.colormaps['magma_r'](np.linspace(0,1,256)))[:,:3]*255).astype(np.int32)
flat=crop.reshape(-1,3)
# nearest lut index (chunked)
idx=np.empty(len(flat),np.int32);dmin=np.empty(len(flat))
for i in range(0,len(flat),200000):
    d=((flat[i:i+200000,None,:]-lut[None])**2).sum(2);idx[i:i+200000]=d.argmin(1);dmin[i:i+200000]=d.min(1)
t=(idx/255.).reshape(crop.shape[:2]);dm=dmin.reshape(crop.shape[:2])
bg=(np.abs(crop-np.array([247,247,244])).sum(2)<18)
valid=(~bg)&(~outline)&(dm<3000)
sy0,sy1,sx0,sx1=1740-257,1830-257,420-413,820-413
valid[sy0:sy1,sx0:sx1]=False
valid[0:260,1880:]=False
t=np.where(valid,t,0)
A=np.clip((t-.03)*1.9,0,1)**.6
# colour ramp violet
c0=np.array([110,70,255]);c1=np.array([236,214,255])
rgb=(c0[None,None]*(1-t[...,None])+c1[None,None]*t[...,None])
img=np.dstack([rgb,A*255]).astype(np.uint8)
im=Image.fromarray(img,'RGBA');im=im.resize((1300,int(1300*im.height/im.width)),Image.LANCZOS)
buf=io.BytesIO();im.save(buf,'PNG',optimize=True);print('heat png',len(buf.getvalue()))
out['heat']='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
im.save('heat_preview.png')
# candidates
b=np.array(Image.open('x/ppt/media/image4.png').convert('RGB')).astype(int)
red=(b[:,:,0]>170)&(b[:,:,1]<110)&(b[:,:,2]<90)
lab,k=ndimage.label(ndimage.binary_closing(red,iterations=2))
objs=ndimage.find_objects(lab);areas=ndimage.sum(red,lab,range(1,k+1))
cents=ndimage.center_of_mass(red,lab,range(1,k+1))
bb4=(417,2489,259,1896)
inside=[(c,ar) for c,ar in zip(cents,areas) if bb4[0]<c[1]<bb4[1] and bb4[2]<c[0]<bb4[3] and ar>20]
med=np.median([ar for c,ar in inside]);print('components',len(inside),'median area',med,'est circles',sum(max(1,round(ar/med)) for c,ar in inside))
out['cand']=[list(geo(c[1],c[0],bb4))+[int(max(1,round(ar/med)))] for c,ar in inside]
json.dump(out,open('rasters.json','w'))
