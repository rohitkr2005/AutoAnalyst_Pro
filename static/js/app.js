/**
 * AutoAnalyst Pro - Client Application Controller
 * Handles 5-stage automated data science pipeline, Chart.js visualizations,
 * user authentication, AI Copilot chat, customizable chart studio,
 * and live dashboard slicing.
 */

// Global State
const appState = {
  activeTab: 'tab-ingest',
  datasetName: 'No dataset loaded',
  currentUser: null,
  rawAudit: null,
  cleanedAudit: null,
  auditReport: null,
  edaData: null,
  mlData: null,
  columns: [],
  cleanedColumns: [],
  inspectorPage: 1,
  inspectorPageSize: 12,
  inspectorSearch: '',
  inspectorViewMode: 'cleaned',
  inspectorSortBy: null,
  inspectorSortAsc: true,
  primaryMetric: null,
  categoryDimension: null,
  scatterX: null,
  scatterY: null
};

// Global Chart References
const chartInstances = {
  distribution: null,
  pcaClusters: null,
  featureImportance: null,
  dashTrend: null,
  dashBreakdown: null,
  pairwiseScatter: null,
  anomalyRadar: null,
  dashStudio: null,
  forecast: null,
  forecastDrivers: null
};

// Color palettes for Chart.js
const CHART_COLORS = {
  indigo: '#6366f1',
  indigoLight: 'rgba(99, 102, 241, 0.25)',
  cyan: '#06b6d4',
  cyanLight: 'rgba(6, 182, 212, 0.25)',
  emerald: '#10b981',
  emeraldLight: 'rgba(16, 185, 129, 0.25)',
  amber: '#f59e0b',
  amberLight: 'rgba(245, 158, 11, 0.25)',
  rose: '#f43f5e',
  roseLight: 'rgba(244, 63, 94, 0.25)',
  purple: '#8b5cf6',
  palette: ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#3b82f6', '#14b8a6']
};

const THEME_PALETTES = {
  neon: ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#3b82f6', '#14b8a6'],
  emerald: ['#10b981', '#059669', '#34d399', '#047857', '#6ee7b7', '#14b8a6', '#0f766e', '#115e59'],
  sunset: ['#f59e0b', '#f97316', '#ef4444', '#ec4899', '#fbbf24', '#f43f5e', '#ea580c', '#e11d48'],
  violet: ['#8b5cf6', '#a855f7', '#6366f1', '#c084fc', '#d946ef', '#4f46e5', '#7c3aed', '#9333ea']
};

// Theme-Aware Chart Colors
function getThemeChartColors() {
  const isDark = window.ThemeManager ? window.ThemeManager.isDark() : true;
  return {
    textColor: isDark ? '#94a3b8' : '#475569',
    gridColor: isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(15, 23, 42, 0.08)',
    radarGrid: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(15, 23, 42, 0.1)'
  };
}

function refreshAllChartsTheme() {
  const { textColor, gridColor, radarGrid } = getThemeChartColors();
  Object.values(chartInstances).forEach((chart) => {
    if (!chart || !chart.options) return;
    if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
      chart.options.plugins.legend.labels.color = textColor;
    }
    if (chart.options.scales) {
      if (chart.options.scales.x) {
        if (chart.options.scales.x.ticks) chart.options.scales.x.ticks.color = textColor;
        if (chart.options.scales.x.grid) chart.options.scales.x.grid.color = gridColor;
      }
      if (chart.options.scales.y) {
        if (chart.options.scales.y.ticks) chart.options.scales.y.ticks.color = textColor;
        if (chart.options.scales.y.grid) chart.options.scales.y.grid.color = gridColor;
      }
      if (chart.options.scales.r) {
        if (chart.options.scales.r.ticks) {
          chart.options.scales.r.ticks.color = textColor;
          chart.options.scales.r.ticks.backdropColor = 'transparent';
        }
        if (chart.options.scales.r.grid) chart.options.scales.r.grid.color = radarGrid;
        if (chart.options.scales.r.angleLines) chart.options.scales.r.angleLines.color = radarGrid;
        if (chart.options.scales.r.pointLabels) chart.options.scales.r.pointLabels.color = textColor;
      }
    }
    chart.update();
  });
}

window.addEventListener('analytica-theme-changed', () => {
  refreshAllChartsTheme();
});

// Initialization on DOM Loaded
document.addEventListener('DOMContentLoaded', () => {
  checkAuthSession();
  setupNavigation();
  setupDropzone();
  setupExportButtons();
  initSidebarResizer();
});

// Authentication Session Verification
async function checkAuthSession() {
  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (data.status === 'success' && data.authenticated) {
      appState.currentUser = data.user;
      const displayName = data.user.full_name || data.user.username;

      // Update sidebar user footer (replaces Engine Online)
      const sidebarNameEl = document.getElementById('sidebar-user-name');
      const sidebarAvatarEl = document.getElementById('sidebar-user-avatar');
      if (sidebarNameEl) sidebarNameEl.textContent = displayName;
      if (sidebarAvatarEl) {
        const initials = displayName
          .split(' ')
          .map(n => n[0])
          .join('')
          .substring(0, 2)
          .toUpperCase();
        sidebarAvatarEl.textContent = initials || 'DA';
      }

      // Also update topbar profile elements if present
      const nameEl = document.getElementById('user-display-name');
      const roleEl = document.getElementById('user-display-role');
      const initEl = document.getElementById('user-avatar-initials');
      if (nameEl) nameEl.textContent = displayName;
      if (roleEl) roleEl.textContent = data.user.role || 'Data Analyst';
      if (initEl) {
        const initials = displayName
          .split(' ')
          .map(n => n[0])
          .join('')
          .substring(0, 2)
          .toUpperCase();
        initEl.textContent = initials || 'DA';
      }
    } else {
      window.location.href = '/login';
    }
  } catch (err) {
    console.warn('Session check warning:', err);
  }
}

async function handleLogout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
  } catch (err) {
    window.location.href = '/login';
  }
}

// UI Loading Indicator
function showLoading(message = 'Processing Dataset...') {
  const overlay = document.getElementById('loading-overlay');
  const msgEl = document.getElementById('loading-message');
  if (msgEl) msgEl.textContent = message;
  if (overlay) overlay.classList.add('active');
}

function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.classList.remove('active');
}

// Enterprise View & Sub-Tab Navigation System
function setupNavigation() {
  // Sidebar navigation items
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const viewId = item.getAttribute('data-view');
      if (viewId) switchView(viewId);
    });
  });

  // Global click listener to close dropdowns when clicking outside
  document.addEventListener('click', (e) => {
    const exportDropdown = document.getElementById('export-dropdown-wrap');
    if (exportDropdown && !exportDropdown.contains(e.target)) {
      document.getElementById('export-dropdown-menu')?.classList.remove('active');
    }
  });

  // Global keyboard shortcut (⌘K or Ctrl+K for search)
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      document.getElementById('topbar-search-input')?.focus();
    }
  });
}

// Map legacy tab IDs to new enterprise views
const TAB_TO_VIEW_MAP = {
  'tab-ingest': 'view-connect',
  'tab-clean': 'view-prep',
  'tab-eda': 'view-reports',
  'tab-ml': 'view-ml',
  'tab-dashboard': 'view-dashboards',
  'view-dashboards': 'view-dashboards',
  'view-connect': 'view-connect',
  'view-prep': 'view-prep',
  'view-reports': 'view-reports',
  'view-ml': 'view-ml',
  'view-table': 'view-table',
  'view-ai': 'view-ai'
};

function switchView(viewId) {
  const targetView = TAB_TO_VIEW_MAP[viewId] || viewId;
  appState.activeView = targetView;
  appState.activeTab = targetView;

  // Update sidebar active states
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.getAttribute('data-view') === targetView);
  });

  // Update workspace views
  document.querySelectorAll('.workspace-view').forEach(view => {
    view.classList.toggle('active', view.id === targetView);
  });

  // Close mobile sidebar if open
  const sidebar = document.getElementById('app-sidebar');
  if (sidebar) sidebar.classList.remove('mobile-open');

  // Lazy loading & view specific actions
  if (targetView === 'view-reports') {
    if (!appState.edaData) {
      fetchEDA();
    } else {
      resizeAllCharts();
    }
  } else if (targetView === 'view-ml') {
    if (!appState.mlData) {
      fetchML();
    } else {
      resizeAllCharts();
    }
  } else if (targetView === 'view-dashboards') {
    if (appState.edaData) {
      renderDashboard();
      resizeAllCharts();
    }
    fetchInspectorRows();
  } else if (targetView === 'view-table') {
    fetchInspectorRows();
  }
}

