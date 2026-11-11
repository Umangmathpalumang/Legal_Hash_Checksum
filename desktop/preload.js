'use strict';
/**
 * Electron preload — runs in renderer context (isolated from Node).
 * Exposes a safe __LHCDesktop bridge that lhc-core.js reads for device info.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('__LHCDesktop', {
  isDesktop:   true,
  platform:    process.platform,
  /**
   * Returns { mac, platform, hostname, arch, version }.
   * lhc-core.js uses mac for license device binding.
   */
  getDeviceId: function () {
    return ipcRenderer.invoke('lhc-get-device-id');
  }
});
