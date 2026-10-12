from pathlib import Path
import io
import hashlib
from html import escape
import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from model import parse
from partition_rom.ui import render_rom
from ui_fonts import FONT_FAMILY, apply_ui_fonts
@st.cache_resource
def pod_module():
    import pod_model
    return pod_model


st.set_page_config(page_title='钢结构安全智能体 v1.3',page_icon='🏗️',layout='wide')
apply_ui_fonts()
st.markdown('''<style>
.stApp {background:#0b1220;color:#f1f5f9;color-scheme:dark}
[data-testid="stMainBlockContainer"] {padding-top:3.5rem;padding-bottom:1.5rem}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {gap:1rem}
[data-testid="stHeader"] {background:#0b1220}
[data-testid="stSidebar"] {background:#101c2e;color:#f1f5f9}
h1,h2,h3,h4,h5,h6 {color:#f8fafc!important}
h1 {letter-spacing:1px}
[data-testid="stMarkdownContainer"],
[data-testid="stWidgetLabel"],
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"] {color:#f1f5f9!important}
[data-testid="stCaptionContainer"] {color:#cbd5e1!important}
[data-testid="stMetric"] {background:#152238;border:1px solid #40536c;border-radius:12px;padding:16px}
[data-baseweb="tab"] {color:#cbd5e1!important}
[data-baseweb="tab"][aria-selected="true"] {color:#67e8f9!important}
[data-baseweb="input"], [data-baseweb="base-input"],
[data-baseweb="select"] > div {background:#152238!important;color:#f1f5f9!important;border-color:#52657f!important}
input,textarea {color:#f1f5f9!important;-webkit-text-fill-color:#f1f5f9!important;caret-color:#67e8f9}
input::placeholder,textarea::placeholder {color:#b8c5d6!important;-webkit-text-fill-color:#b8c5d6!important}
[data-baseweb="popover"], [role="listbox"], [role="option"] {background:#152238!important;color:#f1f5f9!important}
[role="option"][aria-selected="true"] {background:#294462!important;color:#ffffff!important}
[data-testid="stFileUploaderDropzone"] {background:#152238!important;color:#f1f5f9!important;border:1px dashed #7187a3}
[data-testid="stBaseButton-secondary"] {background:#20324b!important;color:#f1f5f9!important;border-color:#7187a3!important}
[data-testid="stBaseButton-secondary"]:hover {background:#304a69!important;border-color:#67e8f9!important}
[data-testid="stAlert"] {background:#172b42!important;color:#f1f5f9!important}
[data-testid="stCode"] {background:#152238!important;color:#e2e8f0!important}
</style>''',unsafe_allow_html=True)
@st.cache_data
def load(raw):return parse(raw)
@st.cache_data(show_spinner=False)
def load_end_stress(mapping_raw, mean_raw):
    """Resolve signed POD mean response by element AND end, not member average."""
    import numpy as np
    mapping = pd.read_csv(io.BytesIO(mapping_raw))
    mean = np.load(io.BytesIO(mean_raw), allow_pickle=False).reshape(-1)
    required = {'element', 'position', 'node', 'index'}
    if not required <= set(mapping):
        raise ValueError('POD 映射缺少必需列')
    if mapping.duplicated(['element', 'position']).any():
        raise ValueError('POD 映射存在重复单元端部')
    result = {}
    for row in mapping.itertuples(index=False):
        idx = int(row.index)
        if idx != row.index or not 0 <= idx < len(mean):
            raise ValueError('POD 响应索引无效')
        result[(int(row.element), str(row.position).strip())] = (int(row.node), float(mean[idx]))
    return result


def sensor_stress_text(row, element, end_stress):
    if row.position not in (0.0, 1.0):
        return '轴向应力：暂无该位置数据（仅有 I/J 端结果）'
    end = 'I' if row.position == 0 else 'J'
    entry = end_stress.get((int(row.element), end))
    node = element['n1' if end == 'I' else 'n2']
    value = entry[1] if entry and entry[0] == node else None
    text = f'{value:.4f}（源数据单位）' if value is not None and math.isfinite(value) else '暂无数据'
    label = '轴向应力（参考）' if row.monitor_type == '弯曲' else '轴向应力'
    result = f'{label} · {end} 端：{text}'
    if row.monitor_type == '弯曲':
        result += '<br>弯曲应力：暂无数据（现有 POD 仅含轴向应力）'
    return result

