'use strict';
(() => {
  const $ = selector => document.querySelector(selector);
  const state = { days: 30, manager: 'all', view: 'overview', search: '', issue: 'all', callQuality: 'all', report: null, source: '', loading: false, request: 0 };
  let drawerReturnFocus = null;
  let toastTimer;
  const icons = {
    overview: '<rect x="3" y="3" width="7" height="7" rx="1.4"/><rect x="14" y="3" width="7" height="7" rx="1.4"/><rect x="3" y="14" width="7" height="7" rx="1.4"/><rect x="14" y="14" width="7" height="7" rx="1.4"/>',
    deals: '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M8 6V4h8v2M3 11h18M9 11v3h6v-3"/>',
    calls: '<path d="M7 3H4a1 1 0 0 0-1 1c0 9.4 7.6 17 17 17a1 1 0 0 0 1-1v-3l-5-2-2 3a16 16 0 0 1-8-8l3-2-2-5Z"/><path d="M15 3a6 6 0 0 1 6 6M15 7a2 2 0 0 1 2 2"/>',
    report: '<path d="M14 3H5a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V9l-6-6Z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
    architecture: '<rect x="8" y="3" width="8" height="5" rx="1"/><rect x="2" y="16" width="8" height="5" rx="1"/><rect x="14" y="16" width="8" height="5" rx="1"/><path d="M12 8v4M6 16v-4h12v4"/>',
    arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
    refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    spark: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/>',
    money: '<path d="M8 21V3h6a5 5 0 0 1 0 10H5m0 4h11"/>',
    flag: '<path d="M5 21V3m0 0c5-3 9 3 14 0v10c-5 3-9-3-14 0"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    shield: '<path d="M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4Z"/><path d="m8 12 3 3 5-6"/>',
    warning: '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v4m0 4h.01"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    link: '<path d="m10 14 4-4m-6 6-2 2a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0m2 1 2-2a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0"/>',
    mic: '<rect x="8" y="2" width="8" height="13" rx="4"/><path d="M5 11v2a7 7 0 0 0 14 0v-2M12 20v2m-4 0h8"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 11h18"/>',
    user: '<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>'
  };
  const icon = (name, className = '') => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"${className ? ` class="${className}"` : ''}>${icons[name] || icons.report}</svg>`;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const number = value => new Intl.NumberFormat('ru-RU').format(Number(value) || 0);
  const money = value => `${number(value)} ₽`;
  const shortMoney = value => {
    const amount = Number(value) || 0;
    if (amount >= 1000000) return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(amount / 1000000)} млн`;
    if (amount >= 1000) return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(amount / 1000)} тыс.`;
    return number(amount);
  };
  const date = (value, withTime = false) => {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return 'Дата не указана';
    return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}), timeZone: 'Europe/Moscow' }).format(parsed);
  };
  const seconds = value => `${String(Math.floor((Number(value) || 0) / 60)).padStart(2, '0')}:${String(Math.floor((Number(value) || 0) % 60)).padStart(2, '0')}`;
  const safeColor = value => /^#[0-9a-f]{6}$/i.test(String(value)) ? value : '#cad9ba';
  const isOpen = deal => !['won', 'lost'].includes(deal.status);
  const inPeriod = value => value && new Date(value) >= new Date(state.report.meta.from) && new Date(value) < new Date(state.report.meta.to);
  const manager = id => state.report.managers.find(person => String(person.id) === String(id)) || { name: 'Не назначен', initials: '—', color: '#d5dec9' };
  const visibleDeals = () => state.report.deals.filter(deal => state.manager === 'all' || String(deal.manager_id) === state.manager);
  const visibleCalls = () => state.report.calls.filter(call => state.manager === 'all' || String(call.manager_id) === state.manager);
  const managerName = () => state.manager === 'all' ? 'Вся команда' : manager(state.manager).name;
  const isDemo = () => state.report?.meta.mode === 'demo';
  const safeURL = value => { try { const url = new URL(String(value)); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; } };
  const analysisLabel = () => ['openai', 'mixed'].includes(state.report.meta.analysis_mode) ? 'LLM + правила' : isDemo() ? 'демо-правила' : 'локальные правила';
  const analysisNote = () => { const source = isDemo() ? 'Демо: синтетические расшифровки' : 'Расшифровки из источника звонков'; return state.report.meta.analysis_mode === 'openai' ? `${source} разобраны моделью после явного запуска интеграции.` : state.report.meta.analysis_mode === 'mixed' ? `${source}: часть разобрана моделью, часть — правилами. Метод указан в деталях звонка.` : `${source} анализируются локальными правилами. Внешняя модель и распознавание аудио здесь не запускаются.`; };
  const issueLabels = { no_task: 'Без задачи', overdue: 'Просрочка', followup_gap: 'Сверить обещание', stale: 'Нет активности' };
  const issuePills = issues => (issues || []).map(issue => `<span class="issue-pill ${esc(issue)}">${esc(issueLabels[issue] || issue)}</span>`).join('');
  const person = id => { const personData = manager(id); return `<span class="person-cell"><span class="avatar" style="background:${safeColor(personData.color)}33;color:#596f50">${esc(personData.initials)}</span><strong>${esc(personData.name)}</strong></span>`; };
  const views = {
    overview: { name: 'Обзор', eyebrow: 'ПУЛЬС ВАШЕГО ОТДЕЛА', title: 'Продажи под контролем.', description: 'Цифры, разговоры и следующие шаги — в одной картине.' },
    deals: { name: 'Сделки', eyebrow: 'НИ ОДНОЙ УПУЩЕННОЙ ВОЗМОЖНОСТИ', title: 'У каждой сделки — следующий шаг.', description: 'Найдите просрочки, потерянные договорённости и сделки без задач.' },
    calls: { name: 'Звонки', eyebrow: 'КОНТЕКСТ, КОТОРОГО НЕТ В ЦИФРАХ', title: 'Слушаем смысл.', description: 'Договорённости и возражения с точными фрагментами разговора.' },
    report: { name: 'Отчёт', eyebrow: 'ОТ АНАЛИЗА К ДЕЙСТВИЮ', title: 'Картина, с которой можно работать.', description: 'Результаты отдела, приоритеты и источники для проверки.' },
    architecture: { name: 'Архитектура', eyebrow: 'ПРОЗРАЧНОСТЬ ПО УМОЛЧАНИЮ', title: 'Как устроен PULSE.', description: 'Данные, роли и граница между автоматизацией и решением человека.' }
  };

  function selectedMetrics() {
    if (state.manager === 'all') return state.report.metrics;
    const deals = visibleDeals();
    const won = deals.filter(deal => deal.status === 'won' && inPeriod(deal.closed_at));
    const closed = deals.filter(deal => ['won', 'lost'].includes(deal.status) && inPeriod(deal.closed_at));
    const stats = state.report.manager_stats.find(row => String(row.id) === state.manager);
    return { new_leads: deals.filter(deal => inPeriod(deal.created_at)).length, won_count: stats?.won_count ?? won.length, won_amount: stats?.won_amount ?? won.reduce((sum, deal) => sum + deal.amount, 0), closed_count: closed.length, win_rate: closed.length ? Math.round(won.length / closed.length * 1000) / 10 : 0, open_count: stats?.open_count ?? deals.filter(isOpen).length, no_task_count: stats?.no_task_count ?? deals.filter(deal => deal.issues.includes('no_task')).length, overdue_count: stats?.overdue_count ?? deals.filter(deal => deal.issues.includes('overdue')).length, calls_count: visibleCalls().length, followup_gap_count: visibleCalls().filter(call => call.followup_gap).length };
  }

  function metricsHTML() {
    const metrics = selectedMetrics();
    const riskCount = visibleDeals().filter(deal => isOpen(deal) && deal.issues.some(issue => ['no_task', 'overdue'].includes(issue))).length;
    const entries = [
      { label: 'Бюджеты выигранных сделок', value: shortMoney(metrics.won_amount), unit: '₽', type: 'money', footer: `${number(metrics.won_count)} сделок за период`, featured: true, footIcon: 'check' },
      { label: 'Выигранные сделки', value: number(metrics.won_count), type: 'flag', footer: `${number(metrics.win_rate)}% от закрытых за период`, footIcon: 'check' },
      { label: 'Сделки с рисками по задачам', value: number(riskCount), type: 'clock', footer: `${number(metrics.overdue_count)} с просрочкой · ${number(metrics.no_task_count)} без задачи`, amber: true, footIcon: 'warning' },
      { label: 'Разобранные звонки', value: number(metrics.calls_count), type: 'calls', footer: `${number(metrics.followup_gap_count)} договорённостей к проверке`, footIcon: 'mic' }
    ];
    return `<div class="metrics-grid">${entries.map(entry => `<article class="metric-card${entry.featured ? ' featured' : ''}"><div class="metric-top"><span class="metric-label">${entry.label}</span><span class="metric-icon">${icon(entry.type)}</span></div><div class="metric-number">${entry.value}${entry.unit ? `<span class="unit">${entry.unit}</span>` : ''}</div><div class="metric-bottom"><span class="${entry.amber ? 'amber' : 'positive'}">${icon(entry.footIcon)}</span>${entry.footer}</div></article>`).join('')}</div>`;
  }

  function filteredSeries() {
    if (state.manager === 'all') return state.report.series;
    const won = visibleDeals().filter(deal => deal.status === 'won' && inPeriod(deal.closed_at));
    const calls = visibleCalls();
    return state.report.series.map(point => ({ ...point, won_amount: won.filter(deal => String(deal.closed_at).slice(0, 10) === point.date).reduce((sum, deal) => sum + Number(deal.amount), 0), calls_count: calls.filter(call => String(call.occurred_at).slice(0, 10) === point.date).length }));
  }

  function chartHTML() {
    const series = filteredSeries();
    const size = Math.max(1, Math.ceil(series.length / 12));
    const buckets = [];
    for (let index = 0; index < series.length; index += size) { const group = series.slice(index, index + size); buckets.push({ label: group[0].label, range: group.length === 1 ? group[0].label : `${group[0].label} — ${group[group.length - 1].label}`, value: group.reduce((sum, point) => sum + Number(point.won_amount || 0), 0) }); }
    const width = 640, height = 198, left = 46, right = 12, top = 12, bottom = 30;
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    const ceiling = Math.max(100000, ...buckets.map(bucket => bucket.value)) * 1.12;
    const step = plotWidth / Math.max(1, buckets.length);
    const grids = [0, 1, 2, 3].map(index => { const y = top + plotHeight * index / 3; return `<line class="chart-grid" x1="${left}" x2="${width - right}" y1="${y}" y2="${y}"/><text x="${left - 8}" y="${y + 3}" text-anchor="end">${esc(shortMoney(ceiling * (3 - index) / 3))}</text>`; }).join('');
    const bars = buckets.map((bucket, index) => { const barHeight = bucket.value / ceiling * plotHeight, x = left + step * index + step * .22, y = top + plotHeight - barHeight; const label = index === 0 || index === buckets.length - 1 || index % Math.max(1, Math.ceil(buckets.length / 5)) === 0; return `<rect x="${x}" y="${y}" width="${Math.max(1, step * .56)}" height="${Math.max(bucket.value > 0 ? 2 : 0, barHeight)}" rx="3" fill="${index === buckets.length - 1 ? '#618c6d' : '#a0bca0'}"><title>${esc(bucket.range)}: ${esc(money(bucket.value))}</title></rect>${label ? `<text x="${x + step * .28}" y="${height - 9}" text-anchor="middle">${esc(bucket.label)}</text>` : ''}`; }).join('');
    return `<section class="panel"><div class="panel-heading"><div><h2 class="panel-title">Динамика продаж</h2><p class="panel-subtitle">Сумма бюджетов выигранных сделок за период</p></div><span class="tag">${icon('calendar')}${state.days} дней</span></div><div class="chart-body"><div class="chart-summary"><strong>${money(selectedMetrics().won_amount)}</strong><span>${esc(managerName())}</span></div><svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Динамика бюджетов выигранных сделок за ${state.days} дней"><title>Выигранные сделки: ${esc(money(selectedMetrics().won_amount))}</title>${grids}${bars}</svg><div class="chart-foot"><span class="chart-legend"><i></i> Бюджеты сделок, ₽</span><span>Расчёт по дате закрытия · не денежная выручка</span></div></div></section>`;
  }

  function pipelineHTML() {
    const deals = visibleDeals().filter(isOpen);
    const pipeline = state.report.pipeline.map(stage => state.manager === 'all' ? stage : { ...stage, count: deals.filter(deal => deal.status === stage.id).length, amount: deals.filter(deal => deal.status === stage.id).reduce((sum, deal) => sum + deal.amount, 0) });
    const maximum = Math.max(1, ...pipeline.map(stage => stage.amount));
    return `<section class="panel"><div class="panel-heading"><div><h2 class="panel-title">В работе сейчас</h2><p class="panel-subtitle">Открытые сделки · снимок на ${esc(date(state.report.meta.as_of))}</p></div><span class="tag">${number(deals.length)} сделок</span></div><div class="pipeline-body">${pipeline.map((stage, index) => `<div class="pipeline-row"><div class="pipeline-meta"><span><i style="background:${safeColor(stage.color)}"></i>${esc(stage.label)}</span><span><strong>${shortMoney(stage.amount)} ₽</strong><small>${number(stage.count)}</small></span></div><div class="pipeline-track"><span style="width:${stage.amount / maximum * 100}%;background:${['#acc1a5', '#9eb99b', '#8dab8d', '#7d9f81', '#62866b'][index % 5]}"></span></div></div>`).join('')}<div class="pipeline-footer"><span>Общий бюджет открытых сделок</span><strong>${shortMoney(deals.reduce((sum, deal) => sum + deal.amount, 0))} ₽</strong></div></div></section>`;
  }

  function teamHTML() {
    const rows = state.report.manager_stats.filter(row => state.manager === 'all' || String(row.id) === state.manager);
    return `<section class="panel"><div class="panel-heading"><div><h2 class="panel-title">Команда в цифрах</h2><p class="panel-subtitle">Результат за период и текущие риски по задачам</p></div><span class="tag">${number(rows.length)} менеджера</span></div><div class="table-wrap"><table class="data-table team-table"><thead><tr><th>Менеджер</th><th>Бюджеты, ₽</th><th>Выиграно</th><th>Риски</th><th><span class="subtext">Фильтр</span></th></tr></thead><tbody>${rows.map(row => { const risk = visibleDeals().filter(deal => String(deal.manager_id) === String(row.id) && isOpen(deal) && deal.issues.some(issue => ['no_task', 'overdue'].includes(issue))).length; return `<tr><td><button class="row-button" type="button" data-manager="${esc(row.id)}" aria-label="Показать данные: ${esc(row.name)}">${person(row.id)}</button></td><td class="amount-cell">${number(row.won_amount)}</td><td>${number(row.won_count)}</td><td><span class="risk-badge${risk ? '' : ' safe'}">${risk ? `${number(risk)} сделок` : 'В порядке'}</span></td><td><button class="table-action" type="button" data-manager="${esc(row.id)}" aria-label="Фильтр по ${esc(row.name)}">${icon('chevron')}</button></td></tr>`; }).join('')}</tbody></table></div></section>`;
  }

  function selectedRecommendations() {
    const deals = new Set(visibleDeals().map(deal => String(deal.id))), calls = new Set(visibleCalls().map(call => String(call.id)));
    return state.report.recommendations.map(recommendation => ({ ...recommendation, deal_ids: recommendation.deal_ids.filter(id => deals.has(String(id))), call_ids: recommendation.call_ids.filter(id => calls.has(String(id))) })).filter(recommendation => recommendation.deal_ids.length || recommendation.call_ids.length);
  }

  function focusHTML() {
    const recommendations = selectedRecommendations().slice(0, 3);
    return `<section class="panel focus-panel"><div class="panel-heading"><div><h2 class="panel-title">На что обратить внимание</h2><p class="panel-subtitle">Приоритеты для руководителя</p></div><span class="tag">${icon('spark')} Анализ</span></div><div class="focus-list">${recommendations.map((recommendation, index) => `<article class="focus-item"><span class="focus-symbol">${icon(['clock', 'warning', 'calls'][index])}</span><div><h3>${esc(recommendation.title)}</h3><p>${number(recommendation.deal_ids.length)} сделок · ${esc(recommendation.description)}</p></div><button type="button" data-view="report" aria-label="Подробнее: ${esc(recommendation.title)}">${icon('chevron')}</button></article>`).join('') || '<div class="empty-state">Рекомендаций для выбранного менеджера нет.</div>'}</div><div class="focus-footer">${icon('shield')} Рекомендации проверяет и утверждает человек</div></section>`;
  }

  function overviewHTML() {
    return `${metricsHTML()}<div class="section-grid">${chartHTML()}${pipelineHTML()}</div><div class="section-grid lower-grid">${teamHTML()}${focusHTML()}</div><section class="review-strip"><span class="review-icon">${icon('report')}</span><div><h3>Все выводы — с опорой на данные.</h3><p>Откройте отчёт, чтобы проверить сделки, фрагменты звонков и предложенные действия.</p></div><button class="button" type="button" data-view="report">Перейти к отчёту ${icon('arrow')}</button></section>`;
  }

  function filteredDeals() {
    const query = state.search.trim().toLocaleLowerCase('ru-RU');
    return visibleDeals().filter(deal => (!query || `${deal.name} ${deal.company} ${deal.id}`.toLocaleLowerCase('ru-RU').includes(query)) && (state.issue === 'all' || (state.issue === 'open' ? isOpen(deal) : deal.issues.includes(state.issue))));
  }

  function dealRowsHTML() {
    const deals = filteredDeals();
    return deals.map(deal => `<tr><td><button class="deal-name-button" type="button" data-deal="${esc(deal.id)}">${esc(deal.name)}</button><span class="subtext">${esc(deal.company)} · #${esc(deal.id)}</span></td><td class="amount-cell">${money(deal.amount)}</td><td><span class="status-pill ${esc(deal.status)}">${esc(deal.status_label)}</span></td><td>${person(deal.manager_id)}</td><td><div class="issue-stack">${issuePills(deal.issues) || '<span class="subtext">Без замечаний</span>'}</div></td><td><button class="table-action" type="button" data-deal="${esc(deal.id)}" aria-label="Открыть сделку ${esc(deal.name)}">${icon('chevron')}</button></td></tr>`).join('') || '<tr><td colspan="6"><div class="empty-state">Сделок с такими условиями нет.<br>Попробуйте изменить поиск или фильтр.</div></td></tr>';
  }

  function dealsHTML() {
    return `<div class="view-toolbar"><label class="search-wrap">${icon('search')}<input id="deal-search" type="search" placeholder="Название, компания или номер сделки" aria-label="Поиск сделок" value="${esc(state.search)}"></label><select id="issue-filter" aria-label="Фильтр сделок"><option value="all">Все сделки</option><option value="open">Открытые сделки</option>${Object.entries(issueLabels).map(([key, label]) => `<option value="${key}"${state.issue === key ? ' selected' : ''}>${label}</option>`).join('')}</select><span class="toolbar-count" id="deal-count">${number(filteredDeals().length)} из ${number(visibleDeals().length)} сделок</span></div><div class="analysis-note">${icon('clock')} Риски проверяются на ${esc(date(state.report.meta.as_of, true))} по всем открытым сделкам, включая созданные раньше периода.</div><section class="panel"><div class="table-wrap"><table class="data-table deal-table"><thead><tr><th>Сделка / компания</th><th>Бюджет</th><th>Этап</th><th>Менеджер</th><th>Сигналы</th><th>Детали</th></tr></thead><tbody id="deals-body">${dealRowsHTML()}</tbody></table></div></section>`;
  }

  function callsHTML() {
    const calls = visibleCalls().filter(call => state.callQuality === 'all' || (state.callQuality === 'attention' ? call.followup_gap : !call.followup_gap));
    return `<div class="analysis-note">${icon('mic')} ${esc(analysisNote())}</div><div class="view-toolbar"><span class="toolbar-count" style="margin-left:0">${number(calls.length)} звонков за выбранный период</span><select id="call-quality-filter" aria-label="Фильтр звонков"><option value="all">Все звонки</option><option value="attention"${state.callQuality === 'attention' ? ' selected' : ''}>Договорённости к проверке</option><option value="good"${state.callQuality === 'good' ? ' selected' : ''}>Без сигнала несоответствия</option></select></div><div class="card-grid">${calls.map(call => `<article class="panel call-card"><div class="call-card-header"><span class="call-card-icon">${icon('calls')}</span><span class="${call.followup_gap ? 'issue-pill followup_gap' : 'status-pill won'}">${call.followup_gap ? 'Сверить обещание' : 'Без сигнала несоответствия'}</span></div><h2 class="call-title">${esc(call.company)}</h2><div class="call-meta"><span>${icon('calendar')}${esc(date(call.occurred_at))}</span><span>${icon('clock')}${seconds(call.duration_seconds)}</span><span>${call.direction === 'incoming' ? 'Входящий' : 'Исходящий'}</span></div><p class="call-summary">${esc(call.summary)}</p><div class="call-card-foot">${person(call.manager_id)}<button class="text-button" type="button" data-call="${esc(call.id)}">Разбор ${icon('arrow')}</button></div></article>`).join('') || '<div class="panel empty-state">За этот период звонков с такими условиями нет.</div>'}</div>`;
  }

  function summaryText() {
    if (state.manager === 'all') return state.report.summary;
    const metrics = selectedMetrics();
    return `${managerName()}: за ${state.days} дней выиграно ${metrics.won_count} сделок с суммой бюджетов ${money(metrics.won_amount)}. Разобрано ${metrics.calls_count} звонков. На дату снимка открыто ${metrics.open_count} сделок: ${metrics.overdue_count} с просроченными задачами, ${metrics.no_task_count} без незавершённых задач. Договорённости из ${metrics.followup_gap_count} звонков требуют проверки.`;
  }

  function recommendationHTML(recommendation, index) {
    const dealIds = recommendation.deal_ids.slice(0, 4), callIds = recommendation.call_ids.slice(0, 3);
    return `<article class="recommendation-row"><span class="recommendation-number">${index + 1}</span><div><h3>${esc(recommendation.title)}</h3><p>${esc(recommendation.description)} ${number(recommendation.deal_ids.length)} сделок${recommendation.call_ids.length ? ` · ${number(recommendation.call_ids.length)} звонков` : ''}.</p><div class="recommendation-sources">${dealIds.map(id => `<button class="source-button" type="button" data-deal="${esc(id)}">${icon('deals')} Сделка #${esc(id)}</button>`).join('')}${callIds.map(id => `<button class="source-button" type="button" data-call="${esc(id)}">${icon('calls')} Звонок #${esc(id)}</button>`).join('')}</div><span class="subtext">${recommendation.requires_approval ? 'Действие требует проверки и решения руководителя' : 'Информационная рекомендация'}</span></div><span class="priority-badge">${recommendation.priority === 'high' ? 'Высокий приоритет' : 'К проверке'}</span></article>`;
  }

  function scopeHTML() {
    return `<div class="scope-box"><div><h3>События за выбранный период</h3><p>Создание и закрытие сделок, звонки: от ${esc(date(state.report.meta.from, true))} до ${esc(date(state.report.meta.to, true))}, конечный момент исключён. Доля выигрышей — выигранные / закрытые за период.</p></div><div><h3>Текущий снимок портфеля</h3><p>Открытые сделки и просрочки проверены на ${esc(date(state.report.meta.as_of, true))}. Бюджеты сделок не равны оплатам. Задачи контактов автоматически к сделкам не относятся.</p></div></div>`;
  }

  function reportHTML() {
    return `<section class="panel report-intro"><span class="eyebrow">ОТЧЁТ ЗА ${state.days} ДНЕЙ · ${esc(managerName().toUpperCase())}</span><h2>Сначала — главное.</h2><p>${esc(summaryText())}</p></section>${metricsHTML()}<section class="panel report-section"><h2>Приоритеты и подтверждения</h2>${selectedRecommendations().map(recommendationHTML).join('') || '<p class="subtext">Для выбранного менеджера рекомендаций нет.</p>'}</section><section class="panel report-section"><h2>Как читать эти цифры</h2>${scopeHTML()}</section><section class="review-strip"><span class="review-icon">${icon('shield')}</span><div><h3>Решения остаются у руководителя.</h3><p>Система собирает факты и предлагает действия. Задачи и сделки в CRM в демо не изменяются.</p></div><button type="button" class="button" data-export="markdown">Скачать отчёт ${icon('download')}</button></section>`;
  }

  function architectureHTML() {
    return `<section class="panel report-section"><h2>Один запрос → проверяемый отчёт</h2><div class="architecture-flow"><div class="flow-card"><span class="eyebrow">01 / ИСТОЧНИКИ</span><h3>CRM и телефония</h3><p>amoCRM: <code>GET /api/v4/leads</code>, <code>/tasks</code>, история изменений. OAuth 2.0, все страницы. Телефония: API выбранного провайдера, метаданные и записи.</p></div><span class="flow-arrow" aria-hidden="true">→</span><div class="flow-card"><span class="eyebrow">02 / ОБРАБОТКА</span><h3>Факты + контекст</h3><p>Детерминированные расчёты KPI и задач. В целевой архитектуре: STT с временными отметками → извлечение договорённостей LLM → привязка доказательств к сделкам.</p></div><span class="flow-arrow" aria-hidden="true">→</span><div class="flow-card"><span class="eyebrow">03 / РЕЗУЛЬТАТ</span><h3>Отчёт и действия</h3><p>SQLite: снимки, задачи, звонки и анализ. Аудио хранится отдельно. В этом демо отчёты — JSON; интерфейс и Markdown показывают источники. Руководитель утверждает действия.</p></div></div></section><section class="panel report-section"><h2>Три роли, понятная ответственность</h2><div class="architecture-roles"><article class="role-card"><span class="metric-icon">${icon('architecture')}</span><h3>Координатор</h3><p>Определяет период, запускает коннекторы, фиксирует время снимка и проверяет полноту данных. Расчёты выполняет обычный код.</p></article><article class="role-card"><span class="metric-icon">${icon('calls')}</span><h3>Аналитик звонков</h3><p>Извлекает возражения и следующий шаг, сохраняет цитаты с таймкодами. Базовый демо-режим использует синтетические расшифровки и правила; LLM включается отдельно.</p></article><article class="role-card"><span class="metric-icon">${icon('report')}</span><h3>Составитель отчёта</h3><p>Соединяет показатели и контекст, формирует приоритеты и прикладывает источники. Спорные выводы передаёт человеку.</p></article></div></section><div class="section-grid"><section class="panel report-section"><h2>Что система делает сама</h2><div class="risk-list"><div class="risk-row"><span>01</span><div><h3>Собирает и считает</h3><p>Загружает разрешённые данные, проверяет пагинацию, рассчитывает метрики и находит задачи с нарушенными сроками.</p></div></div><div class="risk-row"><span>02</span><div><h3>Показывает факты и предложения</h3><p>Связывает выводы с CRM и фрагментами звонка. Проверяет обещанное действие по простым правилам и предлагает сверить результат.</p></div></div><div class="risk-row"><span>03</span><div><h3>Передаёт решения человеку</h3><p>Руководитель оценивает работу сотрудников, подтверждает спорные договорённости и утверждает создание или изменение задач.</p></div></div></div></section><section class="panel report-section"><h2>Три главных ограничения</h2><div class="risk-list"><div class="risk-row"><span>1</span><div><h3>Полнота и связь данных</h3><p>Звонок может быть неверно связан со сделкой; текущий снимок не восстанавливает историю переходов между этапами.</p></div></div><div class="risk-row"><span>2</span><div><h3>Ошибки распознавания и выводов</h3><p>STT и LLM могут ошибаться. Отсутствие задачи по ключевому слову — сигнал для проверки, а не доказательство невыполнения обещания.</p></div></div><div class="risk-row"><span>3</span><div><h3>Персональные данные и доступ</h3><p>Для реальной интеграции нужны согласованные права, политика хранения записей и выбор допустимого сервиса обработки аудио.</p></div></div></div></section></div><section class="panel report-section"><h2>Границы текущего режима</h2><div class="analysis-note">${icon('shield')} ${isDemo() ? 'Интерфейс показывает воспроизводимые синтетические данные. Внешние CRM, телефония, STT и LLM автоматически не вызываются.' : 'Интерфейс показывает загруженные данные CRM и доступные расшифровки. LLM запускается отдельно; изменения в CRM не выполняются.'}</div>${scopeHTML()}</section>`;
  }

  function render() {
    const view = views[state.view];
    $('#navigation').innerHTML = Object.entries(views).map(([key, item]) => `<button type="button" class="nav-item${state.view === key ? ' active' : ''}" data-view="${key}"${state.view === key ? ' aria-current="page"' : ''}>${icon(key)}<span>${item.name}</span>${key === 'calls' && state.report ? `<span class="nav-pill">${number(visibleCalls().length)}</span>` : ''}</button>`).join('');
    $('#breadcrumb-current').textContent = view.name;
    $('#page-eyebrow').textContent = view.eyebrow;
    $('#page-title').textContent = view.title;
    $('#page-description').textContent = view.description;
    document.title = `PULSE — ${view.name}`;
    $('#generate-button').innerHTML = `${icon(state.loading ? 'refresh' : 'spark', state.loading ? 'refresh-spin' : '')}${state.loading ? 'Пересчитываем…' : 'Сформировать отчёт'}`;
    $('#generate-button').disabled = state.loading;
    document.querySelectorAll('[data-days]').forEach(button => { const active = Number(button.dataset.days) === state.days; button.classList.toggle('selected', active); button.setAttribute('aria-pressed', String(active)); });
    if (!state.report) return;
    $('#date-range').textContent = `${date(state.report.meta.from)} — ${date(state.report.meta.to)}`;
    $('#manager-filter').innerHTML = `<option value="all">Все менеджеры</option>${state.report.managers.map(item => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('')}`;
    $('#manager-filter').value = state.manager;
    $('.demo-label').innerHTML = `<span></span>${isDemo() ? 'Демо-данные' : 'Данные amoCRM'}`;
    $('.sidebar-note .eyebrow').innerHTML = `<span class="live-dot"></span> ${isDemo() ? 'ДЕМО-РЕЖИМ' : 'ДАННЫЕ CRM'}`;
    $('.sidebar-footer>small').textContent = isDemo() ? 'Подключения показаны на демо-данных' : 'Источник: amoCRM и расшифровки звонков';
    $('.project-signature small').textContent = isDemo() ? 'Открытый демо-проект' : 'Интеграция с amoCRM';
    $('#data-provenance').textContent = `Снимок: ${date(state.report.meta.as_of, true)} · ${state.source === 'api' ? 'Локальный API' : 'Статический отчёт'} · ${analysisLabel()}`;
    const warnings = state.report.meta.warnings || [];
    $('#warning-notice').hidden = !warnings.length;
    $('#warning-notice').textContent = warnings.map(warning => typeof warning === 'string' ? warning : JSON.stringify(warning)).join(' · ');
    $('#content').innerHTML = ({ overview: overviewHTML, deals: dealsHTML, calls: callsHTML, report: reportHTML, architecture: architectureHTML }[state.view])();
    if ($('#issue-filter')) $('#issue-filter').value = state.issue;
  }

  async function loadReport() {
    const request = ++state.request;
    state.loading = true;
    $('#content').setAttribute('aria-busy', 'true');
    $('#error-notice').hidden = true;
    render();
    try {
      let response;
      let fallback = false;
      try {
        response = await fetch(`/api/report?days=${state.days}`, { headers: { Accept: 'application/json' }, cache: 'no-store' });
        if ([404, 405, 501].includes(response.status)) fallback = true;
        else if (!response.ok) throw new Error(`API вернул ошибку ${response.status}. Отчёт не пересчитан.`);
        else if (!(response.headers.get('content-type') || '').includes('json')) fallback = true;
      } catch (error) {
        if (error instanceof TypeError) fallback = true;
        else throw error;
      }
      if (fallback) response = await fetch(`./data/report-${state.days}.json`, { headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!response.ok) throw new Error(`Не удалось загрузить данные (${response.status}). Запустите python3 -m auditor build-demo.`);
      const report = await response.json();
      if (!report.meta || !report.metrics || !['managers', 'manager_stats', 'pipeline', 'series', 'deals', 'calls', 'recommendations'].every(key => Array.isArray(report[key]))) throw new Error('Формат отчёта не соответствует ожидаемой схеме.');
      if (request !== state.request) return false;
      state.report = report;
      state.source = fallback ? 'static' : 'api';
      if (state.manager !== 'all' && !report.managers.some(item => String(item.id) === state.manager)) state.manager = 'all';
      return true;
    } catch (error) {
      if (request !== state.request) return false;
      if (state.report) state.days = Number(state.report.meta.period_days);
      $('#error-notice').innerHTML = `${esc(error.message)}${state.report ? ' Показан ранее загруженный отчёт.' : ''} <button class="button button-small button-white" type="button" id="retry-button">Повторить</button>`;
      $('#error-notice').hidden = false;
      if (!state.report) $('#content').innerHTML = '<div class="panel empty-state">Отчёт пока недоступен. Проверьте сервер или файлы демо-данных.</div>';
      return false;
    } finally {
      if (request === state.request) { state.loading = false; $('#content').setAttribute('aria-busy', 'false'); render(); }
    }
  }

  function navigate(view) {
    if (!views[view]) return;
    state.view = view;
    history.replaceState(null, '', `#${view}`);
    render();
    closeMobile();
  }

  function openDrawer(html) {
    if ($('#detail-drawer').hidden) drawerReturnFocus = document.activeElement;
    $('#drawer-content').innerHTML = html;
    $('#drawer-overlay').hidden = false;
    $('#detail-drawer').hidden = false;
    $('#detail-drawer').scrollTop = 0;
    document.body.style.overflow = 'hidden';
    $('#close-drawer').focus();
  }

  function closeDrawer() {
    $('#drawer-overlay').hidden = true;
    $('#detail-drawer').hidden = true;
    document.body.style.overflow = '';
    if (drawerReturnFocus?.isConnected) drawerReturnFocus.focus();
  }

  function evidenceHTML(call) {
    return (call.evidence || []).map(evidence => `<blockquote class="evidence-block"><div class="evidence-meta">${icon('link')}<span>${seconds(evidence.start)} — ${seconds(evidence.end)}</span><span>${esc(evidence.speaker)}</span></div><p>«${esc(evidence.text)}»</p></blockquote>`).join('') || '<p>Для этого звонка подтверждающий фрагмент не указан.</p>';
  }

  function openDeal(id) {
    const deal = state.report.deals.find(item => String(item.id) === String(id));
    if (!deal) return toast('Сделка недоступна в текущем отчёте.');
    const calls = state.report.calls.filter(call => String(call.deal_id) === String(deal.id));
    const tasks = deal.tasks || [];
    openDrawer(`<span class="status-pill ${esc(deal.status)}">${esc(deal.status_label)}</span><h2 id="drawer-title">${esc(deal.name)}</h2><div class="drawer-subtitle">${esc(deal.company)} · сделка #${esc(deal.id)}</div><div class="drawer-metrics"><div class="drawer-metric"><span>БЮДЖЕТ СДЕЛКИ</span><strong>${money(deal.amount)}</strong></div><div class="drawer-metric"><span>ОТВЕТСТВЕННЫЙ</span><strong>${esc(manager(deal.manager_id).name)}</strong></div></div><section class="drawer-section"><h3>Сигналы и следующий шаг</h3><div class="issue-stack">${issuePills(deal.issues) || '<span class="status-pill won">Рисков не найдено</span>'}</div><p>${esc(deal.recommendation)}</p><span class="subtext">Предложение проверяет руководитель; изменения в CRM не выполняются.</span></section><section class="drawer-section"><h3>Задачи в CRM · ${number(tasks.length)}</h3>${tasks.map(task => { const completed = task.is_completed ?? task.completed; const due = task.complete_till || task.due_at; return `<div class="task-row"><strong>${esc(task.text || task.title || `Задача #${task.id}`)}</strong>${completed ? 'Завершена' : 'Не завершена'}${due ? ` · срок: ${esc(date(due, true))}` : ''}</div>`; }).join('') || '<p>К сделке не прикреплены задачи. Задачи контактов автоматически не учитываются.</p>'}</section><section class="drawer-section"><h3>Звонки за период · ${number(calls.length)}</h3>${calls.map(call => `<button class="detail-call-button" type="button" data-call="${esc(call.id)}"><span>${esc(call.next_step || call.summary)}<small>${esc(date(call.occurred_at, true))} · ${seconds(call.duration_seconds)} · #${esc(call.id)}</small></span>${icon('chevron')}</button>`).join('') || '<p>В выбранном периоде связанных звонков нет.</p>'}</section>${calls[0] ? `<section class="drawer-section"><h3>Подтверждение из последнего звонка</h3>${evidenceHTML(calls[0])}</section>` : ''}<section class="drawer-section"><h3>Даты сделки</h3><p>Создана: ${esc(date(deal.created_at, true))}<br>Последняя активность: ${esc(date(deal.last_activity_at, true))}${deal.closed_at ? `<br>Закрыта: ${esc(date(deal.closed_at, true))}` : ''}</p></section><div class="audio-note">${isDemo() ? 'Синтетическая сделка из демо-набора. Ссылки на реальную CRM отсутствуют.' : 'Данные сделки из amoCRM. Задачи и статус в CRM интерфейс не изменяет.'}</div>${!isDemo() && safeURL(deal.crm_url) ? `<a class="button button-subtle" href="${esc(safeURL(deal.crm_url))}" target="_blank" rel="noopener noreferrer">Открыть в amoCRM ${icon('link')}</a>` : ''}`);
  }

  function openCall(id) {
    const call = state.report.calls.find(item => String(item.id) === String(id));
    if (!call) return toast('Звонок недоступен в текущем периоде.');
    openDrawer(`<span class="${call.followup_gap ? 'issue-pill followup_gap' : 'status-pill won'}">${call.followup_gap ? 'Договорённость к проверке' : 'Сверка договорённостей'}</span><h2 id="drawer-title">Разговор с ${esc(call.company)}</h2><div class="drawer-subtitle">${esc(date(call.occurred_at, true))} · ${seconds(call.duration_seconds)} · звонок #${esc(call.id)}</div><div class="drawer-metrics"><div class="drawer-metric"><span>МЕНЕДЖЕР</span><strong>${esc(manager(call.manager_id).name)}</strong></div><div class="drawer-metric"><span>СВЯЗАННАЯ СДЕЛКА</span><button class="text-button" type="button" data-deal="${esc(call.deal_id)}">Открыть #${esc(call.deal_id)} ${icon('arrow')}</button></div></div><section class="drawer-section"><h3>Краткий разбор</h3><p>${esc(call.summary)}</p></section><section class="drawer-section"><h3>Следующее действие</h3><p>${esc(call.next_step || 'Не определено')}</p>${call.followup_gap ? '<span class="subtext">Совпадающая задача по ключевому слову не найдена. Это сигнал для проверки, а не доказательство нарушения.</span>' : '<span class="subtext">Сигнал несоответствия не выявлен. Наличие и соответствие задач проверяет человек.</span>'}</section><section class="drawer-section"><h3>Возражения</h3><div class="issue-stack">${(call.objections || []).map(objection => `<span class="issue-pill">${esc(objection)}</span>`).join('') || '<span class="subtext">Не обнаружены правилами демо-анализа</span>'}</div></section><section class="drawer-section"><h3>Фрагменты, на которых основан вывод</h3>${evidenceHTML(call)}</section><section class="drawer-section"><h3>Полная расшифровка</h3>${(call.transcript || []).map(segment => `<div class="transcript-row"><span>${seconds(segment.start)}</span><div><strong>${esc(segment.speaker)}</strong><p>${esc(segment.text)}</p></div></div>`).join('') || '<p>Расшифровка недоступна.</p>'}</section><div class="audio-note">${call.synthetic || isDemo() ? 'Синтетическая расшифровка для демонстрации.' : 'Расшифровка предоставлена через источник звонков.'} Метод анализа: ${call.analysis_mode === 'openai' ? 'LLM после явного запуска' : call.analysis_mode === 'demo_rules' ? 'демо-правила' : 'локальные правила'}.${call.audio_url ? '' : ' Аудиозапись в отчёте отсутствует.'}</div>${safeURL(call.audio_url) ? `<a class="button button-subtle" href="${esc(safeURL(call.audio_url))}" target="_blank" rel="noopener noreferrer">Открыть запись ${icon('link')}</a>` : ''}`);
  }

  function exportReport(format) {
    if (!state.report) return toast('Сначала загрузите отчёт.');
    $('#export-menu').hidden = true;
    $('#export-button').setAttribute('aria-expanded', 'false');
    if (format === 'print') { navigate('report'); window.print(); return; }
    const metrics = selectedMetrics();
    const openDeals = visibleDeals().filter(isOpen);
    const selected = { ...state.report, selection: { manager_id: state.manager, manager_name: managerName() }, managers: state.report.managers.filter(item => state.manager === 'all' || String(item.id) === state.manager), manager_stats: state.report.manager_stats.filter(item => state.manager === 'all' || String(item.id) === state.manager), metrics, pipeline: state.report.pipeline.map(stage => ({ ...stage, count: openDeals.filter(deal => deal.status === stage.id).length, amount: openDeals.filter(deal => deal.status === stage.id).reduce((sum, deal) => sum + deal.amount, 0) })), series: filteredSeries(), deals: visibleDeals(), calls: visibleCalls(), recommendations: selectedRecommendations(), summary: summaryText() };
    let text = JSON.stringify(selected, null, 2), extension = 'json', type = 'application/json;charset=utf-8';
    if (format === 'markdown') {
      extension = 'md'; type = 'text/markdown;charset=utf-8';
      const md = value => String(value ?? '').replace(/[\[\]`*_<>#|]/g, character => `\\${character}`).replace(/\r?\n/g, ' ');
      text = `# PULSE — отчёт отдела продаж\n\n${isDemo() ? 'Демо-данные.' : 'Данные amoCRM.'} Анализ расшифровок: ${analysisLabel()}.\n\nПериод: ${date(state.report.meta.from, true)} — ${date(state.report.meta.to, true)} (конец исключён).\nКоманда: ${md(managerName())}. Снимок: ${date(state.report.meta.as_of, true)}.\n\n## Результат\n\n${md(summaryText())}\n\n| Показатель | Значение |\n| --- | ---: |\n| Выиграно сделок | ${metrics.won_count} |\n| Сумма бюджетов выигранных сделок | ${money(metrics.won_amount)} |\n| Доля выигрышей среди закрытых | ${metrics.win_rate}% |\n| Открытые сделки на дату снимка | ${metrics.open_count} |\n| Сделки с просрочкой | ${metrics.overdue_count} |\n| Сделки без незавершённых задач | ${metrics.no_task_count} |\n| Звонки за период | ${metrics.calls_count} |\n\nБюджеты сделок не равны денежной выручке. Просрочки и открытые сделки — текущий снимок, включая старые сделки.\n\n## Приоритеты и источники\n\n${selectedRecommendations().map((item, index) => `### ${index + 1}. ${md(item.title)}\n\n${md(item.description)}\n\nСделки: ${item.deal_ids.map(id => `#${id}`).join(', ') || '—'}. Звонки: ${item.call_ids.map(id => `#${id}`).join(', ') || '—'}.\n\n${item.requires_approval ? 'Решение принимает руководитель.' : ''}`).join('\n\n')}\n\n## Подтверждения из звонков\n\n${visibleCalls().filter(call => call.followup_gap).map(call => `### Звонок #${call.id} · ${md(call.company)}\n\n${md(call.summary)}\n\n${(call.evidence || []).map(fragment => `> ${seconds(fragment.start)}–${seconds(fragment.end)} · ${md(fragment.speaker)}: ${md(fragment.text)}`).join('\n\n')}`).join('\n\n')}\n\nОтсутствие совпадающей задачи — повод для проверки, а не доказательство невыполнения обещания.\n`;
    }
    const url = URL.createObjectURL(new Blob([text], { type }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `pulse-report-${state.days}days${state.manager === 'all' ? '' : `-manager-${state.manager}`}.${extension}`; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast(format === 'json' ? 'JSON отчёта подготовлен.' : 'Отчёт в Markdown подготовлен.');
  }

  function toast(message) { clearTimeout(toastTimer); $('#toast').textContent = message; $('#toast').hidden = false; toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4000); }
  function closeMobile() { $('#sidebar').classList.remove('open'); $('#mobile-backdrop').hidden = true; $('#mobile-menu').setAttribute('aria-expanded', 'false'); }

  $('#mobile-menu').innerHTML = icon('menu');
  $('#close-drawer').innerHTML = icon('close');
  $('#export-button').innerHTML = `${icon('download')} Экспорт ${icon('down', 'export-button-chevron')}`;
  $('#export-button').addEventListener('click', () => { const open = $('#export-menu').hidden; $('#export-menu').hidden = !open; $('#export-button').setAttribute('aria-expanded', String(open)); });
  $('#mobile-menu').addEventListener('click', () => { const open = !$('#sidebar').classList.contains('open'); $('#sidebar').classList.toggle('open', open); $('#mobile-backdrop').hidden = !open; $('#mobile-menu').setAttribute('aria-expanded', String(open)); });
  $('#mobile-backdrop').addEventListener('click', closeMobile);
  $('#close-drawer').addEventListener('click', closeDrawer);
  $('#drawer-overlay').addEventListener('click', closeDrawer);
  $('#manager-filter').addEventListener('change', event => { state.manager = event.target.value; render(); });
  $('#generate-button').addEventListener('click', async () => { if (await loadReport()) { navigate('report'); toast('Отчёт обновлён: показатели рассчитаны из выбранного набора данных.'); } });

  document.addEventListener('click', async event => {
    const button = event.target.closest('button');
    if (button?.dataset.view) navigate(button.dataset.view);
    if (button?.dataset.days) { state.days = Number(button.dataset.days); await loadReport(); }
    if (button?.dataset.manager) { state.manager = String(button.dataset.manager); render(); toast(`Выбран менеджер: ${managerName()}`); }
    if (button?.dataset.deal && state.report) openDeal(button.dataset.deal);
    if (button?.dataset.call && state.report) openCall(button.dataset.call);
    if (button?.dataset.export) exportReport(button.dataset.export);
    if (button?.id === 'retry-button') await loadReport();
    if (!event.target.closest('.export-wrap')) { $('#export-menu').hidden = true; $('#export-button').setAttribute('aria-expanded', 'false'); }
  });
  document.addEventListener('input', event => { if (event.target.id === 'deal-search') { state.search = event.target.value; $('#deals-body').innerHTML = dealRowsHTML(); $('#deal-count').textContent = `${number(filteredDeals().length)} из ${number(visibleDeals().length)} сделок`; } });
  document.addEventListener('change', event => { if (event.target.id === 'issue-filter') { state.issue = event.target.value; render(); } if (event.target.id === 'call-quality-filter') { state.callQuality = event.target.value; render(); } });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') { closeDrawer(); closeMobile(); $('#export-menu').hidden = true; $('#export-button').setAttribute('aria-expanded', 'false'); }
    if (event.key === 'Tab' && !$('#detail-drawer').hidden) {
      const focusables = Array.from($('#detail-drawer').querySelectorAll('button, a[href], input, select, [tabindex="0"]')).filter(element => !element.disabled);
      const first = focusables[0], last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  window.addEventListener('hashchange', () => { const view = location.hash.slice(1); if (views[view]) { state.view = view; render(); } });
  const initialView = location.hash.slice(1);
  if (views[initialView]) state.view = initialView;
  render();
  loadReport();
})();
