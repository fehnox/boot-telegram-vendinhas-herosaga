const shopsList = document.getElementById('shops-list');
const statusPill = document.getElementById('status-pill');
const summaryText = document.getElementById('summary-text');
const logsOutput = document.getElementById('logs-output');
const shopsCountEl = document.getElementById('shops-count');
const telegramStateEl = document.getElementById('telegram-state');
const discordStateEl = document.getElementById('discord-state');
const vpsStateEl = document.getElementById('vps-state');
const template = document.getElementById('shop-row-template');
const pageButtons = [...document.querySelectorAll('.page-tab')];
const pagePanels = [...document.querySelectorAll('.page-panel')];

const envFields = [
  'TOKEN',
  'CHAT_ID',
  'CHAT_IDS',
  'TELEGRAM_MESSAGE',
  'NOTIFY_COOLDOWN',
  'REQUEST_TIMEOUT',
  'DISCORD_WEBHOOK',
  'DISCORD_MESSAGE',
  'VPS_SSH_TARGET',
  'VPS_SSH_KEY_PATH',
  'VPS_PROJECT_DIR'
];

const buttons = [
  document.getElementById('save-btn'),
  document.getElementById('save-only-btn'),
  document.getElementById('sync-only-btn'),
  document.getElementById('ensure-worker-btn'),
  document.getElementById('run-bot-btn'),
  document.getElementById('add-shop-btn')
];

function setBusy(isBusy) {
  for (const button of buttons) {
    if (button) {
      button.disabled = isBusy;
      button.style.opacity = isBusy ? '0.72' : '1';
      button.style.cursor = isBusy ? 'wait' : 'pointer';
    }
  }
}

function setStatus(text, tone = 'info') {
  const statusText = statusPill.querySelector('.status-text');
  if (statusText) {
    statusText.textContent = text;
  } else {
    statusPill.textContent = text;
  }
  statusPill.dataset.tone = tone;
}

function setLogs(text) {
  logsOutput.textContent = text || '';
}

function appendLogs(lines) {
  setLogs(Array.isArray(lines) ? lines.join('\n') : String(lines || ''));
}

