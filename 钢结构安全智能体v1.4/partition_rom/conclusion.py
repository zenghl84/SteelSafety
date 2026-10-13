"""Evidence-limited stress-change screening conclusions, not capacity certification."""
def assess(summary,watch,alarm):
    peak=summary.loc[summary.max_change_mpa.idxmax()]
    value=float(peak.max_change_mpa)
    level='报警' if value>=alarm else '关注' if value>=watch else '未触发'
    titles={'报警':'应力变化达到报警阈值','关注':'应力变化需重点关注','未触发':'应力变化未触发预警'}
    advice={'报警':'建议核查加载计划及控制杆件，并对调整方案进行技术复核。',
            '关注':'建议重点复核控制杆件的响应变化，关注后续加载安排。',
            '未触发':'本计划所检查的应力变化指标未触发阈值，可继续进行方案比较与复核。'}
    triggered=summary[summary.max_change_mpa>=watch]
    return dict(level=level,title=titles[level],minute=float(peak.minute),element=int(peak.element),
        position=str(peak.position),peak_mpa=value,
        first_trigger_minute=None if triggered.empty else float(triggered.iloc[0].minute),
        text=f"在所检查的计划点中，最大轴向应力变化为 {value:.4f} MPa，出现在 {float(peak.minute):g} min，控制梁端 {int(peak.element)}_{peak.position}。"+advice[level],
        scope='轴向应力变化筛查 · 演示阈值；不等同于承载力或整体安全验算。')
