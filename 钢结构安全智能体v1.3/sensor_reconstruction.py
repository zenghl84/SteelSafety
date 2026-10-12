"""CS13-referenced sparse strain reconstruction. No Streamlit dependency.

Units: stress MPa (N/mm^2), strain microstrain, temperature Celsius.
S7/S8 remain visible but are not pure-axial observations.
"""
from pathlib import Path
import hashlib
import io
import re
import numpy as np
import pandas as pd

REFERENCE_STAGE = 'CS13'
AXIAL_IDS = ('S1', 'S2', 'S3', 'S5', 'S6', 'S9', 'S10')
ALPHAS = (1e-6, 1e-4, 1e-3, 1e-2, 1e-1)


def data_signature(data_dir):
    """Hash source bytes; replacing a source invalidates cached results."""
    p = Path(data_dir)
    return hashlib.sha256(b''.join((p / name).read_bytes() for name in
        ('MIDAS_POD_matrix.xlsx', 'pod_mapping.csv', 'model.mgt'))).hexdigest()


def load_bundle(data_dir, model):
    p = Path(data_dir)
    frame = pd.read_excel(p / 'MIDAS_POD_matrix.xlsx')
    mapping = pd.read_csv(p / 'pod_mapping.csv')
    required = {'DOF', 'element', 'position', 'node', 'index'}
    if not required <= set(mapping):
        raise ValueError('pod_mapping.csv 缺少 DOF、element、position、node 或 index')
    if len(frame) != len(mapping) or frame.iloc[:, 0].duplicated().any():
        raise ValueError('响应矩阵存在重复 DOF 或与映射长度不一致')
    mapping = mapping.sort_values('index').reset_index(drop=True)
    if not np.array_equal(mapping['index'].to_numpy(), np.arange(len(mapping))):
        raise ValueError('POD index 必须从 0 连续排列')
    if not np.array_equal(frame.iloc[:, 0].astype(str), mapping.DOF.astype(str)):
        raise ValueError('响应矩阵与 POD 映射行序不一致，不能继续重构')
    if mapping.duplicated(['element', 'position']).any():
        raise ValueError('POD 映射有重复单元端部')
    for row in mapping.itertuples(index=False):
        e = model['elements'].get(int(row.element))
        if row.position not in ('I', 'J') or not e or e['n1' if row.position == 'I' else 'n2'] != row.node:
            raise ValueError(f'POD 映射与几何不匹配：{row.DOF}')
    columns = [str(c) for c in frame.columns[1:]]
    if REFERENCE_STAGE not in columns:
        raise ValueError('应力矩阵缺少共同基准 CS13')
    stages = sorted((c for c in columns if re.fullmatch(r'CS\d+', c) and int(c[2:]) >= 13), key=lambda c: int(c[2:]))
    if len(stages) < 4:
        raise ValueError('CS13 起至少需要四个阶段用于增量训练和留出验证')
    x = frame[stages].to_numpy(dtype=float)
    if not np.isfinite(x).all():
        raise ValueError('训练矩阵存在缺失或非有限数值')
    active = {s['name']: mapping.element.isin(s['elements']).to_numpy() for s in model['stages']}
    if any(s not in active for s in stages):
        raise ValueError('训练阶段与 MGT 施工阶段不一致')
    baseline = x[:, 0].copy()
    increments = x[:, 1:] - baseline[:, None]
    # Reference centering preserves exactly zero response at the common baseline.
    u, singular, _ = np.linalg.svd(increments, full_matrices=False)
    tol = np.finfo(float).eps * max(increments.shape) * singular[0]
    rank = int(np.sum(singular > tol))
    if rank < 1:
        raise ValueError('CS13 后无可识别的应力变化')
    return {'mapping': mapping, 'baseline': baseline, 'increments': increments,
            'basis': u[:, :rank], 'singular': singular[:rank], 'stages': stages[1:],
            'active': active, 'lookup': {(int(r.element), r.position): int(r.index)
                                      for r in mapping.itertuples(index=False)}}


def sensor_indices(bundle, sensors):
    result = {}
    for row in sensors.itertuples(index=False):
        if row.position not in (0, 1):
            continue
        idx = bundle['lookup'].get((int(row.element), 'I' if row.position == 0 else 'J'))
        if idx is not None:
            result[str(row.sensor_id)] = idx
    return result


