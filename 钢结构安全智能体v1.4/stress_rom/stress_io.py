"""Read complete MIDAS beam-end axial stress, preserving IDs and signs."""
from pathlib import Path
import re
import unicodedata
import numpy as np
import pandas as pd


def normalize(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(value))).lower()


def column_kind(value):
    n = normalize(value)
    if n in ('element', 'elem', '单元', '单元编号', '单元号'):
        return 'element'
    if n in ('position', 'part', '位置', '端部', '杆件位置'):
        return 'position'
    if n in ('stage', '阶段', '施工阶段'):
        return 'stage'
    if n in ('load', '荷载', '荷载工况', '荷载组合'):
        return 'load'
    if n in ('step', '步骤', '步', '阶段步'):
        return 'step'
    if n in ('component', '成分', '截面位置', 'sectionposition'):
        return 'component'
    if n in ('axial_stress_mpa', 'delta_stress_mpa', '轴向应力_mpa', '应力增量_mpa'):
        return 'stress'
    if (n.startswith('轴向') or n.startswith('axial')) and (
            'mpa' in n or re.search(r'(?<![a-z])n/mm\^?2', n)):
        return 'stress'
    return None


def _metadata_key(value, kind):
    """Canonicalize equivalent MIDAS labels, including localized Excel exports."""
    value = normalize(value)
    if kind == 'load' and value in ('合计', '合计(cs)', 'total(cs)', 'totalcs'):
        return '合计(cs)'
    if kind == 'step':
        value = value.replace('最后一步', 'last').replace('最后', 'last')
        value = value.replace('laststep', 'last')
    return value


def normalize_position(value):
    value = normalize(value).upper()
    m = re.fullmatch(r'(?:PART)?([IJ])(?:端)?(?:\[\d+\])?', value)
    return m.group(1) if m else None


def _raw_sheets(path):
    path = Path(path)
    if path.suffix.lower() == '.csv':
        for encoding in ('utf-8-sig', 'gb18030'):
            try:
                return {'CSV': pd.read_csv(path, header=None, dtype=object,
                                          encoding=encoding, keep_default_na=False)}
            except UnicodeDecodeError:
                pass
        raise ValueError(f'{path.name}: 无法读取 CSV 编码。')
    if path.suffix.lower() not in ('.xlsx', '.xls'):
        raise ValueError('应力结果支持 .xlsx、.xls、.csv。')
    return pd.read_excel(path, sheet_name=None, header=None, dtype=object)


