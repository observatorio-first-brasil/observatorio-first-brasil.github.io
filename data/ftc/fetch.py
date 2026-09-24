"""Coleta FTCScout: python3 -m data.ftc.fetch [--refresh]."""
import json,sys
from pathlib import Path
from .client import query
from .config import considered_type
ALLOWED={'Qualifier','SuperQualifier','Championship','FIRSTChampionship','Premier'}
ROOT=Path(__file__).parent

def event_query(season,code):
 return '''{eventByCode(season:%d,code:%s){code name season type start end finished hasMatches divisionCode relatedEvents{code type} location{country state city}
 awards{teamNumber type placement divisionName}
 teams{teamNumber stats{... on TeamEventStats%d{rank wins losses ties qualMatchesPlayed opr{totalPointsNp}}}}
 matches{id hasBeenPlayed tournamentLevel series matchNum teams{teamNumber alliance allianceRole onField} scores{... on MatchScores%d{red{totalPoints} blue{totalPoints}}}}
 }}'''%(season,json.dumps(code),season,season)

def main():
 refresh='--refresh' in sys.argv
 q='{teamsSearch(region:BR,limit:1000){number name location{city state country} rookieYear '+ ' '.join(f'y{s}:events(season:{s}){{eventCode event{{code name type start end}}}}' for s in range(2022,2026))+'}}'
 teams=query(q,refresh)['teamsSearch']
 assert len(teams)<1000,'Listagem possivelmente truncada'
 teams=[t for t in teams if t['location']['country'].lower() in {'brazil','brasil','br'}]
 wanted=sorted({(s,e['eventCode']) for t in teams for s in range(2022,2026) for e in t[f'y{s}'] if considered_type(s,e['eventCode'],e['event']['type']) in ALLOWED})
 # Descoberta por catálogo, além das participações individuais.
 catalogue={}
 for season in range(2022,2026):
  found=query('{eventsSearch(season:%d,region:BR,limit:1000){code name type start hasMatches}}'%season,refresh)['eventsSearch']
  assert len(found)<1000,'Catálogo possivelmente truncado'
  catalogue[str(season)]=found
  wanted=sorted(set(wanted)|{(season,e['code']) for e in found if considered_type(season,e['code'],e['type']) in ALLOWED})
 events={}
 for s,code in wanted:
  e=query(event_query(s,code),refresh)['eventByCode']
  if e is None:raise ValueError(f'Evento ausente {s}/{code}')
  events[f'{s}/{code}']=e
  print(s,code,e['type'],len(e['teams']),flush=True)
 # Algumas participações apontam só para o evento principal; buscar divisões também.
 known=set(events)
 pending=[(s,r['code']) for key,e in list(events.items()) for s in [e['season']] for r in e['relatedEvents'] if r['type'] in ALLOWED and f"{s}/{r['code']}" not in known]
 for s,code in sorted(set(pending)):
  e=query(event_query(s,code),refresh)['eventByCode']
  if e is None:raise ValueError(f'Divisão ausente {s}/{code}')
  events[f'{s}/{code}']=e
  print(s,code,'divisão',len(e['teams']),flush=True)
 payload={'teams':teams,'events':events,'brazil_event_catalog':catalogue}
 (ROOT/'source.json').write_text(json.dumps(payload,ensure_ascii=False))
 print('OK',len(teams),'equipes',len(events),'eventos',flush=True)
if __name__=='__main__':main()
