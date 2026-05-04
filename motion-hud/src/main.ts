import { app, BrowserWindow, ipcMain, screen, session } from "electron";
import * as path from "path";
import * as fs from "fs";

// macOS에서 dock 아이콘 숨기기
if (process.platform === "darwin") {
  app.dock?.hide();
}

// Hardware acceleration enabled — SharedImageManager transparent window crash is fixed in Electron 33+

const SETTINGS_FILE = path.join(app.getPath("userData"), "hud-settings.json");
const DEFAULT_HEIGHT = 700;
const MIN_WIDTH = 400;
const MIN_HEIGHT = 200;

interface HudSettings {
  x: number;
  y: number;
  width: number;
  height: number;
}

function loadSettings(): HudSettings {
  try {
    const raw = JSON.parse(fs.readFileSync(SETTINGS_FILE, "utf-8"));
    const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;
    return {
      x: raw.x ?? 0,
      y: raw.y ?? 0,
      width: raw.width ?? sw,
      height: raw.height ?? DEFAULT_HEIGHT,
    };
  } catch {
    const { width: sw } = screen.getPrimaryDisplay().workAreaSize;
    return { x: 0, y: 0, width: sw, height: DEFAULT_HEIGHT };
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

  mainWindow = new BrowserWindow({
    x: currentSettings.x,
    y: currentSettings.y,
    width: currentSettings.width,
    height: currentSettings.height,
    minWidth: MIN_WIDTH,
    minHeight: MIN_HEIGHT,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    hasShadow: false,
    resizable: true,
    skipTaskbar: true,
    focusable: false,  // never steal keyboard focus from user's app
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

  // 메인 프로세스에서 커서 위치를 폴링 — IPC 레이스 컨디션 없음
  const STATUS_BAR_H = 44; // status-bar 높이 (px, CSS와 맞춤)
  let _ignoring = true;
  mainWindow.setIgnoreMouseEvents(true, { forward: true });

  setInterval(() => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    const cursor = screen.getCursorScreenPoint();
    const bounds = mainWindow.getBounds();
    const inBar  = cursor.x >= bounds.x &&
                   cursor.x <= bounds.x + bounds.width &&
                   cursor.y >= bounds.y &&
                   cursor.y <= bounds.y + STATUS_BAR_H;
    if (inBar === _ignoring) {
      _ignoring = !inBar;
      mainWindow.setIgnoreMouseEvents(_ignoring, { forward: true });
    }
  }, 16);

  // 로컬 hud.html 로드
  mainWindow.loadFile(path.join(__dirname, "..", "hud.html"));

  // 렌더러 로그/에러를 main process stdout으로 중계
  mainWindow.webContents.on("console-message", (_e, level, message) => {
    const tag = ["LOG", "WARN", "ERR", "DBG"][level] ?? "LOG";
    console.log(`[Renderer:${tag}] ${message}`);
  });
  mainWindow.webContents.on("render-process-gone", (_e, details) => {
    console.error(`[Main] Renderer gone: reason=${details.reason} exitCode=${details.exitCode}`);
  });
  mainWindow.webContents.on("did-fail-load", (_e, errCode, errDesc) => {
    console.error(`[Main] Load failed: ${errCode} ${errDesc}`);
  });

  // 위치·크기 저장
  const saveBounds = () => {
    if (!mainWindow) return;
    const [x, y] = mainWindow.getPosition();
    const [width, height] = mainWindow.getSize();
    currentSettings = { x, y, width, height };
    saveSettings(currentSettings);
  };
  mainWindow.on("moved", saveBounds);
  mainWindow.on("resized", saveBounds);
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
app.on("certificate-error", (event, _webContents, url, _error, _cert, callback) => {
  if (url.includes("localhost")) {
    event.preventDefault();
    callback(true);
  } else {
    callback(false);
  }
});

// app ready 이후에 createHudWindow 호출 — screen 모듈 사용 가능
app.whenReady().then(async () => {
  // session-level: fetch/WebSocket/XHR 등 모든 TLS 연결에 적용
  session.defaultSession.setCertificateVerifyProc((_req, callback) => {
    callback(0); // 0 = net::OK (모든 인증서 허용)
  });

  // 마이크 + 음성 인식 권한 자동 허용
  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    const allowed = ['media', 'microphone', 'audioCapture', 'speechRecognition', 'camera'];
    callback(allowed.includes(permission));
  });

  // macOS TCC: 카메라·마이크 권한을 OS 레벨에서 사전 요청
  if (process.platform === "darwin") {
    const { systemPreferences } = await import("electron");
    const camStatus = systemPreferences.getMediaAccessStatus("camera");
    const micStatus = systemPreferences.getMediaAccessStatus("microphone");
    if (camStatus !== "granted") {
      await systemPreferences.askForMediaAccess("camera");
    }
    if (micStatus !== "granted") {
      await systemPreferences.askForMediaAccess("microphone");
    }
  }

  createHudWindow();
});

app.on("window-all-closed", () => {
  app.quit();
});
