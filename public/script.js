const API_BASE = 'http://localhost:8502/api';

// ─── State ────────────────────────────────────────────────────────────────────
let _dashboardData = null;   // full raw payload from /api/dashboard
let _currentTf     = '1y';  // active timeframe button

// ─── Navigation ───────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item[data-target]').forEach(item => {
    item.addEventListener('click', e => {
        e.preventDefault();
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        document.querySelectorAll('.view-section').forEach(v => {
            v.classList.remove('active');
            v.classList.remove('hidden');
        });
        document.getElementById(item.dataset.target).classList.add('active');
    });
});

// ─── Dropdown ─────────────────────────────────────────────────────────────────
const researchNav     = document.getElementById('research-nav');
const companyDropdown = document.getElementById('company-dropdown');

researchNav.addEventListener('click', () => {
    // Switch to the Research View so the user immediately sees the UI change
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    researchNav.classList.add('active');
    document.querySelectorAll('.view-section').forEach(v => {
        v.classList.remove('active');
        v.classList.remove('hidden');
    });
    document.getElementById('research-view').classList.add('active');

    // Toggle the dropdown for selecting a specific company
    companyDropdown.classList.toggle('open');
    const chevron = researchNav.querySelector('.chevron');
    chevron.style.transform = companyDropdown.classList.contains('open') ? 'rotate(180deg)' : 'rotate(0)';
    if (companyDropdown.children.length === 1 && companyDropdown.children[0].classList.contains('dropdown-loading')) {
        loadCompanies();
    }
});

