Promise.all([
  fetch('data/etf_profiles.json').then(r => r.json()),
  fetch('data/etf_status.json').then(r => r.json())
]).then(([profiles, statuses]) => {
  const profile = profiles[0];
  const status = statuses.find(item => item.code === profile.code);
  document.querySelector('#etfName').textContent = `${profile.code} · ${profile.name}`;
  document.querySelector('#trackingIndex').textContent = `跟踪：${profile.tracking_index}`;
  document.querySelector('#updateMeta').textContent = status.as_of;
  document.querySelector('#alertBadge').textContent = status.alert_level;

  const metricItems = [
    ['最新价', status.price],
    ['20日线', status.ma20],
    ['60日线', status.ma60],
    ['相对强弱', status.relative_strength]
  ];
  document.querySelector('#metrics').innerHTML = metricItems.map(([label, value]) => `<article class="metric"><p>${label}</p><strong>${value}</strong></article>`).join('');

  document.querySelector('#actionTitle').textContent = status.action_title;
  document.querySelector('#actionText').textContent = status.action;
  document.querySelector('#logicChain').innerHTML = status.logic_chain.map((item, index) => `${index ? '<b>→</b>' : ''}<span>${item}</span>`).join('');
  const list = (items) => items.map(item => `<li>${item}</li>`).join('');
  document.querySelector('#negativeSignals').innerHTML = list(status.negative_signals);
  document.querySelector('#positiveSignals').innerHTML = list(status.positive_signals);

  const groups = [
    ['关联市场', profile.core_markets],
    ['核心公司', profile.core_companies],
    ['行业变量', profile.industry_factors]
  ];
  document.querySelector('#mapGroups').innerHTML = groups.map(([title, items]) => `<div class="map-group"><h4>${title}</h4><ul>${list(items)}</ul></div>`).join('') + `<div class="map-group"><h4>宏观变量</h4><ul>${profile.macro_factors.map(item => `<li><strong>${item.name}</strong>：${item.logic}</li>`).join('')}</ul></div>`;
}).catch(error => {
  document.querySelector('#app').innerHTML = `<section class="panel"><h3>数据文件读取失败</h3><p>${error.message}</p></section>`;
});