// Backward compatibility alias for switchTab
function switchTab(tabId) {
  switchView(tabId);
}

// Sub-Tab Switcher (Tabbed workspace views)
function switchSubTab(viewId, subtabId) {
  const viewEl = document.getElementById(viewId);
  if (!viewEl) return;

  // Update subtab buttons
  viewEl.querySelectorAll('.subtab-item').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-subtab') === subtabId);
  });

  // Update subtab panes
  viewEl.querySelectorAll('.subtab-pane').forEach(pane => {
    pane.classList.toggle('active', pane.id === `pane-${subtabId}`);
  });

  // Subtab-specific actions
  if (subtabId === 'dash-studio') {
    renderStudioChart();
  } else if (subtabId === 'dash-anomalies') {
    if (appState.mlData) renderAnomalyRadar();
  } else if (subtabId === 'dash-forecast') {
    renderForecastSubTab();
  } else if (subtabId === 'reports-corr') {
    if (appState.scatterX && appState.scatterY) renderPairwiseScatter();
  } else if (subtabId === 'reports-hist') {
    renderSelectedDistribution();
  }
}

function proceedToCleaning() {
  switchView('view-prep');
  switchSubTab('view-prep', 'prep-audit');
}

function proceedToEDA() {
  switchView('view-reports');
  switchSubTab('view-reports', 'reports-corr');
}

function toggleSidebar() {
  const sidebar = document.getElementById('app-sidebar');
  if (!sidebar) return;
  if (window.innerWidth <= 900) {
    sidebar.classList.toggle('mobile-open');
  } else {
    sidebar.classList.toggle('collapsed');
    const collapseBtn = document.getElementById('btn-sidebar-collapse');
    if (collapseBtn) {
      collapseBtn.textContent = sidebar.classList.contains('collapsed') ? '▶' : '◀';
    }
  }
}

function handleSidebarLogoClick() {
  const sidebar = document.getElementById('app-sidebar');
  if (!sidebar) return;
  if (sidebar.classList.contains('collapsed')) {
    sidebar.classList.remove('collapsed');
    const collapseBtn = document.getElementById('btn-sidebar-collapse');
    if (collapseBtn) collapseBtn.textContent = '◀';
  } else if (window.innerWidth <= 900 && !sidebar.classList.contains('mobile-open')) {
    sidebar.classList.add('mobile-open');
  }
}

function initSidebarResizer() {
  const sidebar = document.getElementById('app-sidebar');
  const resizer = document.getElementById('sidebar-resizer');
  if (!sidebar || !resizer) return;

  // Restore saved width from localStorage
  const savedWidth = localStorage.getItem('analytica_sidebar_width');
  if (savedWidth && parseInt(savedWidth, 10) >= 200 && parseInt(savedWidth, 10) <= 480) {
    if (!sidebar.classList.contains('collapsed')) {
      sidebar.style.width = `${savedWidth}px`;
    }
  }

  let isResizing = false;
  let startX = 0;
  let startWidth = 260;

  resizer.addEventListener('mousedown', (e) => {
    if (sidebar.classList.contains('collapsed')) return;
    isResizing = true;
    startX = e.clientX;
    startWidth = sidebar.getBoundingClientRect().width;
    sidebar.classList.add('resizing');
    resizer.classList.add('active');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    const dx = e.clientX - startX;
    let newWidth = startWidth + dx;
    if (newWidth < 200) newWidth = 200;
    if (newWidth > 480) newWidth = 480;
    sidebar.style.width = `${newWidth}px`;
  });

  document.addEventListener('mouseup', () => {
    if (!isResizing) return;
    isResizing = false;
    sidebar.classList.remove('resizing');
    resizer.classList.remove('active');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    const currentWidth = Math.round(sidebar.getBoundingClientRect().width);
    if (currentWidth >= 200 && currentWidth <= 480) {
      localStorage.setItem('analytica_sidebar_width', currentWidth);
    }
  });
}

function toggleExportMenu(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('export-dropdown-menu');
  if (menu) menu.classList.toggle('active');
}

function downloadCleanCSV() {
  window.location.href = '/api/export-csv';
  document.getElementById('export-dropdown-menu')?.classList.remove('active');
}

function downloadPythonScript() {
  window.location.href = '/api/export-script';
  document.getElementById('export-dropdown-menu')?.classList.remove('active');
}

function copyPythonScript() {
  const codeEl = document.getElementById('python-script-preview');
  if (codeEl && codeEl.textContent) {
    navigator.clipboard.writeText(codeEl.textContent);
    alert('Python cleaning pipeline script copied to clipboard!');
  }
}

function openAskAI() {
  switchView('view-ai');
}

// Complete Autonomous End-to-End Pipeline (Ingest -> Clean -> EDA -> ML -> Dashboards)
async function runCompleteAutoPipeline() {
  // If no dataset loaded, load ecommerce by default
  if (!appState.datasetName || appState.datasetName === 'No dataset loaded') {
    showLoading('Auto-Pipeline: Initializing demo dataset (E-Commerce Omnichannel)...');
    try {
      const res = await fetch('/api/load-sample', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sample_id: 'ecommerce' })
      });
      const data = await res.json();
      if (data.status === 'success') {
        onDatasetLoaded(data);
      }
    } catch (err) {
      hideLoading();
      alert(`Auto-Pipeline initialization error: ${err.message}`);
      return;
    }
  }

  // Step 2: Clean
  showLoading('Auto-Pipeline: Step 1/3 - Running Data Preprocessing & Cleaning Studio...');
  try {
    const cleanRes = await fetch('/api/clean', { method: 'POST' });
    const cleanData = await cleanRes.json();
    if (cleanData.status === 'success') {
      renderCleanResults(cleanData.cleaning_report, cleanData.preview, cleanData.columns, cleanData.python_script);
    }
  } catch (err) {
    console.error(err);
  }

  // Step 3: EDA
  showLoading('Auto-Pipeline: Step 2/3 - Computing Statistical Exploratory Analysis & Correlations...');
  try {
    const edaRes = await fetch('/api/eda', { method: 'POST' });
    const edaData = await edaRes.json();
    if (edaData.status === 'success') {
      renderEDAResults(edaData);
    }
  } catch (err) {
    console.error(err);
  }

  // Step 4: ML
  showLoading('Auto-Pipeline: Step 3/3 - Executing AutoML (K-Means, PCA, Isolation Forest & Key Drivers)...');
  try {
    const mlRes = await fetch('/api/ml', { method: 'POST' });
    const mlData = await mlRes.json();
    if (mlData.status === 'success') {
      renderMLResults(mlData);
    }
  } catch (err) {
    console.error(err);
  } finally {
    hideLoading();
  }

  // Transition to Dashboards
  switchView('view-dashboards');
  switchSubTab('view-dashboards', 'dash-overview');
  renderDashboard();
  fetchInspectorRows();
}

// Global Quick Search
function handleGlobalSearch(query) {
  if (!query) return;
  const q = query.toLowerCase().trim();
  if (q.includes('driver') || q.includes('feature')) {
    switchView('view-ml');
  } else if (q.includes('anom') || q.includes('outlier')) {
    switchView('view-dashboards');
    switchSubTab('view-dashboards', 'dash-anomalies');
  } else if (q.includes('cluster') || q.includes('persona')) {
    switchView('view-ml');
  } else if (q.includes('clean') || q.includes('prep') || q.includes('script')) {
    switchView('view-prep');
  } else if (q.includes('table') || q.includes('raw') || q.includes('grid')) {
    switchView('view-table');
  } else if (q.includes('corr') || q.includes('scatter') || q.includes('hist')) {
    switchView('view-reports');
  } else {
    // Search in table
    const searchInput = document.getElementById('inspector-search');
    if (searchInput) {
      searchInput.value = query;
      handleTableSearch();
    }
  }
}