// ─── Formatters ───────────────────────────────────────────────────────────────
function formatPrice(val) {
    if (val === null || val === undefined) return '--';
    return '₹' + parseFloat(val).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function formatPercent(val) {
    if (val === null || val === undefined) return '--';
    const num = parseFloat(val);
    return (num > 0 ? '+' : '') + num.toFixed(2) + '%';
}
function getColorClass(val) {
    if (val === null || val === undefined) return '';
    return parseFloat(val) >= 0 ? 'text-green' : 'text-red';
}
function formatMarketCap(val) {
    if (val === null || val === undefined) return '--';
    const num = parseFloat(val);
    if (isNaN(num)) return '--';
    // If already in Cr range (< 1e9), display directly
    if (num < 1e9) return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 0 }) + ' Cr';
    // Convert from raw rupees to Cr (1 Cr = 1e7)
    const inCr = num / 1e7;
    if (inCr >= 100000) return '₹' + (inCr / 100000).toFixed(2) + ' Lakh Cr';
    if (inCr >= 1000)   return '₹' + (inCr / 1000).toFixed(2) + ' K Cr';
    return '₹' + inCr.toFixed(2) + ' Cr';
}
function formatRatio(val, decimals = 2) {
    if (val === null || val === undefined) return 'N/A';
    const num = parseFloat(val);
    if (isNaN(num)) return 'N/A';
    // If value is absurdly large (raw rupees instead of ratio), return N/A
    if (Math.abs(num) > 1e9) return 'N/A';
    // If value is exactly 0 and shouldn't be, it's missing data
    if (num === 0 && val !== 0 && val !== '0') return 'N/A';
    return num.toFixed(decimals);
}
/** Extract a displayable string from an item that may be a string or an object */
function extractText(item) {
    if (typeof item === 'string') return item;
    if (typeof item === 'object' && item !== null) {
        // Handle financial observation objects with metric/value/explanation
        if (item.metric && item.explanation) {
            const severityIcon = {high: '⚠️', medium: '⚡', low: '📉'}[item.severity?.toLowerCase()] || '';
            return `${severityIcon} ${item.metric}: ${item.value} - ${item.explanation}`;
        }
        if (item.metric && item.value) {
            return `${item.metric}: ${item.value}`;
        }
        // Common field names used by AI agents
        return item.explanation || item.description || item.text || item.message || item.flag || item.event || item.signal ||
               item.name || item.detail || JSON.stringify(item).replace(/[{"]/g, '').substring(0, 120);
    }
    return String(item);
}

// ─── Chart ────────────────────────────────────────────────────────────────────

/**
 * Choose the right data source for a timeframe.
 * 1D / 1W  → intraday (5-min bars)
 * 1M / 6M / 1Y / 5Y → daily bars
 */
function getChartData(tf) {
    if (!_dashboardData) return [];
    const idx = _dashboardData.index || {};
    const daily    = idx.history   || [];
    const intraday = idx.intraday  || [];

    const now = new Date();
    let cutoff;

    if (tf === '1d') {
        // 1 trading day in India is approx 75 bars of 5-min intervals
        return intraday.slice(-75);
    }

    if (tf === '1w') {
        cutoff = new Date(now - 7 * 86400e3);
        const filtered = intraday.filter(d => new Date(d.date) >= cutoff);
        return filtered.length > 3 ? filtered : daily.slice(-7);
    }

    // For daily data: filter by cutoff date
    switch (tf) {
        case '1m': cutoff = new Date(now - 30  * 86400e3); break;
        case '6m': cutoff = new Date(now - 182 * 86400e3); break;
        case '1y': cutoff = new Date(now - 365 * 86400e3); break;
        case '5y': cutoff = new Date(now.getTime() - 5*365*24*60*60*1000); break;
        default:   return daily;
    }
    const filtered = daily.filter(d => {
        const dTime = new Date(d.date).getTime();
        return !isNaN(dTime) && dTime >= cutoff.getTime();
    });
    return filtered.length >= 2 ? filtered : daily;
}

/**
 * Render a Plotly area chart.
 * Uses a dual-trace approach (invisible baseline + price line) so the area
 * fill is correctly anchored to the visible Y range — NOT to zero.
 * This prevents NIFTY (≈24,000) from rendering as a solid colour block.
 */
function renderChart(historyData, containerId, tf) {
    const el = document.getElementById(containerId);
    if (!el) return;

    // Remove loading spinner
    const spinner = el.querySelector('.loading-spinner');
    if (spinner) spinner.remove();

    if (!historyData || historyData.length === 0) {
        el.innerHTML = '<p style="text-align:center;padding:2rem;color:#64748b;">No data for this period</p>';
        return;
    }

    const dates  = historyData.map(d => d.date);
    const closes = historyData.map(d => parseFloat(d.close));

    const first = closes[0], last = closes[closes.length - 1];
    const up = last >= first;
    // Distinct accent per timeframe; red when the selected window is down
    const TF_COLORS = {
        '1d': '#f59e0b', '1w': '#3b82f6', '1m': '#8b5cf6',
        '6m': '#14b8a6', '1y': '#10b981', '5y': '#ec4899',
    };
    const lineColor = up ? (TF_COLORS[tf] || '#10b981') : '#ef4444';
    const rgb = parseInt(lineColor.slice(1), 16);
    const areaColor = `rgba(${(rgb >> 16) & 255},${(rgb >> 8) & 255},${rgb & 255},0.13)`;

    // Baseline anchored 2% below visible minimum — NOT zero
    const yFloor   = Math.min(...closes) * 0.98;
    const baseline = closes.map(() => yFloor);

    const baseTrace = {
        x: dates, y: baseline,
        type: 'scatter', mode: 'lines',
        line: { color: 'transparent', width: 0 },
        hoverinfo: 'none', showlegend: false
    };

    const priceTrace = {
        x: dates, y: closes,
        type: 'scatter', mode: 'lines+markers',
        fill: 'tonexty', fillcolor: areaColor,
        line: { color: lineColor, width: 2 },
        marker: {
            size: 0,  // Invisible by default
            symbol: 'diamond',
            color: lineColor,
            opacity: 0
        },
        hovertemplate: '<b>%{x}</b> | <b>₹%{y:,.2f}</b><extra></extra>',
        showlegend: false
    };

    const layout = {
        margin: { t: 8, r: 8, b: 35, l: 65 },
        autosize: true,
        paper_bgcolor: 'transparent',
        plot_bgcolor:  'transparent',
        xaxis: {
            showgrid: false, color: '#94a3b8',
            tickfont: { size: 10, color: '#94a3b8' },
            linecolor: 'rgba(148,163,184,0.15)'
        },
        yaxis: {
            autorange: true,   // never force zero
            showgrid: true,
            gridcolor: 'rgba(255,255,255,0.06)',
            color: '#94a3b8',
            tickfont: { size: 10, color: '#94a3b8' },
            tickformat: ',.0f'
        },
        hovermode: 'x unified',
        hoverlabel: { 
            bgcolor: 'rgba(30, 41, 59, 0.95)', 
            bordercolor: 'rgba(255, 255, 255, 0.2)',
            font: { color: '#ffffff', size: 13, family: 'Inter' },
            align: 'left'
        },
        showlegend: false
    };

    Plotly.purge(containerId);
    Plotly.newPlot(containerId, [baseTrace, priceTrace], layout,
        { responsive: true, displayModeBar: false });
    
    // Add hover event to show diamond marker on hover
    if (el) {
        el.on('plotly_hover', (data) => {
            const markerSize = new Array(closes.length).fill(0);
            if (data.points && data.points[0]) {
                const pointIndex = data.points[0].pointNumber;
                markerSize[pointIndex] = 10; // Show diamond at hover point
            }
            Plotly.restyle(containerId, { 'marker.size': [null, markerSize] });
        });
        
        // Hide diamond marker when not hovering
        el.on('plotly_unhover', () => {
            Plotly.restyle(containerId, { 'marker.size': [null, new Array(closes.length).fill(0)] });
        });
    }
}

/** Apply a timeframe: choose data source → re-render chart → update active btn */
function applyTimeframe(tf) {
    if (!_dashboardData) return;
    _currentTf = tf;
    const chartData = getChartData(tf);
    renderChart(chartData, 'nifty-chart', tf);

    // Update Price Bar based on the selected timeframe
    const idx = _dashboardData.index || {};
    let currentPrice = idx.current_price;
    let prevClose = idx.prev_close;
    let changePct = idx.change_pct;

    if (tf !== '1d') {
        if (chartData.length >= 2) {
            currentPrice = parseFloat(chartData[chartData.length - 1].close);
            prevClose = parseFloat(chartData[0].close);
            changePct = ((currentPrice - prevClose) / prevClose) * 100;
        }
    } else {
        // For 1D, if real-time price missing, derive from daily history
        if (!currentPrice && (idx.history || []).length >= 2) {
            const h = idx.history;
            currentPrice = parseFloat(h[h.length - 1].close);
            prevClose    = parseFloat(h[h.length - 2].close);
            changePct    = ((currentPrice - prevClose) / prevClose) * 100;
        }
    }

    if (currentPrice != null) {
        const priceEl = document.getElementById('nifty-price');
        const chgEl   = document.getElementById('nifty-chg');
        if (priceEl) priceEl.textContent = currentPrice.toLocaleString('en-IN', { maximumFractionDigits: 2 });
        if (chgEl && changePct != null) {
            const up = changePct >= 0;
            const pts = prevClose ? Math.abs(currentPrice - prevClose).toFixed(2) : '';
            chgEl.textContent = `${up ? '+' : ''}${changePct.toFixed(2)}%  (${up ? '+' : '-'}${pts})`;
            chgEl.className   = 'chart-price-chg ' + (up ? 'up' : 'down');
        }
    }

    document.querySelectorAll('.timeframe-selector .tf-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.timeframe-selector .tf-btn[data-tf="${tf}"]`);
    if (btn) btn.classList.add('active');
}

// Wire timeframe buttons (NIFTY chart selector only — company chart has its own wiring)
document.querySelectorAll('.timeframe-selector .tf-btn').forEach(btn => {
    btn.addEventListener('click', () => applyTimeframe(btn.dataset.tf));
});

// ─── Dashboard ────────────────────────────────────────────────────────────────
async function loadDashboard() {
    document.getElementById('nifty-chart').innerHTML         = '<div class="loading-spinner"></div>';
    document.getElementById('market-news').innerHTML         = '<div class="loading-spinner"></div>';
    document.getElementById('sector-performance').innerHTML  = '<div class="loading-spinner"></div>';

    try {
        const res    = await fetch(`${API_BASE}/dashboard`);
        const result = await res.json();

        if (!result.success || !result.data) throw new Error(result.detail || 'No data');

        const data = result.data;
        _dashboardData = data;

        // ── Chart & Price Bar ──────────────────────────────────────────────
        // This will now render the chart AND populate the price bar
        applyTimeframe(_currentTf);

        // ── Market Indicators ──────────────────────────────────────────────
        const ind   = data.indicators || {};
        const adv   = ind.advancing_stocks;
        const dec   = ind.declining_stocks;
        const total = (adv != null && dec != null) ? adv + dec : null;

        document.getElementById('ind-adv').textContent     = adv ?? '--';
        document.getElementById('ind-dec').textContent     = dec ?? '--';
        document.getElementById('ind-adr').textContent     = ind.advance_decline_ratio ?? '--';
        document.getElementById('ind-breadth').textContent = ind.market_breadth != null ? ind.market_breadth + '%' : '--';
        document.getElementById('ind-return').textContent  = formatPercent(ind.average_daily_return);

        document.getElementById('ind-turnover').textContent =
            ind.total_turnover != null && ind.total_turnover > 0
                ? '₹' + ind.total_turnover.toLocaleString('en-IN') + ' Cr'
                : 'N/A';

        // Show volume count, not "stocks traded"
        document.getElementById('ind-volume').textContent =
            ind.total_traded_volume != null && ind.total_traded_volume > 0
                ? (ind.total_traded_volume / 1e6).toFixed(2) + 'M'
                : 'N/A';

        // ── News ───────────────────────────────────────────────────────────
        const newsEl    = document.getElementById('market-news');
        const newsItems = data.news || [];

        if (newsItems.length > 0) {
            newsEl.innerHTML = newsItems.map(item => {
                const desc     = item.description || item.summary || '';
                const company  = item.company_name ? `<span class="news-tag">${item.company_name}</span>` : '';
                const srcDate  = [item.source, item.date].filter(Boolean).join(' · ');
                return `
                <div class="news-item">
                    <div class="news-top">
                        ${company}
                        <span class="news-src">${srcDate}</span>
                    </div>
                    <h4><a href="${item.url || '#'}" target="_blank" rel="noopener noreferrer">
                        ${item.headline || item.title || 'Untitled'}
                    </a></h4>
                    ${desc ? `<p class="news-desc">${desc}</p>` : ''}
                </div>`;
            }).join('');
        } else {
            newsEl.innerHTML = '<p class="no-data-msg">No news available at this time.</p>';
        }

        // ── Top Movers ─────────────────────────────────────────────────────
        document.getElementById('top-gainers').innerHTML =
            (data.movers?.gainers || []).map(m =>
                `<li><span>${m.symbol}</span><span class="text-green">+${m.change.toFixed(2)}%</span></li>`
            ).join('') || '<li class="muted">No data</li>';

        document.getElementById('top-losers').innerHTML =
            (data.movers?.losers || []).map(m =>
                `<li><span>${m.symbol}</span><span class="text-red">${m.change.toFixed(2)}%</span></li>`
            ).join('') || '<li class="muted">No data</li>';

        // ── Sectors ────────────────────────────────────────────────────────
        const sectorEl = document.getElementById('sector-performance');
        const sectors  = data.sectors || [];
        sectorEl.innerHTML = sectors.length > 0
            ? sectors.map(s => `
                <div class="sector-item">
                    <span>${s.sector}</span>
                    <span class="${getColorClass(s.change)}">${formatPercent(s.change)}</span>
                </div>`).join('')
            : '<p class="no-data-msg">No sector data</p>';

        // ── AI Price Predictions ───────────────────────────────────────────
        const predictions = data.predictions || [];
        const forecastTableBody = document.querySelector('.forecast-card tbody');
        if (forecastTableBody) {
            if (predictions.length > 0) {
                forecastTableBody.innerHTML = predictions.map(pred => {
                    const directionClass = pred.direction === 'UP' ? 'text-green' : 
                                          pred.direction === 'DOWN' ? 'text-red' : '';
                    const directionSymbol = pred.direction === 'UP' ? '▲' : 
                                           pred.direction === 'DOWN' ? '▼' : '—';
                    const returnVal = pred.expected_return != null ? formatPercent(pred.expected_return) : '--';
                    const currentPrice = formatPrice(pred.current_price);
                    
                    return `
                    <tr>
                        <td><strong>${pred.company}</strong></td>
                        <td>${currentPrice}</td>
                        <td class="${directionClass}">${directionSymbol} ${pred.direction}</td>
                        <td class="${getColorClass(pred.expected_return)}">${returnVal}</td>
                    </tr>`;
                }).join('');
            } else {
                forecastTableBody.innerHTML = '<tr><td colspan="4" class="text-center">Loading predictions...</td></tr>';
            }
        }

        // ── Tables ─────────────────────────────────────────────────────────
        const companies = data.companies || [];

        document.getElementById('high-low-table').innerHTML = companies.map(c => `
            <tr>
                <td><strong>${c.symbol}</strong></td>
                <td class="text-green">${formatPrice(c.high_52w)}</td>
                <td class="text-red">${formatPrice(c.low_52w)}</td>
            </tr>`).join('');

        document.getElementById('nifty50-table').innerHTML = companies.map(c => `
            <tr>
                <td><strong>${c.symbol}</strong></td>
                <td>${c.company}</td>
                <td>${formatPrice(c.price)}</td>
                <td class="${getColorClass(c.change)}">${formatPercent(c.change)}</td>
                <td>${c.pe != null ? c.pe : '--'}</td>
                <td><button class="research-btn-small" onclick="researchCompany('${c.company}','${c.ticker}')">View</button></td>
            </tr>`).join('');

    } catch (err) {
        console.error('Dashboard error:', err);
        document.getElementById('nifty-chart').innerHTML  = '<p class="error-msg">Failed to load chart. Is the backend running?</p>';
        document.getElementById('market-news').innerHTML  = '<p class="no-data-msg">Could not load news.</p>';
        document.getElementById('sector-performance').innerHTML = '<p class="no-data-msg">Could not load sector data.</p>';
    }
}

// ─── Companies Dropdown ───────────────────────────────────────────────────────
async function loadCompanies() {
    try {
        const res    = await fetch(`${API_BASE}/companies`);
        const result = await res.json();
        if (result.success && result.companies) {
            companyDropdown.innerHTML = result.companies.map(c =>
                `<a class="dropdown-item" onclick="researchCompany('${c.name}','${c.ticker}')">${c.name}</a>`
            ).join('');
        }
    } catch {
        companyDropdown.innerHTML = '<div class="dropdown-item">Failed to load</div>';
    }
}

// ─── Company Research ─────────────────────────────────────────────────────────
let _companyChartTf = '1y';
let _companyPriceHistory = [];
let _companyTicker = '';

/** Filter stored price history to a given timeframe. */
function _filterCompanyHistory(history, tf) {
    if (!history || history.length === 0) return [];
    const now  = new Date();
    let cutoff;
    switch (tf) {
        case '1d': return history.slice(-1);
        case '1w': cutoff = new Date(now - 7   * 86400e3); break;
        case '1m': cutoff = new Date(now - 30  * 86400e3); break;
        case '6m': cutoff = new Date(now - 182 * 86400e3); break;
        case '1y': cutoff = new Date(now - 365 * 86400e3); break;
        case '5y': return history;
        default:   return history;
    }
    const filtered = history.filter(d => new Date(d.date) >= cutoff);
    return filtered.length >= 2 ? filtered : history.slice(-30);
}

async function researchCompany(name, ticker) {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('research-nav').classList.add('active');
    document.querySelectorAll('.view-section').forEach(v => {
        v.classList.remove('active');
        v.classList.remove('hidden');
    });
    document.getElementById('research-view').classList.add('active');

    // Highlight selected company in search dropdown
    document.querySelectorAll('.dropdown-item').forEach(item => {
        if (item.textContent.trim() === name || item.textContent.trim() === ticker) {
            item.classList.add('active');
            item.style.color = '#10b981';
            item.style.fontWeight = 'bold';
        } else {
            item.classList.remove('active');
            item.style.color = '';
            item.style.fontWeight = '';
        }
    });
    const searchInput = document.getElementById('company-search-input');
    if (searchInput) searchInput.value = name;

    _companyTicker = ticker;

    // Reset and show loading state
    document.getElementById('cr-header-name').textContent = `Company Specific Research - ${name}`;
    document.getElementById('cr-header-price').textContent = '--';
    document.getElementById('cr-header-change').textContent = '--';
    document.getElementById('cr-ticker').textContent = ticker;
    document.getElementById('cr-date').textContent = new Date().toLocaleDateString('en-IN', { 
        day: '2-digit', month: 'short', year: 'numeric' 
    }) + ' | ' + new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    document.getElementById('cr-summary').textContent = 'Fetching company data from multiple agents...';

    try {
        const res = await fetch(`${API_BASE}/company-research`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, ticker })
        });
        const result = await res.json();

        if (result.success) {
            // ── Header ─────────────────────────────────────────────────────
            document.getElementById('cr-header-name').textContent = result.company_name || name;
            document.getElementById('cr-header-price').textContent = formatPrice(result.price);
            document.getElementById('cr-header-change').textContent = formatPercent(result.change_percent);
            document.getElementById('cr-header-change').className = 'price-change ' + getColorClass(result.change_percent);

            // ── Business Fundamentals ───────────────────────────────────────
            document.getElementById('cr-sector').textContent = result.sector || 'N/A';
            document.getElementById('cr-industry').textContent = result.industry || 'N/A';
            document.getElementById('cr-summary').textContent = result.summary || 'No summary available.';

            // ── Company Snapshot ───────────────────────────────────────────
            document.getElementById('cr-mcap').textContent = formatMarketCap(result.market_cap);
            document.getElementById('cr-pe').textContent = formatRatio(result.pe_ratio);
            document.getElementById('cr-div-yield').textContent = result.dividend_yield ? parseFloat(result.dividend_yield).toFixed(2) + '%' : 'N/A';
            document.getElementById('cr-high52').textContent = formatPrice(result.high_52w);
            document.getElementById('cr-low52').textContent = formatPrice(result.low_52w);

            // ── Market Intelligence ────────────────────────────────────────
            const agent2 = result.agent2 || {};
            
            // AI News Summary
            document.getElementById('cr-news-summary').textContent = agent2.summary || 'Awaiting agent analysis...';
            
            // Top Developments - from agent2.important_events
            const topDevelopments = agent2.important_events || [];
            document.getElementById('cr-news-events').innerHTML = topDevelopments.length > 0 
                ? topDevelopments.map(e => `<li>${extractText(e)}</li>`).join('') 
                : '<li style="color: var(--text-muted);">No significant developments identified</li>';
            
            // Key Events - from agent2.key_events (separate section)
            const keyEvents = agent2.key_events || [];
            document.getElementById('cr-key-events').innerHTML = keyEvents.length > 0
                ? keyEvents.map(e => `<li>${typeof e === 'string' ? e : (e.title || e.headline || extractText(e))}</li>`).join('') 
                : '<li style="color: var(--text-muted);">No major events in recent period</li>';

            const newsArticles = result.news_articles || agent2.news_articles || [];
            document.getElementById('cr-news').innerHTML = newsArticles.length > 0 ? newsArticles.map(item => `
                <div class="news-item">
                    <div class="news-top"><span class="news-src">${item.source || 'News'} · ${item.date || ''}</span></div>
                    <h4><a href="${item.url || '#'}" target="_blank" rel="noopener">${item.headline || item.title || 'Article'}</a></h4>
                    ${item.summary ? `<p class="news-desc">${item.summary}</p>` : ''}
                </div>`).join('') : '<p class="no-data-msg" style="color: var(--text-muted);">No recent news articles available</p>';

            // ── Company Outlook (Enhanced Market Mood) ────────────────────────
            const mood = agent2.market_mood || {};
            
            // Overall Sentiment
            const sentiment = mood.overall_sentiment || 'Neutral';
            const sentimentEl = document.getElementById('cr-mood-sentiment');
            if (sentimentEl) {
                sentimentEl.textContent = sentiment;
                sentimentEl.className = 'sentiment-badge ' + sentiment.toLowerCase();
            }
            
            // Positive Factors
            document.getElementById('cr-mood-positive').innerHTML = (mood.positive_factors || []).length > 0
                ? (mood.positive_factors || []).map(e => `<li>${extractText(e)}</li>`).join('')
                : '<li style="color: var(--text-muted);">No significant positive factors identified</li>';
            
            // Areas to Watch
            document.getElementById('cr-mood-uncertainty').innerHTML = (mood.areas_to_watch || []).length > 0
                ? (mood.areas_to_watch || []).map(e => `<li>${extractText(e)}</li>`).join('')
                : '<li style="color: var(--text-muted);">No major concerns identified</li>';
            
            // Market Focus
            document.getElementById('cr-mood-watching').innerHTML = (mood.market_focus || []).length > 0
                ? (mood.market_focus || []).map(e => `<li>${extractText(e)}</li>`).join('')
                : '<li style="color: var(--text-muted);">Standard market dynamics</li>';

            // ── Price Chart ────────────────────────────────────────────────
            _companyPriceHistory = result.price_history || [];
            _companyChartTf = '1y';
            document.querySelectorAll('#cr-timeframe-selector .tf-btn').forEach(b => b.classList.toggle('active', b.dataset.tf === '1y'));
            renderCompanyPriceChart(_filterCompanyHistory(_companyPriceHistory, '1y'), ticker);

            // ── Broader Drivers (with explanations) ────────────────────────
            const drivers = agent2.broader_drivers || {};
            
            // NIFTY 50
            const nifty = drivers.nifty_trend || {};
            document.getElementById('cr-drv-nifty').textContent = nifty.value || '--';
            document.getElementById('cr-drv-nifty').className = 'value ' + getColorClass(parseFloat(nifty.value));
            document.getElementById('cr-drv-nifty-exp').textContent = nifty.explanation || '';
            
            // Sector Performance
            const sector = drivers.sector_performance || {};
            document.getElementById('cr-drv-sector').textContent = sector.value || '--';
            document.getElementById('cr-drv-sector').className = 'value ' + getColorClass(parseFloat(sector.value));
            document.getElementById('cr-drv-sector-exp').textContent = sector.explanation || '';
            
            // Company vs NIFTY
            const companyVsNifty = drivers.company_vs_nifty || {};
            document.getElementById('cr-drv-company').textContent = companyVsNifty.value || '--';
            document.getElementById('cr-drv-company').className = 'value ' + getColorClass(parseFloat(companyVsNifty.value));
            document.getElementById('cr-drv-company-exp').textContent = companyVsNifty.explanation || '';
            
            // Market Correlation
            const correlation = drivers.market_correlation || {};
            document.getElementById('cr-drv-corr').textContent = correlation.value || '--';
            document.getElementById('cr-drv-corr-exp').textContent = correlation.explanation || '';

            // ── AI Price Forecast (Simplified Clean Output) ────────────────────────
            const forecast = result.price_forecast || {};
            const currentPriceVal = forecast.current_price || result.price;
            const predictedPriceVal = forecast.predicted_price;
            const expectedReturnVal = forecast.expected_return;
            
            document.getElementById('ml-current').textContent = formatPrice(currentPriceVal);
            
            if (predictedPriceVal != null && !isNaN(predictedPriceVal)) {
                document.getElementById('ml-predicted').textContent = formatPrice(predictedPriceVal);
            } else {
                document.getElementById('ml-predicted').textContent = 'Model unavailable';
            }
            
            const retEl = document.getElementById('ml-return');
            if (expectedReturnVal != null && !isNaN(expectedReturnVal)) {
                const sign = expectedReturnVal >= 0 ? '+' : '';
                retEl.textContent = `${sign}${parseFloat(expectedReturnVal).toFixed(2)}%`;
                retEl.className = 'value ' + (expectedReturnVal >= 0 ? 'text-green' : 'text-red');
            } else {
                retEl.textContent = 'Pending';
                retEl.className = 'value';
            }

            // ── Investment Risk Analysis (Enhanced) ────────────────────────
            const riskAnalysis = result.risk_analysis || {};
            
            // Overall Risk Level
            const riskLevel = riskAnalysis.overall_risk || result.risk_level || 'Low';
            const riskBadge = document.getElementById('cr-risk-level');
            if (riskBadge) {
                riskBadge.textContent = riskLevel;
                riskBadge.className = 'risk-badge ' + riskLevel.toLowerCase();
            }
            
            // Financial Observations (Risk Factors)
            const financial = riskAnalysis.financial_observations || result.risk_factors || [];
            document.getElementById('cr-rf-financial').innerHTML = financial.length > 0
                ? financial.map(e => `<li>${extractText(e)}</li>`).join('')
                : '<li style="color: var(--text-muted);">No significant financial risks identified</li>';
            
            // Isolation Forest Status & Explanation
            const isolationForest = riskAnalysis.isolation_forest || {};
            document.getElementById('cr-if-status').textContent = isolationForest.status || '--';
            document.getElementById('cr-if-explanation').textContent = isolationForest.explanation || result.risk_detail || '';
            
            // Statistical Findings (fallback to risk_detail if available)
            const statistical = riskAnalysis.statistical_findings || (result.risk_detail ? [result.risk_detail] : []);
            document.getElementById('cr-rf-statistical').innerHTML = statistical.length > 0
                ? statistical.map(e => `<li>${extractText(e)}</li>`).join('')
                : '<li style="color: var(--text-muted);">No statistical anomalies detected</li>';
            
            // Peer Comparison
            const peerComp = riskAnalysis.peer_comparison || [];
            document.getElementById('cr-rf-peers').innerHTML = peerComp.length > 0
                ? peerComp.map(e => `<li>${extractText(e)}</li>`).join('')
                : '<li style="color: var(--text-muted);">Peer comparison data unavailable</li>';

            // ── AI Research Assistant (Chat Interface) ─────────────────────────────
            const chatBtn = document.getElementById('ai-chat-btn');
            const chatInput = document.getElementById('ai-chat-input');
            const chatHistory = document.getElementById('ai-chat-history');
            
            // Clear previous chat history except for the system message
            if (chatHistory) {
                chatHistory.innerHTML = `
                    <div class="chat-msg system-msg" style="color: var(--text-muted); font-style: italic; margin-bottom: 1rem;">
                        AI Assistant ready. Ask me any general questions about ${result.company_name || name}!
                    </div>
                `;
            }
            
            // Set up chat interaction
            if (chatBtn && chatInput) {
                // Remove previous listeners by cloning
                const newChatBtn = chatBtn.cloneNode(true);
                chatBtn.parentNode.replaceChild(newChatBtn, chatBtn);
                const newChatInput = chatInput.cloneNode(true);
                chatInput.parentNode.replaceChild(newChatInput, chatInput);
                
                const handleChat = async () => {
                    const q = newChatInput.value.trim();
                    if (!q) return;
                    
                    // Add user message
                    chatHistory.innerHTML += `
                        <div class="chat-msg user-msg" style="background: rgba(255,255,255,0.1); padding: 0.75rem; border-radius: 8px; margin-bottom: 1rem; margin-left: 2rem;">
                            <strong>You:</strong> ${q}
                        </div>
                    `;
                    newChatInput.value = '';
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                    
                    // Add loading message
                    const loadingId = 'loading-' + Date.now();
                    chatHistory.innerHTML += `
                        <div id="${loadingId}" class="chat-msg system-msg" style="color: var(--text-muted); font-style: italic; margin-bottom: 1rem;">
                            Thinking...
                        </div>
                    `;
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                    
                    try {
                        const res = await fetch(`${API_BASE}/company-research`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name, ticker, chat_query: q })
                        });
                        const data = await res.json();
                        
                        document.getElementById(loadingId).remove();
                        
                        // Add AI response
                        const answer = data.agent4?.response || 'Sorry, I could not generate an answer at this time.';
                        chatHistory.innerHTML += `
                            <div class="chat-msg ai-msg" style="background: rgba(16, 185, 129, 0.1); padding: 0.75rem; border-radius: 8px; margin-bottom: 1rem; margin-right: 2rem; border-left: 3px solid #10b981;">
                                <strong>AI:</strong> ${answer}
                            </div>
                        `;
                    } catch (err) {
                        document.getElementById(loadingId).remove();
                        chatHistory.innerHTML += `
                            <div class="chat-msg error-msg" style="color: #ef4444; margin-bottom: 1rem;">
                                Error connecting to AI assistant.
                            </div>
                        `;
                    }
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                };
                
                newChatBtn.addEventListener('click', handleChat);
                newChatInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') handleChat();
                });
            }

        } else {
            document.getElementById('cr-summary').textContent = 'Error: ' + (result.detail || result.error || 'Unknown error');
        }
    } catch (err) {
        console.error('Research error:', err);
        document.getElementById('cr-summary').textContent = 'Failed to connect to the backend server.';
    }
}

