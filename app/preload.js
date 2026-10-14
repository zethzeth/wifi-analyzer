const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('kestrel', {
    send: (command) => ipcRenderer.send('engine', command),
    onEvent: (callback) => ipcRenderer.on('engine', (_event, message) => callback(message)),
});
