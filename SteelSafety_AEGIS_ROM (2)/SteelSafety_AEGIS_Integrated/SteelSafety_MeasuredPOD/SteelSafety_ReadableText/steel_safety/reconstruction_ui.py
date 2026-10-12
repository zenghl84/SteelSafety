"""Streamlit controls and result presentation for sparse reconstruction."""
import hashlib
import json
import pandas as pd
import streamlit as st
from sensor_reconstruction import (REFERENCE_STAGE, data_signature, load_bundle,
    parse_monitoring, prepare_observations, sensor_indices, validate_candidates,
    reconstruct, full_result_frame, simulated_monitoring)


@st.cache_resource(show_spinner=False)
def cached_bundle(data_dir, signature, _model):
    return load_bundle(data_dir, _model)


@st.cache_data(show_spinner=False)
def cached_csv(raw):
    return parse_monitoring(raw)


@st.cache_data(show_spinner=False)
def cached_validation(signature, indices, _bundle):
    return validate_candidates(_bundle, indices)


def render_reconstruction(data_dir, model, sensors, enabled):
    st.subheader('实测驱动重构')
    st.caption('以 CS13 为共同基准，使用有效轴向测点估计应力增量。S7、S8 保留显示，不参与纯轴向求解。')
    if not enabled:
        st.info('请使用与 POD 数据匹配的原模型，并先核对九测点配置。')
        return None
    source = st.radio('数据来源', ['上传实测 CSV', 'MIDAS 模拟数据演示'], horizontal=True, key='rom_source')
    uploaded = None
    if source == '上传实测 CSV':
        uploaded = st.file_uploader('上传用于重构的监测数据', type=['csv'], key='rom_csv')
        st.download_button('下载重构 CSV 空白模板',
            'time,sensor_id,strain_ue,temperature_c\n'.encode('utf-8-sig'), 'reconstruction_template.csv')
        st.caption('应变单位 με；应力输出 MPa。支持中文列名“时间、测点编号、应变、温度”。只记录真实读数，缺测请留出该行。')
        if uploaded is None:
            st.info('上传数据后，选择基准、温度处理和目标时刻，再运行重构；也可先选择模拟演示。')
            return None
    try:
        signature = data_signature(data_dir)
        with st.spinner('加载增量 POD 数据…'):
            bundle = cached_bundle(str(data_dir), signature, model)
        if uploaded is not None:
            raw = uploaded.getvalue()
            frame = cached_csv(raw)
            source_label = '用户导入数据'
            if 'source' in frame and frame.source.fillna('').str.contains('模拟|演示|synthetic', case=False).any():
                source_label = '导入模拟数据（非实测）'
        else:
            frame = simulated_monitoring(bundle, sensors)
            raw = frame.to_csv(index=False).encode('utf-8-sig')
            source_label = 'MIDAS 模拟演示（非实测）'
        if '模拟' in source_label:
            st.info('当前为 MIDAS 模拟演示。时间为虚构标记；S7/S8 的演示值也仅来自轴向计算，不能用于验证弯曲测量。')
            st.download_button('下载模拟演示 CSV', raw, 'MIDAS_simulated_monitoring.csv')
        times = sorted(frame.time.unique())
        file_key = hashlib.sha256(raw).hexdigest()[:12]
        target = st.selectbox('目标时刻', times, index=len(times)-1,
                              format_func=lambda t: str(pd.Timestamp(t)), key='rom_target_' + file_key)
        stage_options = [REFERENCE_STAGE] + bundle['stages']
        if source == 'MIDAS 模拟数据演示':
            current_stage = str(frame.loc[frame.time == target, 'stage'].iloc[0])
            st.caption('模拟数据对应阶段：' + current_stage)
        else:
            current_stage = st.selectbox('该时刻对应的施工阶段', stage_options,
                                        index=len(stage_options)-1, key='rom_stage')
            st.caption('按实际施工记录选择；侧栏阶段只筛选几何，重构阶段以此处设置为准。')
        c1, c2 = st.columns(2)
        with c1:
            basis_label = st.selectbox('实测应变基准', ['请选择应变基准', '已相对 CS13 归零的增量', '原始读数：扣除 CS13 参考时刻'],
                index=1 if uploaded is None else 0, key='rom_basis_' + file_key)
        with c2:
            temp_label = st.selectbox('温度处理', ['请选择温度处理', '已完成温度补偿', '按温度差扣除指定温度项'],
                index=1 if uploaded is None else 0, key='rom_temp_' + file_key)
        mode = {'已相对 CS13 归零的增量': 'increment', '原始读数：扣除 CS13 参考时刻': 'raw'}.get(basis_label)
        temperature_mode = {'已完成温度补偿': 'corrected', '按温度差扣除指定温度项': 'subtract'}.get(temp_label)
        reference_time = None
        if mode == 'raw':
            options = [None] + [t for t in times if t <= target]
            reference_time = st.selectbox('CS13 参考时刻（按现场记录选择）', options,
                format_func=lambda t: '请选择对应 CS13 的参考时刻' if t is None else str(pd.Timestamp(t)),
                key='rom_reference_' + file_key)
        with st.expander('材料、同步与温度参数'):
            elastic_mpa = st.number_input('弹性模量 E / MPa', min_value=1.0, value=206000.0, step=1000.0, key='rom_E')
            max_age_s = st.number_input('允许各测点落后目标时刻的最长时间 / s', min_value=0.0, value=60.0, step=1.0, key='rom_age')
            st.caption('使用不晚于目标时刻的最近读数；过期或缺失读数不参与求解。E 默认取附件材料值 206000 MPa。')
            thermal = st.number_input('有效温度修正系数 / (με/℃)', value=12.0, step=0.1, key='rom_thermal')
            st.caption('默认 12 来自模型热膨胀系数。只有原始读数确实包含可按此项扣除的温度影响时才适用；应变计补偿方式、约束热应变需结合试验核验，避免重复扣除。')
        if mode is None or temperature_mode is None or (mode == 'raw' and reference_time is None):
            st.info('请选择数据的实际基准与温度处理；程序不会默认把首条记录当作 CS13。')
            return None
        observations = prepare_observations(frame, sensors, target, mode, reference_time,
                                             temperature_mode, thermal, max_age_s)
        indices = sensor_indices(bundle, sensors)
        for i, row in observations.iterrows():
            idx = indices.get(row.sensor_id)
            if row.eligible and (idx is None or not bundle['active'][current_stage][idx] or not bundle['active'][REFERENCE_STAGE][idx]):
                observations.loc[i, 'eligible'] = False
                observations.loc[i, 'reason'] = '缺少端部映射或当前/基准阶段未启用'
        used = observations[observations.eligible]
        st.caption(f'有效轴向观测：{len(used)} / 7；九测点均保留在结果列表中。')
        if len(used) < 2:
            st.error('有效轴向测点不足两个，无法重构。请检查时刻、允许时差与参考读数。')
            st.dataframe(observations[['sensor_id', 'reason']], hide_index=True, width='stretch')
            return None
        used_indices = tuple(indices[s] for s in used.sensor_id)
        with st.spinner('核对测点可观测性与留出阶段误差…'):
            validation = cached_validation(signature, used_indices, bundle)
        with st.expander('求解参数与验证依据'):
            selection = st.radio('参数选择', ['按阶段交叉验证推荐', '手动设置'], horizontal=True, key='rom_parameters')
            rank, alpha = validation['rank'], validation['alpha']
            if selection == '手动设置':
                max_rank = int(validation['summary']['rank'].max())
                rank = st.selectbox('增量 POD 阶数', list(range(1, max_rank+1)), index=min(rank,max_rank)-1, key='rom_rank_' + str(len(used)))
                alpha = st.selectbox('相对正则化参数', [1e-6, 1e-4, 1e-3, 1e-2, 1e-1], index=2, key='rom_alpha')
            st.caption('该模块以 CS13 为零点，从 CS14～CS18 的差值训练增量基底；原十阶 POD 文件保持可用。')
            display = validation['summary'].rename(columns={'rank': '阶数', 'alpha': '正则化参数',
                'folds': '留出阶段数', 'mean_error': '平均相对L2误差', 'max_error': '最大相对L2误差', 'noise_error': '假设1με噪声的平均误差'})
            st.dataframe(display, hide_index=True, width='stretch')
            st.caption('每折排除被验证阶段，再重新训练基底；只在该阶段活动端部计算误差。推荐按假设 1με 独立噪声（E=206000 MPa）的误差排序。此表用于调参，不是独立最终测试，也不是现场精度。')
        cv_row = validation['summary'][(validation['summary']['rank'] == rank) & (validation['summary'].alpha == alpha)].iloc[0]
        st.caption(f'当前参数：{rank} 阶，正则化 {alpha:g}；留出阶段平均全场增量误差 {cv_row.mean_error:.1%}。')
        if cv_row.mean_error > 0.10:
            st.warning('当前模型的留出阶段全场误差仍较大。结果用于重构方法试验与趋势查看，尚不足以支持定量安全判断。')
        request = {'data': hashlib.sha256(raw).hexdigest(), 'model': signature,
            'mapping': sensors.to_json(orient='records'), 'source': source_label,
            'target': str(pd.Timestamp(target)), 'stage': current_stage, 'mode': mode,
            'reference_time': str(reference_time), 'temperature': temperature_mode,
            'thermal': thermal, 'E': elastic_mpa, 'max_age': max_age_s, 'rank': rank, 'alpha': alpha}
        request_id = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        if st.button('运行实测驱动重构', type='primary', key='rom_run'):
            with st.spinner('估计系数并恢复全结构响应…'):
                result = reconstruct(bundle, sensors, observations, current_stage, rank, alpha, elastic_mpa)
                result.update(source=source_label, target_time=str(pd.Timestamp(target)),
                              request_id=request_id, settings=request,
                              cv_mean_error=float(cv_row.mean_error))
                result['full_csv'] = full_result_frame(bundle, result).to_csv(index=False).encode('utf-8-sig')
                result['sensor_csv'] = result['sensors'].assign(source=source_label,
                    target_time=str(pd.Timestamp(target)), reference_stage=REFERENCE_STAGE,
                    stage=current_stage).to_csv(index=False).encode('utf-8-sig')
                result['report_json'] = json.dumps({'settings': request, 'fit_rmse_ue': result['fit_rmse_ue'],
                    'condition': result['condition'], 'cv_mean_error': float(cv_row.mean_error),
                    'coefficients': result['coefficients'].tolist(),
                    'note': '调参交叉验证误差，非现场精度；总应力依赖CS13模型基准'}, ensure_ascii=False, indent=2).encode('utf-8')
                st.session_state['rom_last_result'] = result
        result = st.session_state.get('rom_last_result')
        if result is None or result['request_id'] != request_id:
            st.info('点击“运行实测驱动重构”生成当前设置对应的结果。修改输入后，旧结果不会继续用于三维测点。')
            return None
        a, b, c = st.columns(3)
        a.metric('参与求解测点', int(result['sensors'].eligible.sum()))
        b.metric('观测拟合 RMSE / με', f"{result['fit_rmse_ue']:.2f}")
        c.metric('有效梁端响应数', result['active_count'])
        st.caption(f"结果时刻：{result['target_time']} · {current_stage} · {source_label}。拟合残差仅针对参与求解测点，不能作为全结构误差。")
        if result['outside_training_scale']:
            st.warning('本次系数幅值超出训练样本的常见范围，可能存在外推、基准不一致或异常观测。')
        table = result['sensors'].rename(columns={'sensor_id':'测点', 'element':'单元', 'monitor_type':'监测类别',
            'sample_time':'采用读数时间', 'age_s':'时差/s', 'delta_strain_ue':'观测应变增量/με',
            'predicted_axial_strain_ue':'估计轴向应变增量/με', 'predicted_delta_mpa':'估计轴向应力增量/MPa',
            'estimated_total_mpa':'估计轴向总应力/MPa', 'residual_ue':'观测拟合残差/με', 'reason':'用途'})
        st.dataframe(table[['测点','单元','监测类别','用途','观测应变增量/με','估计轴向应力增量/MPa',
                           '估计轴向总应力/MPa','观测拟合残差/με','采用读数时间','时差/s']], hide_index=True, width='stretch')
        axial = result['sensors'][result['sensors'].eligible].set_index('sensor_id')
        st.bar_chart(axial[['delta_strain_ue', 'predicted_axial_strain_ue']].rename(columns={
            'delta_strain_ue':'观测应变增量/με', 'predicted_axial_strain_ue':'重构应变增量/με'}))
        st.caption('估计总应力 = CS13 模型应力 + 重构增量；S7/S8 的轴向预测仅作参考，不与表面弯曲观测计算拟合残差。')
        a, b, c = st.columns(3)
        with a: st.download_button('导出全梁端重构结果', result['full_csv'], 'reconstructed_axial_stress.csv')
        with b: st.download_button('导出九测点对比', result['sensor_csv'], 'sensor_reconstruction_comparison.csv')
        with c: st.download_button('导出本次参数与诊断', result['report_json'], 'reconstruction_diagnostics.json')
        with st.expander('导入的应变历史'):
            sid = st.selectbox('查看测点历史', sorted(frame.sensor_id.unique()), key='rom_history_sensor')
            history = frame[frame.sensor_id == sid].set_index('time')
            st.line_chart(history['strain_ue'])
            if 'temperature_c' in history:
                st.line_chart(history['temperature_c'])
        # Small lookup only: the 3D view never adds per-member stress traces.
        result['hover'] = {r.sensor_id: r for r in result['sensors'].itertuples(index=False)}
        return result
    except Exception as ex:
        st.error('重构未完成：' + str(ex))
        return None
