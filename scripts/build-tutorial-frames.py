"""Create captioned synthetic tutorial slides. Authoring-only Pillow; no live data input."""
from pathlib import Path
import json, textwrap
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1]
guides=json.loads((root/'docs/guides/catalogue.json').read_text())
fontroot=Path('C:/Windows/Fonts')
fonts=[ImageFont.truetype(str(fontroot/'segoeuib.ttf'),s) for s in (22,32,48,64)]
bodyfont=ImageFont.truetype(str(fontroot/'segoeui.ttf'),30)
for index,g in enumerate(guides,1):
 out=root/'tmp/tutorial-frames'/g['id'];out.mkdir(parents=True,exist_ok=True)
 for i,s in enumerate(g['sections']):
  im=Image.new('RGB',(1920,1080),'#f3f5f8');d=ImageDraw.Draw(im)
  d.rectangle((0,0,330,1080),fill='#202020');d.text((36,46),'CLUSTER\nASSURANCE',font=fonts[1],fill='white',spacing=8)
  for n,label in enumerate(['Dashboard','Operator Triage','Cluster Estate','Health Runs','Prism Incidents','Diagnostics','Evidence','Settings']):d.text((36,212+n*66),label,font=fonts[0],fill='#d1d1d1')
  d.text((378,44),f'TUTORIAL {index:02d} / SYNTHETIC TRAINING',font=fonts[0],fill='#087c91')
  for n,line in enumerate(textwrap.wrap(g['title'],43)):d.text((378,99+n*65),line,font=fonts[2],fill='#17334f')
  d.rounded_rectangle((378,260,1864,924),radius=12,fill='white',outline='#dbe2ea',width=2)
  for n,line in enumerate(textwrap.wrap(s['title'],55)):d.text((418,294+n*48),line,font=fonts[1],fill='#17334f')
  y=418
  # Short on-screen captions; complete procedure remains in transcript/PDF.
  for n,text in enumerate(s['steps'],1):
   first=text.split('. ')[0]+'.'
   lines=textwrap.wrap(first,78)
   d.text((418,y),f'{n:02d}',font=fonts[1],fill='#087c91')
   for line in lines:d.text((480,y),line,font=bodyfont,fill='#26374a');y+=44
   y+=24
  assert y <= 924, (g['id'], i, y)
  d.text((378,976),f'Step {i+1}/4 | Captioned overview; read the full companion guide before action.',font=fonts[0],fill='#536a7e')
  d.text((378,1014),'Fictional examples. No infrastructure changes. No production acceptance implied.',font=fonts[0],fill='#536a7e')
  im.save(out/f'{i:02d}.png')
 print(g['id'])
