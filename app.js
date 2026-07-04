Promise.all([
  fetch('data/etf_profiles.json').then(r => r.json()),
  fetch('data/etf_status.json').then(r => r.json())
]).then(([profiles, statuses]) => {
  const profile = profiles[0];
  const status = statuses.find(item => item.code === profile.code);
  document.querySelector('#etfName').textContent = `${profile.code} · ${profile.name}`;
  document.querySelector('#trackingIndex').textContent = `跟踪：${profile.tracking_index}`;
  document.querySelector('#updateMeta').textContent = status.as_of;
  document.querySelector('#alertBadge').textContent = `数据状态：${status.alert_level}`;

  const metricItems = [
    ['场内价格', status.price],
    ['20日线', status.ma20],
    ['60日线', status.ma60],
    ['关联市场', status.relative_strength]
  ];
  document.querySelector('#metrics').innerHTML = metricItems.map(([label, value]) => `<article class="metric"><p>${label}</p><strong>${value}</strong></article>`).join('');

  document.querySelector('#actionTitle').textContent = status.action_title;
  document.querySelector('#actionText').textContent = status.action;
  document.querySelector('#logicChain').innerHTML = status.logic_chain.map((item, index) => `${index ? '<b>→</b>' : ''}<span>${item}</span>`).join('');
  const list = (items) => items.map(item => `<li>${item}</li>`).join('');
  document.querySelector('#negativeSignals').innerHTML = list(status.negative_signals);
  document.querySelector('#positiveSignals').innerHTML = list(status.positive_signals);

  const checklist = [
    '价格在20日线和60日线的哪一侧？这是短中期趋势事实，不自动等于买卖。',
    '恒生科技代理与159822是否同向？若不同向，先问：ETF自身成分或估值是否有独立问题？',
    '美债和美元数据是否已成功更新？未更新时，不把“宏观环境”纳入结论。',
    '当前是价格先走弱、关联市场先走弱，还是两者都弱？谁先变，是下一步要追的因果。',
    '你原先买它的理由是什么？页面上哪些事实支持它，哪些事实已经反对它？'
  ];
  document.querySelector('#decisionChecklist').innerHTML = list(checklist);

  const groups = [
    ['关联市场', profile.core_markets],
    ['核心公司', profile.core_companies],
    ['行业变量', profile.industry_factors]
  ];
  document.querySelector('#mapGroups').innerHTML = groups.map(([title, items]) => `<div class="map-group"><h4>${title}</h4><ul>${list(items)}</ul></div>`).join('') + `<div class="map-group"><h4>宏观变量</h4><ul>${profile.macro_factors.map(item => `<li><strong>${item.name}</strong>：${item.logic}</li>`).join('')}</ul></div>`;
}).catch(error => {
  document.querySelector('#app').innerHTML = `<section class="panel"><h3>数据文件读取失败</h3><p>${error.message}</p></section>`;
});