function resizeAllCharts() {
  setTimeout(() => {
    Object.values(chartInstances).forEach(chart => {
      if (chart && typeof chart.resize === 'function') {
        chart.resize();
      }
    });
  }, 100);
}

// Studio Chart Renderer
function renderStudioChart() {
  const ctx = document.getElementById('chart-dash-studio-canvas')?.getContext('2d');
  if (!ctx || !appState.edaData) return;

  if (chartInstances.dashStudio) {
    chartInstances.dashStudio.destroy();
  }

  const metric = document.getElementById('dash-metric-select')?.value || appState.primaryMetric;
  const category = document.getElementById('dash-category-select')?.value || appState.categoryDimension;
  const chartType = appState.studioChartType || 'doughnut';
  const colorTheme = document.getElementById('dash-color-theme-select')?.value || 'neon';

  const catStat = appState.edaData.categorical_stats[category];
  if (!catStat || !catStat.frequency_distribution) return;

  const labels = catStat.frequency_distribution.slice(0, 8).map(d => d.category);
  const values = catStat.frequency_distribution.slice(0, 8).map(d => d.count);
  const palette = THEME_PALETTES[colorTheme] || CHART_COLORS.palette;

  const config = {
    type: chartType,
    data: {
      labels: labels,
      datasets: [{
        label: `${category} Distribution`,
        data: values,
        backgroundColor: palette.slice(0, labels.length),
        borderColor: chartType === 'doughnut' ? '#090e1a' : palette[0],
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: chartType === 'doughnut' || chartType === 'polarArea' ? 'right' : 'top',
          labels: { color: '#94a3b8', boxWidth: 14 }
        }
      }
    }
  };

  if (chartType === 'bar') {
    config.options.scales = {
      x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
      y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
    };
  } else if (chartType === 'radar' || chartType === 'polarArea') {
    config.options.scales = {
      r: {
        grid: { color: 'rgba(255,255,255,0.08)' },
        angleLines: { color: 'rgba(255,255,255,0.08)' },
        ticks: { backdropColor: 'transparent', color: '#94a3b8' }
      }
    };
  }

  chartInstances.dashStudio = new Chart(ctx, config);
}

function setDashboardChartType(chartType) {
  appState.studioChartType = chartType;
  const select = document.getElementById('dash-chart-type-select');
  if (select) select.value = chartType;
  
  // Update studio pill buttons
  document.querySelectorAll('#pane-dash-studio .pill-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('onclick')?.includes(chartType));
  });

  renderStudioChart();
  updateDashboardVisuals();
}

function renderForecastSubTab() {
  const tsCtx = document.getElementById('chart-forecast-canvas')?.getContext('2d');
  const drvCtx = document.getElementById('chart-forecast-drivers')?.getContext('2d');

  if (tsCtx && appState.mlData?.time_series) {
    if (chartInstances.forecast) chartInstances.forecast.destroy();
    const ts = appState.mlData.time_series;
    const allLabels = [...ts.historical_dates, ...ts.forecast_dates];
    const histData = [...ts.historical_values, ...new Array(ts.forecast_dates.length).fill(null)];
    const foreData = [...new Array(ts.historical_dates.length).fill(null), ...ts.forecast_values];
    const upperData = [...new Array(ts.historical_dates.length).fill(null), ...(ts.confidence_upper || ts.forecast_values.map(v => v * 1.1))];
    const lowerData = [...new Array(ts.historical_dates.length).fill(null), ...(ts.confidence_lower || ts.forecast_values.map(v => v * 0.9))];

    chartInstances.forecast = new Chart(tsCtx, {
      type: 'line',
      data: {
        labels: allLabels,
        datasets: [
          {
            label: 'Historical Trajectory',
            data: histData,
            borderColor: CHART_COLORS.cyan,
            backgroundColor: CHART_COLORS.cyanLight,
            borderWidth: 2,
            pointRadius: 2
          },
          {
            label: '14-Day AI Forecast',
            data: foreData,
            borderColor: CHART_COLORS.emerald,
            borderWidth: 2.5,
            pointRadius: 3
          },
          {
            label: 'Upper 95% Bound',
            data: upperData,
            borderColor: 'rgba(16, 185, 129, 0.3)',
            borderDash: [4, 4],
            pointRadius: 0
          },
          {
            label: 'Lower 95% Bound',
            data: lowerData,
            borderColor: 'rgba(16, 185, 129, 0.3)',
            borderDash: [4, 4],
            pointRadius: 0
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#94a3b8' } } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8', maxTicksLimit: 10 } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
        }
      }
    });
  }

  if (drvCtx && appState.mlData?.key_drivers) {
    if (chartInstances.forecastDrivers) chartInstances.forecastDrivers.destroy();
    const kd = appState.mlData.key_drivers;
    const topFeats = kd.slice(0, 7);

    chartInstances.forecastDrivers = new Chart(drvCtx, {
      type: 'bar',
      data: {
        labels: topFeats.map(f => f.feature),
        datasets: [{
          label: 'Impact Score (%)',
          data: topFeats.map(f => f.importance_pct),
          backgroundColor: CHART_COLORS.indigo,
          borderRadius: 6
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
        }
      }
    });
  }
}

// Full-Page AI Agent Studio Methods
function sendFullAIAgentQuery(prompt) {
  const input = document.getElementById('full-ai-input');
  if (input) {
    input.value = prompt;
    handleFullAISubmit(new Event('submit'));
  }
}

async function handleFullAISubmit(e) {
  if (e && e.preventDefault) e.preventDefault();
  const input = document.getElementById('full-ai-input');
  if (!input) return;
  const query = input.value.trim();
  if (!query) return;

  input.value = '';
  appendFullAIMessage(query, 'user');

  const typingId = appendFullAITyping();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: query })
    });
    const data = await res.json();
    removeChatTyping(typingId);
    if (data.status === 'success') {
      appendFullAIMessage(data.reply, 'ai');
    } else {
      appendFullAIMessage(data.message || 'Error processing request.', 'ai');
    }
  } catch (err) {
    removeChatTyping(typingId);
    appendFullAIMessage('Unable to communicate with AI Analyst Agent.', 'ai');
  }
}