def read_stress(path, expected=None, stage='CS18', load='合计(CS)', step='001(last)'):
    pieces, included, metadata_missing = [], [], set()
    for sheet, raw in _raw_sheets(path).items():
        header_index = None
        selected = {}
        for i in range(min(60, len(raw))):
            kinds = [column_kind(v) for v in raw.iloc[i]]
            if all(k in kinds for k in ('element', 'position', 'stress')):
                for k in ('element', 'position', 'stress', 'stage', 'load', 'step', 'component'):
                    indices = [j for j, kind in enumerate(kinds) if kind == k]
                    if len(indices) > 1:
                        raise ValueError(f'{sheet}: 多个 {k} 列，无法确定对应结果。')
                    if indices:
                        selected[k] = indices[0]
                header_index = i
                break
        if header_index is None:
            continue
        frame = raw.iloc[header_index + 1:, list(selected.values())].copy()
        frame.columns = list(selected)
        # Skip table titles/repeated headers; retain every numeric element row.
        numeric = pd.to_numeric(frame.element, errors='coerce')
        frame = frame.loc[numeric.notna()].copy()
        numeric = numeric.loc[numeric.notna()]
        if (numeric % 1 != 0).any() or (numeric <= 0).any():
            raise ValueError(f'{sheet}: 单元编号必须是正整数。')
        frame['element'] = numeric.astype(np.int64)
        for key, wanted in [('stage', stage), ('load', load), ('step', step)]:
            if key in frame:
                frame = frame.loc[frame[key].map(lambda value: _metadata_key(value, key)) ==
                                  _metadata_key(wanted, key)]
            else:
                metadata_missing.add(key)
        if 'component' in frame:
            distinct = set(frame.component.dropna().map(normalize)) - {''}
            if 'pos-1' in distinct:
                frame = frame.loc[frame.component.map(normalize) == 'pos-1']
            elif len(distinct) > 1:
                raise ValueError(f'{sheet}: 存在多个截面成分 {sorted(distinct)}，请只导出 Pos-1。')
        if frame.empty:
            continue
        frame['position'] = frame.position.map(normalize_position)
        if frame.position.isna().any():
            raise ValueError(f'{sheet}: 包含 I/J 端以外的位置，请仅导出 I、J 两端。')
        frame['stress'] = pd.to_numeric(frame.stress, errors='coerce')
        if not np.isfinite(frame.stress.to_numpy(dtype=float)).all():
            raise ValueError(f'{sheet}: 应力有空值或非数值；不能用零补齐。')
        pieces.append(frame[['element', 'position', 'stress']])
        included.append(str(sheet))
    if not pieces:
        raise ValueError(f'{Path(path).name}: 没有找到对应的轴向应力。'
                         f'需 {stage}/{load}/{step}，列名含 MPa 或 N/mm²，且为 I/J 两端。')
    joined = pd.concat(pieces, ignore_index=True)
    counts = joined.groupby(['element', 'position']).stress.nunique()
    if (counts > 1).any():
        raise ValueError('同一单元端部存在不同应力；请检查荷载、阶段、步骤或重复工作表。')
    duplicates = int(joined.duplicated(['element', 'position']).sum())
    joined = joined.drop_duplicates(['element', 'position']).set_index(['element', 'position'])
    inactive_zeros = 0
    if expected is not None:
        index = pd.MultiIndex.from_frame(expected[['element', 'position']])
        active_column = f'active_{stage}'
        if active_column in expected:
            active = expected[active_column].astype(bool).to_numpy()
            required_index = pd.MultiIndex.from_frame(expected.loc[active, ['element', 'position']])
            inactive_index = pd.MultiIndex.from_frame(expected.loc[~active, ['element', 'position']])
            missing = required_index.difference(joined.index)
            missing_inactive = inactive_index.difference(joined.index)
            inactive_present = inactive_index.intersection(joined.index)
            if len(inactive_present):
                inactive_values = joined.reindex(inactive_present).stress.to_numpy()
                if np.any(np.abs(inactive_values) > 1e-9):
                    raise ValueError(f'{Path(path).name}: {stage} 中未激活杆件出现非零应力。')
            extra = joined.index.difference(index)
            if len(missing):
                raise ValueError(f'{Path(path).name}: 缺少 {len(missing)} 个 CS13 有效梁端，不能用零代替。'
                                 f'缺失示例 {list(missing[:4])}。')
            if len(extra):
                raise ValueError(f'{Path(path).name}: 多出 {len(extra)} 个映射外梁端。'
                                 f'示例 {list(extra[:4])}。')
            # A beam not yet activated in this stage has zero member stress.
            # Fill only those IDs confirmed inactive by the supplied MGT map.
            out = pd.Series(0., index=index, name='axial_stress_mpa')
            out.loc[joined.index] = joined.stress
            joined = out.to_frame()
            inactive_zeros = len(missing_inactive)
        else:
            missing = index.difference(joined.index)
            extra = joined.index.difference(index)
            if len(missing) or len(extra):
                raise ValueError(f'{Path(path).name}: 缺少 {len(missing)} 个梁端，多出 {len(extra)} 个。'
                                 f'缺失示例 {list(missing[:4])}；程序不会截断或补零。')
        joined = joined.reindex(index)
    else:
        joined = joined.sort_index()
    audit = dict(file=str(Path(path).name), sheets=included, rows=len(joined),
                 identical_duplicate_rows_removed=duplicates,
                 inactive_endpoints_zero_filled=inactive_zeros,
                 missing_metadata_columns=sorted(metadata_missing),
                 unit='MPa', stage=stage, load=load, step=step)
    return joined.reset_index().rename(columns={'stress': 'axial_stress_mpa'}), audit


def find_result(root, base):
    base = Path(root) / base
    found = [base.with_suffix(s) for s in ('.xlsx', '.xls', '.csv') if base.with_suffix(s).exists()]
    if len(found) > 1:
        raise ValueError(f'{base.name}: 同名结果有多个格式，请只保留一个，避免读取旧数据。')
    return found[0] if found else None
