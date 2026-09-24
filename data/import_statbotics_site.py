"""Importa os arquivos públicos compactados usados pelo site Statbotics.
Execute: python3 -m data.import_statbotics_site
Não consulta a API REST. Mantém snapshots e um relatório de cobertura.
"""
import concurrent.futures
import datetime
import json
from pathlib import Path
import urllib.error
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parent
BASE = 'https://storage.googleapis.com/site_v1'
SNAPSHOTS = ROOT / 'raw' / 'statbotics_site'


def download(path):
    url = BASE + path
    target = SNAPSHOTS / (path.strip('/').replace('/', '_') + '.json')
    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            payload = json.loads(zlib.decompress(response.read()))
        envelope = {'source_url': url, 'retrieved_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'data': payload}
        target.write_text(json.dumps(envelope, ensure_ascii=False))
        return {'path': path, 'status': 'ok'}
    except (urllib.error.URLError, TimeoutError, ValueError, zlib.error) as exc:
        return {'path': path, 'status': 'unavailable', 'reason': str(exc)}


def main():
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    dataset = json.loads((ROOT.parent / 'web/data/data.json').read_text())
    events = sorted({event for team in dataset['teams'].values() for season in team['seasons'].values() for event in season['events']})
    paths = [f'/team_years/{year}' for year in dataset['seasons']] + [f'/event/{event}' for event in events]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        for result in executor.map(download, paths):
            results.append(result)
            print(result['path'], result['status'], flush=True)
    (SNAPSHOTS / 'report.json').write_text(json.dumps(results, indent=2))
    print(f"Disponíveis: {sum(r['status'] == 'ok' for r in results)}/{len(results)}", flush=True)


if __name__ == '__main__':
    main()
