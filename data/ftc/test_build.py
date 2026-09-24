import unittest
from .build import percentile,award_detail,playoffs,score,build
from .fetch import ALLOWED

class FTCScoring(unittest.TestCase):
 def test_percentiles_ties_and_missing(self):
  self.assertIsNone(percentile(5,[5]))
  self.assertEqual(percentile(5,[5,5]),.5)
  self.assertEqual(percentile(1,[1,2,3]),0)
  self.assertEqual(percentile(3,[1,2,3]),1)
 def test_award_placement_and_no_duplicate_result(self):
  self.assertEqual(award_detail({'type':'Inspire','placement':2},'x')['weight'],.5)
  self.assertIsNone(award_detail({'type':'Winner','placement':1},'x'))
  self.assertIsNone(award_detail({'type':'DeansListWinner','placement':1},'x'))
 def test_division_not_overall_champion(self):
  self.assertEqual(playoffs(1,{'divisionCode':'parent'},[{'type':'Winner'}])[0],.9)
  self.assertEqual(playoffs(1,{},[{'type':'Winner'}])[0],1)
 def test_unplayed_matches_do_not_count(self):
  event={'matches':[{'hasBeenPlayed':False,'tournamentLevel':'Finals','teams':[{'teamNumber':1}]}]}
  self.assertEqual(playoffs(1,event,[])[0],0)
 def test_missing_performance_is_not_zero(self):
  a,_=score({'performance':None,'premios':1,'playoff':1,'winrate':1})
  b,_=score({'performance':0,'premios':1,'playoff':1,'winrate':1})
  self.assertEqual(a,100);self.assertLess(b,a)
 def test_official_types(self):
  self.assertTrue({'Qualifier','Championship','FIRSTChampionship','Premier'}<=ALLOWED)
  self.assertFalse({'OffSeason','Scrimmage','Other','LeagueMeet'}&ALLOWED)
 def test_only_brazil_and_allowed_events(self):
  event={'code':'TEST','season':2022,'type':'Scrimmage','end':'2023-01-01','teams':[{'teamNumber':1}]}
  team={'number':1,'name':'Teste','rookieYear':2022,'location':{'country':'Brazil','state':'SP','city':'X'}}
  self.assertEqual(build({'teams':[team],'events':{'x':event}})['n_teams'],0)
  team['location']['country']='USA'
  self.assertEqual(build({'teams':[team],'events':{}})['n_teams'],0)

class FTCProgression(unittest.TestCase):
 def test_guaranteed_order_even_at_extremes(self):
  from .build import level_score
  from .config import W
  best={k:1. for k in W};worst={k:0. for k in W}
  self.assertLess(level_score(best,0)[0],level_score(worst,1)[0])
  self.assertLess(level_score(best,1)[0],level_score(worst,2)[0])
  for level in range(3):
   value,weighted,_=level_score(best,level)
   self.assertAlmostEqual(value,sum(weighted.values()),places=2)
 def test_classifies_national_and_international(self):
  from .build import event_level
  for kind in ['Premier','FIRSTChampionship']:
   self.assertEqual(event_level({'type':kind}),2)
  self.assertEqual(event_level({'type':'Championship','location':{'country':'Brazil'}}),1)
  self.assertEqual(event_level({'type':'Championship','location':{'country':'USA'}}),0)
 def test_harder_events_have_more_influence(self):
  from .build import weighted_mean
  self.assertGreater(weighted_mean([(0,1),(1,2)]),weighted_mean([(0,2),(1,1)]))
 def test_low_national_result_promotes_and_future_entry_does_not(self):
  def event(kind,country,played=True):
   return {'season':2025,'type':kind,'code':kind,'name':kind,'start':'2026-03-01','end':'2026-03-01','finished':True,'divisionCode':None,'location':{'country':country},'awards':[],
    'teams':[{'teamNumber':n,'stats':{'rank':n,'wins':0,'losses':1,'ties':0,'qualMatchesPlayed':1,'opr':{'totalPointsNp':0 if n==1 else 100}}} for n in [1,2]],
    'matches':[{'hasBeenPlayed':played,'tournamentLevel':'Quals','teams':[{'teamNumber':1}]}]}
  team={'number':1,'name':'Teste','rookieYear':2025,'location':{'country':'Brazil','state':'SP','city':'X'}}
  regional=event('Qualifier','Brazil');national=event('Championship','Brazil');world=event('Premier','USA')
  source={'teams':[team],'events':{'r':regional}}
  a=build(source)['teams']['1']['seasons']['2026']
  source['events']['n']=national
  b=build(source)['teams']['1']['seasons']['2026']
  source['events']['w']=world
  c=build(source)['teams']['1']['seasons']['2026']
  self.assertLess(a['score'],b['score']);self.assertLess(b['score'],c['score'])
  self.assertEqual([a['level'],b['level'],c['level']],[0,1,2])
  source['events']['w']['matches'][0]['hasBeenPlayed']=False
  self.assertEqual(build(source)['teams']['1']['seasons']['2026']['level'],1)


class FTCEventCorrections(unittest.TestCase):
 def test_overrides_are_season_specific(self):
  from .config import considered_type
  from .build import event_level
  self.assertEqual(considered_type(2023,'BRBHS','Scrimmage'),'Qualifier')
  self.assertEqual(considered_type(2022,'BRBHS','Scrimmage'),'Scrimmage')
  self.assertEqual(considered_type(2023,'BRNHS','Scrimmage'),'Scrimmage')
  self.assertEqual(considered_type(2023,'BRPAS','Scrimmage'),'Scrimmage')
  self.assertEqual(considered_type(2025,'BRNHS','Scrimmage'),'Scrimmage')
  self.assertEqual(considered_type(2024,'BRCUS','Scrimmage'),'Qualifier')
  self.assertEqual(considered_type(2023,'BRCUS','Scrimmage'),'Scrimmage')
  self.assertEqual(considered_type(2024,'BRPAS','Scrimmage'),'Scrimmage')
  self.assertEqual(considered_type(2025,'BRPIQ','Qualifier'),'Championship')
  self.assertEqual(event_level({'season':2025,'code':'BRPIQ','type':'Qualifier'}),1)
 def test_catalog_retains_source_classification(self):
  from .build import event_catalog
  team={'number':1,'location':{'country':'Brazil'}}
  event={'season':2024,'code':'BRCUS','type':'Scrimmage','name':'Regional','start':'2024-10-10',
    'location':{'country':'Brazil'},'teams':[{'teamNumber':1}],'matches':[]}
  row=event_catalog({'teams':[team],'events':{'2024/BRCUS':event}})[0]
  self.assertEqual(row['type'],'Qualifier');self.assertEqual(row['source_type'],'Scrimmage')
  self.assertEqual(row['year'],2025)
