const fs = require("node:fs");
const [,, cdp, tid, flag, file] = process.argv;
let expr = process.argv[5] || "";
if (flag === "--file" && file) expr = fs.readFileSync(file, "utf-8");
(async () => {
  const list = await (await fetch(cdp + "/json/list")).json();
  const t = list.find(x => x.id === tid) || list.find(x => x.type === "page");
  if (!t) { console.error("no tab"); process.exit(2); }
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0; const pend = new Map();
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const i = ++id; pend.set(i, m => m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result));
    ws.send(JSON.stringify({ id: i, method, params }));
    setTimeout(() => { if (pend.has(i)) { pend.delete(i); rej(new Error("timeout")); } }, 30000);
  });
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
  if (r.exceptionDetails) {
    const d = r.exceptionDetails;
    const msg = (d.exception && (d.exception.description || d.exception.value)) || d.text || "unknown";
    console.error("JS_ERROR: " + msg);
    process.exit(3);
  }
  process.stdout.write(r.result && r.result.value != null ? String(r.result.value) : "");
  ws.close();
})().catch(e => { console.error(e.message); process.exit(1); });