// ─── Company Price Chart ──────────────────────────────────────────────────────
function renderCompanyPriceChart(historyData, ticker) {
    const el = document.getElementById('cr-price-chart');
    if (!el) {
        console.error('Chart element not found');
        return;
    }

    console.log('Rendering chart with', historyData ? historyData.length : 0, 'data points');

    if (!historyData || historyData.length === 0) {
        el.innerHTML = '<p class="chart-placeholder">No price history available for this company</p>';
        return;
    }

    // Filter out any invalid data points
    const validData = historyData.filter(d => d.date && d.close !== null && d.close !== undefined && !isNaN(d.close));
    
    if (validData.length === 0) {
        el.innerHTML = '<p class="chart-placeholder">Invalid price data</p>';
        return;
    }

    console.log('Valid data points:', validData.length);

    const dates = validData.map(d => d.date);
    const closes = validData.map(d => parseFloat(d.close));

    const first = closes[0], last = closes[closes.length - 1];
    const up = last >= first;
    const lineColor = up ? '#10b981' : '#ef4444';
    const areaColor = up ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)';

    // Baseline anchored 2% below visible minimum
    const yFloor = Math.min(...closes) * 0.98;
    const baseline = closes.map(() => yFloor);

    const baseTrace = {
        x: dates, y: baseline,
        type: 'scatter', mode: 'lines',
        line: { color: 'transparent', width: 0 },
        hoverinfo: 'none', showlegend: false
    };

    const priceTrace = {
        x: dates, y: closes,
        type: 'scatter', mode: 'lines+markers',
        fill: 'tonexty', fillcolor: areaColor,
        line: { color: lineColor, width: 2 },
        marker: {
            size: 0,  // Invisible by default
            symbol: 'diamond',
            color: lineColor,
            opacity: 0
        },
        hovertemplate: '<b>%{x}</b> | <b>₹%{y:,.2f}</b><extra></extra>',
        showlegend: false
    };

    const layout = {
        margin: { t: 10, r: 10, b: 40, l: 70 },
        autosize: true,
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        xaxis: {
            showgrid: false, 
            color: '#94a3b8',
            tickfont: { size: 10, color: '#94a3b8' },
            linecolor: 'rgba(148,163,184,0.15)'
        },
        yaxis: {
            autorange: true,
            showgrid: true,
            gridcolor: 'rgba(255,255,255,0.06)',
            color: '#94a3b8',
            tickfont: { size: 10, color: '#94a3b8' },
            tickformat: ',.0f'
        },
        hovermode: 'x unified',
        hoverlabel: { 
            bgcolor: 'rgba(30, 41, 59, 0.95)', 
            bordercolor: 'rgba(255, 255, 255, 0.2)',
            font: { color: '#ffffff', size: 13, family: 'Inter' },
            align: 'left'
        },
        showlegend: false
    };

    try {
        Plotly.purge('cr-price-chart');
        Plotly.newPlot('cr-price-chart', [baseTrace, priceTrace], layout, 
            { responsive: true, displayModeBar: false });
        
        // Add hover event to show diamond marker on hover
        el.on('plotly_hover', (data) => {
            const markerSize = new Array(closes.length).fill(0);
            if (data.points && data.points[0]) {
                const pointIndex = data.points[0].pointNumber;
                markerSize[pointIndex] = 10; // Show diamond at hover point
            }
            Plotly.restyle('cr-price-chart', { 'marker.size': [null, markerSize] });
        });
        
        // Hide diamond marker when not hovering
        el.on('plotly_unhover', () => {
            Plotly.restyle('cr-price-chart', { 'marker.size': [null, new Array(closes.length).fill(0)] });
        });
        
        console.log('Chart rendered successfully');
    } catch (error) {
        console.error('Error rendering chart:', error);
        el.innerHTML = '<p class="chart-placeholder">Error rendering chart</p>';
    }
}

