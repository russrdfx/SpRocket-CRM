'use strict';
const {app, BrowserWindow, dialog, Menu, shell, session} = require('electron');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const http = require('node:http');
const origin = 'http://127.0.0.1:18765';
const secret = crypto.randomBytes(32).toString('hex');
let backend, win, quitting = false, backendEnv, loginPending = false, mailPending = false;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
function command() {
  return app.isPackaged ? [path.join(process.resourcesPath, 'backend', 'sprocket-server'), []] :
    [process.env.SPROCKET_PYTHON || 'python3', [path.resolve(__dirname, '..', 'server.py')]];
}
async function request(route) {
  const cookies = await session.defaultSession.cookies.get({url: origin});
  return new Promise((resolve, reject) => {
    const req = http.get(origin + route, {headers: {'X-SpRocket-Desktop': secret,
      Cookie: cookies.map(c => `${c.name}=${c.value}`).join('; ')}}, res => {
      let data = '';
      res.on('data', chunk => {data += chunk; if (data.length > 10000) req.destroy();});
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error(`Server returned ${res.statusCode}`));
        try {resolve(JSON.parse(data));} catch (error) {reject(error);}
      });
    });
    req.setTimeout(2000, () => req.destroy(new Error('Server did not respond')));
    req.on('error', reject);
  });
}
function environment() {
  const folder = app.getPath('userData');
  fs.mkdirSync(folder, {recursive: true, mode: 0o700});
  const configPath = path.join(folder, 'desktop-config.json');
  let config = {};
  if (fs.existsSync(configPath)) config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const allowed = ['OIDC_ISSUER', 'OIDC_CLIENT_ID', 'OIDC_CLIENT_SECRET', 'OIDC_ALLOWED_SUBJECTS',
    'OIDC_ADMIN_SUBJECTS', 'GOOGLE_MAIL_CLIENT_ID', 'GOOGLE_MAIL_CLIENT_SECRET',
    'MICROSOFT_MAIL_CLIENT_ID', 'MICROSOFT_MAIL_CLIENT_SECRET'];
  const env = {...process.env};
  for (const key of allowed) if (typeof config[key] === 'string') env[key] = config[key];
  const keyPath = path.join(folder, 'mail-token.key');
  if (!fs.existsSync(keyPath)) fs.writeFileSync(keyPath, crypto.randomBytes(32).toString('base64'), {mode: 0o600, flag: 'wx'});
  return {...env, SPROCKET_RELEASE_VERSION: app.getVersion(), PORT: '18765', SPROCKET_ORIGIN: origin, OIDC_ORIGIN: origin,
    SPROCKET_DB: path.join(folder, 'sprocket.db'), SPROCKET_SSO_CONFIG: path.join(folder, 'sso.json'),
    MAIL_TOKEN_KEY: fs.readFileSync(keyPath, 'utf8').trim(), SPROCKET_DESKTOP_TOKEN: secret};
}
async function login() {
  if (loginPending) return;
  loginPending = true;
  try {
    const {ticket} = await request('/api/desktop/login');
    await shell.openExternal(origin + '/desktop/start?ticket=' + encodeURIComponent(ticket));
    for (let i = 0; i < 600 && !quitting; i++) {
      await delay(1000);
      const result = await request('/api/desktop/result?ticket=' + encodeURIComponent(ticket));
      if (result.expired) throw new Error('Sign-in expired. Please try again.');
      if (result.cookie) {
        const pieces = result.cookie.split(';').map(p => p.trim());
        const value = pieces[0].slice('sprocket_session='.length);
        const age = Number((pieces.find(p => p.toLowerCase().startsWith('max-age=')) || 'Max-Age=0').split('=')[1]);
        await session.defaultSession.cookies.set({url: origin, name: 'sprocket_session', value,
          httpOnly: true, sameSite: 'lax', expirationDate: Date.now()/1000+age});
        await win.loadURL(origin);
        break;
      }
    }
  } catch (error) {if (!quitting) dialog.showErrorBox('Sign-in failed', error.message);}
  finally {loginPending = false;}
}
function openLink(url) {
  let target;
  try {target = new URL(url, origin);} catch {return;}
  if (target.origin === origin && target.pathname === '/auth/login') {login(); return;}
  if (target.origin === origin && target.pathname === '/desktop/start') {mailPending = true; shell.openExternal(target.href); return;}
  if (target.protocol === 'https:' || target.protocol === 'mailto:') shell.openExternal(target.href);
}
async function backup() {
  const result = await dialog.showSaveDialog(win, {title: 'Back up CRM database', defaultPath: 'SpRocket-backup.db', filters: [{name: 'CRM database', extensions: ['db']}]});
  if (result.canceled) return;
  const [exe, args] = command();
  const child = spawn(exe, [...args, '--backup', result.filePath], {env: backendEnv, stdio: 'ignore'});
  child.once('error', e => dialog.showErrorBox('Backup failed', e.message));
  child.once('exit', code => {
    if (code !== 0) dialog.showErrorBox('Backup failed', 'The database could not be copied.');
    else dialog.showMessageBox(win, {message: 'Database backup saved.', detail: 'Email credentials also require the mail-token.key in your data folder. Keep that key private.'});
  });
}
if (process.env.SPROCKET_DESKTOP_DATA_DIR) {
  fs.mkdirSync(process.env.SPROCKET_DESKTOP_DATA_DIR, {recursive: true, mode: 0o700});
  app.setPath('userData', path.resolve(process.env.SPROCKET_DESKTOP_DATA_DIR));
}
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.setName('SpRocket CRM');
  app.on('second-instance', () => {if (win) {if (win.isMinimized()) win.restore(); win.show(); win.focus();}});
  app.on('before-quit', () => {quitting = true; if (backend && backend.exitCode === null) backend.kill('SIGTERM');});
  app.on('window-all-closed', () => app.quit());
  app.whenReady().then(async () => {
    try {
      backendEnv = environment();
      const [exe, args] = command();
      backend = spawn(exe, args, {env: backendEnv, stdio: 'ignore'});
      let failure;
      backend.once('error', error => {failure = error;});
      backend.once('exit', () => {
        failure ||= new Error('The local server stopped. Port 18765 may already be in use.');
        if (win && !quitting) {dialog.showErrorBox('SpRocket CRM stopped', failure.message); app.quit();}
      });
      let ready = false;
      for (let i=0; i<120; i++) {
        if (failure) throw failure;
        try {ready = (await request('/api/desktop/health')).ready; if (ready) break;} catch {}
        await delay(250);
      }
      if (!ready) throw new Error('The local server did not start. Check that port 18765 is available.');
      session.defaultSession.webRequest.onBeforeSendHeaders({urls: [origin+'/*']}, (details, callback) => {
        details.requestHeaders['X-SpRocket-Desktop'] = secret;
        callback({requestHeaders: details.requestHeaders});
      });
      session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
      win = new BrowserWindow({width: 1440, height: 960, minWidth: 900, minHeight: 650,
        title: 'SpRocket CRM', icon: path.join(__dirname, 'assets/icon.png'),
        webPreferences: {nodeIntegration: false, contextIsolation: true, sandbox: true}});
      win.webContents.setWindowOpenHandler(({url}) => {openLink(url); return {action: 'deny'};});
      win.on('focus', () => {if (mailPending) {mailPending = false; win.webContents.reload();}});
      const guardNavigation = (event, url) => {
        const target = new URL(url);
        if (target.origin !== origin || ['/auth/login', '/desktop/start'].includes(target.pathname)) {event.preventDefault(); openLink(url);}
      };
      win.webContents.on('will-navigate', guardNavigation);
      win.webContents.on('will-redirect', guardNavigation);
      Menu.setApplicationMenu(Menu.buildFromTemplate([
        {label: app.name, submenu: [{role: 'about'}, {type: 'separator'}, {role: 'quit'}]},
        {label: 'File', submenu: [{label: 'Back up database…', click: backup}, {label: 'Open data folder', click: () => shell.openPath(app.getPath('userData'))}]},
        {role: 'editMenu'}, {role: 'viewMenu'}, {role: 'windowMenu'}
      ]));
      await win.loadURL(origin);
    } catch (error) {dialog.showErrorBox('SpRocket CRM could not start', error.message); app.quit();}
  });
}
