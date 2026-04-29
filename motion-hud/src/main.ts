import { app, BrowserWindow, ipcMain, screen } from "electron";
import * as path from "path";
import * as fs from "fs";

// macOS에서 dock 아이콘 숨기기
if (process.platform === "darwin") {
  app.dock?.hide();
}

const SETTINGS_FILE = path.join(app.getPath("userData"), "hud-settings.json");
const HUD_HEIGHT = 700;

interface HudSettings {
  x: number;
  y: number;
  width: number;
}

function loadSettings(): HudSettings {
  try {
    const raw = JSON.parse(fs.readFileSync(SETTINGS_FILE, "utf-8"));
    return { x: raw.x ?? 0, y: raw.y ?? 0, width: raw.width ?? screen.getPrimaryDisplay().workAreaSize.width };
  } catch {
    const { width: sw } = screen.getPrimaryDisplay().workAreaSize;
    return { x: 0, y: 0, width: sw };
  }
}

function saveSettings(s: HudSettings) {
  try {
    fs.writeFileSync(SETTINGS_FILE, JSON.stringify(s, null, 2));
  } catch {}
}

let mainWindow: BrowserWindow | null = null;
let currentSettings: HudSettings;

function createHudWindow() {
  currentSettings = loadSettings();

  const { width: sw } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    x: 0,
    y: 0,
    width: sw,
    height: HUD_HEIGHT,
    minWidth: sw,
    minHeight: HUD_HEIGHT,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    hasShadow: false,
    resizable: false,
    skipTaskbar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,
    },
  });

  // 모든 macOS Space에 표시 + 전체화면 앱 위에도 표시
  mainWindow.setAlwaysOnTop(true, "screen-saver");
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  // 로컬 hud.html 로드
  mainWindow.loadFile(path.join(__dirname, "..", "hud.html"));

  // 위치 저장 (크기는 고정)
  const savePos = () => {
    if (!mainWindow) return;
    const [x, y] = mainWindow.getPosition();
    const [width] = mainWindow.getSize();
    currentSettings = { x, y, width };
    saveSettings(currentSettings);
  };
  mainWindow.on("moved", savePos);
}

// IPC 핸들러
ipcMain.handle("hud:close", () => {
  app.quit();
});

ipcMain.handle("hud:getScreenSize", () => {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const scaleFactor = screen.getPrimaryDisplay().scaleFactor;
  return { width, height, scaleFactor };
});

// localhost 자체서명 인증서 허용 (백엔드 wss:// 연결)
app.on("certificate-error", (event, webContents, url, error, cert, callback) => {
  if (url.startsWith("wss://localhost") || url.startsWith("https://localhost")) {
    event.preventDefault();
    callback(true);
  } else {
    callback(false);
  }
});

// app ready 이후에 createHudWindow 호출 — screen 모듈 사용 가능
app.whenReady().then(() => {
  createHudWindow();
});

app.on("window-all-closed", () => {
  app.quit();
});