// Company chart timeframe buttons — re-render from stored data on click
document.querySelectorAll('#cr-timeframe-selector .tf-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('#cr-timeframe-selector .tf-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _companyChartTf = btn.dataset.tf;
        renderCompanyPriceChart(_filterCompanyHistory(_companyPriceHistory, _companyChartTf), _companyTicker);
    });
});

// ─── Generate Report ──────────────────────────────────────────────────────────
const btnGenerate = document.getElementById('btn-generate-report');
if (btnGenerate) {
    btnGenerate.addEventListener('click', async () => {
        const companyName = document.getElementById('cr-header-name').textContent || 'the selected company';
        const ticker = _companyTicker;
        
        if (!ticker) {
            alert('Please select a company first');
            return;
        }
        
        // Show loading state
        btnGenerate.disabled = true;
        btnGenerate.textContent = 'Generating Report...';
        
        try {
            const res = await fetch(`${API_BASE}/generate-report`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: companyName, ticker: ticker })
            });
            
            const reportData = await res.json();
            
            if (reportData.success) {
                // Switch to reports view
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                document.querySelector('.nav-item[data-target="reports-view"]').classList.add('active');
                document.querySelectorAll('.view-section').forEach(v => {
                    v.classList.remove('active');
                    v.classList.remove('hidden');
                });
                document.getElementById('reports-view').classList.add('active');
                
                // Render report using the structured data (not PDF, but HTML)
                renderReport(reportData);
            } else {
                alert('Failed to generate report: ' + (reportData.detail || 'Unknown error'));
            }
        } catch (err) {
            console.error('Report generation error:', err);
            alert('Error generating report. Check console for details.');
        } finally {
            btnGenerate.disabled = false;
            btnGenerate.textContent = 'Generate PDF Report';
        }
    });
}