function appendFullAIMessage(text, sender = 'ai') {
  const stream = document.getElementById('full-ai-chat-messages');
  if (!stream) return;
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${sender}`;

  let formatted = escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>');

  bubble.innerHTML = formatted;
  stream.appendChild(bubble);
  stream.scrollTop = stream.scrollHeight;
}

function appendFullAITyping() {
  const stream = document.getElementById('full-ai-chat-messages');
  if (!stream) return null;
  const id = 'full-typing-' + Date.now();
  const bubble = document.createElement('div');
  bubble.id = id;
  bubble.className = 'chat-bubble ai';
  bubble.innerHTML = '<em>Consulting statistical models and generating insight...</em>';
  stream.appendChild(bubble);
  stream.scrollTop = stream.scrollHeight;
  return id;
}

// Drag & Drop File Upload
function setupDropzone() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-uploader');

  if (!dropzone || !fileInput) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', e => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  });

  fileInput.addEventListener('change', e => {
    if (e.target.files.length > 0) {
      uploadFile(e.target.files[0]);
    }
  });
}

function setupExportButtons() {
  const btnCsv = document.getElementById('btn-export-csv');
  const btnScript = document.getElementById('btn-export-script');

  if (btnCsv) {
    btnCsv.addEventListener('click', () => {
      window.location.href = '/api/export-csv';
    });
  }

  if (btnScript) {
    btnScript.addEventListener('click', () => {
      window.location.href = '/api/export-script';
    });
  }
}

// API: Load Sample Dataset
async function loadSample(sampleId) {
  showLoading(`Loading and inspecting ${sampleId} dataset...`);
  try {
    const res = await fetch('/api/load-sample', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sample_id: sampleId })
    });
    const data = await res.json();
    if (data.status === 'success') {
      onDatasetLoaded(data);
    } else {
      alert(`Error loading dataset: ${data.message}`);
    }
  } catch (err) {
    alert(`Request error: ${err.message}`);
  } finally {
    hideLoading();
  }
}

// API: Upload Local File
async function uploadFile(file) {
  showLoading(`Reading & sniffing ${file.name}...`);
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.status === 'success') {
      onDatasetLoaded(data);
    } else {
      alert(`Upload error: ${data.message}`);
    }
  } catch (err) {
    alert(`Failed to upload file: ${err.message}`);
  } finally {
    hideLoading();
  }
}

// Handle Raw Dataset Loaded Event
function onDatasetLoaded(data) {
  appState.datasetName = data.dataset_name;
  appState.rawAudit = data.raw_audit;
  appState.columns = data.columns || [];
  appState.cleanedAudit = null;
  appState.auditReport = null;
  appState.edaData = null;
  appState.mlData = null;

  // Update Header UI & Breadcrumb
  const labelEl = document.getElementById('active-dataset-label');
  const dotEl = document.getElementById('active-status-dot');
  if (labelEl) labelEl.textContent = `${data.dataset_name} (${data.shape.rows.toLocaleString()} rows)`;
  if (dotEl) dotEl.classList.remove('idle');

  const wsName = document.getElementById('sidebar-workspace-name');
  if (wsName) wsName.textContent = data.dataset_name;

  const healthBadge = document.getElementById('sidebar-health-badge');
  if (healthBadge && data.raw_audit) {
    healthBadge.textContent = `${data.raw_audit.health_score}%`;
    healthBadge.className = 'nav-badge health';
  }

  // Mark step 1 completed
  document.getElementById('step-nav-1')?.classList.add('completed');
  const exportGroup = document.getElementById('header-exports');
  if (exportGroup) exportGroup.style.display = 'flex';

  // Render Raw Audit
  renderRawAudit(data.raw_audit, data.preview, data.columns);

  // Reset Cleaned Results section
  const cleanResults = document.getElementById('clean-results-section');
  if (cleanResults) cleanResults.style.display = 'none';
}

// Render Raw Audit Summary & Preview Table
function renderRawAudit(audit, previewRows, columns) {
  const container = document.getElementById('raw-audit-results');
  if (!container) return;
  container.style.display = 'block';

  // Health Score Dial
  const scoreEl = document.getElementById('raw-health-score');
  const circleEl = document.getElementById('raw-dial-circle');
  if (scoreEl) scoreEl.textContent = audit.health_score;
  if (circleEl) {
    circleEl.className = 'dial-circle ' + (audit.health_score >= 80 ? 'good' : '');
  }

  // Stats
  document.getElementById('raw-stat-rows').textContent = audit.total_rows.toLocaleString();
  document.getElementById('raw-stat-cols').textContent = `${audit.total_cols} dimensions`;
  document.getElementById('raw-stat-missing').textContent = audit.total_missing_cells.toLocaleString();
  document.getElementById('raw-stat-missing-pct').textContent = `${audit.missing_cell_pct}% of total cells`;
  document.getElementById('raw-stat-dups').textContent = audit.duplicate_rows.toLocaleString();
  document.getElementById('raw-stat-dups-pct').textContent = `${audit.duplicate_pct}% duplicate rows`;
  document.getElementById('raw-stat-dirty-types').textContent = audit.dirty_type_cols;

  // Summary Text
  const titleEl = document.getElementById('raw-audit-title');
  const descEl = document.getElementById('raw-audit-summary');
  if (titleEl) titleEl.textContent = `Raw Data Health Score: ${audit.health_score}/100`;
  if (descEl) {
    descEl.textContent = `Detected ${audit.total_missing_cells.toLocaleString()} missing entries, ${audit.duplicate_rows} duplicate rows, ${audit.total_outliers} outliers, and ${audit.dirty_type_cols} dirty type columns requiring sanitization.`;
  }

  // Preview Table
  renderTable('raw-preview-table', previewRows, columns);

  // Smooth scroll to audit results
  container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// API: Trigger Auto-Clean Pipeline
async function triggerCleanPipeline() {
  showLoading('Sanitizing types, parsing dates, imputing missing values, and treating outliers...');
  try {
    const res = await fetch('/api/clean', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        remove_duplicates: true,
        clean_dirty_numerics: true,
        standardize_text: true,
        parse_dates: true,
        extract_temporal_features: true,
        impute_missing: true,
        numeric_impute_strategy: 'median',
        categorical_impute_strategy: 'mode',
        treat_outliers: true,
        outlier_strategy: 'winsorize',
        decompose_composites: true
      })
    });
    const data = await res.json();
    if (data.status === 'success') {
      appState.auditReport = data.audit_report;
      appState.cleanedColumns = data.cleaned_columns;
      renderCleanResults(data.audit_report, data.preview, data.cleaned_columns, data.python_script);
      document.getElementById('step-nav-2')?.classList.add('completed');
    } else {
      alert(`Cleaning error: ${data.message}`);
    }
  } catch (err) {
    alert(`Request error: ${err.message}`);
  } finally {
    hideLoading();
  }
}

// Render Cleaning Results
function renderCleanResults(report, previewRows, cleanedCols, pythonScript) {
  const container = document.getElementById('clean-results-section');
  if (!container) return;
  container.style.display = 'block';

  // Dial
  const scoreEl = document.getElementById('cleaned-health-score');
  if (scoreEl) scoreEl.textContent = report.cleaned_health_score;

  const healthBadge = document.getElementById('sidebar-health-badge');
  if (healthBadge) {
    healthBadge.textContent = `${report.cleaned_health_score}%`;
    healthBadge.className = 'nav-badge health live';
  }

  // Comparison metrics
  document.getElementById('comp-score-before').textContent = `${report.initial_health_score}%`;
  document.getElementById('comp-score-after').textContent = `${report.cleaned_health_score}% (+${report.health_score_delta}%)`;
  document.getElementById('comp-missing-before').textContent = report.initial_missing_cells.toLocaleString();
  document.getElementById('comp-missing-after').textContent = `${report.cleaned_missing_cells} (0%)`;
  document.getElementById('comp-dups-before').textContent = `${report.duplicates_removed} found`;
  document.getElementById('comp-dups-after').textContent = `0 (Purged)`;
  document.getElementById('comp-outliers-after').textContent = `${report.outliers_treated} treated`;

  // Log Box
  const logBox = document.getElementById('cleaning-log-box');
  if (logBox) {
    logBox.innerHTML = '';
    report.transform_log.forEach(msg => {
      const entry = document.createElement('div');
      entry.className = 'log-entry';
      entry.innerHTML = `<span class="log-icon">✓</span> <span>${escapeHtml(msg)}</span>`;
      logBox.appendChild(entry);
    });
  }

  // Python Script Preview
  const pyPre = document.getElementById('python-script-preview');
  if (pyPre) pyPre.textContent = pythonScript;

  // Cleaned Preview Table
  renderTable('cleaned-preview-table', previewRows, cleanedCols);

  container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// API: Fetch EDA Data
async function fetchEDA() {
  showLoading('Computing descriptive statistics, histograms, and correlation matrices...');
  try {
    const res = await fetch('/api/eda', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      appState.edaData = data.eda;
      renderEDA(data.eda);
      document.getElementById('step-nav-3')?.classList.add('completed');
    }
  } catch (err) {
    console.error('EDA fetch error:', err);
  } finally {
    hideLoading();
  }
}

// Render EDA Section
function renderEDA(eda) {
  // 1. Numerical Stats Table
  const tableBody = document.querySelector('#eda-num-stats-table tbody');
  if (tableBody) {
    tableBody.innerHTML = '';
    Object.values(eda.numeric_stats).forEach(stat => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${escapeHtml(stat.name)}</strong></td>
        <td>${stat.count.toLocaleString()}</td>
        <td>${stat.mean.toLocaleString()}</td>
        <td>${stat.std.toLocaleString()}</td>
        <td>${stat.min.toLocaleString()}</td>
        <td>${stat.q25.toLocaleString()}</td>
        <td><strong>${stat.median.toLocaleString()}</strong></td>
        <td>${stat.q75.toLocaleString()}</td>
        <td>${stat.max.toLocaleString()}</td>
        <td>${stat.iqr.toLocaleString()}</td>
        <td>${stat.skewness}</td>
        <td><span class="bullet-badge">${stat.distribution_shape}</span></td>
      `;
      tableBody.appendChild(tr);
    });
  }

  // 2. Correlation Heatmap Table
  const corr = eda.correlation;
  const heatmapEl = document.getElementById('correlation-matrix-table');
  if (heatmapEl && corr && corr.columns.length > 0) {
    document.getElementById('corr-feature-count').textContent = `${corr.columns.length} variables`;
    let html = '<thead><tr><th></th>';
    corr.columns.forEach(col => {
      html += `<th>${escapeHtml(col.substring(0, 12))}</th>`;
    });
    html += '</tr></thead><tbody>';

    corr.columns.forEach((rowCol, rIdx) => {
      html += `<tr><th>${escapeHtml(rowCol.substring(0, 12))}</th>`;
      corr.pearson_matrix[rIdx].forEach((val, cIdx) => {
        const absVal = Math.abs(val);
        let bgColor = 'rgba(255, 255, 255, 0.05)';
        if (rIdx === cIdx) {
          bgColor = 'rgba(99, 102, 241, 0.5)';
        } else if (val > 0) {
          bgColor = `rgba(16, 185, 129, ${Math.min(0.85, absVal * 0.9)})`;
        } else if (val < 0) {
          bgColor = `rgba(244, 63, 94, ${Math.min(0.85, absVal * 0.9)})`;
        }
        html += `<td style="background: ${bgColor}; cursor: pointer;" onclick="onCorrelationCellClick('${rowCol}', '${corr.columns[cIdx]}')" title="Click to plot scatter: ${rowCol} vs ${corr.columns[cIdx]} (r = ${val})">${val}</td>`;
      });
      html += '</tr>';
    });
    html += '</tbody>';
    heatmapEl.innerHTML = html;
  }

  // 3. Top Correlations Cards
  const topCorrContainer = document.getElementById('top-correlations-container');
  if (topCorrContainer && corr && corr.top_correlations) {
    topCorrContainer.innerHTML = '';
    corr.top_correlations.slice(0, 5).forEach(pair => {
      const card = document.createElement('div');
      card.className = 'executive-bullet-card ' + (pair.direction === 'Positive' ? 'driver' : 'anomaly');
      card.style.padding = '0.9rem 1.1rem';
      card.style.marginBottom = '0.75rem';
      card.style.cursor = 'pointer';
      card.onclick = () => onCorrelationCellClick(pair.feature_a, pair.feature_b);
      card.innerHTML = `
        <div class="bullet-top-row">
          <span class="bullet-badge">${pair.strength} ${pair.direction}</span>
          <span style="font-weight: 700; color: #fff; font-family: 'Outfit', sans-serif;">r = ${pair.pearson_r}</span>
        </div>
        <div style="font-weight: 600; font-size: 0.92rem; color: #fff;">${escapeHtml(pair.feature_a)} ⟷ ${escapeHtml(pair.feature_b)}</div>
        <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem;">Spearman: ${pair.spearman_rho} • Click to plot scatter</div>
      `;
      topCorrContainer.appendChild(card);
    });
  }

  // 4. Pairwise Scatter Explorer Dropdowns Setup
  populateScatterSelectors(corr.columns);

  // 5. Distribution Histogram Dropdown
  const metricSelect = document.getElementById('distribution-metric-select');
  if (metricSelect && eda.distributions) {
    metricSelect.innerHTML = '';
    const distKeys = Object.keys(eda.distributions);
    distKeys.forEach(k => {
      const opt = document.createElement('option');
      opt.value = k;
      opt.textContent = k;
      metricSelect.appendChild(opt);
    });
    if (distKeys.length > 0) {
      renderSelectedDistribution();
    }
  }
}

