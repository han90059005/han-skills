// 从已打开的浏览器（CDP）里读某个标签页的 DOM 快照，不导航、不刷新。
// 用途：复用一个已经登录 / 过了 Cloudflare 的页面，避免无头浏览器被拦。
// 用法: node cdp_dom.mjs <cdpBaseUrl> <urlSubstring> <outFile>
import { writeFileSync } from 'node:fs';

const [cdpBase, needle, outFile] = process.argv.slice(2);
if (!cdpBase || !needle || !outFile) {
  console.error('usage: node cdp_dom.mjs <cdpBaseUrl> <urlSubstring> <outFile>');
  process.exit(2);
}

const base = cdpBase.replace(/\/$/, '');
const list = await (await fetch(`${base}/json/list`)).json();
const pages = list.filter(t => t.type === 'page' && t.webSocketDebuggerUrl);
const needles = needle.split('|').map(s => s.trim().toLowerCase()).filter(Boolean);
const matches = (t) => needles.some(n =>
  (t.url || '').toLowerCase().includes(n) || (t.title || '').toLowerCase().includes(n));
let target = pages.find(matches);
if (!target && pages.length === 1) target = pages[0];
if (!target) {
  console.error(`no tab matching "${needle}" among ${pages.length} pages`);
  process.exit(3);
}

const ws = new WebSocket(target.webSocketDebuggerUrl);
const done = (code, payload) => {
  try { ws.close(); } catch {}
  if (payload) console.log(JSON.stringify(payload));
  process.exit(code);
};

ws.addEventListener('open', () => {
  ws.send(JSON.stringify({
    id: 1,
    method: 'Runtime.evaluate',
    params: {
      expression: 'document.documentElement.outerHTML',
      returnByValue: true,
      awaitPromise: false,
    },
  }));
});

ws.addEventListener('message', (ev) => {
  let msg;
  try { msg = JSON.parse(ev.data); } catch { return; }
  if (msg.id !== 1) return;
  const html = msg.result?.result?.value;
  if (typeof html !== 'string' || html.length < 200) {
    done(4, { ok: false, error: 'DOM empty', url: target.url });
    return;
  }
  writeFileSync(outFile, html, 'utf8');
  done(0, { ok: true, url: target.url, title: target.title, bytes: html.length });
});

ws.addEventListener('error', (e) => done(5, { ok: false, error: String(e?.message || 'websocket error'), url: target.url }));
setTimeout(() => done(6, { ok: false, error: 'timeout', url: target.url }), 15000);
