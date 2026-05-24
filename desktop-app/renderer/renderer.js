const shopsList = document.getElementById('shops-list');
const statusLine = document.getElementById('status');
const logsOutput = document.getElementById('logs-output');
const statusPill = document.getElementById('status-pill');
const summaryText = document.getElementById('summary-text');
const shopsCountEl = document.getElementById('shops-count');
const telegramStateEl = document.getElementById('telegram-state');
const discordStateEl = document.getElementById('discord-state');
const vpsStateEl = document.getElementById('vps-state');
const template = document.getElementById('shop-row-template');

const envFields = [
  'TOKEN',
  'CHAT_ID',
  'CHAT_IDS',
  'DISCORD_WEBHOOK',
  'DISCORD_MESSAGE',
  'VPS_SSH_TARGET',
  'VPS_SSH_KEY_PATH',
  'VPS_PROJECT_DIR'
];

const buttons = [
  document.getElementById('save-btn'),
  document.getElementById('sync-btn'),
  document.getElementById('run-bot-btn'),
  document.getElementById('save-only-btn'),
  document.getElementById('sync-only-btn'),
  document.getElementById('ensure-worker-btn'),
  document.getElementById('run-bot-inline-btn'),
  document.getElementById('add-shop-btn')
];

function setBusy(isBusy) {
  for (const button of buttons) {
    if (button) {
      button.disabled = isBusy;
      button.style.opacity = isBusy ? '0.7' : '1';
      button.style.cursor = isBusy ? 'wait' : 'pointer';
    }
  }
}

function setStatus(text, tone = 'info') {
  statusLine.textContent = text;
  statusPill.textContent = text;
  statusPill.style.background = tone === 'error'
    ? 'rgba(251, 113, 133, 0.14)'
    : tone === 'success'
      ? 'rgba(52, 211, 153, 0.14)'
      : 'rgba(250, 204, 21, 0.12)';
  statusPill.style.borderColor = tone === 'error'
    ? 'rgba(251, 113, 133, 0.35)'
    : tone === 'success'
      ? 'rgba(52, 211, 153, 0.35)'
      : 'rgba(250, 204, 21, 0.3)';
  statusPill.style.color = tone === 'error'
    ? '#fecdd3'
    : tone === 'success'
      ? '#bbf7d0'
      : '#fef08a';
}

function setLogs(text) {
  logsOutput.textContent = text || '';
}

function appendLogs(lines) {
  const next = Array.isArray(lines) ? lines.join('\n') : String(lines || '');
  setLogs(next);
}

function addShopRow(shop = { name: '', url: '' }) {
  const fragment = template.content.cloneNode(true);
  const row = fragment.querySelector('.shop-row');
  const nameInput = fragment.querySelector('.shop-name');
  const urlInput = fragment.querySelector('.shop-url');
  const removeBtn = fragment.querySelector('.remove-shop-btn');

  nameInput.value = shop.name || '';
  urlInput.value = shop.url || '';

  removeBtn.addEventListener('click', () => {
    row.remove();
    if (shopsList.children.length === 0) {
      addShopRow();
    }
    updateSummary();
  });

  nameInput.addEventListener('input', updateSummary);
  urlInput.addEventListener('input', updateSummary);

  shopsList.appendChild(fragment);
  updateSummary();
}

function collectShops() {
  const rows = [...shopsList.querySelectorAll('.shop-row')];
  return rows
    .map((row) => ({
      name: row.querySelector('.shop-name')?.value?.trim() || '',
      url: row.querySelector('.shop-url')?.value?.trim() || ''
    }))
    .filter((shop) => shop.url);
}

function collectEnv() {
  const env = {};
  for (const field of envFields) {
    env[field] = document.getElementById(field).value.trim();
  }
  return env;
}

function fillEnv(env) {
  for (const field of envFields) {
    document.getElementById(field).value = env[field] || '';
  }
}

