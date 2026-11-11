'use strict';
const { app, BrowserWindow, shell, ipcMain, Menu } = require('electron');
const { spawn }   = require('child_process');
const path        = require('path');
const os          = require('os');
const net         = require('net');

const PORT = 18765; // private port — avoids collision with any running browser server
let serverProcess = null;
let mainWindow    = null;
let serverReady   = false;

/* ── Helpers ──────────────────────────────────────────────────── */
function portAvailable(port) {
  return new Promise(function (res) {
    var s = net.createServer();
    s.once('error', function () { res(false); });
    s.once('listening', function () { s.close(); res(true); });
    s.listen(port);
  });
}

function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

/* ── Start the FastAPI / uvicorn server ───────────────────────── */
async function startServer() {
  // In packaged app, resources are under process.resourcesPath/app
  const appRoot = app.isPackaged
    ? path.join(process.resourcesPath, 'app')
    : path.join(__dirname, '..');

  // Use .venv python if present, otherwise fall back to system python
  const venvPy = process.platform === 'win32'
    ? path.join(appRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(appRoot, '.venv', 'bin', 'python');
  const { existsSync } = require('fs');
  const pythonExe = existsSync(venvPy) ? venvPy : (process.platform === 'win32' ? 'python' : 'python3');

  const available = await portAvailable(PORT);
  if (!available) {
    // Server already running (e.g. dev mode) — skip spawn
    serverReady = true;
    return;
  }

  serverProcess = spawn(pythonExe, [
    '-m', 'uvicorn', 'main:app',
    '--port', String(PORT),
    '--host', '127.0.0.1',
    '--no-access-log'
  ], { cwd: appRoot, windowsHide: true });

  serverProcess.stderr.on('data', function (d) {
    const line = d.toString();
    if (line.includes('Application startup complete')) serverReady = true;
    console.log('[server]', line.trim());
  });

  // Poll until server responds
  for (var i = 0; i < 30; i++) {
    await wait(500);
    try {
      const http = require('http');
      await new Promise(function (res, rej) {
        http.get('http://127.0.0.1:' + PORT + '/health', function (r) {
          serverReady = true; res();
        }).on('error', rej);
      });
      break;
    } catch (e) { /* keep polling */ }
  }
}

/* ── Create the main window ───────────────────────────────────── */
function createWindow() {
  mainWindow = new BrowserWindow({
    width:      1280,
    height:     840,
    minWidth:   768,
    minHeight:  600,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    title:      'LegalHashChecksum Pro',
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
      // Allow loading localhost
      webSecurity: true
    }
  });

  mainWindow.loadURL('http://127.0.0.1:' + PORT + '/');

  // Open all <a target="_blank"> links in default browser, not in-app
  mainWindow.webContents.setWindowOpenHandler(function (_ref) {
    shell.openExternal(_ref.url);
    return { action: 'deny' };
  });

  // Remove default menu on Windows/Linux (Mac keeps the system menu)
  if (process.platform !== 'darwin') Menu.setApplicationMenu(null);
}

/* ── App lifecycle ────────────────────────────────────────────── */
app.whenReady().then(async function () {
  await startServer();
  createWindow();
  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (serverProcess) serverProcess.kill('SIGTERM');
  if (process.platform !== 'darwin') app.quit();
});

app.on('quit', function () {
  if (serverProcess) serverProcess.kill('SIGTERM');
});

/* ── IPC: device identity for license binding ─────────────────── */
ipcMain.handle('lhc-get-device-id', async function () {
  try {
    const ifaces = Object.values(os.networkInterfaces()).flat();
    const phy    = ifaces.filter(function (n) { return n && !n.internal && n.mac !== '00:00:00:00:00:00'; });
    const mac    = phy.length ? phy[0].mac : 'unknown';
    return {
      mac:      mac,
      platform: process.platform,          // 'darwin' | 'win32' | 'linux'
      hostname: os.hostname(),
      arch:     os.arch(),
      version:  app.getVersion()
    };
  } catch (err) {
    return { mac: 'unknown', platform: process.platform, hostname: os.hostname(), arch: os.arch(), version: app.getVersion() };
  }
});
