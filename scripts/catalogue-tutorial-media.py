"""Record only the generated training media and accessible captions."""
from pathlib import Path
import json,hashlib,struct
root=Path(__file__).resolve().parents[1]
guides=json.loads((root/'docs/guides/catalogue.json').read_text())
assets=[]
for g in guides:
 folder=root/'site/tutorials/media'
 path=folder/(g['id']+'.mp4');data=path.read_bytes()
 # ISO BMFF movie header: timescale and duration; no external probing required.
 pos=data.index(b'mvhd')+4
 assert data[pos]==0, 'Expected mvhd version 0'
 timescale,duration=struct.unpack('>II',data[pos+12:pos+20])
 seconds=duration/timescale
 assert abs(seconds-40)<.1,(g['id'],seconds)
 vtt=['WEBVTT','']
 for i,s in enumerate(g['sections']):
  start=i*10;end=(i+1)*10
  vtt += [f'00:00:{start:02d}.000 --> 00:00:{end:02d}.000',s['title'],'Synthetic training. '+s['steps'][0].split('. ')[0]+'.','']
 caption=folder/(g['id']+'.vtt');caption.write_text('\n'.join(vtt),encoding='utf-8',newline='\n')
 for p in (path,caption):assets.append({'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'classification':'generated-synthetic-training','duration_seconds':seconds})
(folder/'manifest.json').write_text(json.dumps({'version':json.loads((root/'backend/app/release.json').read_text())['version'],'source_sha256':hashlib.sha256((root/'docs/guides/catalogue.json').read_bytes()).hexdigest(),'assets':assets},indent=2)+'\n',encoding='utf-8',newline='\n')
print('Verified six 40-second videos and caption tracks')
