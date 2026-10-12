import hashlib,json
import numpy as np
import pandas as pd
import streamlit as st
from .core import ROOT,load,evaluate
from .conclusion import assess
from stress_rom.integrated_ui import geometry,make_figure,sensor_values

@st.cache_resource
def cached_model(stamp):return load()

def render_rom(sensors,model_id):
    st.subheader('安全预测与预警')
    model,report=cached_model((ROOT/'trained.npz').stat().st_mtime_ns)
    if report['geometry_sha256']!=model_id:
        st.warning('当前替换模型未关联此代理，暂停预测。');return None
    with st.sidebar:
        st.divider();st.subheader('分区加载计划')
        st.caption('倍率来自结果文件名；分区 MGT 荷载定义待核验。保持 CS18 构件、支承与施工历史不变。')
        default=pd.DataFrame({'minute':[0.,10.,20.,30.],'A':[1.,1.05,1.10,1.15],'B':[1.,1.,1.,1.]})
        plan=st.data_editor(default,num_rows='dynamic',hide_index=True,key='partition_plan',
            column_config={'minute':'时间 / min','A':'A区倍率','B':'B区倍率'})
        st.caption('有效区域：|A−1|+|B−1|≤0.2；两区同时1.2不可预测。')
        st.subheader('应力变化演示阈值')
        watch=st.number_input('关注阈值 / MPa',min_value=.001,value=2.,step=.1)
        alarm=st.number_input('报警阈值 / MPa',min_value=.002,value=3.,step=.1)
        st.caption('比较每个梁端相对计划起点的 |Δσ|。默认值仅用于流程演示，不是规范或承载力限值。')
    try:summary,fields,delta=evaluate(model,plan,watch,alarm)
    except (ValueError,TypeError,KeyError) as ex:
        st.warning('待核验：'+str(ex));return None
    conclusion=assess(summary,watch,alarm)
    idx=summary.max_change_mpa.idxmax()
    selected=float(summary.loc[idx,'minute'])
    field=pd.DataFrame({'element':model['elements'],'position':model['positions'],
        'delta_stress_mpa':delta[idx],'total_axial_stress_mpa':fields[idx],
        'predicted_axial_delta_strain_microstrain':np.nan})
    left,right=st.columns([3,1.15])
    with right:
        st.subheader('安全结论与预警')
        row=summary.iloc[idx];status=conclusion['level']
        (st.error if status=='报警' else st.warning if status=='关注' else st.info)(conclusion['title'])
        st.write(conclusion['text'])
        st.caption(conclusion['scope'])
        st.metric('计划内最大 |Δσ| / MPa',f"{conclusion['peak_mpa']:.4f}")
        st.write(f"控制位置：{conclusion['element']}_{conclusion['position']}")
        message='所检查计划点均未触发阈值' if conclusion['first_trigger_minute'] is None else f"首次触发：{conclusion['first_trigger_minute']:g} min 计划点"
        st.write(message)
        focus=int(conclusion['element'])
        with st.expander('杆件查询与重点位置'):
            focus=st.number_input('定位梁单元',min_value=0,value=focus,step=1,key='partition_focus')
            top=field.assign(abs_change=field.delta_stress_mpa.abs()).nlargest(5,'abs_change')
            st.dataframe(top[['element','position','delta_stress_mpa']].rename(columns={'element':'杆件','position':'端部','delta_stress_mpa':'变化 / MPa'}),hide_index=True)
            picked=field[field.element==focus]
            if len(picked):st.dataframe(picked[['element','position','delta_stress_mpa','total_axial_stress_mpa']],hide_index=True)
            else:st.caption('该编号无梁端结果。')
    with left:
        st.caption(f'自动显示计划内最大应力变化时点：{selected:g} min · CS18')
        mode=st.radio('云图显示',['应力变化','总轴向应力'],horizontal=True,label_visibility='collapsed')
        plotted=field.copy()
        total=mode=='总轴向应力'
        if total:plotted['delta_stress_mpa']=plotted.total_axial_stress_mpa
        limit=max(float(np.max(abs(fields if total else delta))),.001)
        elements,xyz=geometry((ROOT.parent/'data/model.mgt').read_bytes())
        fig=make_figure(elements,xyz,plotted,limit,int(focus))
        fig.data[-1].marker.colorbar.title.text='σ / MPa' if total else 'Δσ / MPa'
        st.plotly_chart(fig,width='stretch',key='partition_cloud')
        st.caption('两端绝对值较大者控制杆件颜色，保留正负号；灰色表示无梁应力输出。整个计划共用色标。')
    with st.expander('预测曲线与数据下载',expanded=False):
        st.subheader('计划响应与触发记录')
        import plotly.graph_objects as go
        curve=go.Figure(go.Scatter(x=summary.minute,y=summary.max_change_mpa,mode='lines+markers',name='最大 |Δσ|'))
        curve.add_hline(y=watch,line_dash='dash',line_color='orange',annotation_text='关注（演示）')
        curve.add_hline(y=alarm,line_dash='dash',line_color='red',annotation_text='报警（演示）')
        curve.update_layout(xaxis_title='计划时间 / min',yaxis_title='最大 |Δσ| / MPa',height=280)
        st.plotly_chart(curve,width='stretch');st.dataframe(summary,hide_index=True)
        st.download_button('下载计划预测 CSV',summary.to_csv(index=False).encode('utf-8-sig'),'stress_plan.csv')
        st.download_button('下载当前梁端应力 CSV',field.drop(columns='predicted_axial_delta_strain_microstrain').to_csv(index=False).encode('utf-8-sig'),'stress_field.csv')
    with st.expander('候选方案复算：减少本时间窗的加载进度'):
        st.caption('将各时点相对起点的荷载变化乘以下方比例。剩余加载延后，完成工作量发生变化；不是同工作量最优方案。')
        fraction=st.number_input('加载进度比例',min_value=0.,max_value=1.,value=.5,step=.05)
        candidate=plan.copy()
        for c in ['A','B']:candidate[c]=float(plan[c].iloc[0])+fraction*(plan[c]-float(plan[c].iloc[0]))
        alt,_,_=evaluate(model,candidate,watch,alarm)
        compare=pd.DataFrame({'minute':summary.minute,'原计划最大变化_MPa':summary.max_change_mpa,
            '候选最大变化_MPa':alt.max_change_mpa,'原状态':summary.status,'候选状态':alt.status})
        st.dataframe(compare,hide_index=True)
        st.download_button('下载候选计划',candidate.to_csv(index=False).encode('utf-8-sig'),'candidate_plan.csv')
    with st.expander('评估依据与适用范围'):
        st.write('当前结论仅检查固定CS18、给定加载计划下的梁端轴向应力变化。阈值为演示配置；尚未完成现场校准和承载力验算。只检查输入计划点，不包含点间连续峰值。')
        st.write('四个分区工况训练 POD + 二参数仿射回归；两组交叉工况独立检验。基准点 A1/B1 为代理估计，尚无单独中心工况验证。CS13 表保留存档，不参与本版训练或基线计算。')
        st.dataframe(pd.DataFrame(report['validation']),hide_index=True)
        st.caption('检验误差不是置信区间。几何连通性已核对，但未核验分区荷载 MGT，当前属于条件演示。')
        st.download_button('下载检验与输入来源报告',json.dumps(report,ensure_ascii=False,indent=2),'partition_validation.json')
    return dict(stage='CS18',reference_stage='计划起点',rank=model['basis'].shape[1],parameter=float(row.A),
        field=field,source='分区荷载 POD 应力变化代理（演示）',
        target_time=f'{selected:g} min · A={row.A:.2f} / B={row.B:.2f}',hover=sensor_values(field,sensors),
        warning=conclusion['title'],warning_detail=message,conclusion=conclusion,
        agent_snapshot=dict(plan=plan.to_dict('records'),watch=float(watch),alarm=float(alarm),
            selected_minute=float(selected),validation=report['validation'],
            geometry_sha256=model_id,model_sha256=hashlib.sha256((ROOT/'trained.npz').read_bytes()).hexdigest()))