@st.cache_data(show_spinner=False)
def material_geometry(raw, stage, mat, sec, colorby):
    """Batch all members of a material/type into one WebGL trace."""
    model = load(raw)
    active = set(model['elements']) if stage == '完整模型' else next(
        s['elements'] for s in model['stages'] if s['name'] == stage)
    key = 'material' if colorby == '材料' else 'type'
    palette = ['#44d7ed','#839bff','#ffca74','#bd8afd','#68e0b0']
    categories = sorted({e[key] for e in model['elements'].values()}, key=str)
    groups = {}
    for eid, e in model['elements'].items():
        if eid not in active or (mat != '全部' and e['material'] != mat) or (sec != '全部' and e['section'] != sec):
            continue
        xyz = groups.setdefault(e[key], [[], [], []])
        for j in range(3):
            xyz[j].extend([model['nodes'][e['n1']][j], model['nodes'][e['n2']][j], None])
    traces = []
    for group, xyz in groups.items():
        label = model['materials'].get(group, str(group)) if key == 'material' else str(group)
        traces.append(go.Scatter3d(x=xyz[0], y=xyz[1], z=xyz[2], mode='lines',
            name=label, line=dict(color=palette[categories.index(group) % len(palette)], width=3),
            hoverinfo='skip'))
    return traces


def default_sensors(model):
    # User-supplied monitoring schedule; S4 excluded explicitly. Keep original IDs.
    return pd.DataFrame([
        ('S1', 11368, 1.0, '应力'),
        ('S2', 5545, 1.0, '应力'),
        ('S3', 5879, 0.0, '应力'),
        ('S5', 10341, 0.0, '应力'),
        ('S6', 4437, 1.0, '应力'),
        ('S7', 4540, 0.0, '弯曲'),
        ('S8', 10443, 1.0, '弯曲'),
        ('S9', 4429, 0.0, '应力'),
        ('S10', 10334, 1.0, '应力'),
    ], columns=['sensor_id', 'element', 'position', 'monitor_type'])


def validate_sensors(frame, model):
    columns = ['sensor_id', 'element', 'position', 'monitor_type']
    if not set(columns) <= set(frame.columns) or len(frame) != 9:
        raise ValueError('必须提供九行，列名为 sensor_id、element、position、monitor_type。')
    frame = frame[columns].copy()
    if frame.isna().any().any():
        raise ValueError('测点配置不能有空值。')
    frame['sensor_id'] = frame['sensor_id'].astype(str).str.strip()
    if not frame.monitor_type.isin(['应力', '弯曲']).all():
        raise ValueError('monitor_type 必须为“应力”或“弯曲”。')
    if frame.sensor_id.eq('').any() or frame.sensor_id.duplicated().any():
        raise ValueError('测点编号必须非空且唯一。')
    for col in ['element', 'position']:
        frame[col] = pd.to_numeric(frame[col], errors='raise')
        if not all(math.isfinite(v) for v in frame[col]):
            raise ValueError('单元编号和位置必须为有限数值。')
    if (frame.element % 1 != 0).any():
        raise ValueError('单元编号必须为整数。')
    frame['element'] = frame.element.astype(int)
    missing = set(frame.element) - set(model['elements'])
    if missing:
        raise ValueError('模型中不存在单元：' + ', '.join(map(str, sorted(missing))))
    if not frame.position.between(0, 1).all():
        raise ValueError('position 必须在 0～1 之间。')
    if frame.duplicated(['element', 'position']).any():
        raise ValueError('两个测点不能位于同一单元的同一位置。')
    return frame

from aegis_dashboard import render_overview, render_snapshot
render_overview()