// ─── Report Renderer ──────────────────────────────────────────────────────────
function renderReport(data) {
    const reportsView = document.getElementById('reports-view');
    
    const html = `
        <div style="max-width: 900px; margin: 0 auto; padding: 20px;">
            <!-- Cover Page -->
            <div class="report-section" style="page-break-after: always; text-align: center; padding: 60px 20px; background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%); border-radius: 16px; margin-bottom: 40px;">
                <h1 style="font-size: 2.5rem; margin-bottom: 20px; letter-spacing: 2px;">${data.cover.title}</h1>
                <p style="font-size: 1.1rem; color: var(--text-muted); margin-bottom: 40px;">${data.cover.subtitle}</p>
                <h2 style="font-size: 2rem; margin-bottom: 10px;">${data.cover.company}</h2>
                <p style="font-size: 1.3rem; color: var(--primary); margin-bottom: 30px;"><strong>${data.cover.ticker}</strong></p>
                <p style="font-size: 0.9rem; color: var(--text-muted);">Generated On: ${data.generated_date}</p>
            </div>
            
            <!-- Executive Summary -->
            <div class="report-section card glass-panel" style="margin-bottom: 30px;">
                <h2 style="font-size: 2rem; margin-bottom: 20px; border-bottom: 2px solid var(--primary); padding-bottom: 10px;">Executive Summary</h2>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    <div>
                        <p><strong>Company:</strong> ${data.executive_summary.company}</p>
                        <p><strong>Sector:</strong> ${data.executive_summary.sector || 'N/A'}</p>
                    </div>
                    <div>
                        <p><strong>Current Price:</strong> ₹${parseFloat(data.executive_summary.current_price).toFixed(2)}</p>
                        <p><strong>Today's Change:</strong> <span style="color: ${parseFloat(data.executive_summary.change) >= 0 ? '#10b981' : '#ef4444'}">${parseFloat(data.executive_summary.change).toFixed(2)}%</span></p>
                    </div>
                </div>
                <div style="background: rgba(16, 185, 129, 0.1); padding: 15px; border-radius: 8px; border-left: 3px solid #10b981; margin-bottom: 15px;">
                    <p><strong>Overall Assessment:</strong> <span style="font-size: 1.1rem; color: #10b981;">${data.executive_summary.assessment}</span></p>
                </div>
                <div>
                    <h4>Key Highlights:</h4>
                    <ul style="list-style: none; padding-left: 0;">
                        ${(data.executive_summary.highlights || []).slice(0, 5).map(h => `<li style="padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">✓ ${h}</li>`).join('')}
                    </ul>
                </div>
            </div>
            
            <!-- Company Overview -->
            <div class="report-section card glass-panel" style="margin-bottom: 30px;">
                <h2 style="font-size: 2rem; margin-bottom: 20px; border-bottom: 2px solid var(--primary); padding-bottom: 10px;">Company Overview</h2>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 20px;">
                    <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px;">
                        <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 5px;">Market Cap</p>
                        <p style="font-size: 1.3rem; font-weight: 600;">₹${data.company_overview.market_cap ? (parseFloat(data.company_overview.market_cap) / 1e7).toFixed(0) : 'N/A'} Cr</p>
                    </div>
                    <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px;">
                        <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 5px;">P/E Ratio</p>
                        <p style="font-size: 1.3rem; font-weight: 600;">${data.company_overview.pe_ratio ? parseFloat(data.company_overview.pe_ratio).toFixed(2) : 'N/A'}</p>
                    </div>
                    <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px;">
                        <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 5px;">Dividend Yield</p>
                        <p style="font-size: 1.3rem; font-weight: 600;">${data.company_overview.dividend_yield ? parseFloat(data.company_overview.dividend_yield).toFixed(2) + '%' : 'N/A'}</p>
                    </div>
                </div>
                <div>
                    <h4>Business Summary:</h4>
                    <p style="color: #cbd5e1; line-height: 1.7;">${data.company_overview.summary || 'No summary available.'}</p>
                </div>
            </div>
            
            <!-- Investment Risk Analysis -->
            <div class="report-section card glass-panel" style="margin-bottom: 30px;">
                <h2 style="font-size: 2rem; margin-bottom: 20px; border-bottom: 2px solid var(--primary); padding-bottom: 10px;">Investment Risk Analysis</h2>
                <div style="background: ${data.risk_analysis.overall_risk === 'High' ? 'rgba(239, 68, 68, 0.1)' : data.risk_analysis.overall_risk === 'Moderate' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(16, 185, 129, 0.1)'}; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                    <p style="color: var(--text-muted); margin-bottom: 10px;">Overall Risk Level:</p>
                    <p style="font-size: 1.8rem; font-weight: 700; color: ${data.risk_analysis.overall_risk === 'High' ? '#ef4444' : data.risk_analysis.overall_risk === 'Moderate' ? '#f59e0b' : '#10b981'};">${data.risk_analysis.overall_risk}</p>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div>
                        <h4>Financial Observations:</h4>
                        <ul style="list-style: none; padding-left: 0;">
                            ${(data.risk_analysis.financial_observations || []).slice(0, 4).map(obs => `<li style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">• ${typeof obs === 'string' ? obs : (obs.metric || obs)}</li>`).join('')}
                        </ul>
                    </div>
                    <div>
                        <h4>Statistical Analysis:</h4>
                        <p style="color: #cbd5e1; margin-bottom: 10px;"><strong>Status:</strong> ${data.risk_analysis.isolation_forest?.status || 'N/A'}</p>
                        <p style="color: #94a3b8; font-size: 0.9rem; line-height: 1.6;">${data.risk_analysis.isolation_forest?.explanation || 'No analysis available.'}</p>
                    </div>
                </div>
                ${data.risk_analysis.peer_comparison && data.risk_analysis.peer_comparison.length > 0 ? `
                    <div style="margin-top: 20px;">
                        <h4>Peer Comparison:</h4>
                        <ul style="list-style: none; padding-left: 0;">
                            ${data.risk_analysis.peer_comparison.slice(0, 3).map(p => `<li style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">• ${typeof p === 'string' ? p : p}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
            
            <!-- AI Price Forecast -->
            <div class="report-section card glass-panel" style="margin-bottom: 30px;">
                <h2 style="font-size: 2rem; margin-bottom: 20px; border-bottom: 2px solid var(--primary); padding-bottom: 10px;">AI Price Forecast</h2>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px;">
                    <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px; text-align: center;">
                        <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 8px;">Current Price</p>
                        <p style="font-size: 1.5rem; font-weight: 700;">₹${parseFloat(data.price_forecast.current_price).toFixed(2)}</p>
                    </div>
                    <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px; text-align: center;">
                        <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 8px;">Predicted Price</p>
                        <p style="font-size: 1.5rem; font-weight: 700;">₹${data.price_forecast.predicted_price ? parseFloat(data.price_forecast.predicted_price).toFixed(2) : 'N/A'}</p>
                    </div>
                    <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px; text-align: center;">
                        <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 8px;">Expected Return</p>
                        <p style="font-size: 1.5rem; font-weight: 700; color: ${data.price_forecast.expected_return >= 0 ? '#10b981' : '#ef4444'};">${data.price_forecast.expected_return ? (data.price_forecast.expected_return > 0 ? '+' : '') + parseFloat(data.price_forecast.expected_return).toFixed(2) + '%' : 'N/A'}</p>
                    </div>
                    <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px; text-align: center;">
                        <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 8px;">Direction</p>
                        <p style="font-size: 1.5rem; font-weight: 700; color: ${data.price_forecast.direction === 'UP' ? '#10b981' : '#ef4444'};">${data.price_forecast.direction === 'UP' ? '▲ UP' : data.price_forecast.direction === 'DOWN' ? '▼ DOWN' : '→ HOLD'}</p>
                    </div>
                </div>
                <div style="margin-top: 15px; padding: 15px; background: rgba(255,255,255,0.05); border-radius: 8px;">
                    <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 5px;">Model Used:</p>
                    <p style="color: #cbd5e1;">${data.price_forecast.model}</p>
                </div>
            </div>
            
            <!-- Final AI Assessment -->
            <div class="report-section card glass-panel" style="margin-bottom: 30px;">
                <h2 style="font-size: 2rem; margin-bottom: 20px; border-bottom: 2px solid var(--primary); padding-bottom: 10px;">Final AI Assessment</h2>
                <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(59, 130, 246, 0.1) 100%); padding: 25px; border-radius: 12px; border: 1px solid rgba(16, 185, 129, 0.3); margin-bottom: 20px; text-align: center;">
                    <p style="color: var(--text-muted); font-size: 0.95rem; margin-bottom: 10px;">Overall Assessment:</p>
                    <p style="font-size: 2rem; font-weight: 700; color: #10b981;">${data.final_assessment.overall}</p>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div>
                        <h4 style="color: #10b981; margin-bottom: 12px;">✓ Strengths</h4>
                        <ul style="list-style: none; padding-left: 0;">
                            ${(data.final_assessment.strengths || []).slice(0, 4).map(s => `<li style="padding: 8px 0; border-bottom: 1px solid rgba(16, 185, 129, 0.2); color: #cbd5e1;">• ${s}</li>`).join('')}
                        </ul>
                    </div>
                    <div>
                        <h4 style="color: #f59e0b; margin-bottom: 12px;">⚠ Areas to Watch</h4>
                        <ul style="list-style: none; padding-left: 0;">
                            ${(data.final_assessment.areas_to_watch || []).slice(0, 4).map(a => `<li style="padding: 8px 0; border-bottom: 1px solid rgba(245, 158, 11, 0.2); color: #cbd5e1;">• ${a}</li>`).join('')}
                        </ul>
                    </div>
                </div>
                
                <div style="margin-top: 20px; padding: 20px; background: rgba(0,0,0,0.3); border-radius: 8px;">
                    <h4 style="margin-bottom: 12px;">Conclusion:</h4>
                    <p style="color: #cbd5e1; line-height: 1.8;">${data.final_assessment.conclusion || 'Based on the comprehensive analysis above, this company presents a balanced investment opportunity with identified strengths in operational performance and market position.'}</p>
                </div>
            </div>
            
            <div style="text-align: center; padding: 20px; color: var(--text-muted); font-size: 0.85rem;">
                <p>This report was generated by the AI Investment Analysis System on ${data.generated_date}</p>
                <p>For the most up-to-date analysis, please refresh this report regularly.</p>
            </div>
        </div>
    `;
    
    reportsView.innerHTML = html;
}

// ─── Init ──────────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => { loadDashboard(); });