def ridge_operator(basis, indices, rank, alpha):
    indices = np.asarray(indices, dtype=int)
    if len(np.unique(indices)) != len(indices):
        raise ValueError('重构观测不能重复引用同一端部')
    if not 1 <= rank <= min(len(indices), basis.shape[1]):
        raise ValueError('求解阶数不能超过有效观测数或基底阶数')
    if not np.isfinite(alpha) or alpha <= 0:
        raise ValueError('正则化参数必须大于零')
    a = basis[indices, :rank]
    q, s, vt = np.linalg.svd(a, full_matrices=False)
    if s[0] <= 0:
        raise ValueError('当前测点无法观测基底')
    numerical_rank = int(np.sum(s > s[0] * max(a.shape) * np.finfo(float).eps))
    if numerical_rank < rank:
        raise ValueError('当前测点观测矩阵秩不足，请降低阶数')
    regularization = alpha * s[0] ** 2
    operator = (vt.T * (s / (s*s + regularization))) @ q.T
    return operator, float(s[0] / s[-1])


def validate_candidates(bundle, indices):
    """Leave out each CS14-CS18 snapshot and refit its basis, avoiding SVD leakage.

    Results tune hyperparameters, not an independent final-test estimate.
    Noise sensitivity is an explicit hypothetical 1 microstrain / E=206000 test.
    """
    indices = list(indices)
    if len(indices) < 2:
        raise ValueError('至少需要两个有效轴向测点')
    d = bundle['increments']
    max_rank = min(len(indices) - 1, d.shape[1] - 1, bundle['basis'].shape[1])
    records = []
    rng = np.random.default_rng(20260920)
    for j, stage in enumerate(bundle['stages']):
        train = np.delete(d, j, axis=1)
        u, singular, _ = np.linalg.svd(train, full_matrices=False)
        fold_rank = int(np.sum(singular > max(train.shape) * np.finfo(float).eps * singular[0]))
        truth = d[:, j]
        mask = bundle['active'][stage]
        norm = np.linalg.norm(truth[mask])
        if norm < 1e-12:
            continue
        noise = rng.normal(0, 0.206, size=(len(indices), 8))
        for rank in range(1, min(max_rank, fold_rank) + 1):
            for alpha in ALPHAS:
                try:
                    op, cond = ridge_operator(u, indices, rank, alpha)
                except ValueError:
                    continue
                predicted = u[mask, :rank] @ (op @ truth[indices])
                noisy = u[mask, :rank] @ (op @ (truth[indices, None] + noise))
                records.append({'stage': stage, 'rank': rank, 'alpha': alpha,
                    'relative_error': float(np.linalg.norm(predicted - truth[mask]) / norm),
                    'noise_relative_error': float(np.mean(np.linalg.norm(noisy - truth[mask, None], axis=0) / norm)),
                    'condition': cond})
    details = pd.DataFrame(records)
    if details.empty:
        raise ValueError('当前映射无法完成阶段留出验证')
    summary = details.groupby(['rank', 'alpha'], as_index=False).agg(
        folds=('stage', 'nunique'), mean_error=('relative_error', 'mean'),
        max_error=('relative_error', 'max'), noise_error=('noise_relative_error', 'mean'))
    summary = summary[summary.folds == len(bundle['stages'])].sort_values(
        ['noise_error', 'mean_error', 'rank']).reset_index(drop=True)
    if summary.empty:
        raise ValueError('没有通过全部阶段验证的参数组合')
    best = summary.iloc[0]
    return {'rank': int(best['rank']), 'alpha': float(best.alpha),
            'summary': summary, 'details': details}


