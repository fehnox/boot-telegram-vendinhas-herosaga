const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('heroDesktop', {
  loadConfig: () => ipcRenderer.invoke('config:load'),
  saveConfig: (payload) => ipcRenderer.invoke('config:save', payload),
  syncToVps: (payload) => ipcRenderer.invoke('ops:sync', payload),
  ensureWorker: (payload) => ipcRenderer.invoke('ops:ensureWorker', payload),
  runBotCheck: () => ipcRenderer.invoke('ops:runBotCheck'),
  runMonitorCycle: (payload) => ipcRenderer.invoke('ops:runMonitorCycle', payload)
});
