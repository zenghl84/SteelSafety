import re

def ids(text):
    out=set()
    for token in text.split():
        m=re.fullmatch(r'(\d+)(?:to(\d+)(?:by(\d+))?)?',token,re.I)
        if not m: raise ValueError('无法识别编号范围：'+token)
        a,b,step=m.groups();out.update(range(int(a),int(b or a)+1,int(step or 1)))
    return out

def parse(raw):
    try: text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:text=raw.decode('gb18030')
    sections={};key='';pending=''
    for line in text.splitlines():
        line=line.split(';')[0].strip()
        if not line:continue
        if line.startswith('*'):
            key=line.split(',')[0].strip();sections.setdefault(key,[]);continue
        pending+=line.rstrip('\\').strip()+' '
        if line.endswith('\\'):continue
        sections.setdefault(key,[]).append(pending.strip());pending=''
    units=[v.strip() for v in sections['*UNIT'][0].split(',')]
    scale={'MM':.001,'M':1.,'CM':.01}.get(units[1].upper())
    if scale is None:raise ValueError('暂不支持长度单位 '+units[1])
    nodes={};elements={}
    for row in sections['*NODE']:
        v=row.split(',');n=int(v[0]);nodes[n]=tuple(float(x)*scale for x in v[1:4])
    for row in sections['*ELEMENT']:
        v=[x.strip() for x in row.split(',')]
        if v[1] not in ('BEAM','TENSTR','TRUSS'):raise ValueError('暂不支持单元类型 '+v[1])
        i=int(v[0])
        if i in elements:raise ValueError('单元编号重复')
        elements[i]={'id':i,'type':v[1],'material':int(v[2]),'section':int(v[3]),'n1':int(v[4]),'n2':int(v[5])}
    for e in elements.values():
        if e['n1'] not in nodes or e['n2'] not in nodes:raise ValueError('单元引用缺失节点')
    def names(key):return {int(v[0]):v[2].strip() for r in sections.get(key,[]) for v in [r.split(',')]}
    groups={}
    for row in sections.get('*GROUP',[]):
        v=row.split(',');groups[v[0].strip()]=ids(v[2]) if len(v)>2 else set()
    stages=[];active=set();current=None
    for row in sections.get('*STAGE',[]):
        if '=' not in row:continue
        k,val=row.split('=',1);parts=[x.strip() for x in val.split(',')]
        if k=='NAME':
            if current:current['elements']=set(active);stages.append(current)
            current={'name':parts[0],'changes':[]}
        elif current:
            current['changes'].append(row)
            if k in ('AELEM','DELEM'):
                for name in parts[::2]:
                    if name not in groups:raise ValueError('施工阶段引用未知结构组 '+name)
                    if k=='AELEM':active.update(groups[name])
                    else:active.difference_update(groups[name])
    if current:current['elements']=set(active);stages.append(current)
    return dict(nodes=nodes,elements=elements,materials=names('*MATERIAL'),sections=names('*SECTION'),stages=stages,units=units,loads=sections.get('*STLDCASE',[]))