def parse_monitoring(raw):
    frame = None
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            frame = pd.read_csv(io.BytesIO(raw), encoding=encoding, dtype=str)
            break
        except UnicodeDecodeError:
            continue
    if frame is None or frame.empty:
        raise ValueError('CSV 没有可读取的数据行')
    aliases = {'时间': 'time', '采集时间': 'time', '测点': 'sensor_id', '测点编号': 'sensor_id',
               '应变': 'strain_ue', 'strain': 'strain_ue', '应变变化值': 'strain_ue', '温度': 'temperature_c'}
    frame.columns = [aliases.get(str(c).strip(), str(c).strip()) for c in frame.columns]
    if frame.columns.duplicated().any():
        raise ValueError('CSV 含重复或同义列，请保留一列')
    if not {'time', 'sensor_id', 'strain_ue'} <= set(frame):
        raise ValueError('CSV 至少需要 time、sensor_id、strain_ue；原始温度补偿还需要 temperature_c')
    if frame[['time', 'sensor_id', 'strain_ue']].isna().any().any():
        raise ValueError('时间、测点或应变为空；请明确删除无效记录，不能用零填充')
    frame['time'] = pd.to_datetime(frame.time, errors='raise', format='mixed')
    frame['sensor_id'] = frame.sensor_id.str.strip().str.upper().str.replace(r'^S0+(\d+)$', r'S\1', regex=True)
    if frame.sensor_id.eq('').any():
        raise ValueError('测点编号不能为空')
    frame['strain_ue'] = pd.to_numeric(frame.strain_ue, errors='raise')
    if not np.isfinite(frame.strain_ue).all():
        raise ValueError('应变必须为有限数值')
    if 'temperature_c' in frame:
        frame['temperature_c'] = pd.to_numeric(frame.temperature_c, errors='raise')
        if np.isinf(frame.temperature_c).any():
            raise ValueError('温度不能为无穷值')
    if frame.duplicated(['time', 'sensor_id']).any():
        raise ValueError('同一测点同一时刻有重复记录')
    return frame.sort_values(['time', 'sensor_id']).reset_index(drop=True)


def aligned_readings(frame, target, max_age_s):
    if not np.isfinite(max_age_s) or max_age_s < 0:
        raise ValueError('允许时差必须为非负有限值')
    target = pd.Timestamp(target)
    rows = frame[frame.time <= target].sort_values('time').groupby('sensor_id', sort=False).tail(1).copy()
    rows['age_s'] = (target - rows.time).dt.total_seconds()
    return rows[rows.age_s <= max_age_s].set_index('sensor_id')


def prepare_observations(frame, sensors, target, mode, reference_time,
                         temperature_mode, alpha_ue_per_c, max_age_s):
    if mode not in ('increment', 'raw'):
        raise ValueError('请选择应变基准')
    if temperature_mode not in ('corrected', 'subtract'):
        raise ValueError('请选择温度处理方式')
    if not np.isfinite(alpha_ue_per_c):
        raise ValueError('温度系数必须为有限数值')
    if temperature_mode == 'subtract' and mode != 'raw':
        raise ValueError('温度扣除需要原始读数和 CS13 参考时刻；已归零数据请先完成温度补偿')
    current = aligned_readings(frame, target, max_age_s)
    if mode == 'raw':
        if reference_time is None or pd.Timestamp(reference_time) > pd.Timestamp(target):
            raise ValueError('必须选择不晚于目标时刻的 CS13 参考时刻')
        reference = aligned_readings(frame, reference_time, max_age_s)
    else:
        reference = None
    rows = []
    for s in sensors.itertuples(index=False):
        sid = str(s.sensor_id)
        row = {'sensor_id': sid, 'element': int(s.element), 'position': float(s.position),
               'monitor_type': s.monitor_type, 'delta_strain_ue': np.nan,
               'sample_time': None, 'age_s': np.nan, 'reason': '', 'eligible': False}
        if sid not in current.index:
            row['reason'] = '目标时刻缺少未过期读数'
        elif reference is not None and sid not in reference.index:
            row['reason'] = 'CS13 参考时刻缺少未过期读数'
        else:
            c = current.loc[sid]
            delta = float(c.strain_ue)
            row['sample_time'], row['age_s'] = c.time, float(c.age_s)
            if reference is not None:
                r = reference.loc[sid]
                delta -= float(r.strain_ue)
                if temperature_mode == 'subtract':
                    if 'temperature_c' not in current or not np.isfinite([c.temperature_c, r.temperature_c]).all():
                        row['reason'] = '温度补偿缺少当前或参考温度'
                    else:
                        delta -= alpha_ue_per_c * float(c.temperature_c - r.temperature_c)
            if not row['reason']:
                row['delta_strain_ue'] = delta
                if sid not in AXIAL_IDS or s.monitor_type != '应力':
                    row['reason'] = '弯曲/未定义观测，不参与轴向求解'
                elif s.position not in (0, 1):
                    row['reason'] = '仅支持 I/J 端轴向观测'
                else:
                    row['eligible'] = True
                    row['reason'] = '参与轴向求解'
        rows.append(row)
    return pd.DataFrame(rows)


