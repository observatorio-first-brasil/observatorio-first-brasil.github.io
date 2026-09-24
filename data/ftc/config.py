"""Pesos FTC independentes dos pesos FRC; escala total 0–100."""
W = {'performance':50/95,'premios':20/95,'playoff':18/95,'winrate':7/95}

# Faixas sem sobreposição: a progressão precede o desempenho no ranking anual.
LEVELS = {
 0: {'label':'Seletivas', 'floor':0., 'ceiling':39., 'weight':1.},
 1: {'label':'Nacional', 'floor':40., 'ceiling':69., 'weight':2.},
 2: {'label':'Mundial / Premier', 'floor':70., 'ceiling':100., 'weight':3.},
}

# Correções editoriais por temporada/código, sem alterar o registro original da fonte.
EVENT_OVERRIDES = {
 '2023/BRBHS': {'type':'Qualifier', 'level':0,
                'reason':'Seletiva CENTERSTAGE 2023–24 confirmada pelo responsável; FTCScout registra Scrimmage.'},
 '2024/BRCUS': {'type':'Qualifier', 'level':0,
                'reason':'Seletiva regional incluída por indicação do responsável; FTCScout registra Scrimmage.'},
 '2025/BRPIQ': {'type':'Championship', 'level':1,
               'reason':'Classificado pelo responsável pelo observatório como championship de nível nacional.'},
}

def considered_type(season, code, source_type):
 return EVENT_OVERRIDES.get(f'{season}/{code}', {}).get('type', source_type)
