"""Gera web/ftc/data.json a partir de FTCScout: python3 -m data.ftc.build."""
import datetime,json,math,statistics
from pathlib import Path
from .fetch import ALLOWED
from ..build import norm_state,assign_ranks,build_states
from .config import W, LEVELS, EVENT_OVERRIDES, considered_type
ROOT=Path(__file__).parent
OUT=ROOT.parent.parent/'web'/'ftc'
RESULT_AWARDS={'Winner','Finalist','DivisionWinner','DivisionFinalist','ConferenceFinalist','TopRanked'}
INDIVIDUAL={'DeansListFinalist','DeansListSemiFinalist','DeansListWinner','Compass'}
AWARD_WEIGHTS={'Inspire':1.,'Think':.7,**dict.fromkeys(['Connect','Control','Design','Innovate','Motivate','Reach','Sustain'],.45)}

def percentile(value,values):
 if value is None or len(values)<2:return None
 return (sum(v<value for v in values)+(sum(v==value for v in values)-1)/2)/(len(values)-1)

def award_detail(a,event):
 if a['type'] in RESULT_AWARDS|INDIVIDUAL:return None
 base=AWARD_WEIGHTS.get(a['type'],.25)
 place=max(1,a['placement'])
 return {'name':a['type']+f' · {place}º lugar','award_type':a['type'],'event_key':event,'tier':{1.:'S',.7:'A',.45:'B',.25:'C'}[base],'weight':base/place,'placement':place,'is_champs':False}

def playoffs(team,event,awards):
 types={a['type'] for a in awards}
 # O resultado da aliança é dado pelo tipo; placement não é colocação em Winner/Finalist.
 for name,value,label in [('Winner',1.,'Campeão'),('DivisionWinner',.9,'Campeão de divisão'),('Finalist',.8,'Finalista'),('DivisionFinalist',.8,'Finalista de divisão'),('ConferenceFinalist',.8,'Finalista de conferência')]:
  if name in types:
   if name=='Winner' and event.get('divisionCode'):return .9,'Campeão de divisão'
   return value,label
 matches=[m for m in event['matches'] if m['hasBeenPlayed'] and m['tournamentLevel']!='Quals' and any(t['teamNumber']==team for t in m['teams'])]
 if not matches:return 0.,'Sem playoffs'
 if any(m['tournamentLevel']=='Finals' for m in matches):return .8,'Finalista (partidas)'
 if any(m['tournamentLevel']=='Semis' for m in matches):return .6,'Semifinal'
 wins=0
 for m in matches:
  entry=next(t for t in m['teams'] if t['teamNumber']==team)
  color=entry['alliance'].lower();sc=m['scores'] or {}
  if color in ('red','blue') and sc and sc[color]['totalPoints']>sc['blue' if color=='red' else 'red']['totalPoints']:wins+=1
 return min(.6,.25+.1*wins),f'Double elimination · {wins} vitórias'

def score(comps):
 available={k:v for k,v in comps.items() if v is not None}
 total=sum(W[k] for k in available)
 weighted={k:round(100*W[k]*available[k]/total,4) if k in available and total else 0 for k in W}
 return round(sum(weighted.values()),2),weighted

def event_level(event):
 override=EVENT_OVERRIDES.get(f"{event.get('season')}/{event.get('code')}",{})
 if 'level' in override:return override['level']
 if event['type'] in {'FIRSTChampionship','Premier'}:return 2
 if event['type']=='Championship' and event.get('location',{}).get('country','').lower() in {'br','brazil','brasil'}:return 1
 return 0

def level_score(comps,level):
 base,weighted=score(comps)
 rule=LEVELS[level];span=rule['ceiling']-rule['floor']
 scaled={k:round(v*span/100,4) for k,v in weighted.items()}
 scaled['progression']=rule['floor']
 return round(rule['floor']+base*span/100,2),scaled,base

def weighted_mean(values):
 return sum(v*w for v,w in values)/sum(w for _,w in values) if values else None

