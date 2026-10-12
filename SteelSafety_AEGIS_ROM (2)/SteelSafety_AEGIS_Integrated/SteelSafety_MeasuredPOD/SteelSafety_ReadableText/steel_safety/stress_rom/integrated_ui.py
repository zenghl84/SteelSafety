"""Local Streamlit preview of a CS13-to-CS18 axial stress-increment surrogate."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
import streamlit as st
from .mgt_geometry import parse
from .rom import ROOT, load_model, prediction_table, status, train
from .stress_io import find_result, read_stress

@st.cache_resource
def geometry(raw):
    model = parse(raw)
    active = next(s['elements'] for s in model['stages'] if s['name'] == 'CS18')
    elements = [e for e in model['elements'].values() if e['id'] in active]
    xyz = np.full((len(elements), 3, 3), np.nan)
    for i, e in enumerate(elements):
        xyz[i, 0] = model['nodes'][e['n1']]
        xyz[i, 1] = model['nodes'][e['n2']]
    return elements, xyz


@st.cache_resource
def cached_rom(raw):
    import io
    return load_model(io.BytesIO(raw))


def make_figure(elements, xyz, field, limit, focus):
    # Keep signed stress change from the I/J end with the larger magnitude.
    ordered = field.assign(magnitude=field.delta_stress_mpa.abs()).sort_values('magnitude')
    ends = ordered.drop_duplicates('element', keep='last')
    responses = ends.set_index('element').delta_stress_mpa.to_dict()
    values = np.array([responses.get(e['id'], np.nan) for e in elements])
    fig = go.Figure()
    valid = np.isfinite(values)
    def draw(mask, color, width):
        lines = xyz[mask]
        if len(lines):
            fig.add_trace(go.Scatter3d(x=lines[:, :, 0].ravel(), y=lines[:, :, 1].ravel(),
                                      z=lines[:, :, 2].ravel(), mode='lines',
                                      line=dict(color=color, width=width),
                                      showlegend=False, hoverinfo='skip'))
    draw(~valid, '#607088', 1.5)
    limit = max(float(limit), 1e-9)
    colors = sample_colorscale('RdBu_r', np.linspace(0, 1, 41))
    bins = np.zeros(len(elements), dtype=int)
    bins[valid] = np.clip(np.rint((values[valid] / limit + 1) * 20), 0, 40).astype(int)
    for i, color in enumerate(colors):
        draw(valid & (bins == i), color, 2.5)
    draw(np.array([e['id'] == focus for e in elements]), '#ffe282', 7)
    fig.add_trace(go.Scatter3d(x=[None], y=[None], z=[None], mode='markers',
                              marker=dict(color=[-limit], cmin=-limit, cmax=limit,
                                          colorscale='RdBu_r', showscale=True,
                              colorbar=dict(title='Δσ / MPa', thickness=12, len=.65)),
                              hoverinfo='skip', showlegend=False))
    fig.update_layout(height=660, paper_bgcolor='#0b1220', font_color='#dce9f9',
                      margin=dict(l=0, r=0, t=0, b=0), uirevision='CS18', showlegend=False,
                      scene=dict(bgcolor='#0b1220', aspectmode='data',
                                 xaxis=dict(title='X / m', showbackground=False),
                                 yaxis=dict(title='Y / m', showbackground=False),
                                 zaxis=dict(title='Z / m', showbackground=False),
                                 camera=dict(eye=dict(x=1.35, y=1.35, z=.85))))
    return fig



def sensor_values(field, sensors):
    """Only map exact I/J ends; interior positions have no end output."""
    from types import SimpleNamespace
    lookup = field.set_index(['element', 'position'])
    result = {}
    for row in sensors.itertuples(index=False):
        if float(row.position) not in (0., 1.):
            continue
        key = (int(row.element), 'I' if float(row.position) == 0. else 'J')
        if key not in lookup.index:
            continue
        value = lookup.loc[key]
        result[str(row.sensor_id)] = SimpleNamespace(
            predicted_delta_mpa=float(value.delta_stress_mpa),
            predicted_strain_ue=(float(value.predicted_axial_delta_strain_microstrain)
                                 if row.monitor_type != '弯曲' else float('nan')))
    return result


def render_rom(sensors, model_id):
    st.subheader('荷载驱动降阶预测')
    st.caption('CS13 → CS18 轴向应力增量 Δσ / MPa；倍率不是时间，当前结果不是实测反演。')
    import hashlib
    if hashlib.sha256((ROOT / 'source/model.mgt').read_bytes()).hexdigest() != model_id:
        st.warning('当前替换模型未关联本代理，请恢复随包原 MGT 后使用预测。')
        return None
    try:
        return _render_rom(sensors, model_id)
    except (ValueError, OSError, KeyError, ImportError) as exc:
        st.error('降阶预测暂不可用：' + str(exc))
        return None


def _render_rom(sensors, model_id):
    with st.expander('工况数据与训练', expanded=False):
        st.subheader('工况数据')
        st.caption('将 MIDAS 导出的同名结果放入 results 文件夹。')
        try:
            current_status = status(ROOT)
            st.dataframe(current_status, hide_index=True, width='stretch')
        except ValueError as exc:
            st.error(str(exc))
            return None
        if st.button('刷新数据状态'):
            st.rerun()
        if st.button('训练并检验', type='primary'):
            try:
                with st.spinner('读取应力并验证独立工况…'):
                    train(ROOT)
                st.success('训练与独立工况检验完成。请查看右侧误差。')
            except (ValueError, FileNotFoundError, ImportError) as exc:
                st.error(str(exc))
    
    model_path = ROOT / 'trained/stress_rom.npz'
    expected = pd.read_csv(ROOT / 'source/end_mapping.csv')
    model = None
    if model_path.exists():
        model = cached_rom(model_path.read_bytes())
        if model['metadata'].get('source_mgt_sha256') != model_id:
            st.error('代理训练模型与当前 MGT 不一致，请切回原模型。')
            return None
        interval = model['metadata']['applicable_interval']
        parameter = st.slider('CS18 施工活荷载倍率', float(interval[0]), float(interval[1]),
                                      float(np.clip(1., *interval)), .01)
        field = prediction_table(model, parameter)
        limit = max(abs(model['mean'][:, None] + model['basis'] @ model['coefficients'].T).max(), 1.)
        st.caption('仅改变施工荷载组18；其他荷载及施工历史沿用训练模型。')
        st.caption('显示代理预测。训练时间：' + model['metadata']['created_at'])
    else:
        cs18_path = find_result(ROOT, 'results/case_100_CS18')
        cs13_path = find_result(ROOT, 'results/CS13_reference')
        if cs18_path is None or cs13_path is None:
            st.info('请先提供 CS13 参考表和 case_100 的 CS18 应力表。')
            return None
        cs13, _ = read_stress(cs13_path, expected=expected, stage='CS13')
        cs18, _ = read_stress(cs18_path, expected=expected, stage='CS18')
        field = expected[['element', 'position']].copy()
        field['delta_stress_mpa'] = cs18.axial_stress_mpa.to_numpy() - cs13.axial_stress_mpa.to_numpy()
        field['predicted_axial_delta_strain_microstrain'] = (
            field.delta_stress_mpa.to_numpy() / expected.e_mpa.to_numpy() * 1e6)
        parameter = 1.
        limit = max(field.delta_stress_mpa.abs().max(), 1.)
        st.info('当前显示历史基准的 CS18−CS13 应力增量。补齐 4 个倍率工况后点击“训练并检验”。')
    
    elements, xyz = geometry((ROOT / 'source/model.mgt').read_bytes())
    left, right = st.columns([3, 1])
    with right:
        st.metric('施工活荷载倍率', f'{parameter:.2f}')
        st.metric('最大 Δσ / MPa', f'{field.delta_stress_mpa.max():.2f}')
        st.metric('最小 Δσ / MPa', f'{field.delta_stress_mpa.min():.2f}')
        st.caption('轴向测点的应变估算：Δε = Δσ/E；单位 με。')
        focus = st.number_input('查询梁单元编号', min_value=0, value=0, step=1)
        if focus:
            selected = field.loc[field.element == focus,
                                 ['element', 'position', 'delta_stress_mpa', 'predicted_axial_delta_strain_microstrain']]
            if selected.empty:
                st.info('该单元没有本版梁端应力输出。')
            else:
                st.dataframe(selected, hide_index=True, width='stretch')
        st.download_button('下载当前梁端增量 CSV', field.to_csv(index=False).encode('utf-8-sig'),
                           file_name=f'CS13_CS18_delta_stress_{parameter:.2f}.csv', mime='text/csv')
        sensor_map = sensors
        end_map = field.merge(expected[['element', 'position', 'e_mpa']], on=['element', 'position'], validate='one_to_one')
        sensor_rows = []
        for sensor in sensor_map.itertuples(index=False):
            if float(sensor.position) not in (0., 1.):
                continue
            position = 'I' if float(sensor.position) == 0 else 'J'
            rows = end_map.loc[(end_map.element == int(sensor.element)) & (end_map.position == position)]
            if len(rows):
                row = rows.iloc[0]
                sensor_rows.append(dict(测点=sensor.sensor_id, 单元=int(sensor.element),
                                        类型=sensor.monitor_type,
                                        Δσ_MPa=float(row.delta_stress_mpa),
                                        轴向Δε估算_με=(float(row.predicted_axial_delta_strain_microstrain) if sensor.monitor_type != '弯曲' else np.nan)))
        st.write('测点位置的模型增量')
        st.dataframe(pd.DataFrame(sensor_rows), hide_index=True, width='stretch')
        st.caption('S7/S8 当前映射为弯曲测点，上表的轴向 Δε 估算不代表弯曲表面应变。')
        if model is not None:
            st.write('独立工况检验')
            metrics = pd.DataFrame(model['metadata']['validation'])
            display = metrics[['lambda_value', 'rmse_mpa', 'max_abs_error_mpa']].rename(
                columns={'lambda_value': '倍率', 'rmse_mpa': 'RMSE / MPa', 'max_abs_error_mpa': '最大误差 / MPa'})
            st.dataframe(display, hide_index=True, width='stretch')
            st.caption('完整报告同时给出全场相对误差、荷载效应相对误差和峰值位置。')
    with left:
        st.plotly_chart(make_figure(elements, xyz, field, limit, int(focus)), width='stretch')
        st.caption('杆件颜色表示两阶段的轴向应力增量，采用 I/J 端绝对值较大者并保留正负号。')
    with st.expander('方法与适用范围'):
        st.write('应力 POD + 一维分段线性插值；预测 CS18 相对 CS13 的轴向应力增量。'
                 '适用于当前 CS18 施工历史、当前荷载分布及已采样倍率区间。'
                 '倍率不是未来时间，也不代表实测应力反演。')
        if model is not None:
            st.json(model['metadata'])
    
    with st.expander('POD 能量与完整检验报告'):
        energy_path = ROOT / 'trained/pod_energy.csv'
        if energy_path.exists():
            st.dataframe(pd.read_csv(energy_path), hide_index=True)
        if model is not None:
            st.download_button('下载完整检验报告 JSON', json.dumps(model['metadata'], ensure_ascii=False, indent=2), 'validation_report.json')
    return dict(stage='CS18', reference_stage='CS13', rank=model['basis'].shape[1] if model else 0,
                parameter=parameter, field=field, source='荷载驱动 POD 增量代理' if model else '历史基准增量',
                target_time=f'施工活荷载倍率 {parameter:.2f}', hover=sensor_values(field, sensors))