// Bivariate Pairwise Scatter Plot Controller
function populateScatterSelectors(numCols) {
  const xSel = document.getElementById('scatter-x-select');
  const ySel = document.getElementById('scatter-y-select');
  if (!xSel || !ySel || !numCols || numCols.length < 2) return;

  xSel.innerHTML = '';
  ySel.innerHTML = '';

  numCols.forEach((col, idx) => {
    const optX = document.createElement('option');
    optX.value = col;
    optX.textContent = col;
    xSel.appendChild(optX);

    const optY = document.createElement('option');
    optY.value = col;
    optY.textContent = col;
    ySel.appendChild(optY);
  });

  xSel.value = numCols[0];
  ySel.value = numCols[1];
  renderPairwiseScatter();
}

function onCorrelationCellClick(colA, colB) {
  if (colA === colB) return;
  const xSel = document.getElementById('scatter-x-select');
  const ySel = document.getElementById('scatter-y-select');
  if (xSel && ySel) {
    xSel.value = colA;
    ySel.value = colB;
    renderPairwiseScatter();
    document.getElementById('scatter-explorer-card')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

async function renderPairwiseScatter() {
  const xCol = document.getElementById('scatter-x-select')?.value;
  const yCol = document.getElementById('scatter-y-select')?.value;
  const ctx = document.getElementById('chart-pairwise-scatter')?.getContext('2d');

  if (!xCol || !yCol || !ctx) return;

  document.getElementById('scatter-explorer-title').textContent = `Bivariate Scatter: ${xCol} vs ${yCol}`;

  // Fetch sample rows for scatter
  try {
    const res = await fetch('/api/data-query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ view_mode: 'cleaned', page: 1, page_size: 80 })
    });
    const data = await res.json();
    if (data.status === 'success') {
      const points = data.rows
        .filter(r => r[xCol] !== null && r[yCol] !== null && !isNaN(r[xCol]) && !isNaN(r[yCol]))
        .map(r => ({ x: Number(r[xCol]), y: Number(r[yCol]) }));

      if (chartInstances.pairwiseScatter) {
        chartInstances.pairwiseScatter.destroy();
      }

      chartInstances.pairwiseScatter = new Chart(ctx, {
        type: 'scatter',
        data: {
          datasets: [{
            label: `${xCol} vs ${yCol}`,
            data: points,
            backgroundColor: 'rgba(6, 182, 212, 0.6)',
            borderColor: '#06b6d4',
            pointRadius: 4,
            pointHoverRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            x: {
              title: { display: true, text: xCol, color: '#94a3b8' },
              grid: { color: 'rgba(255,255,255,0.05)' },
              ticks: { color: '#94a3b8' }
            },
            y: {
              title: { display: true, text: yCol, color: '#94a3b8' },
              grid: { color: 'rgba(255,255,255,0.05)' },
              ticks: { color: '#94a3b8' }
            }
          }
        }
      });
    }
  } catch (err) {
    console.error('Scatter query error:', err);
  }
}

// Render Distribution Histogram
function renderSelectedDistribution() {
  const metricSelect = document.getElementById('distribution-metric-select');
  if (!metricSelect || !appState.edaData) return;
  const colName = metricSelect.value;
  const dist = appState.edaData.distributions[colName];
  const stat = appState.edaData.numeric_stats[colName];

  if (!dist) return;

  const shapeBadge = document.getElementById('distribution-shape-badge');
  if (shapeBadge && stat) {
    shapeBadge.textContent = stat.distribution_shape;
  }

  const ctx = document.getElementById('chart-distribution').getContext('2d');
  if (chartInstances.distribution) {
    chartInstances.distribution.destroy();
  }

  chartInstances.distribution = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: dist.labels,
      datasets: [{
        label: `${colName} Freq`,
        data: dist.counts,
        backgroundColor: CHART_COLORS.indigoLight,
        borderColor: CHART_COLORS.indigo,
        borderWidth: 2,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#131c31',
          titleColor: '#fff',
          bodyColor: '#94a3b8',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: '#94a3b8', maxRotation: 45, font: { size: 10 } }
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: '#94a3b8' }
        }
      }
    }
  });
}

// API: Fetch ML Data
async function fetchML() {
  showLoading('Running K-Means clustering, PCA, Isolation Forest, and Random Forest feature importance...');
  try {
    const res = await fetch('/api/ml', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      appState.mlData = data.ml;
      renderML(data.ml);
      document.getElementById('step-nav-4')?.classList.add('completed');
    }
  } catch (err) {
    console.error('ML fetch error:', err);
  } finally {
    hideLoading();
  }
}

