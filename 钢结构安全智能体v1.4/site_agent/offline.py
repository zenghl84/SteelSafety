"""Deterministic local assistant. Never makes network requests."""
import re
from .agent import collect,parse_plan

def route_question(question,history=()):
    q=question.strip()
    if any(w in q for w in ['倒塌','坍塌','掉落','明显变形','人员受伤','断裂']):return {'intent':'knowledge','topic':'emergency'}
    if any(w in q for w in ['吨','堆料','堆煤','拆撑','吊装','卸载','修改阈值','调高阈值','改成','改为','A=','B=','A区','B区','施工许可','复工']):return {'intent':'knowledge','topic':'unsupported'}
    if any(w in q for w in ['进度','减半','保留','减少','比较方案','对比方案']):
        f=None
        if '减半' in q:f=.5
        else:
            m=re.search(r'(保留|减少|降低)(?:到|为)?\s*(\d+(?:\.\d+)?)\s*[%％]',q)
            if m:
                v=float(m[2])/100
                f=v if m[1]=='保留' or '到' in m[0] or '为' in m[0] else 1-v
        return {'intent':'compare','fraction':f}
    m=re.search(r'(?:杆件|梁单元|单元)(?:编号)?\s*[:：]?\s*(\d+)',q)
    if m:return {'intent':'element','element':int(m[1])}
    if any(w in q for w in ['这根','刚才的杆件','该杆件']):
        for msg in reversed(history):
            rows=msg.get('evidence',{}).get('element_history',[])
            if rows:return {'intent':'element','element':rows[0]['element']}
        return {'intent':'element','element':None}
    if any(w in q for w in ['报警','预警','阈值','安全吗','危险吗','安全结论','安全状态']):return {'intent':'warning'}
    if any(w in q for w in ['当前计划','分析计划','应力变化','预测结果']):return {'intent':'plan'}
    if any(w in q.lower() for w in ['pod','降阶','算法','原理']):return {'intent':'knowledge','topic':'method'}
    if any(w in q for w in ['实测','传感器','现场数据']):return {'intent':'knowledge','topic':'measured'}
    if any(w in q.lower() for w in ['rmse','误差','精度']):return {'intent':'knowledge','topic':'validation'}
    if any(w in q for w in ['你好','您好','怎么用','功能','帮助']):return {'intent':'knowledge','topic':'help'}
    return {'intent':'knowledge','topic':'unknown'}

class OfflineSiteAgent:
    def __init__(self,model):self.model=model
    def answer(self,question,snapshot,history=(),role='管理人员',preset=None):
        route=preset or route_question(question,history)
        topic=route.get('topic')
        knowledge={
            'method':'本项目采用应力 POD＋二参数仿射回归，保留2阶。四个分区工况训练、两个交叉工况检验。预测固定CS18下，给定加载计划相对计划起点的轴向应力变化。[K1][K2]',
            'measured':'本版预测来自MIDAS结果训练的代理，不是现场实测反演。实测与模型尚未完成校准，不能据此判断现场真实安全状态。[K3]',
            'unsupported':'这类现场作业或输入变更不能由离线助手自动判定。请先核实区域、传力路径、荷载分布及模型适用性；计划和阈值须在界面编辑后重新计算。本次未修改计划、未批准施工或复工。[K3][K4]',
            'emergency':'若现场存在危及人身安全的情况，应按现场应急机制立即远离危险区域、报告负责人，不等待模型计算，也不要进入危险区取证。此聊天未通知任何人员、未保存异常工单。[K5]',
            'help':'支持：分析当前计划、解释当前预警、查询杆件2081、加载进度减半、保留80%的加载进度、解释POD方法和检验误差。快捷按钮可直接使用。',
            'unknown':'离线规则暂不支持这个问题。可尝试“分析当前计划”“解释当前预警”“查询杆件2081”“加载进度减半”或“POD是什么”。本次未执行任何现场操作。'}
        if topic in knowledge:
            return {'answer':knowledge[topic],'route':route,'evidence':{'mode':'本地规则问答','topic':topic}}
        if snapshot is None:
            return {'answer':'当前没有有效预测，请先核对计划、阈值和模型。不能使用旧结果解释本次预警。','route':route,'evidence':{'error':'当前预测无效'}}
        checked=parse_plan(__import__('json').dumps({k:v for k,v in route.items() if k!='topic'}))
        e=collect(self.model,snapshot,checked)
        if 'clarification' in e:text=e['clarification']
        elif topic=='validation':
            text='独立检验结果：'+ '；'.join(f"A={v['A']}/B={v['B']}，RMSE={v['rmse_mpa']:.8f} MPa，最大误差={v['max_error_mpa']:.6f} MPa" for v in e['validation'])+'。RMSE是均方根误差。这些数值衡量与本批MIDAS结果的一致性，不是现场精度或整个参数域的误差上界。[E1]'
        elif checked['intent']=='element':
            rows=e['element_history'];selected=[x for x in rows if x['minute']==e['selected_minute']]
            text=f"杆件 {checked['element']}，当前查看 {e['selected_minute']:g} min：\n\n"+'\n'.join(f"- {x['position']}端：Δσ={x['delta_mpa']:.4f} MPa，总轴向应力={x['total_axial_mpa']:.4f} MPa。" for x in selected)+'\n\nΔσ相对计划第0分钟；不包含杆件内部峰值。[E1]'
        elif checked['intent']=='compare':
            original=max(e['summary'],key=lambda x:x['max_change_mpa'])
            candidate=max(e['candidate_summary'],key=lambda x:x['max_change_mpa'])
            text=f"保留 {e['candidate_fraction']*100:g}% 的加载进度后，计划点最大 |Δσ| 从 {original['max_change_mpa']:.4f} MPa 变为 {candidate['max_change_mpa']:.4f} MPa。两者峰值点的演示状态分别为“{original['status']}”和“{candidate['status']}”。[E1]\n\n仅完成候选复算，原计划未修改；本时间窗完成工作量减少，剩余加载延后，不能称为同工作量最优方案。"
        else:
            row=next(x for x in e['summary'] if x['minute']==e['selected_minute'])
            peak=max(e['summary'],key=lambda x:x['max_change_mpa'])
            triggers=[x for x in e['summary'] if x['status']!='未触发']
            alarms=[x for x in e['summary'] if x['status']=='报警']
            text=f"当前查看 {row['minute']:g} min，最大 |Δσ| 为 {row['max_change_mpa']:.4f} MPa，控制梁端 {row['element']}_{row['position']}，演示状态“{row['status']}”。\n\n计划点峰值为 {peak['max_change_mpa']:.4f} MPa，位于 {peak['minute']:g} min；关注/报警演示阈值为 {e['watch_mpa']:g}/{e['alarm_mpa']:g} MPa。[E1]"
            text+='\n\n'+(f"首次触发关注或报警：{triggers[0]['minute']:g} min计划点。" if triggers else '所有输入计划点均未触发演示阈值。')
            if alarms:text+=f"首次报警：{alarms[0]['minute']:g} min计划点。"
            text+='只检查输入计划点，未触发不代表结构安全；请核对加载计划与阈值依据。'
        if role=='工人 / 班组长':text+='\n\n请向班组负责人确认现场安排；A/B现场位置尚未核验，不能按模型编号自行确定危险区域。'
        return {'answer':text,'route':route,'evidence':e}
