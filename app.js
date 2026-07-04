Promise.all([
  fetch('data/etf_profiles.json').then(r => r.json()),
  fetch('data/etf_status.json').then(r => r.json())
]).then(([profiles, statuses]) => {
  const profile = profiles[0];
  const status = statuses.find(item => item.code === profile.code);
  if (!profile || !status) throw new Error('未找到159822的资料或状态数据');

  const setText = (selector, value) => {
    const node = document.querySelector(selector);
    if (node) node.textContent = value;
  };

  setText('#etfName', `${profile.code} · ${profile.name}`);
  setText('#trackingIndex', `跟踪：${profile.tracking_index}`);
  setText('#updateMeta', status.as_of);
  setText('#alertBadge', `数据状态：${status.alert_level}`);

  const metricItems = [
    ['场内价格', status.price],
    ['20日线', status.ma20],
    ['60日线', status.ma60],
    ['关联市场', status.relative_strength]
  ];
  const metrics = document.querySelector('#metrics');
  if (metrics) metrics.innerHTML = metricItems.map(([label, value]) => `<article class="metric"><p>${label}</p><strong>${value}</strong></article>`).join('');

  setText('#actionTitle', status.action_title);
  setText('#actionText', status.action);
  const logicChain = document.querySelector('#logicChain');
  if (logicChain) logicChain.innerHTML = status.logic_chain.map((item, index) => `${index ? '<b>→</b>' : ''}<span>${item}</span>`).join('');

  const list = (items) => (items || []).map(item => `<li>${item}</li>`).join('');
  const weak = document.querySelector('#negativeSignals');
  const strong = document.querySelector('#positiveSignals');
  if (weak) weak.innerHTML = list(status.negative_signals);
  if (strong) strong.innerHTML = list(status.positive_signals);

  const checklist = [
    '价格在20日线和60日线的哪一侧？这是短中期趋势事实，不自动等于买卖。',
    '恒生科技代理与159822是否同向？若不同向，先问：ETF自身成分或估值是否有独立问题？',
    '美债和美元数据是否已成功更新？未更新时，不把“宏观环境”纳入结论。',
    '当前是价格先走弱、关联市场先走弱，还是两者都弱？谁先变，是下一步要追的因果。',
    '你原先买它的理由是什么？页面上哪些事实支持它，哪些事实已经反对它？'
  ];
  const checklistNode = document.querySelector('#decisionChecklist');
  if (checklistNode) checklistNode.innerHTML = list(checklist);

  const groups = [
    ['关联市场', profile.core_markets],
    ['核心公司', profile.core_companies],
    ['行业变量', profile.industry_factors]
  ];
  const mapGroups = document.querySelector('#mapGroups');
  if (mapGroups) {
    mapGroups.innerHTML = groups.map(([title, items]) => `<div class="map-group"><h4>${title}</h4><ul>${list(items)}</ul></div>`).join('') + `<div class="map-group"><h4>宏观变量</h4><ul>${profile.macro_factors.map(item => `<li><strong>${item.name}</strong>：${item.logic}</li>`).join('')}</ul></div>`;
  }
}).catch(error => {
  const app = document.querySelector('#app');
  if (app) app.innerHTML = `<section class="panel"><h3>数据文件读取失败</h3><p>${error.message}</p></section>`;
});