// Render ML & Executive Insights
function renderML(ml) {
  // 1. Executive Summary Bullets
  const bulletsContainer = document.getElementById('executive-bullets-container');
  if (bulletsContainer && ml.executive_summary) {
    bulletsContainer.innerHTML = '';
    ml.executive_summary.forEach(b => {
      const card = document.createElement('div');
      card.className = `executive-bullet-card ${b.type}`;
      card.innerHTML = `
        <div class="bullet-top-row">
          <span class="bullet-badge">${escapeHtml(b.badge)}</span>
        </div>
        <div class="bullet-headline">${escapeHtml(b.headline)}</div>
        <div class="bullet-detail">${escapeHtml(b.detail)}</div>
      `;
      bulletsContainer.appendChild(card);
    });
  }

  // 2. K-Means 2D PCA Scatter Chart
  const clustering = ml.clustering;
  if (clustering && clustering.scatter_points) {
    document.getElementById('clustering-k-badge').textContent = `Optimal K = ${clustering.optimal_k}`;
    document.getElementById('pca-variance-label').textContent = 
      `PCA Explains: PC1 (${clustering.pca_explained_variance[0]}%), PC2 (${clustering.pca_explained_variance[1]}%)`;

    // Group scatter points by cluster
    const clusterDatasets = [];
    for (let k = 0; k < clustering.optimal_k; k++) {
      const pts = clustering.scatter_points.filter(p => p.cluster === k).map(p => ({ x: p.x, y: p.y }));
      const color = CHART_COLORS.palette[k % CHART_COLORS.palette.length];
      clusterDatasets.push({
        label: `Cluster ${k}`,
        data: pts,
        backgroundColor: color,
        borderColor: color,
        pointRadius: 4,
        pointHoverRadius: 6
      });
    }

    const ctxPca = document.getElementById('chart-pca-clusters').getContext('2d');
    if (chartInstances.pcaClusters) {
      chartInstances.pcaClusters.destroy();
    }

    chartInstances.pcaClusters = new Chart(ctxPca, {
      type: 'scatter',
      data: { datasets: clusterDatasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94a3b8' } }
        },
        scales: {
          x: {
            title: { display: true, text: 'Principal Component 1', color: '#64748b' },
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: '#94a3b8' }
          },
          y: {
            title: { display: true, text: 'Principal Component 2', color: '#64748b' },
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: '#94a3b8' }
          }
        }
      }
    });

    // Render Personas
    const personaContainer = document.getElementById('cluster-personas-container');
    if (personaContainer && clustering.personas) {
      personaContainer.innerHTML = '';
      clustering.personas.forEach(p => {
        const div = document.createElement('div');
        div.className = 'persona-card';
        div.innerHTML = `
          <div class="persona-title">
            <span>${escapeHtml(p.name)}</span>
            <span style="font-size: 0.82rem; color: var(--accent-cyan);">${p.size} records (${p.percentage}%)</span>
          </div>
          <div class="persona-traits">
            ${p.key_traits.map(t => `<span class="trait-tag">${escapeHtml(t)}</span>`).join('')}
          </div>
        `;
        personaContainer.appendChild(div);
      });
    }
  }

  // 3. Random Forest Feature Importance Chart
  const featImp = ml.feature_importance;
  if (featImp && featImp.drivers) {
    document.getElementById('driver-target-label').textContent = `Target Variable: ${featImp.target_metric}`;

    const labels = featImp.drivers.map(d => d.feature);
    const values = featImp.drivers.map(d => d.importance);

    const ctxImp = document.getElementById('chart-feature-importance').getContext('2d');
    if (chartInstances.featureImportance) {
      chartInstances.featureImportance.destroy();
    }

    chartInstances.featureImportance = new Chart(ctxImp, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: '% Relative Importance',
          data: values,
          backgroundColor: CHART_COLORS.emeraldLight,
          borderColor: CHART_COLORS.emerald,
          borderWidth: 2,
          borderRadius: 4
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: '#94a3b8' }
          },
          y: {
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: '#94a3b8' }
          }
        }
      }
    });
  }

  // 4. Anomaly Flags (populate in both dashboard view and ML view)
  ['anomaly-summary-container', 'anomaly-summary-container-ml'].forEach(containerId => {
    const anomContainer = document.getElementById(containerId);
    if (anomContainer && ml.anomalies) {
      anomContainer.innerHTML = '';
      const anom = ml.anomalies;
      const summaryCard = document.createElement('div');
      summaryCard.style.fontSize = '0.85rem';
      summaryCard.style.color = 'var(--text-secondary)';
      summaryCard.style.marginBottom = '0.6rem';
      summaryCard.textContent = `Flagged ${anom.total_anomalies_detected} anomalies (${anom.anomaly_percentage}% of data). Most divergent record indices:`;
      anomContainer.appendChild(summaryCard);

      const list = document.createElement('div');
      list.style.display = 'flex';
      list.style.flexWrap = 'wrap';
      list.style.gap = '0.4rem';
      anom.top_anomalies.slice(0, 8).forEach(item => {
        const chip = document.createElement('span');
        chip.className = 'trait-tag';
        chip.style.borderColor = 'rgba(245, 158, 11, 0.4)';
        chip.style.color = '#fbbf24';
        chip.textContent = `Row #${item.row_index} (Score: ${item.anomaly_score})`;
        list.appendChild(chip);
      });
      anomContainer.appendChild(list);
    }
  });
}

// Stage 5: Render Live Interactive Dashboard
function renderDashboard() {
  populateDashboardSelectors();
  updateDashboardVisuals();
  renderAnomalyRadar();
  document.getElementById('step-nav-5')?.classList.add('completed');
}

function populateDashboardSelectors() {
  const metricSelect = document.getElementById('dash-metric-select');
  const catSelect = document.getElementById('dash-category-select');

  if (!metricSelect || !catSelect || !appState.edaData) return;

  const numCols = Object.keys(appState.edaData.numeric_stats);
  const catCols = Object.keys(appState.edaData.categorical_stats);

  if (metricSelect.options.length === 0) {
    numCols.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      metricSelect.appendChild(opt);
    });
    if (numCols.length > 0) metricSelect.value = numCols[0];
  }

  if (catSelect.options.length === 0) {
    catCols.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      catSelect.appendChild(opt);
    });
    if (catCols.length > 0) catSelect.value = catCols[0];
  }

  appState.primaryMetric = metricSelect.value;
  appState.categoryDimension = catSelect.value;
}

function updateDashboardVisuals() {
  const metric = document.getElementById('dash-metric-select')?.value;
  const category = document.getElementById('dash-category-select')?.value;
  const chartType = document.getElementById('dash-chart-type-select')?.value || 'doughnut';
  const colorTheme = document.getElementById('dash-color-theme-select')?.value || 'neon';

  if (!metric || !appState.edaData) return;

  const numStat = appState.edaData.numeric_stats[metric];
  if (numStat) {
    document.getElementById('kpi-total-records').textContent = numStat.count.toLocaleString();
    document.getElementById('kpi-metric-1-label').textContent = `Total ${metric}`;
    const sumVal = numStat.count * numStat.mean;
    document.getElementById('kpi-metric-1-val').textContent = sumVal > 1000 ? sumVal.toLocaleString(undefined, { maximumFractionDigits: 1 }) : sumVal.toFixed(1);
    
    document.getElementById('kpi-metric-2-label').textContent = `Average ${metric}`;
    document.getElementById('kpi-metric-2-val').textContent = numStat.mean.toLocaleString();
    
    const hScore = appState.auditReport ? appState.auditReport.cleaned_health_score : (appState.rawAudit ? appState.rawAudit.health_score : 100);
    document.getElementById('kpi-health-score').textContent = `${hScore}%`;
  }

  // 1. Time Series or Trend Chart
  renderDashboardTrendChart(metric);

  // 2. Category Breakdown Chart (with Studio customization)
  renderDashboardCategoryChart(category, metric, chartType, colorTheme);

  // 3. Studio Full Canvas Chart
  renderStudioChart();

  // 4. Forecast and Anomaly Visuals
  renderForecastSubTab();
  renderAnomalyRadar();
}

