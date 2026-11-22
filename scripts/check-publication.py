"""Fail closed on identifying public content, invalid local links and stale guide hashes.
This validates a curated publication artifact, not arbitrary anonymisation quality.
"""
import argparse, hashlib, ipaddress, json, re
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
from pypdf import PdfReader

class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k in ('href','src') and v:self.links.append(v)

def issues(text):
 bad=[]
 for value in re.findall(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])',text):
  try: ip=ipaddress.ip_address(value)
  except ValueError: continue
  if ip.is_loopback or any(ip in ipaddress.ip_network(net) for net in ('192.0.2.0/24','198.51.100.0/24','203.0.113.0/24')):continue
  bad.append('Non-documentation IPv4 address')
 for pattern in [r'(?i)\bDEV_[A-Z]+\b',r'(?i)\b[a-z0-9-]+\.(?:corp|internal|local)\b',r'(?i)[A-Z]:[\\/]Users[\\/]',r'(?i)\bNTNX-[a-f0-9]{8}-[A-Z]\b',r'(?i)-----BEGIN .*PRIVATE KEY',r'(?i)\b(?:ghp|github_pat)_[A-Za-z0-9_]+',r'(?i)Bearer\s+[A-Za-z0-9._-]{24,}']:
  if re.search(pattern,text):bad.append('Identifying or secret-like content')
 for email in re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',text):
  if not email.endswith('@example.invalid'):bad.append('Non-example email address')
 for value in re.findall(r'\[([0-9a-fA-F:]+)\]',text):
  if ':' in value:
   try:
    ip=ipaddress.ip_address(value)
    if ip.is_private and not ip.is_loopback and ip not in ipaddress.ip_network('2001:db8::/32'):bad.append('Private IPv6 address')
   except ValueError:pass
 return bad

def check(root,require_demo=False):
 errors=[]; root=root.resolve()
 media=json.loads((root/'tutorials/media/manifest.json').read_text())
 approved={a['file']:a for a in media['assets']}
 catalogue=Path(__file__).resolve().parents[1]/'docs/guides/catalogue.json'
 if media.get('source_sha256')!=hashlib.sha256(catalogue.read_bytes()).hexdigest():errors.append('Stale tutorial media source')
 for name,asset in approved.items():
  p=root/'tutorials/media'/name
  if hashlib.sha256(p.read_bytes()).hexdigest()!=asset['sha256']:errors.append('Media hash mismatch: '+name)
 library=json.loads((root/'documentation/library.json').read_text())
 release=json.loads((Path(__file__).resolve().parents[1]/'backend/app/release.json').read_text())
 if media['version']!=release['version']:errors.append('Stale tutorial media version')
 if library['version']!=release['version']:errors.append('Stale documentation version')
 for guide in library['guides']:
  pdf=root/'documentation'/guide['pdf']
  if hashlib.sha256(pdf.read_bytes()).hexdigest()!=guide['sha256']:errors.append('PDF hash mismatch: '+pdf.name)
 if require_demo and not (root/'demo/index.html').exists():errors.append('Missing synthetic demo')
 for file in root.rglob('*'):
  if not file.is_file() or file.name=='.nojekyll':continue
  if file.suffix=='.pdf':
   reader=PdfReader(file);text='\n'.join(p.extract_text() or '' for p in reader.pages)+'\n'+str(reader.metadata)
  elif file.suffix in ('.html','.css','.js','.json','.svg','.txt','.vtt') or file.name=='SHA256SUMS':text=file.read_text(encoding='utf-8')
  elif file.suffix=='.mp4':
   if file.parent!=root/'tutorials/media' or file.name not in approved:errors.append('Unreviewed video: '+file.name)
   continue
  elif file.suffix in ('.png','.jpg','.jpeg','.webp','.ico'):
   # The only raster image allowed here is the established synthetic-demo logo.
   if 'demo' not in file.parts or file.name!='cao-logo.png':errors.append('Unreviewed raster asset: '+str(file.relative_to(root)))
   continue
  else:errors.append('Unreviewed public asset: '+str(file.relative_to(root)));continue
  errors += [str(file.relative_to(root))+': '+v for v in issues(text)]
  if file.suffix=='.html':
   parser=Links();parser.feed(text)
   for link in parser.links:
    url=urlsplit(link)
    if url.scheme or url.netloc or not url.path:continue
    local=unquote(url.path)
    if local.startswith('/Cluster-Assurance-Orchestrator/'):local=local.removeprefix('/Cluster-Assurance-Orchestrator/')
    dest=((root/local.lstrip('/')) if url.path.startswith('/') else (file.parent/local)).resolve()
    if not dest.is_relative_to(root):errors.append('Escaping link: '+link);continue
    if dest.is_dir():dest=dest/'index.html'
    if not dest.exists() and not (not require_demo and '/demo' in str(dest).replace('\\','/')):errors.append(str(file.relative_to(root))+': broken link '+link)
 if errors:raise SystemExit('\n'.join(errors))
 print('Publication checks passed:',len(library['guides']),'PDFs; synthetic data, hashes and local links verified')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--site',default='site');parser.add_argument('--require-demo',action='store_true');args=parser.parse_args();check(Path(args.site),args.require_demo)
