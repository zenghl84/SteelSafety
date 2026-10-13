"""Fixed-CS18 axial stress POD with affine two-parameter coefficient regression."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
TRAIN=[(0.8,1.),(1.2,1.),(1.,0.8),(1.,1.2)]
TEST=[(0.9,1.1),(1.1,0.9)]
def valid(a,b):
    return bool(np.isfinite([a,b]).all() and abs(a-1)+abs(b-1)<=0.200000001)
def read_case(a,b):
    path=ROOT/'results'/f'X_A{round(a*100):03d}_B{round(b*100):03d}_CS18.xls'
    d=pd.read_excel(path,header=1,engine='xlrd')
    if set(d['阶段'])!={'CS18'} or set(d['荷载'])!={'合计'} or set(d['步骤'])!={'001(最后)'}:
        raise ValueError('阶段、荷载或步骤不一致')
    out=pd.DataFrame({'element':pd.to_numeric(d['单元']).astype(int),'position':d['位置'].str[0],
        'node':d['位置'].str.extract(r'\[(\d+)\]')[0].astype(int),
        'stress':pd.to_numeric(d['轴向\n(N/mm^2)'])}).sort_values(['element','position']).reset_index(drop=True)
    if out.duplicated(['element','position']).any() or not np.isfinite(out.stress).all():raise ValueError('重复或无效应力')
    if len(out)!=23838 or not out.position.isin(['I','J']).all():raise ValueError('端部覆盖异常')
    return out,path

def train():
    frames=[read_case(*v) for v in TRAIN+TEST]
    mapping=frames[0][0][['element','position','node']]
    for d,_ in frames:
        if not d[['element','position','node']].equals(mapping):raise ValueError('工况映射不一致')
    # Compare connectivity to bundled display model; does not verify load provenance.
    from model import parse
    geometry=parse((ROOT.parent/'data/model.mgt').read_bytes())
    for r in mapping.itertuples(index=False):
        if geometry['elements'][r.element]['n1' if r.position=='I' else 'n2']!=r.node:raise ValueError('几何端部不匹配')
    y=np.column_stack([d.stress.to_numpy() for d,_ in frames[:4]])
    mean=y.mean(axis=1);u,s,_=np.linalg.svd(y-mean[:,None],full_matrices=False)
    rank=min(3,int(np.searchsorted(np.cumsum(s*s)/sum(s*s),.9999))+1)
    basis=u[:,:rank];coef=(basis.T@(y-mean[:,None])).T
    design=np.column_stack([np.ones(4),np.array(TRAIN)-1])
    regression=np.linalg.lstsq(design,coef,rcond=None)[0]
    model=dict(mean=mean,basis=basis,regression=regression,elements=mapping.element.to_numpy(),positions=mapping.position.to_numpy(dtype='U1'))
    metrics=[]
    for (a,b),(d,_) in zip(TEST,frames[4:]):
        actual=d.stress.to_numpy();pred=predict(model,a,b);err=pred-actual
        metrics.append(dict(A=a,B=b,rmse_mpa=float(np.sqrt(np.mean(err**2))),max_error_mpa=float(abs(err).max()),
            relative_l2=float(np.linalg.norm(err)/np.linalg.norm(actual)),
            load_effect_relative_l2=float(np.linalg.norm(err)/np.linalg.norm(actual-mean))))
    report=dict(method='轴向应力 POD + 二参数仿射系数回归',rank=rank,training=TRAIN,independent_test=TEST,
        validation=metrics,domain='|A-1|+|B-1|<=0.2',stage='CS18',unit='MPa',
        geometry_sha256=hashlib.sha256((ROOT.parent/'data/model.mgt').read_bytes()).hexdigest(),
        provenance='几何端部已核对；分区荷载 MGT 未提供，倍率取自文件名，荷载定义尚待核验。',
        sources=[dict(file=f.name,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for _,f in frames])
    np.savez_compressed(ROOT/'trained.npz',**model)
    (ROOT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def load():
    with np.load(ROOT/'trained.npz',allow_pickle=False) as z:model={k:z[k].copy() for k in z.files}
    return model,json.loads((ROOT/'validation.json').read_text(encoding='utf-8'))
def predict(model,a,b):
    if not valid(a,b):raise ValueError('超出菱形采样范围：|A−1|+|B−1|必须≤0.2')
    return model['mean']+model['basis']@(np.array([1.,a-1,b-1])@model['regression'])
def evaluate(model,plan,watch,alarm):
    arr=np.asarray(plan[['minute','A','B']],float)
    if len(arr)<2 or len(arr)>61 or not np.isfinite(arr).all():raise ValueError('计划需要2～61行有限数值')
    if arr[0,0]!=0 or np.any(np.diff(arr[:,0])<=0) or arr[-1,0]>30:raise ValueError('时间须从0开始、严格递增且不超过30分钟')
    if not 0<watch<alarm:raise ValueError('阈值须满足0<关注阈值<报警阈值')
    fields=np.stack([predict(model,a,b) for _,a,b in arr]);delta=fields-fields[0]
    rows=[]
    for (t,a,b),s,d in zip(arr,fields,delta):
        i=int(np.argmax(abs(d)));peak=float(abs(d[i]))
        rows.append(dict(minute=t,A=a,B=b,max_change_mpa=peak,max_abs_stress_mpa=float(abs(s).max()),
            element=int(model['elements'][i]),position=str(model['positions'][i]),
            status='报警' if peak>=alarm else '关注' if peak>=watch else '未触发'))
    return pd.DataFrame(rows),fields,delta
if __name__=='__main__':print(json.dumps(train(),ensure_ascii=False,indent=2))