with st.sidebar:
    st.header('模型与视图')
    uploaded=st.file_uploader('替换 MGT 模型',type=['mgt'])
raw_model = uploaded.getvalue() if uploaded else (Path(__file__).parent/'data/model.mgt').read_bytes()
try: m = load(raw_model)
except Exception as ex: st.error('模型读取失败：'+str(ex)); st.stop()
model_id = hashlib.sha256(raw_model).hexdigest()
# A replacement model must not silently inherit stresses from the bundled model.
reference_id = '00b2b7b8afe2d9ffe3c6e887725db966a3b60ac9d2693e24273a157e882871d5'
end_stress = {}
if model_id == reference_id:
    try:
        end_stress = load_end_stress((Path(__file__).parent/'data/pod_mapping.csv').read_bytes(),
                                     (Path(__file__).parent/'data/pod_mean.npy').read_bytes())
    except Exception as ex:
        st.warning('端部应力读取失败，测点仍可显示：' + str(ex))
sensor_version = model_id + ':actual-nine-without-S4-v1'
if st.session_state.get('sensor_model') != sensor_version:
    st.session_state.sensor_model = sensor_version
    st.session_state.sensor_mapping = default_sensors(m)
    st.session_state.sensor_confirmed = model_id == reference_id
with st.sidebar:
    stage=st.selectbox('施工阶段',['完整模型']+[s['name'] for s in m['stages']])
    mat=st.selectbox('材料',['全部']+list(m['materials']),format_func=lambda x:x if x=='全部' else f"{x} · {m['materials'][x]}")
    sec=st.selectbox('截面',['全部']+list(m['sections']),format_func=lambda x:x if x=='全部' else f"{x} · {m['sections'][x]}")
    colorby = st.radio('颜色依据',['材料', '单元类型'])
    st.caption('颜色表示分类，不表示安全等级。坐标显示单位为米。')
active=set(m['elements']) if stage=='完整模型' else next(s['elements'] for s in m['stages'] if s['name']==stage)
visible=[e for i,e in m['elements'].items() if i in active and (mat=='全部' or e['material']==mat) and (sec=='全部' or e['section']==sec)]
with st.sidebar:
    with st.expander('模型资料', expanded=False):
        st.subheader('模型数据')
        st.write('荷载工况：'+' / '.join(m['loads']))
        st.warning('自定义材料及施工阶段需要结合原 MIDAS 模型核验。本页面的几何检查不能替代受力模型审查。')
        rows=[{**e,'material_name':m['materials'].get(e['material'],''),'section_name':m['sections'].get(e['section'],'')}
              for e in m['elements'].values()]
        elements_frame=pd.DataFrame(rows)
        st.dataframe(elements_frame,width='stretch',height=280)
        st.download_button('导出单元清单',elements_frame.to_csv(index=False).encode('utf-8-sig'),'elements.csv')
        st.dataframe(pd.DataFrame([{'阶段':s['name'],'活动单元数':len(s['elements'])}
                                  for s in m['stages']]),width='stretch',height=240)
cs=st.columns(4)
for c,label,value in zip(cs,['模型节点','当前可见单元','施工阶段','安全评估'],[len(m['nodes']),len(visible),len(m['stages']),'待评估']):c.metric(label,value)
snapshot,twin,reconstruction_tab,assistant=st.tabs(['实测快照','三维孪生','安全预测与预警','现场安全助手'])
with reconstruction_tab:
    reconstruction_result = render_rom(st.session_state.sensor_mapping, model_id)
