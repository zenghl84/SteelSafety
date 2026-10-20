"""Assemble the v1.8 dashboard from local model, monitoring and UI resources."""
from pathlib import Path
import json
import hashlib
import base64
from datetime import timezone, timedelta
import pandas as pd
from .model import parse
from .viewer import build_scene, viewer_html, script_json
from .monitoring import load_monitoring_data, WORKBOOK_NAME
from .assessment import build_assessment
from .key_indicators import build_key_indicators
from .alerts import build_alerts
from .resources import font_styles, load_knowledge_catalog

ROOT = Path(__file__).resolve().parents[1]

def build_homepage():
    raw = (ROOT / 'data/model.mgt').read_bytes()
    model = parse(raw)
    mapping = pd.read_csv(ROOT / 'data/sensor_mapping.csv')
    points, labels, details = [], [], []
    for r in mapping.itertuples(index=False):
        e = model['elements'].get(int(r.element))
        if e is None: continue
        a,b = model['nodes'][e['n1']], model['nodes'][e['n2']]
        points.append([a[i]+float(r.position)*(b[i]-a[i]) for i in range(3)])
        labels.append(str(r.sensor_id)); details.append(f'{r.sensor_id} · 单元 E{int(r.element)}<br>沿用 v1.4 映射')
    scene = build_scene(raw,model,list(model['elements'].values()),'钢材质感',points,labels,details,0,True,hashlib.sha256(raw).hexdigest())
    stress = json.loads((ROOT/'data/stress_cs19.json').read_text(encoding='utf-8'))
    if stress['model_sha256'] != hashlib.sha256(raw).hexdigest():
        raise ValueError('CS19应力结果与当前模型不匹配，请重新导入')
    scene['stress'] = stress
    doc = viewer_html(scene,'reference-home').replace('</head>','<style>#viewer{height:100vh;border:0;border-radius:0}.topbar,.foot{display:none}#selection{top:auto;bottom:53px;right:14px;font-size:10px;max-width:210px}.sensor-pin span{font-size:10px}</style></head>')
    data = load_monitoring_data(ROOT/'data'/WORKBOOK_NAME)
    assessment = build_assessment(ROOT, data, model, mapping.to_dict(orient='records'))
    history = {p:[{'timestamp':r['timestamp'].replace(tzinfo=timezone(timedelta(hours=8))).isoformat(),'value':r['strain'],'unit':r['strain_unit'],'temperature':r['temperature'],'temperature_unit':r['temperature_unit']} for r in rows] for p,rows in data['history'].items()}
    payload={'stress':{k:v for k,v in stress.items() if k!='records'},'stress_values':{k:v['abs_mpa']/stress['range_mpa'][1] for k,v in stress['records'].items()},'viewer':doc,'history':history,'latest':max(r['timestamp'] for rows in data['history'].values() for r in rows).isoformat(),'record_count':data['record_count'],'source':WORKBOOK_NAME,'metric':'应变变化值','mapping':mapping.to_dict(orient='records'),'knowledge':load_knowledge_catalog(ROOT)}
    payload['assessment'] = assessment
    payload['key_indicators'] = build_key_indicators(ROOT, assessment)
    payload['alerts'] = build_alerts(assessment, payload['key_indicators'])
    assets=ROOT/'assets/home'
    fonts = font_styles(assets)
    runtime = '\n'.join((assets/name).read_text(encoding='utf-8') for name in ('app.js', 'monitoring.js', 'knowledge.js', 'assessment.js', 'key_indicators.js', 'alerts.js'))
    html = (assets/'index.html').read_text(encoding='utf-8').replace('__ASSESSMENT__', (assets/'assessment.html').read_text(encoding='utf-8')).replace('__ALERTS__', (assets/'alerts.html').read_text(encoding='utf-8'))
    return html.replace('__STYLE__',fonts+(assets/'style.css').read_text(encoding='utf-8')).replace('__PROJECT_FRONT__','data:image/png;base64,'+base64.b64encode((assets/'project-front-v2.png').read_bytes()).decode('ascii')).replace('__PAYLOAD__',script_json(payload)).replace('__RUNTIME__',runtime)
