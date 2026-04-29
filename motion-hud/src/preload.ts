import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  close: () => ipcRenderer.invoke("hud:close"),
  getScreenSize: () => ipcRenderer.invoke("hud:getScreenSize"),
  platform: process.platform,
});