function renderDashboardTrendChart(metric) {
  const ctx = document.getElementById('chart-dash-trend')?.getContext('2d');
  if (!ctx) return;

  if (chartInstances.dashTrend) {
    chartInstances.dashTrend.destroy();
  }

  const ts = appState.mlData?.time_series;
  if (ts && ts.historical_dates) {
    document.getElementById('dash-trend-chart-title').textContent = `${ts.target_metric} Chronological Trend & Forecast`;
    document.getElementById('trend-direction-badge').textContent = `${ts.trend_direction} (${ts.growth_rate_pct}%)`;

    // Combine historical and future
    const allLabels = [...ts.historical_dates, ...ts.forecast_dates];
    const histData = [...ts.historical_values, ...new Array(ts.forecast_dates.length).fill(null)];
    const rollData = [...ts.rolling_moving_average, ...new Array(ts.forecast_dates.length).fill(null)];
    const foreData = [...new Array(ts.historical_dates.length).fill(null), ...ts.forecast_values];

    chartInstances.dashTrend = new Chart(ctx, {
      type: 'line',
      data: {
        labels: allLabels,
        datasets: [
          {
            label: 'Historical',
            data: histData,
            borderColor: CHART_COLORS.cyan,
            backgroundColor: CHART_COLORS.cyanLight,
            borderWidth: 2,
            pointRadius: 2,
            tension: 0.2
          },
          {
            label: 'Rolling Avg',
            data: rollData,
            borderColor: CHART_COLORS.indigo,
            borderWidth: 2,
            borderDash: [5, 5],
            pointRadius: 0
          },
          {
            label: 'Forecast Projection',
            data: foreData,
            borderColor: CHART_COLORS.emerald,
            borderWidth: 2,
            pointRadius: 3,
            tension: 0.1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94a3b8' } }
        },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8', maxTicksLimit: 10 } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
        }
      }
    });
  } else {
    // Fallback: Distribution of the selected metric
    document.getElementById('dash-trend-chart-title').textContent = `${metric} Value Distribution Curve`;
    const dist = appState.edaData?.distributions[metric];
    if (dist) {
      chartInstances.dashTrend = new Chart(ctx, {
        type: 'line',
        data: {
          labels: dist.labels,
          datasets: [{
            label: `${metric} Density`,
            data: dist.counts,
            borderColor: CHART_COLORS.indigo,
            backgroundColor: CHART_COLORS.indigoLight,
            fill: true,
            tension: 0.4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8', font: { size: 9 } } },
            y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
          }
        }
      });
    }
  }
}

function renderDashboardCategoryChart(category, metric, chartType = 'doughnut', colorTheme = 'neon') {
  const ctx = document.getElementById('chart-dash-breakdown')?.getContext('2d');
  if (!ctx) return;

  if (chartInstances.dashBreakdown) {
    chartInstances.dashBreakdown.destroy();
  }

  const catStat = appState.edaData?.categorical_stats[category];
  if (!catStat || !catStat.frequency_distribution) return;

  document.getElementById('dash-category-chart-title').textContent = `Breakdown by ${category}`;
  document.getElementById('chart-type-badge').textContent = chartType.toUpperCase();

  const labels = catStat.frequency_distribution.slice(0, 7).map(d => d.category);
  const values = catStat.frequency_distribution.slice(0, 7).map(d => d.count);
  const palette = THEME_PALETTES[colorTheme] || CHART_COLORS.palette;

  const chartConfig = {
    type: chartType,
    data: {
      labels: labels,
      datasets: [{
        label: `${category} Distribution`,
        data: values,
        backgroundColor: palette.slice(0, labels.length),
        borderColor: chartType === 'doughnut' ? '#0e1526' : palette[0],
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: chartType === 'doughnut' || chartType === 'polarArea' ? 'right' : 'top',
          labels: { color: '#94a3b8', boxWidth: 12 }
        }
      }
    }
  };

  if (chartType === 'bar') {
    chartConfig.options.scales = {
      x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
      y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
    };
  } else if (chartType === 'radar' || chartType === 'polarArea') {
    chartConfig.options.scales = {
      r: {
        grid: { color: 'rgba(255,255,255,0.1)' },
        angleLines: { color: 'rgba(255,255,255,0.1)' },
        ticks: { backdropColor: 'transparent', color: '#94a3b8' }
      }
    };
  }

  chartInstances.dashBreakdown = new Chart(ctx, chartConfig);
}

// Anomaly Multi-Attribute Radar Chart
function renderAnomalyRadar() {
  const ctx = document.getElementById('chart-anomaly-radar')?.getContext('2d');
  if (!ctx || !appState.mlData || !appState.mlData.anomalies) return;

  if (chartInstances.anomalyRadar) {
    chartInstances.anomalyRadar.destroy();
  }

  const anom = appState.mlData.anomalies;
  if (!anom.top_anomalies || anom.top_anomalies.length === 0) return;

  const top1 = anom.top_anomalies[0].metrics;
  const labels = Object.keys(top1);

  // Normalize values between 0 and 100 for intuitive radar comparison
  const anomalyVals = [];
  const baselineVals = [];

  labels.forEach(feat => {
    const stat = appState.edaData?.numeric_stats[feat];
    const mean = stat ? stat.mean : 50;
    const maxVal = stat ? Math.max(1, stat.max) : 100;
    
    const normAnom = Math.min(100, Math.round((Number(top1[feat]) / maxVal) * 100));
    const normBase = Math.min(100, Math.round((mean / maxVal) * 100));
    
    anomalyVals.push(normAnom);
    baselineVals.push(normBase);
  });

  chartInstances.anomalyRadar = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: labels,
      datasets: [
        {
          label: `Top Outlier (Row #${anom.top_anomalies[0].row_index})`,
          data: anomalyVals,
          backgroundColor: 'rgba(244, 63, 94, 0.25)',
          borderColor: '#f43f5e',
          pointBackgroundColor: '#f43f5e',
          borderWidth: 2
        },
        {
          label: 'Dataset Average (Baseline)',
          data: baselineVals,
          backgroundColor: 'rgba(16, 185, 129, 0.2)',
          borderColor: '#10b981',
          pointBackgroundColor: '#10b981',
          borderWidth: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#94a3b8' } }
      },
      scales: {
        r: {
          grid: { color: 'rgba(255,255,255,0.08)' },
          angleLines: { color: 'rgba(255,255,255,0.08)' },
          ticks: { backdropColor: 'transparent', color: '#64748b' }
        }
      }
    }
  });
}

// AI Copilot Chat Drawer Controller
function toggleCopilotDrawer() {
  const drawer = document.getElementById('copilot-drawer');
  if (drawer) drawer.classList.toggle('open');
}

function sendCopilotQuery(prompt) {
  const input = document.getElementById('copilot-input');
  if (input) {
    input.value = prompt;
    handleCopilotSubmit(new Event('submit'));
  }
}

async function handleCopilotSubmit(e) {
  if (e && e.preventDefault) e.preventDefault();
  const input = document.getElementById('copilot-input');
  if (!input) return;
  const query = input.value.trim();
  if (!query) return;

  input.value = '';
  appendChatMessage(query, 'user');

  // Typing indicator
  const typingId = appendChatTyping();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: query })
    });
    const data = await res.json();
    removeChatTyping(typingId);
    if (data.status === 'success') {
      appendChatMessage(data.reply, 'ai');
    } else {
      appendChatMessage(data.message || 'Error processing inquiry.', 'ai');
    }
  } catch (err) {
    removeChatTyping(typingId);
    appendChatMessage('Unable to reach analytics copilot backend.', 'ai');
  }
}

