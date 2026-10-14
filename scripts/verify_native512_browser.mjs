// Read-only browser checks through an already running local Chrome DevTools port.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const origin = process.env.CBIR_URL || "http://127.0.0.1:8000";
const devtools = process.env.CBIR_DEVTOOLS || "http://127.0.0.1:9223";
const tab = await (await fetch(`${devtools}/json/new?about:blank`, { method: "PUT" })).json();
const socket = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); });
let nextId = 1;
const pending = new Map();
const errors = [];
socket.addEventListener("message", (event) => {
  const data = JSON.parse(event.data);
  if (data.id) {
    const callbacks = pending.get(data.id);
    pending.delete(data.id);
    if (data.error) callbacks.reject(new Error(JSON.stringify(data.error))); else callbacks.resolve(data.result);
  }
  if (data.method === "Runtime.exceptionThrown") errors.push(data.params.exceptionDetails.text);
  if (data.method === "Runtime.consoleAPICalled" && data.params.type === "error") errors.push(JSON.stringify(data.params.args));
});
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await call("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function until(expression, timeout = 15000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    if (await evaluate(expression)) return;
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error(`Timed out: ${expression}`);
}
async function screenshot(name) {
  const result = await call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  const target = path.join(root, "artifacts", "figures", "native512", name);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, Buffer.from(result.data, "base64"));
  console.log(target);
}
try {
  await call("Page.enable"); await call("Runtime.enable");
  await call("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  await call("Page.navigate", { url: `${origin}/?profile=native512-v1#processing` });
  await until("document.readyState === 'complete' && document.querySelector('#view-processing.is-active') && document.querySelector('#processing-summary').textContent.includes('/600')");
  await until("[...document.querySelectorAll('#mask-review-grid img')].every(im => im.complete && im.naturalWidth === 512)");
  const state = await evaluate(`({profile: document.querySelector('#profile-select').value, actions: document.querySelectorAll('[data-processing-action]').length, cards: document.querySelectorAll('.mask-review-card').length, dimensions: document.querySelector('.sidebar-note').textContent, progress: document.querySelector('#processing-job').textContent})`);
  if (state.profile !== "native512-v1" || state.actions !== 3 || !state.dimensions.includes("512×512") || state.cards < 1) throw new Error(JSON.stringify(state));
  if (state.progress.includes("Có lỗi")) throw new Error(`Latest processing job failed: ${state.progress}`);
  await evaluate("document.querySelector('#review-select-page').click()");
  if (!await evaluate("[...document.querySelectorAll('.mask-review-checkbox:not(:disabled)')].every(im => im.checked)")) throw new Error("Review page selection failed");
  await screenshot("processing-ui.png");
  await evaluate("document.querySelector('[data-view=search]').click()");
  await until("document.querySelector('#view-search.is-active')");
  await screenshot("search-ui.png");
  await evaluate("document.querySelector('#profile-select').value = 'background512-white-v1'; document.querySelector('#profile-select').dispatchEvent(new Event('change', {bubbles:true}))");
  await until("document.readyState === 'complete' && window.__PROFILE__ === 'background512-white-v1'");
  if (!await evaluate("document.querySelector('#upload-zone small').textContent.includes('tự tách nền')")) throw new Error("Automatic query background hint missing");
  await call("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  if (await evaluate("document.documentElement.scrollWidth > innerWidth + 1")) throw new Error("Mobile page overflows horizontally");
  if (errors.length) throw new Error(JSON.stringify(errors));
  console.log(JSON.stringify({ ...state, browser_errors: errors.length, mobile_overflow: false, profile_switch: true }));
} finally {
  socket.close();
  await fetch(`${devtools}/json/close/${tab.id}`);
}
