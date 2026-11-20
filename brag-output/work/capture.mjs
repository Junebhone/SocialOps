// Frame capture over the Chrome DevTools Protocol (no Playwright/Puppeteer needed).
// usage: node capture.mjs <url> <outDir> <seconds> [fps] [onlyTimes,comma,separated]
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';

const [url, outDir, secs, fpsArg, only] = process.argv.slice(2);
const fps = Number(fpsArg || 30), total = Math.round(Number(secs) * fps);
mkdirSync(outDir, { recursive: true });
const port = 9333;
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${port}`, '--hide-scrollbars', '--window-size=1080,1080',
  '--force-device-scale-factor=1', '--user-data-dir=' + outDir + '/../chrome-profile', 'about:blank'], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(t => t.type === 'page'); } catch { await sleep(200); }
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r));
let id = 0; const pending = new Map();
ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evalJs = async expr => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;

await send('Emulation.setDeviceMetricsOverride', { width: 1080, height: 1080, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url });
for (let i = 0; i < 100 && !(await evalJs('window.__ready === true')); i++) await sleep(100);

const times = only ? only.split(',').map(Number) : [...Array(total).keys()].map(f => f / fps);
for (let k = 0; k < times.length; k++) {
  const t = times[k];
  await evalJs(`renderAt(${t}); new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`);
  const shot = await send('Page.captureScreenshot', { format: 'png', clip: { x: 0, y: 0, width: 1080, height: 1080, scale: 1 } });
  const name = only ? `t${t.toFixed(2)}.png` : `f${String(k).padStart(4, '0')}.png`;
  writeFileSync(`${outDir}/${name}`, Buffer.from(shot.result.data, 'base64'));
}
ws.close(); chrome.kill();
console.log(`captured ${times.length} frames`);