function appendChatMessage(text, sender = 'ai') {
  const msgContainer = document.getElementById('copilot-messages');
  if (!msgContainer) return;
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${sender}`;

  let formatted = escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>');

  bubble.innerHTML = formatted;
  msgContainer.appendChild(bubble);
  msgContainer.scrollTop = msgContainer.scrollHeight;
}

function appendChatTyping() {
  const msgContainer = document.getElementById('copilot-messages');
  if (!msgContainer) return null;
  const id = 'typing-' + Date.now();
  const bubble = document.createElement('div');
  bubble.id = id;
  bubble.className = 'chat-bubble ai';
  bubble.innerHTML = '<em>Thinking and analyzing active dataset...</em>';
  msgContainer.appendChild(bubble);
  msgContainer.scrollTop = msgContainer.scrollHeight;
  return id;
}

function removeChatTyping(id) {
  if (!id) return;
  const el = document.getElementById(id);
  if (el) el.remove();
}

// Live Data Inspector Table
async function fetchInspectorRows() {
  const tableEl = document.getElementById('inspector-table');
  if (!tableEl) return;

  try {
    const res = await fetch('/api/data-query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        view_mode: appState.inspectorViewMode,
        page: appState.inspectorPage,
        page_size: appState.inspectorPageSize,
        search: appState.inspectorSearch,
        sort_by: appState.inspectorSortBy,
        sort_asc: appState.inspectorSortAsc
      })
    });
    const data = await res.json();
    if (data.status === 'success') {
      renderInspectorTable(data.rows, data.columns);
      updateInspectorPagination(data.page, data.total_pages, data.total_rows);
    }
  } catch (err) {
    console.error('Inspector fetch error:', err);
  }
}

function renderInspectorTable(rows, columns) {
  const thead = document.querySelector('#inspector-table thead');
  const tbody = document.querySelector('#inspector-table tbody');
  if (!thead || !tbody) return;

  // Header
  thead.innerHTML = '';
  const trHead = document.createElement('tr');
  columns.forEach(col => {
    const th = document.createElement('th');
    th.className = 'sortable';
    th.textContent = col;
    th.onclick = () => {
      if (appState.inspectorSortBy === col) {
        appState.inspectorSortAsc = !appState.inspectorSortAsc;
      } else {
        appState.inspectorSortBy = col;
        appState.inspectorSortAsc = true;
      }
      fetchInspectorRows();
    };
    trHead.appendChild(th);
  });
  thead.appendChild(trHead);

  // Body
  tbody.innerHTML = '';
  if (rows.length === 0) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="${columns.length}" style="text-align: center; color: var(--text-muted); padding: 2rem;">No matching records found.</td>`;
    tbody.appendChild(tr);
    return;
  }

  rows.forEach(r => {
    const tr = document.createElement('tr');
    columns.forEach(c => {
      const td = document.createElement('td');
      const val = r[c];
      if (val === null || val === undefined) {
        td.innerHTML = '<span class="null-badge">null</span>';
      } else {
        td.textContent = val;
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function updateInspectorPagination(page, totalPages, totalRows) {
  appState.inspectorPage = page;
  const indicator = document.getElementById('inspector-page-indicator');
  const btnPrev = document.getElementById('btn-page-prev');
  const btnNext = document.getElementById('btn-page-next');

  if (indicator) {
    indicator.textContent = `Page ${page} of ${totalPages} (${totalRows.toLocaleString()} total rows)`;
  }
  if (btnPrev) btnPrev.disabled = page <= 1;
  if (btnNext) btnNext.disabled = page >= totalPages;
}

function changeInspectorPage(delta) {
  appState.inspectorPage += delta;
  fetchInspectorRows();
}

let searchDebounceTimeout = null;
function handleTableSearch() {
  clearTimeout(searchDebounceTimeout);
  searchDebounceTimeout = setTimeout(() => {
    const input = document.getElementById('inspector-search');
    appState.inspectorSearch = input ? input.value : '';
    appState.inspectorPage = 1;
    fetchInspectorRows();
  }, 250);
}

function toggleCleanedRawView() {
  const select = document.getElementById('dash-view-mode');
  if (select) {
    appState.inspectorViewMode = select.value;
    appState.inspectorPage = 1;
    fetchInspectorRows();
  }
}

// Utility: Generic Table Renderer
function renderTable(tableId, rows, columns) {
  const table = document.getElementById(tableId);
  if (!table || !columns) return;

  const thead = table.querySelector('thead');
  const tbody = table.querySelector('tbody');
  if (!thead || !tbody) return;

  thead.innerHTML = '';
  tbody.innerHTML = '';

  // Columns
  const trHead = document.createElement('tr');
  columns.forEach(col => {
    const th = document.createElement('th');
    th.textContent = col;
    trHead.appendChild(th);
  });
  thead.appendChild(trHead);

  // Rows
  if (!rows || rows.length === 0) return;
  rows.forEach(row => {
    const tr = document.createElement('tr');
    columns.forEach(c => {
      const td = document.createElement('td');
      const val = row[c];
      if (val === null || val === undefined || val === '') {
        td.innerHTML = '<span class="null-badge">null</span>';
      } else {
        td.textContent = val;
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function escapeHtml(str) {
  if (typeof str !== 'string') return String(str);
  return str.replace(/[&<>"']/g, match => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[match]));
}

// ============================================================
// ANALYSIS ACTIVITY HISTORY MODAL CONTROLLER
// ============================================================

function openHistoryModal() {
  const modal = document.getElementById('history-modal');
  if (modal) {
    modal.style.display = 'flex';
    fetchUserHistory();
  }
}

function closeHistoryModal() {
  const modal = document.getElementById('history-modal');
  if (modal) modal.style.display = 'none';
}

async function fetchUserHistory() {
  const listEl = document.getElementById('history-list');
  if (!listEl) return;
  listEl.innerHTML = '<div class="history-loading-placeholder" style="text-align: center; padding: 2rem; color: var(--text-muted);">Loading your analysis logs...</div>';

  try {
    const res = await fetch('/api/user/history');
    const data = await res.json();

    if (data.status === 'success' && Array.isArray(data.history)) {
      renderUserHistory(data.history);
      const countBadge = document.getElementById('sidebar-history-count');
      if (countBadge) {
        countBadge.textContent = `${data.history.length} Logs`;
      }
    } else {
      listEl.innerHTML = '<div class="history-empty-state">Unable to load activity history.</div>';
    }
  } catch (err) {
    listEl.innerHTML = '<div class="history-empty-state">Network or server error loading history.</div>';
  }
}

function renderUserHistory(history) {
  const listEl = document.getElementById('history-list');
  if (!listEl) return;

  if (!history || history.length === 0) {
    listEl.innerHTML = `
      <div class="history-empty-state">
        <div style="font-size: 2.2rem; margin-bottom: 0.75rem;">📂</div>
        <div style="font-weight: 600; font-size: 1.05rem; color: var(--text-primary); margin-bottom: 0.3rem;">No Activity History Yet</div>
        <p style="color: var(--text-muted); font-size: 0.85rem;">Load a sample dataset, upload CSV/Excel, or run clean & ML pipelines to build your history log.</p>
      </div>
    `;
    return;
  }

  let html = '';
  history.forEach(item => {
    let actionIcon = '📊';
    const action = item.action_type || '';
    if (action.includes('Clean')) actionIcon = '🧹';
    else if (action.includes('ML')) actionIcon = '🧠';
    else if (action.includes('Upload')) actionIcon = '📁';
    else if (action.includes('Demo') || action.includes('Sample')) actionIcon = '⚡';

    html += `
      <div class="history-item">
        <div class="history-item-main">
          <div class="history-item-icon">${actionIcon}</div>
          <div class="history-item-details">
            <div class="history-item-title">${escapeHtml(item.dataset_name || 'Active Dataset')}</div>
            <div class="history-item-meta">
              <span>📅 ${escapeHtml(item.created_at || 'Recent')}</span>
              <span>•</span>
              <span>🔢 ${item.records_count ? item.records_count.toLocaleString() : 0} rows</span>
            </div>
          </div>
        </div>
        <div class="history-item-badges">
          <span class="history-badge action">${escapeHtml(item.action_type || 'Analyzed')}</span>
          <span class="history-badge score">Score: ${item.health_score || 0}%</span>
        </div>
      </div>
    `;
  });

  listEl.innerHTML = html;
}

async function clearUserHistory() {
  if (!confirm('Are you sure you want to clear your analysis activity history?')) return;
  try {
    const res = await fetch('/api/user/history', { method: 'DELETE' });
    const data = await res.json();
    if (data.status === 'success') {
      fetchUserHistory();
      const countBadge = document.getElementById('sidebar-history-count');
      if (countBadge) countBadge.textContent = '0 Logs';
    } else {
      alert(data.message || 'Failed to clear history');
    }
  } catch (err) {
    alert('Error clearing history.');
  }
}