function updateSummary() {
  const shops = collectShops();
  const env = collectEnv();
  const telegramReady = Boolean((env.TOKEN || '') && ((env.CHAT_ID || '') || (env.CHAT_IDS || '')));
  const discordReady = Boolean(env.DISCORD_WEBHOOK);
  const vpsReady = Boolean(env.VPS_SSH_TARGET && env.VPS_PROJECT_DIR);

  shopsCountEl.textContent = String(shops.length);
  telegramStateEl.textContent = telegramReady ? 'OK' : 'Pendente';
  discordStateEl.textContent = discordReady ? 'OK' : 'Pendente';
  vpsStateEl.textContent = vpsReady ? 'OK' : 'Pendente';

  summaryText.textContent = shops.length
    ? `${shops.length} lojinha(s) configurada(s). Telegram ${telegramReady ? 'pronto' : 'pendente'}, Discord ${discordReady ? 'pronto' : 'pendente'}, VPS ${vpsReady ? 'pronta' : 'pendente'}.`
    : 'Adicione suas lojinhas para começar a monitorar e sincronizar.';
}

async function load() {
  setStatus('Carregando configuração...', 'info');
  setBusy(true);
  try {
    const payload = await window.heroDesktop.loadConfig();
    shopsList.innerHTML = '';
    const shops = payload.shops && payload.shops.length ? payload.shops : [{ name: '', url: '' }];
    shops.forEach(addShopRow);
    fillEnv(payload.env || {});
    updateSummary();
    setLogs('Configuração carregada com sucesso.');
    setStatus('Configuração carregada.', 'success');
  } catch (error) {
    setStatus(`Erro ao carregar: ${error.message}`, 'error');
    setLogs(error.stack || error.message);
  } finally {
    setBusy(false);
  }
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

async function saveOnly() {
  const shops = collectShops();
  const err = validateShops(shops);
  if (err) {
    setStatus(err, 'error');
    setLogs(err);
    return;
  }

  setBusy(true);
  setStatus('Salvando configuração...', 'info');
  try {
    const result = await window.heroDesktop.saveConfig({ shops, env: collectEnv() });
    appendLogs(result.logs || ['Configuração salva.']);
    setStatus('Configuração salva localmente.', 'success');
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
  setStatus('Salvando e sincronizando VPS...', 'info');
  setLogs('Preparando envio para GitHub e VPS...');
  try {
    const result = await window.heroDesktop.syncToVps({ shops, env: collectEnv() });
    appendLogs(result.logs || ['Sincronização sem saída.']);
    setStatus(result.ok ? 'Sincronização concluída.' : 'Sincronização falhou.', result.ok ? 'success' : 'error');
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
  setStatus('Restaurando worker na VPS...', 'info');
  setLogs('Tentando recriar a sessão tmux bot...');
  try {
    const result = await window.heroDesktop.ensureWorker({ env: collectEnv() });
    appendLogs(result.logs || ['Worker restaurado.']);
    setStatus(result.ok ? 'Worker restaurado na VPS.' : 'Falha ao restaurar worker.', result.ok ? 'success' : 'error');
  } catch (error) {
    setStatus(`Erro ao restaurar worker: ${error.message}`, 'error');
    setLogs(error.stack || error.message);
  } finally {
    setBusy(false);
  }
}

async function runBotCheck() {
  setBusy(true);
  setStatus('Executando teste local do bot...', 'info');
  setLogs('Rodando bot.py uma vez...');
  try {
    const result = await window.heroDesktop.runBotCheck();
    setLogs(result.output || '(sem saída)');
    setStatus(result.ok ? 'Teste local executado com sucesso.' : 'Teste local retornou erro.', result.ok ? 'success' : 'error');
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
document.getElementById('sync-btn').addEventListener('click', syncNow);
document.getElementById('sync-only-btn').addEventListener('click', syncNow);
document.getElementById('ensure-worker-btn').addEventListener('click', ensureWorker);
document.getElementById('run-bot-btn').addEventListener('click', runBotCheck);
document.getElementById('run-bot-inline-btn').addEventListener('click', runBotCheck);

for (const field of envFields) {
  document.getElementById(field).addEventListener('input', updateSummary);
}

load();