with twin:
    left,right=st.columns([4,1])
    with right:
        st.subheader('杆件查询')
        selected=st.number_input('单元编号（0 为不选择）',min_value=0,value=0,step=1)
        e=m['elements'].get(selected)
        if selected and not e:st.warning('该单元编号不存在。')
        if e:
            st.write('类型：'+e['type']);st.write('材料：'+m['materials'].get(e['material'],str(e['material'])))
            st.write('截面：'+m['sections'].get(e['section'],str(e['section'])))
            a,b=m['nodes'][e['n1']],m['nodes'][e['n2']]
            st.write(f"长度：{math.dist(a,b):.3f} m")
            st.write(f"节点：{e['n1']} → {e['n2']}")
            if e not in visible:st.info('该杆件不在当前阶段或筛选范围中，未高亮。')
        st.info('材料颜色保留原配色；圆点表示测点，悬停查看对应单元及应力。杆件信息请按编号查询。')
        st.divider()
        st.subheader('安全预测与预警')
        if reconstruction_result is None:
            st.write('在“安全预测与预警”页检查工况数据并训练代理。')
            st.caption('当前暂无代理预测结果。')
        else:
            st.write(f"结果阶段：{reconstruction_result['stage']}")
            st.write(f"POD 阶数：{reconstruction_result['rank']}")
            st.write(reconstruction_result["warning"])
            st.write(reconstruction_result["warning_detail"])
            st.caption(reconstruction_result['source'])
            st.caption(reconstruction_result['target_time'])
    with st.expander('九测点配置（填写实际测点对应单元）', expanded=not st.session_state.sensor_confirmed):
        st.caption('已按实际布置表配置九个测点并排除 S4。position：0 为 I 端，1 为 J 端；应力按对应控制端读取。')
        mapping_file = st.file_uploader('导入测点配置 CSV', type=['csv'], key='sensor_csv_' + model_id)
        with st.form('sensor_config_' + model_id):
            edited = st.data_editor(st.session_state.sensor_mapping, num_rows='fixed', hide_index=True,
                column_config={'sensor_id': '测点编号', 'element': '单元编号',
                    'monitor_type': st.column_config.SelectboxColumn('监测类别', options=['应力','弯曲']),
                    'position': st.column_config.NumberColumn('沿杆件位置（0～1）', min_value=0.0, max_value=1.0, step=0.05)},
                key='sensor_editor_' + sensor_version)
            confirmed = st.checkbox('已核对以上九个测点与实际布置一致', value=st.session_state.sensor_confirmed)
            apply_mapping = st.form_submit_button('应用配置（上传 CSV 时优先使用 CSV）')
        if apply_mapping:
            try:
                candidate = pd.read_csv(io.BytesIO(mapping_file.getvalue()), dtype={'sensor_id':str}) if mapping_file else edited
                st.session_state.sensor_mapping = validate_sensors(candidate, m)
                st.session_state.sensor_confirmed = confirmed
                st.session_state.pop('rom_last_result', None)
                st.rerun()
            except Exception as ex:
                st.error('测点配置未应用：' + str(ex))
        st.download_button('下载当前测点配置 CSV', st.session_state.sensor_mapping.to_csv(index=False).encode('utf-8-sig'), 'sensor_mapping.csv')
        st.caption('配置在当前会话保留；下载 CSV 后，下次打开可重新导入。')
    if not st.session_state.sensor_confirmed:
        st.warning('当前模型或配置尚未核对，暂不显示测点；请在“九测点配置”中核对并确认。')
    if reconstruction_result is None:
        st.caption('当前无荷载代理结果；S7/S8 的弯曲应力待接入。')
    else:
        st.caption(f"测点数值来自 {reconstruction_result['target_time']} / {reconstruction_result['stage']} 的轴向应力增量预测，单位 MPa（相对计划起点）。侧栏筛选仅改变几何范围。")
    if model_id != reference_id:
        st.info('当前为替换模型，未关联其应力数据，测点应力显示“暂无数据”。')
    show_sensors = st.checkbox('显示测点标记', value=True)
    fig = go.Figure(data=material_geometry(raw_model, stage, mat, sec, colorby))
    visible_ids = {e['id'] for e in visible}
    points, labels, details = [], [], []
    rows_to_plot = st.session_state.sensor_mapping.itertuples(index=False) if st.session_state.sensor_confirmed else []
    for row in rows_to_plot:
        e = m['elements'].get(int(row.element))
        if not e or e['id'] not in visible_ids:
            continue
        start, end = m['nodes'][e['n1']], m['nodes'][e['n2']]
        points.append([a + float(row.position)*(b-a) for a,b in zip(start,end)])
        labels.append(escape(str(row.sensor_id)))
        stress_text = '轴向应力增量：暂无代理结果'
        stress_source = '尚未关联有效代理结果'
        if reconstruction_result is not None:
            value = reconstruction_result['hover'].get(str(row.sensor_id))
            stress_source = escape(reconstruction_result['source']) + '<br>结果工况：' + escape(reconstruction_result['target_time']) + ' · ' + escape(reconstruction_result['stage'])
            if value is not None and math.isfinite(value.predicted_delta_mpa):
                stress_text = f'预测轴向应力增量：{value.predicted_delta_mpa:.4f} MPa（相对计划起点，同一 CS18）'
                if math.isfinite(value.predicted_strain_ue):
                    stress_text += f'<br>模型轴向应变增量估算：{value.predicted_strain_ue:.3f} με'
                if row.monitor_type == '弯曲':
                    stress_text += '<br>弯曲应力：暂无数据；轴向估计仅作参考'
            else:
                stress_text = '轴向应力增量：暂无该位置有效结果'

        status = '已确认位置'
        control_end = 'I' if row.position == 0 else ('J' if row.position == 1 else '杆件内部')
        details.append(f"测点：{escape(str(row.sensor_id))}（{status}）<br>单元：{e['id']} · {e['type']}"
            f"<br>材料：{escape(m['materials'].get(e['material'], str(e['material'])))}"
            f"<br>截面：{escape(m['sections'].get(e['section'], str(e['section'])))}"
            f"<br>监测类别：{escape(row.monitor_type)} · 控制端：{control_end}"
            f"<br>I / J 节点：{e['n1']} / {e['n2']}<br>沿杆件位置：{row.position:.2f}"
            f"<br>{stress_text}<br>来源：{stress_source}")
    if show_sensors and points:
        fig.add_trace(go.Scatter3d(x=[p[0] for p in points], y=[p[1] for p in points], z=[p[2] for p in points],
            mode='markers+text', text=labels, textposition='top center', textfont=dict(color='#ffffff', size=12, family=FONT_FAMILY),
            marker=dict(size=7, color='#ff657e', symbol='circle', line=dict(color='#ffffff', width=2)),
            customdata=details, hovertemplate='%{customdata}<extra></extra>', showlegend=False, name='测点'))
    st.caption(f'当前筛选范围内测点：{len(points)} / 9。阶段、材料和截面筛选会同步隐藏范围外的测点。')
    e=m['elements'].get(selected)
    if e and e in visible:
        pts=[m['nodes'][e[n]] for n in ['n1','n2']]
        fig.add_trace(go.Scatter3d(x=[p[0] for p in pts],y=[p[1] for p in pts],z=[p[2] for p in pts],mode='lines+markers',line=dict(color='#ff657e',width=10),name=f'选中 {selected}'))
    fig.update_layout(height=650,margin=dict(l=0,r=0,t=10,b=0),paper_bgcolor='#0b1220',font_color='#dce8f9',font_family=FONT_FAMILY,hoverlabel_font_family=FONT_FAMILY,legend=dict(orientation='h'),scene=dict(bgcolor='#0b1220',aspectmode='data',xaxis_title='X / m',yaxis_title='Y / m',zaxis_title='Z / m'),uirevision=model_id)
    with left:st.plotly_chart(fig,width='stretch',key='model_view',config={'displaylogo':False})
    if stage!='完整模型':
        st.caption('阶段视图按结构组累计启用与撤除杆件；不执行受力分析，也不显示支撑的实际变形。')
        with st.expander('该阶段原始设置'):st.code('\n'.join(next(s['changes'] for s in m['stages'] if s['name']==stage)))
with snapshot:
    # Reuse the finished twin figure, including its markers, hover data and highlight.
    render_snapshot(fig)
with assistant:
    from site_agent.ui import render_assistant
    render_assistant(reconstruction_result)
