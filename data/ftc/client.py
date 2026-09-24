import hashlib,json,urllib.request,urllib.parse,time,subprocess
from pathlib import Path
CACHE=Path(__file__).parent/'raw'
ENDPOINT='https://api.ftcscout.org/graphql'
def query(q,refresh=False):
 CACHE.mkdir(parents=True,exist_ok=True)
 p=CACHE/(hashlib.sha256(q.encode()).hexdigest()+'.json')
 if p.exists() and not refresh:return json.loads(p.read_text())
 req=urllib.request.Request(ENDPOINT+'?'+urllib.parse.urlencode({'query':q}),headers={'Content-Type':'application/json'})
 for attempt in range(3):
  try:
   result=subprocess.run(['curl','--fail-with-body','-sS','--max-time','90','-G','-H','Content-Type: application/json','--data-urlencode','query='+q,ENDPOINT],capture_output=True,text=True,check=True)
   d=json.loads(result.stdout)
   if d.get('errors'):raise ValueError(d['errors'])
   p.write_text(json.dumps(d['data'],ensure_ascii=False));return d['data']
  except Exception:
   if attempt==2:raise
   time.sleep(attempt+1)
