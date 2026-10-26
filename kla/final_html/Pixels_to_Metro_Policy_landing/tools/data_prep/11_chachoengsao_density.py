"""Registered residents 2564 for the metropolitan map tooltips and totals (bkk.metro.pop64).

Note: an earlier version also coloured Chachoengsao districts (ccsDens); it was removed from the page at the
project lead's request, the per-district numbers below are kept for reference only.

Chachoengsao is outside the Urban TH density map used for Bangkok and vicinity, so its 11 districts are
coloured from registration data instead, on the same 15-class scale (bkk.densCls / bkk.densRamp).
- Population 2564: NSO Chachoengsao Table 1.1 "Population from Registration Record, Growth Rate and Density
  by District: 2018-2022" (source DOPA); sums to the DOPA provincial total 724,178 at 31 Dec 2564.
- District area: population 2565 / density 2565 from the same table (sums to 5,352 km2).
- Province totals (pop64): DOPA announcement of registered population at 31 Dec 2564 (dopa.go.th news/preview/9159).
"""
import json
P64={'Mueang Chachoengsao':162874,'Bang Khla':45736,'Bang Nam Priao':89288,'Bang Pakong':92763,'Ban Pho':53281,
     'Phanom Sarakham':83238,'Ratchasan':12696,'Sanam Chai Khet':75058,'Plaeng Yao':49479,'Tha Takiap':47077,'Khlong Khuean':12688}
P65D={'Mueang Chachoengsao':(163482,431.35),'Bang Khla':(45658,200.25),'Bang Nam Priao':(89477,179.31),'Bang Pakong':(93424,362.11),
      'Ban Pho':(53403,244.97),'Phanom Sarakham':(83223,151.31),'Ratchasan':(12629,93.55),'Sanam Chai Khet':(75142,45.10),
      'Plaeng Yao':(50700,213.92),'Tha Takiap':(46968,44.52),'Khlong Khuean':(12581,99.06)}
POP64={'10':5527994,'11':1356449,'12':1288637,'13':1190060,'73':922171,'74':586789,'24':724178}
b=json.load(open('data/bkk.json'));cls=b['densCls'];out={}
for n,p in P64.items():
    area=P65D[n][0]/P65D[n][1];d=p/area;out[n]=[p,round(area,1),round(d,1),next(i for i,(lo,hi) in enumerate(cls) if d<=hi)]
assert sum(P64.values())==724178
b['metro']['pop64']=POP64  # ccsDens (out) is computed but not stored
json.dump(b,open('data/bkk.json','w'),ensure_ascii=False,separators=(',',':'))
