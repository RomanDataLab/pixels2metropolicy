import json
csv='''บางกะปิ,11,21,32
ลาดกระบัง,13,17,30
บางขุนเทียน,7,22,29
ประเวศ,10,14,24
บางเขน,10,10,20
มีนบุรี,11,8,19
บางซื่อ,3,15,18
วังทองหลาง,6,12,18
บางแค,8,9,17
บางบอน,7,10,17
ภาษีเจริญ,11,6,17
หนองจอก,11,6,17
คลองเตย,6,10,16
บางกอกน้อย,8,8,16
บางพลัด,8,8,16
พระโขนง,7,9,16
ดอนเมือง,10,4,14
ตลิ่งชัน,5,9,14
พระนคร,3,11,14
สวนหลวง,7,7,14
ห้วยขวาง,5,9,14
คลองสามวา,7,6,13
จตุจักร,5,8,13
ทุ่งครุ,4,9,13
วัฒนา,6,7,13
สายไหม,8,5,13
หนองแขม,6,7,13
จอมทอง,4,8,12
ยานนาวา,3,9,12
ราชเทวี,6,6,12
บึงกุ่ม,6,5,11
ดินแดง,7,3,10
ทวีวัฒนา,5,5,10
ธนบุรี,6,4,10
ราษฎร์บูรณะ,4,6,10
สาทร,4,6,10
คลองสาน,4,5,9
บางคอแหลม,4,5,9
บางรัก,3,5,8
ลาดพร้าว,4,4,8
คันนายาว,2,5,7
บางกอกใหญ่,2,5,7
หลักสี่,3,4,7
ดุสิต,4,2,6
บางนา,1,5,6
ปทุมวัน,1,5,6
พญาไท,3,3,6
สะพานสูง,4,2,6
ป้อมปราบศัตรูพ่าย,1,2,3
สัมพันธวงศ์,1,1,2'''
D=json.load(open('/root/geo/ogd/districts.geojson'))['features']
th2en={f['properties']['amp_th'].replace('ษฏ','ษฎ'):f['properties']['amp_en'] for f in D if f['properties']['pro_code']=='10'}
fire={}
for l in csv.split('\n'):
    t,a,b,c=l.split(',');fire[th2en[t.replace('ษฏ','ษฎ')]]=[int(a),int(b),int(c)]
print(len(fire),sum(v[2] for v in fire.values()),sum(v[1] for v in fire.values()))
claims={'Lat Krabang':20045,'Bang Kapi':14251,'Sai Mai':11145,'Khlong Sam Wa':8291,'Min Buri':7269}
assert all(k in th2en.values() for k in claims)
B=json.load(open('/home/claude/p2mp_landing/data/bkk.json'))
B['fire68']=fire;B['claims69']=claims;B['stillFlooded']=['Lat Krabang','Nong Chok']
# spearman fire vs congested count per district
import numpy as np
cg={r[0]:r[1] for r in B['dstat']}
ks=list(fire);x=np.array([fire[k][2] for k in ks]);y=np.array([cg.get(k,0) for k in ks])
from scipy.stats import spearmanr
print('rho fire~congested',spearmanr(x,y))
east=set(k for k in ks if k not in 'Bangkok Noi,Bangkok Yai,Bang Phlat,Thon Buri,Khlong San,Chom Thong,Rat Burana,Thung Khru,Bang Khun Thian,Bang Bon,Bang Khae,Phasi Charoen,Nong Khaem,Taling Chan,Thawi Watthana'.split(','))
print('east share fires',sum(fire[k][2] for k in east)/sum(v[2] for v in fire.values()))
json.dump(B,open('/home/claude/p2mp_landing/data/bkk.json','w'),separators=(',',':'),ensure_ascii=False)
