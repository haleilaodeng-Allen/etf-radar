Promise.all([
  fetch('data/candidate_universe.json').then(r => r.json()),
  fetch('data/candidate_status.json').then(r => r.json())
]).then(([universe, status]) => {
  document.querySelector('#screenerMeta').textContent = status.as_of;
  document.querySelector('#method').textContent = status.method;
  const byCode = Object.fromEntries((status.items || []).map(item => [item.code, item]));
  const rows = universe.map(base => {
    const item = byCode[base.code];
    if (!item) return {
      ...base,
      data_state: '待同步',
      price: '—', ma20: '—', ma60: '—', trend: '尚无日线数据', environment: '待验证', research: '暂不判断'
    };
    return {...base, ...item};
  });
  const header = '<div class="candidate-row candidate-header"><span>代码 / 方向</span><span>价格</span><span>20日 / 60日</span><span>趋势事实</span><span>环境</span><span>下一步</span></div>';
  const body = rows.map(row => `<div class="candidate-row"><span><strong>${row.label}</strong><small>${row.category}</small></span><span>${row.price}</span><span>${row.ma20} / ${row.ma60}</span><span>${row.trend}</span><span>${row.environment}</span><span>${row.research}</span></div>`).join('');
  document.querySelector('#candidateTable').innerHTML = header + body;
}).catch(error => {
  document.querySelector('#candidateTable').innerHTML = `<p>候选池数据读取失败：${error.message}</p>`;
});