def build(source):
 teams={}; audit=[]
 for t in source['teams']:
  if t['location']['country'].lower() not in {'brazil','brasil','br'}:continue
  num=t['number'];rec={'team':num,'name':t['name'],'state':norm_state(t['location']['state']),'city':t['location']['city'],'country':'Brazil','rookie_year':t['rookieYear'],'seasons':{},'event_points':[]}
  for season in range(2022,2026):
   year=season+1;events=[];awards=[];perfs=[];oprs=[];pfs=[];wr=[0,0,0];event_keys=[];incomplete=[];highest_level=0;weighted_wr=[0.,0.,0.]
   for key,e in sorted(source['events'].items(),key=lambda kv:(kv[1]['end'],kv[0])):
    if e['season']!=season or considered_type(e['season'],e['code'],e['type']) not in ALLOWED:continue
    part=next((p for p in e['teams'] if p['teamNumber']==num),None)
    if part is None:continue
    raw_awards=[a for a in e['awards'] if a['teamNumber']==num]
    level=event_level(e);importance=LEVELS[level]['weight']
    detail=[{**d,'weight':d['weight']*importance,'event_weight':importance} for a in raw_awards for d in [award_detail(a,key)] if d]
    awards.extend(detail)
    played=any(m['hasBeenPlayed'] and any(mt['teamNumber']==num for mt in m['teams']) for m in e['matches'])
    if not played and not raw_awards:continue
    highest_level=max(highest_level,level)
    event_keys.append(key)
    st=part['stats'];pf,label=playoffs(num,e,raw_awards);pfs.append((pf*importance,label))
    if not played:continue # Prêmios gerais contam, mas não criam uma queda fictícia na série por evento.
    values=[p['stats']['opr']['totalPointsNp'] for p in e['teams'] if p['stats'] and p['stats']['qualMatchesPlayed']>0 and p['stats']['opr']['totalPointsNp'] is not None]
    opr=st['opr']['totalPointsNp'] if st and st['qualMatchesPlayed']>0 else None
    perf=percentile(opr,values)
    if perf is not None:perfs.append((perf,importance));oprs.append(opr)
    if st:
     for i,k in enumerate(['wins','losses','ties']):
      wr[i]+=st[k]
      weighted_wr[i]+=st[k]*importance
    n=sum(st[k] for k in ['wins','losses','ties']) if st else 0
    winrate=st['wins']/n if n else None
    comps={'performance':perf,'premios':1-math.exp(-.55*sum(a['weight'] for a in detail)),'playoff':pf,'winrate':winrate}
    value,weighted,base=level_score(comps,level)
    if perf is None or winrate is None:incomplete.append(key)
    end=datetime.date.fromisoformat(e['end']);start=datetime.date(season,8,1)
    x=year+(end-start).days/366*.6
    point={'event':key,'event_name':e['name'],'year':year,'season':season,'date':e['end'],'x':x,'score':value,'epa_norm':None,'opr':opr,'opr_pct':perf,'playoff_score':pf,'playoff_label':label,'qual_rank':st['rank'] if st else None,'qual_num_teams':len(values),'n_awards':len(detail),'is_champs':e['type']=='FIRSTChampionship','event_type':EVENT_OVERRIDES.get(key,{}).get('type',e['type']),'source_event_type':e['type'],'classification_note':EVENT_OVERRIDES.get(key,{}).get('reason'),'level':level,'level_label':LEVELS[level]['label'],'event_weight':importance,'base_score':base,'source_url':f'https://ftcscout.org/events/{season}/{e["code"]}','provisional':not e['finished'] or perf is None or winrate is None}
    rec['event_points'].append(point);events.append(point)
   if not event_keys:continue
   # Remove registros idênticos repetidos pela fonte.
   awards=list({(a['event_key'],a['award_type'],a['placement']):a for a in awards}.values())
   pf,label=max(pfs,default=(0.,'Sem playoffs'))
   pf=pf/LEVELS[highest_level]['weight']
   perf=weighted_mean(perfs)
   winrate=weighted_wr[0]/sum(weighted_wr) if sum(weighted_wr) else None
   comps={'performance':perf,'premios':1-math.exp(-.55*sum(a['weight'] for a in awards)),'playoff':pf,'winrate':winrate}
   value,weighted,base=level_score(comps,highest_level)
   rec['seasons'][str(year)]={'score':value,'base_score':base,'level':highest_level,'level_label':LEVELS[highest_level]['label'],'components':comps,'weighted':weighted,'epa_norm':None,'opr_pct':perf,'opr_mean':statistics.mean(oprs) if oprs else None,'winrate':winrate,'events':event_keys,'n_events':len(events),'awards':awards,'playoff_best':label,'qual_record':dict(zip(['w','l','t'],wr)),'provisional':bool(incomplete) or perf is None or winrate is None,'incomplete_events':incomplete,'season_label':f'{season}–{str(year)[2:]}','source':'FTCScout GraphQL'}
  if rec['seasons']:teams[str(num)]=rec
 assign_ranks(teams)
 return {'program':'FTC','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'seasons':[2023,2024,2025,2026],'season_labels':{str(y):f'{y-1}–{str(y)[2:]}' for y in range(2023,2027)},'weights':W,'n_teams':len(teams),'teams':teams,'states':build_states(teams),'anchor_events':[],'methodology_version':'ftc-2-levels','levels':LEVELS,'allowed_event_types':sorted(ALLOWED),'event_catalog':event_catalog(source),'event_overrides':EVENT_OVERRIDES}

def event_catalog(source):
 brazil={t['number'] for t in source['teams'] if t['location']['country'].lower() in {'brazil','brasil','br'}}
 rows=[]
 for key,e in source['events'].items():
  if considered_type(e['season'],e['code'],e['type']) not in ALLOWED:continue
  participants={p['teamNumber'] for p in e['teams']}&brazil
  if not participants:continue
  override=EVENT_OVERRIDES.get(key,{})
  played={t['teamNumber'] for m in e['matches'] if m['hasBeenPlayed'] for t in m['teams']}&participants
  rows.append({'key':key,'year':e['season']+1,'season_label':f"{e['season']}–{str(e['season']+1)[2:]}",
    'name':e['name'],'type':override.get('type',e['type']),'source_type':e['type'],
    'level_label':LEVELS[event_level(e)]['label'],'date':e['start'],'country':e['location']['country'],
    'team_count':len(participants),'played_team_count':len(played),'classification_note':override.get('reason'),
    'url':f"https://ftcscout.org/events/{e['season']}/{e['code']}"})
 return sorted(rows,key=lambda r:(r['year'],r['date'],r['key']))

def main():
 d=build(json.loads((ROOT/'source.json').read_text()))
 assert d['n_teams']>0
 OUT.mkdir(exist_ok=True)
 (OUT/'data.json').write_text(json.dumps(d,ensure_ascii=False))
 (OUT/'config.json').write_text(json.dumps({'weights':W,'levels':LEVELS,'award_weights':AWARD_WEIGHTS,'allowed_event_types':sorted(ALLOWED)},ensure_ascii=False))
 print('FTC:',d['n_teams'],'equipes',len(d['states']),'estados',sum(len(t['seasons']) for t in d['teams'].values()),'temporadas-equipe')
 for y in d['seasons']:print(y,sum(str(y) in t['seasons'] for t in d['teams'].values()))
if __name__=='__main__':main()
