from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model import parse
from sensor_reconstruction import (load_bundle, sensor_indices, simulated_monitoring,
    parse_monitoring, prepare_observations, reconstruct, validate_candidates, ridge_operator,
    full_result_frame, aligned_readings)

@pytest.fixture(scope='module')
def model():
    return parse((ROOT/'data/model.mgt').read_bytes())

@pytest.fixture(scope='module')
def bundle(model):
    return load_bundle(ROOT/'data', model)

@pytest.fixture
def sensors():
    return pd.read_csv(ROOT/'data/sensor_mapping.csv')


def observations(frame, sensors, target, **kw):
    settings = dict(mode='increment', reference_time=None, temperature_mode='corrected',
                    alpha_ue_per_c=12.0, max_age_s=0)
    settings.update(kw)
    return prepare_observations(frame, sensors, target, **settings)


def test_real_mapping_and_reference(bundle, sensors):
    assert len(bundle['mapping']) == 23838
    assert list(sensors.sensor_id) == ['S1','S2','S3','S5','S6','S7','S8','S9','S10']
    assert bundle['stages'] == ['CS14','CS15','CS16','CS17','CS18']
    assert len(sensor_indices(bundle, sensors)) == 9


def test_reference_zero_does_not_inject_mean(bundle, sensors):
    frame = simulated_monitoring(bundle, sensors)
    obs = observations(frame, sensors, frame.time.min())
    result = reconstruct(bundle, sensors, obs, 'CS13', 2, .001, 206000)
    assert obs.eligible.sum() == 7
    np.testing.assert_allclose(result['delta'][np.isfinite(result['delta'])], 0, atol=0)
    mask = bundle['active']['CS13']
    np.testing.assert_allclose(result['total'][mask], bundle['baseline'][mask])
    assert np.isnan(result['total'][~mask]).all()


def test_known_low_rank_field_recovered(bundle, sensors):
    idx = sensor_indices(bundle,sensors)
    coeff = np.array([120.0, -45.0, 15.0])
    field = bundle['basis'][:,:3] @ coeff
    frame = pd.DataFrame([dict(time=pd.Timestamp('2026-01-01'),sensor_id=s.sensor_id,
                    strain_ue=field[idx[s.sensor_id]]/206000*1e6) for s in sensors.itertuples()])
    obs = observations(frame,sensors,frame.time.iloc[0])
    result = reconstruct(bundle,sensors,obs,'CS18',3,1e-10,206000)
    np.testing.assert_allclose(result['delta'],field,atol=1e-4,rtol=1e-5)
    assert result['fit_rmse_ue'] < 1e-4
    altered = obs.copy()
    altered.loc[altered.sensor_id.isin(['S7','S8']),'delta_strain_ue'] = 1e6
    same = reconstruct(bundle,sensors,altered,'CS18',3,1e-10,206000)
    np.testing.assert_array_equal(same['delta'],result['delta'])
    assert same['sensors'].loc[same['sensors'].sensor_id.isin(['S7','S8']),'residual_ue'].isna().all()


def test_raw_baseline_and_temperature(sensors):
    rows=[]
    for t,strain,temp in [('2026-01-01',100,20),('2026-01-02',134,22)]:
        for s in sensors.sensor_id:rows.append(dict(time=pd.Timestamp(t),sensor_id=s,strain_ue=strain,temperature_c=temp))
    frame=pd.DataFrame(rows)
    corrected=observations(frame,sensors,frame.time.max(),mode='raw',reference_time=frame.time.min(),temperature_mode='subtract')
    np.testing.assert_allclose(corrected.delta_strain_ue,10.0) # 134-100-12*(22-20)
    already=observations(frame,sensors,frame.time.max(),mode='raw',reference_time=frame.time.min())
    np.testing.assert_allclose(already.delta_strain_ue,34.0)
    with pytest.raises(ValueError,match='温度扣除需要'):
        observations(frame,sensors,frame.time.max(),temperature_mode='subtract')


def test_missing_stale_and_future_not_zero_filled(sensors):
    frame=pd.DataFrame({'time':pd.to_datetime(['2026-01-01 00:00:00','2026-01-01 00:02:00','2026-01-01 00:01:00']),
                        'sensor_id':['S1','S2','S3'],'strain_ue':[1,2,3]})
    selected=aligned_readings(frame,'2026-01-01 00:01:00',30)
    assert list(selected.index)==['S3']
    obs=observations(frame,sensors,'2026-01-01 00:01:00',max_age_s=30)
    assert obs.eligible.sum()==1
    assert obs.loc[obs.sensor_id=='S1','delta_strain_ue'].isna().all()


def test_parser_rejects_bad_observations():
    for data in ['time,sensor_id,strain_ue\n2026-01-01,S1,inf\n',
                 'time,sensor_id,strain_ue\n2026-01-01,S1,1\n2026-01-01,S01,2\n',
                 'time,sensor_id,strain_ue\n2026-01-01,S1,\n']:
        with pytest.raises(ValueError):parse_monitoring(data.encode())
    frame=parse_monitoring('时间,测点编号,应变\n2026-01-01,S01,10\n'.encode('utf-8-sig'))
    assert frame.sensor_id.iloc[0]=='S1' and frame.strain_ue.iloc[0]==10


def test_invalid_reference_and_missing_temperature(sensors):
    frame=pd.DataFrame({'time':pd.to_datetime(['2026-01-01','2026-01-02']), 'sensor_id':['S1','S1'], 'strain_ue':[0,1]})
    with pytest.raises(ValueError,match='不晚于'):
        observations(frame,sensors,frame.time.min(),mode='raw',reference_time=frame.time.max())
    obs=observations(frame,sensors,frame.time.max(),mode='raw',reference_time=frame.time.min(),temperature_mode='subtract')
    assert not obs.eligible.any()


def test_rank_and_duplicate_constraints(bundle):
    with pytest.raises(ValueError):ridge_operator(bundle['basis'],[0,1],3,.001)
    with pytest.raises(ValueError):ridge_operator(bundle['basis'],[0,0],1,.001)
    with pytest.raises(ValueError):ridge_operator(bundle['basis'],[0,1],1,0)


def test_stage_masks_and_exports(bundle,sensors):
    frame=simulated_monitoring(bundle,sensors)
    obs=observations(frame,sensors,frame.time.max())
    result=reconstruct(bundle,sensors,obs,'CS14',2,.001,206000)
    result.update(source='MIDAS模拟演示（非实测）',target_time='2000-01-06')
    export=full_result_frame(bundle,result)
    assert len(export)==23838
    assert export.loc[~export.active,'delta_axial_stress_mpa'].isna().all()
    assert export.active.sum()==bundle['active']['CS14'].sum()
    assert export.source.str.contains('非实测').all()


def test_cross_validation_retrains_and_reports(bundle,sensors):
    indices=sensor_indices(bundle,sensors)
    selected=[indices[s] for s in ['S1','S2','S3','S5','S6','S9','S10']]
    validation=validate_candidates(bundle,selected)
    assert 1<=validation['rank']<=4
    assert set(validation['details'].stage)==set(bundle['stages'])
    assert (validation['summary'].folds==5).all()
    assert np.isfinite(validation['summary'].mean_error).all()
    assert validation['summary'].mean_error.min()>.01 # expose the real model error, not self-projection
    print('recommended', validation['rank'],validation['alpha'],validation['summary'].iloc[0].to_dict())
