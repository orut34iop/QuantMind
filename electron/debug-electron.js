#!/usr/bin/env node

const { app, BrowserWindow } = require('electron');
const path = require('path');

console.log('[DEBUG] Starting Electron debug script...');

// 检查文件是否存在
const distReactPath = path.join(__dirname, 'dist-react');
const indexPath = path.join(distReactPath, 'index.html');

console.log('[DEBUG] Current working directory:', __dirname);
console.log('[DEBUG] dist-react path:', distReactPath);
console.log('[DEBUG] index.html path:', indexPath);

const fs = require('fs');

if (!fs.existsSync(distReactPath)) {
  console.error('[DEBUG] dist-react directory does not exist!');
  process.exit(1);
}

if (!fs.existsSync(indexPath)) {
  console.error('[DEBUG] index.html does not exist!');
  process.exit(1);
}

console.log('[DEBUG] Both dist-react directory and index.html exist!');

// 读取index.html内容
const indexContent = fs.readFileSync(indexPath, 'utf8');
console.log('[DEBUG] index.html content length:', indexContent.length);
console.log('[DEBUG] index.html first 200 chars:', indexContent.substring(0, 200));

// 创建一个简单的窗口进行测试
function createTestWindow() {
  console.log('[DEBUG] Creating test window...');

  const testWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // 开发模式
  console.log('[DEBUG] Loading in development mode');
  testWindow.loadURL('http://127.0.0.1:3000').then(() => {
    console.log('[DEBUG] Successfully loaded dev server');
  }).catch(err => {
    console.error('[DEBUG] Failed to load dev server:', err);

    // 回退到生产模式
    console.log('[DEBUG] Falling back to production mode');
    testWindow.loadFile(indexPath).then(() => {
      console.log('[DEBUG] Successfully loaded production file');
    }).catch(err => {
      console.error('[DEBUG] Failed to load production file:', err);
    });
  });

  testWindow.webContents.openDevTools({ mode: 'detach' });

  testWindow.webContents.on('did-finish-load', () => {
    console.log('[DEBUG] Page finished loading');

    // 检查页面内容
    testWindow.webContents.executeJavaScript(`
      console.log('[PAGE] Document title:', document.title);
      console.log('[PAGE] Document readyState:', document.readyState);
      console.log('[PAGE] Root element:', document.getElementById('root'));
      console.log('[PAGE] Root element innerHTML:', document.getElementById('root')?.innerHTML);
    `);
  });

  testWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('[DEBUG] Page failed to load:', errorCode, errorDescription);
  });

  testWindow.on('closed', () => {
    console.log('[DEBUG] Test window closed');
    app.quit();
  });
}

app.whenReady().then(() => {
  console.log('[DEBUG] App is ready, creating test window');
  createTestWindow();
});

app.on('window-all-closed', () => {
  console.log('[DEBUG] All windows closed');
  app.quit();
});

console.log('[DEBUG] Debug script setup complete');
