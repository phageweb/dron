"""Read-only baseline geometry survey, run through aktualizuj_desku.sh --python.

Rotations are simulated in memory; the PCB is never saved. Missing courtyards
mean UNKNOWN clearance, not no collisions. Track totals exclude zones and arcs.
The pads dictionary retains one position per pad number (not every repeated pad).
"""
import pcbnew,sys,json,math,hashlib
from pathlib import Path
b=pcbnew.LoadBoard(sys.argv[1]); mm=pcbnew.ToMM
fps={f.GetReference():f for f in b.GetFootprints()}
def xy(p):return [round(mm(p.x),4),round(mm(p.y),4)]
def bbox(f):
 c=f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
 if not c.OutlineCount():return None
 bb=c.BBox();return [round(mm(v),4) for v in (bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom())]
def overlap(a,c):return a and c and a[0]<c[2] and c[0]<a[2] and a[1]<c[3] and c[1]<a[3]
data={'board':sys.argv[1],'sha256':hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest(),'footprints':{}}
for ref,f in fps.items():
 data['footprints'][ref]={'value':f.GetValue(),'sheet':f.GetSheetname(),'xy':xy(f.GetPosition()),'rotation':f.GetOrientationDegrees(),'side':'B' if f.IsFlipped() else 'F','courtyard':bbox(f),'pads':{p.GetNumber():{'net':p.GetNetname(),'xy':xy(p.GetPosition())} for p in f.Pads() if p.GetNumber()}}
u=fps['U301'];original_mcu_rotation=u.GetOrientationDegrees();data['mcu_rotation_groups']={}
groups={'USB':['USB_DP','USB_DM'],'SD':['SD_CK','SD_CMD','SD_D0','SD_D1','SD_D2','SD_D3'],'BMI270':['IMU_SPI.SCK','IMU_SPI.MISO','IMU_SPI.MOSI','IMU_CS','IMU_INT'],'ICM42688':['IMU2_SCK','IMU2_MISO','IMU2_MOSI','IMU2_CS','IMU2_INT'],'GPS':['GPS_TX','GPS_RX'],'RC':['RC_TX','RC_RX'],'HSE':['HSE_IN','HSE_OUT']}
for rot in (0,90,180,270):
 u.SetOrientationDegrees(rot);table={}
 for name,nets in groups.items():
  pads=[p for p in u.Pads() if p.GetNetname().split('/')[-1] in nets]
  table[name]=[round(sum(mm(p.GetPosition().x-u.GetPosition().x) for p in pads)/len(pads),3),round(sum(mm(p.GetPosition().y-u.GetPosition().y) for p in pads)/len(pads),3)]
 data['mcu_rotation_groups'][rot]=table
u.SetOrientationDegrees(original_mcu_rotation)
f=fps['J302'];original_sd_rotation=f.GetOrientationDegrees();data['sd_rotations']={}
for rot in (0,90,180,270):
 f.SetOrientationDegrees(rot);box=bbox(f)
 data['sd_rotations'][rot]={'courtyard':box,'overlaps':[r for r,other in fps.items() if r not in ('J302','U24') and other.IsFlipped()==f.IsFlipped() and overlap(box,bbox(other))],'pads':{p.GetNumber():xy(p.GetPosition()) for p in f.Pads() if p.GetNumber() in map(str,range(1,9))}}
f.SetOrientationDegrees(original_sd_rotation)
data['plane_signal_tracks']={}
for name in ('L2.GND','L7.GND'):
 layer=b.GetLayerID(name);nets={}
 for t in b.GetTracks():
  if t.GetClass()=='PCB_TRACK' and t.GetLayer()==layer and t.GetNetname()!='GND':
   n=t.GetNetname();nets[n]=nets.get(n,0)+mm(t.GetLength())
 data['plane_signal_tracks'][name]={k:round(v,3) for k,v in sorted(nets.items())}
Path(sys.argv[2]).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
for ref in ('U301','U8','U303','J301','J302','J303','J304','J305','R301','TP304','U201','C203'):
 p=data['footprints'][ref];print(ref,p['xy'],p['rotation'],p['courtyard'])
print('SD rotation checks',data['sd_rotations'])
print('MCU group directions',data['mcu_rotation_groups'])