def reconstruct(bundle, sensors, observations, stage, rank, alpha, elastic_mpa):
    if stage not in bundle['stages'] and stage != REFERENCE_STAGE:
        raise ValueError('当前阶段不在 CS13～CS18 训练范围内')
    if not np.isfinite(elastic_mpa) or elastic_mpa <= 0:
        raise ValueError('弹性模量必须为正数，单位 MPa')
    indices = sensor_indices(bundle, sensors)
    obs = observations.copy()
    for i, row in obs.iterrows():
        idx = indices.get(row.sensor_id)
        if row.eligible and (idx is None or not bundle['active'][stage][idx] or not bundle['active'][REFERENCE_STAGE][idx]):
            obs.loc[i, 'eligible'] = False
            obs.loc[i, 'reason'] = '控制端缺少映射或不在当前/基准阶段活动范围'
    used = obs[obs.eligible]
    if len(used) < 2:
        raise ValueError('至少需要两个有当前/参考读数的有效轴向测点')
    selected = [indices[s] for s in used.sensor_id]
    if not np.isfinite(used.delta_strain_ue).all():
        raise ValueError('有效观测中存在非有限应变')
    op, condition = ridge_operator(bundle['basis'], selected, int(rank), float(alpha))
    stress_increment = used.delta_strain_ue.to_numpy(float) * elastic_mpa * 1e-6
    coefficients = op @ stress_increment
    delta = bundle['basis'][:, :rank] @ coefficients
    total = bundle['baseline'] + delta
    mask = bundle['active'][stage]
    # Inactive or unsupported members must never be reported as zero stress.
    delta = np.where(mask, delta, np.nan)
    total = np.where(mask, total, np.nan)
    residual = []
    for i, row in obs.iterrows():
        idx = indices.get(row.sensor_id)
        ds = delta[idx] if idx is not None else np.nan
        ts = total[idx] if idx is not None else np.nan
        obs.loc[i, 'predicted_delta_mpa'] = ds
        obs.loc[i, 'estimated_total_mpa'] = ts
        obs.loc[i, 'predicted_axial_strain_ue'] = ds / elastic_mpa * 1e6
        error = ds / elastic_mpa * 1e6 - row.delta_strain_ue if row.eligible else np.nan
        obs.loc[i, 'residual_ue'] = error
        if row.eligible:
            residual.append(error)
    training_coordinates = bundle['basis'][:, :rank].T @ bundle['increments']
    training_scale = np.sqrt(np.mean(training_coordinates**2, axis=1))
    scaled_distance = float(np.linalg.norm(coefficients / np.maximum(training_scale, 1e-12)))
    train_max = float(np.max(np.linalg.norm(training_coordinates / np.maximum(training_scale[:, None], 1e-12), axis=0)))
    result = {'delta': delta, 'total': total, 'coefficients': coefficients,
              'sensors': obs, 'rank': rank, 'alpha': alpha, 'condition': condition,
              'fit_rmse_ue': float(np.sqrt(np.mean(np.square(residual)))),
              'outside_training_scale': scaled_distance > 1.5 * train_max,
              'active_count': int(mask.sum()), 'stage': stage, 'elastic_mpa': elastic_mpa}
    return result


def full_result_frame(bundle, result):
    frame = bundle['mapping'][['DOF', 'element', 'position', 'node']].copy()
    frame['stage'] = result['stage']
    frame['reference_stage'] = REFERENCE_STAGE
    frame['source'] = result.get('source', '用户观测重构')
    frame['target_time'] = str(result.get('target_time', ''))
    frame['active'] = np.isfinite(result['delta'])
    frame['delta_axial_stress_mpa'] = result['delta']
    frame['estimated_total_axial_stress_mpa'] = result['total']
    frame['status'] = np.where(frame.active, '模型估计', '当前阶段未启用')
    return frame


def simulated_monitoring(bundle, sensors, elastic_mpa=206000.0):
    indices = sensor_indices(bundle, sensors)
    rows = []
    for j, stage in enumerate([REFERENCE_STAGE] + bundle['stages']):
        for s in sensors.itertuples(index=False):
            idx = indices.get(s.sensor_id)
            if idx is None:
                continue
            strain = 0.0 if j == 0 else bundle['increments'][idx, j-1] / elastic_mpa * 1e6
            rows.append({'time': pd.Timestamp('2000-01-01') + pd.Timedelta(days=j),
                         'sensor_id': s.sensor_id, 'strain_ue': strain, 'temperature_c': 20.0,
                         'stage': stage, 'source': 'MIDAS模拟演示（非实测）'})
    return pd.DataFrame(rows)