function setActivePage(pageName) {
  for (const button of pageButtons) {
    button.classList.toggle('active', button.dataset.page === pageName);
  }

  for (const panel of pagePanels) {
    panel.classList.toggle('active', panel.dataset.pagePanel === pageName);
  }

  const target = document.querySelector(`[data-page-panel="${pageName}"]`);
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function addShopRow(shop = { name: '', url: '' }) {
  const fragment = template.content.cloneNode(true);
  const row = fragment.querySelector('.shop-row');
  const nameInput = fragment.querySelector('.shop-name');
  const urlInput = fragment.querySelector('.shop-url');
  const removeBtn = fragment.querySelector('.remove-shop-btn');

  nameInput.value = shop.name || '';
  urlInput.value = shop.url || '';

  const refresh = () => updateSummary();
  nameInput.addEventListener('input', refresh);
  urlInput.addEventListener('input', refresh);

  removeBtn.addEventListener('click', () => {
    row.remove();
    if (shopsList.children.length === 0) {
      addShopRow();
    }
    updateSummary();
  });

  shopsList.appendChild(fragment);
}

function collectShops() {
  return [...shopsList.querySelectorAll('.shop-row')]
    .map((row) => ({
      name: row.querySelector('.shop-name')?.value?.trim() || '',
      url: row.querySelector('.shop-url')?.value?.trim() || ''
    }))
    .filter((shop) => shop.url);
}

function collectEnv() {
  const env = {};
  for (const field of envFields) {
    const element = document.getElementById(field);
    env[field] = element ? element.value.trim() : '';
  }
  return env;
}

function fillEnv(env) {
  for (const field of envFields) {
    const element = document.getElementById(field);
    if (element) {
      element.value = env[field] || '';
    }
  }
}

function updateSummary() {
  const shops = collectShops();
  const env = collectEnv();
  const telegramReady = Boolean((env.TOKEN || '') && ((env.CHAT_ID || '') || (env.CHAT_IDS || '')));
  const discordReady = Boolean(env.DISCORD_WEBHOOK);
  const vpsReady = Boolean(env.VPS_SSH_TARGET && env.VPS_PROJECT_DIR);

  shopsCountEl.textContent = String(shops.length);
  telegramStateEl.textContent = telegramReady ? 'Ligado' : 'Desligado';
  discordStateEl.textContent = discordReady ? 'Ligado' : 'Desligado';
  vpsStateEl.textContent = vpsReady ? 'Ligado' : 'Desligado';
  telegramStateEl.dataset.state = telegramReady ? 'on' : 'off';
  discordStateEl.dataset.state = discordReady ? 'on' : 'off';
  vpsStateEl.dataset.state = vpsReady ? 'on' : 'off';

  summaryText.textContent = shops.length
    ? `${shops.length} lojinha(s) configurada(s). Telegram ${telegramReady ? 'ligado' : 'desligado'}, Discord ${discordReady ? 'ligado' : 'desligado'}, VPS ${vpsReady ? 'ligada' : 'desligada'}.`
    : 'Adicione sua primeira lojinha para começar.';
}

function validateShops(shops) {
  if (shops.length === 0) {
    return 'Cadastre pelo menos uma lojinha com URL.';
  }
  for (const shop of shops) {
    if (!shop.url.startsWith('http://') && !shop.url.startsWith('https://')) {
      return `URL inválida: ${shop.url}`;
    }
  }
  return '';
}

async function load() {
  setBusy(true);
  setStatus('Conectando...', 'info');
  try {
    const payload = await window.heroDesktop.loadConfig();
    shopsList.innerHTML = '';
    const shops = payload.shops && payload.shops.length ? payload.shops : [{ name: '', url: '' }];
    shops.forEach(addShopRow);
    fillEnv(payload.env || {});
    updateSummary();
    setLogs('Configuração carregada.');
    setStatus('Ligado', 'success');
  } catch (error) {
    setStatus(`Erro ao carregar: ${error.message}`, 'error');
    setLogs(error.stack || error.message);
  } finally {
    setBusy(false);
  }
}

async function saveOnly() {
  const shops = collectShops();
  const err = validateShops(shops);
  if (err) {
    setStatus(err, 'error');
    setLogs(err);
    return;
  }

  setBusy(true);
  setStatus('Salvando...', 'info');
  try {
    const result = await window.heroDesktop.saveConfig({ shops, env: collectEnv() });
    appendLogs(result.logs || ['Configuração salva.']);
    setStatus('Salvo e ligado', 'success');
    updateSummary();
  } catch (error) {
    setStatus(`Falha ao salvar: ${error.message}`, 'error');
    setLogs(error.stack || error.message);
  } finally {
    setBusy(false);
  }
}

async function syncNow() {
  const shops = collectShops();
  const err = validateShops(shops);
  if (err) {
    setStatus(err, 'error');
    setLogs(err);
    return;
  }

  setBusy(true);
  setStatus('Sincronizando...', 'info');
  setLogs('Preparando envio para GitHub e VPS...');
  try {
    const result = await window.heroDesktop.syncToVps({ shops, env: collectEnv() });
    appendLogs(result.logs || ['Sincronização sem saída.']);
    setStatus(result.ok ? 'Sincronizado e ligado' : 'Desligado', result.ok ? 'success' : 'error');
  } catch (error) {
    setStatus(`Erro na sincronização: ${error.message}`, 'error');
    setLogs(error.stack || error.message);
  } finally {
    setBusy(false);
    updateSummary();
  }
}

async function ensureWorker() {
  setBusy(true);
  setStatus('Restaurando worker...', 'info');
  setLogs('Tentando recriar a sessão tmux bot...');
  try {
    const result = await window.heroDesktop.ensureWorker({ env: collectEnv() });
    appendLogs(result.logs || ['Worker restaurado.']);
    setStatus(result.ok ? 'Worker ligado na VPS' : 'Worker desligado', result.ok ? 'success' : 'error');
  } catch (error) {
    setStatus(`Erro ao restaurar worker: ${error.message}`, 'error');
    setLogs(error.stack || error.message);
  } finally {
    setBusy(false);
  }
}

async function runBotCheck() {
  setBusy(true);
  setStatus('Rodando teste manual...', 'info');
  setLogs('Executando teste manual de conectividade com bot.py...');
  try {
    const result = await window.heroDesktop.runBotCheck();
    setLogs(result.output || '(sem saída)');
    setStatus(result.ok ? 'Conectividade OK' : 'Conectividade falhou', result.ok ? 'success' : 'error');
  } catch (error) {
    setStatus(`Erro ao executar teste: ${error.message}`, 'error');
    setLogs(error.stack || error.message);
  } finally {
    setBusy(false);
  }
}

document.getElementById('add-shop-btn').addEventListener('click', () => addShopRow());
document.getElementById('save-btn').addEventListener('click', saveOnly);
document.getElementById('save-only-btn').addEventListener('click', saveOnly);
document.getElementById('sync-only-btn').addEventListener('click', syncNow);
document.getElementById('ensure-worker-btn').addEventListener('click', ensureWorker);
document.getElementById('run-bot-btn').addEventListener('click', runBotCheck);

for (const button of pageButtons) {
  button.addEventListener('click', () => setActivePage(button.dataset.page));
}

for (const field of envFields) {
  const element = document.getElementById(field);
  if (element) {
    element.addEventListener('input', updateSummary);
  }
}

setActivePage('lojinhas');
load();
