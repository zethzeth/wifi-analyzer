// Electron shell: spawns the Python engine (`python -m kestrel serve`) and relays JSON lines to the window.
const { app, BrowserWindow, ipcMain, nativeTheme } = require('electron');
const { spawn } = require('node:child_process');
const path = require('node:path');
const readline = require('node:readline');

const ROOT = path.resolve(__dirname, '..');
const PYTHON = process.env.KESTREL_PYTHON || path.join(ROOT, '.venv', 'bin', 'python');

let engine = null;
let win = null;

function send(message) {
    if (win && !win.isDestroyed()) win.webContents.send('engine', message);
}

function startEngine() {
    engine = spawn(PYTHON, ['-m', 'kestrel', 'serve'], { cwd: ROOT, stdio: ['pipe', 'pipe', 'inherit'] });
    readline.createInterface({ input: engine.stdout }).on('line', (line) => {
        try {
            send(JSON.parse(line));
        } catch {
            console.error('[engine]', line);
        }
    });
    engine.on('error', (error) => send({ event: 'error', data: { message: `Could not start ${PYTHON}: ${error.message}. Run make setup-env.` } }));
    engine.on('exit', (code) => send({ event: 'engine_exit', data: { code } }));
}

ipcMain.on('engine', (_event, command) => engine?.stdin.write(JSON.stringify(command) + '\n'));

app.whenReady().then(() => {
    startEngine();
    win = new BrowserWindow({
        width: 1320,
        height: 900,
        minWidth: 960,
        minHeight: 640,
        title: 'Kestrel',
        backgroundColor: nativeTheme.shouldUseDarkColors ? '#0d0d0d' : '#f9f9f7',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            sandbox: true,
        },
    });
    win.setMenuBarVisibility(false);
    win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
});

app.on('window-all-closed', () => app.quit());
app.on('will-quit', () => engine?.kill());
