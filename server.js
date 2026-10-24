import 'dotenv/config';
import express from 'express';
import Database from 'better-sqlite3';
import crypto from 'node:crypto';
import { Telegraf, Markup } from 'telegraf';

const port = Number(process.env.PORT || 10000);
const botToken = process.env.BOT_TOKEN;
const ownerId = String(process.env.OWNER_TELEGRAM_ID || '');
const apiKey = process.env.APP_API_KEY || '';
const db = new Database(process.env.DB_PATH || './vip.sqlite');

db.pragma('journal_mode = WAL');
db.exec(`
  CREATE TABLE IF NOT EXISTS admins (
    telegram_id TEXT PRIMARY KEY,
    role TEXT NOT NULL DEFAULT 'admin',
    created_at TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS licenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    telegram_id TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
  );
`);
if (ownerId) db.prepare('INSERT OR IGNORE INTO admins (telegram_id, role, created_at) VALUES (?, ?, ?)').run(ownerId, 'owner', new Date().toISOString());

const app = express();
app.use(express.json({ limit: '32kb' }));
app.get('/health', (_req, res) => res.json({ ok: true, service: 'vip-telegram-activation', time: new Date().toISOString() }));
app.get('/', (_req, res) => res.send('VIP activation service is running'));

function authorized(req) {
  return apiKey && req.get('x-api-key') === apiKey;
}
app.post('/api/activate', (req, res) => {
  if (!authorized(req)) return res.status(401).json({ ok: false, error: 'unauthorized' });
  const deviceId = String(req.body?.deviceId || '').trim();
  const code = String(req.body?.code || '').trim();
  if (!deviceId || !code) return res.status(400).json({ ok: false, error: 'deviceId and code are required' });
  const row = db.prepare('SELECT device_id, expires_at FROM licenses WHERE device_id = ? AND code = ? AND revoked = 0 ORDER BY id DESC LIMIT 1').get(deviceId, code);
  if (!row) return res.status(403).json({ ok: false, error: 'invalid_device_or_code' });
  const expiry = Date.parse(row.expires_at);
  if (!Number.isFinite(expiry) || expiry <= Date.now()) return res.status(403).json({ ok: false, error: 'expired' });
  return res.json({ ok: true, deviceId, expiresAt: row.expires_at });
});

if (!botToken) {
  console.error('BOT_TOKEN is missing');
  process.exit(1);
}
const bot = new Telegraf(botToken);
const awaiting = new Map();

function isAdmin(id) { return !!db.prepare('SELECT 1 FROM admins WHERE telegram_id = ?').get(String(id)); }
function isOwner(id) { return String(id) === ownerId; }
function now() { return new Date().toISOString(); }
function menu() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('📥 Pending', 'tab:pending'), Markup.button.callback('✅ Active', 'tab:active')],
    [Markup.button.callback('👥 Admins', 'tab:admins'), Markup.button.callback('🔄 Refresh', 'tab:home')]
  ]);
}
function adminPanel(ctx, text = 'VIP Admin Panel') { return ctx.reply(text, menu()); }
function dateLabel(iso) { return new Date(iso).toLocaleString('en-GB', { timeZone: 'Asia/Yangon', hour12: false }); }
function parseMyanmarDate(s) {
  const m = String(s).trim().match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$/);
  if (!m) return null;
  const [, y, mo, d, h, mi, sec = '00'] = m;
  const t = Date.parse(`${y}-${mo}-${d}T${h}:${mi}:${sec}+06:30`);
  return Number.isFinite(t) ? new Date(t).toISOString() : null;
}
function newCode() { return `VIP-${crypto.randomBytes(3).toString('hex').toUpperCase()}-${crypto.randomBytes(2).toString('hex').toUpperCase()}`; }

bot.start(ctx => {
  if (isAdmin(ctx.from.id)) return adminPanel(ctx);
  return ctx.reply('Send your Device ID here. Then an admin will approve your VIP access.');
});
bot.command('admin', ctx => isAdmin(ctx.from.id) ? adminPanel(ctx) : ctx.reply('This menu is for admins only.'));

bot.on('text', async ctx => {
  const text = ctx.message.text.trim();
  const uid = String(ctx.from.id);
  if (text.startsWith('/')) return;
  if (isAdmin(uid) && awaiting.has(uid)) {
    const state = awaiting.get(uid);
    if (state.type === 'add_admin' && isOwner(uid)) {
      const target = text.replace(/[^0-9]/g, '');
      if (!target) return ctx.reply('Send a numeric Telegram User ID.');
      db.prepare('INSERT OR IGNORE INTO admins (telegram_id, role, created_at) VALUES (?, ?, ?)').run(target, 'admin', now());
      awaiting.delete(uid);
      return ctx.reply(`Admin added: ${target}`, menu());
    }
    if (state.type === 'custom_expiry') {
      const exp = parseMyanmarDate(text);
      if (!exp || Date.parse(exp) <= Date.now()) return ctx.reply('Invalid or past date. Use: 2026-10-27 23:00:00');
      awaiting.delete(uid);
      return approveRequest(ctx, state.requestId, exp);
    }
  }
  if (!/^[-A-Za-z0-9_:.]{4,100}$/.test(text)) return ctx.reply('Please send a valid Device ID.');
  const existing = db.prepare("SELECT id FROM requests WHERE telegram_id = ? AND status = 'pending'").get(uid);
  if (existing) return ctx.reply(`Request #${existing.id} is already pending.`);
  const t = now();
  const result = db.prepare('INSERT INTO requests (telegram_id, chat_id, device_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)').run(uid, String(ctx.chat.id), text, t, t);
  await ctx.reply(`Device ID received. Request #${result.lastInsertRowid} is waiting for admin approval.`);
  for (const a of db.prepare('SELECT telegram_id FROM admins').all()) {
    try { await bot.telegram.sendMessage(a.telegram_id, `New VIP request #${result.lastInsertRowid}\nDevice ID: ${text}`, Markup.inlineKeyboard([[Markup.button.callback('Review / Approve', `req:${result.lastInsertRowid}`)]])); } catch {}
  }
});

async function showPending(ctx) {
  const rows = db.prepare("SELECT * FROM requests WHERE status = 'pending' ORDER BY id DESC LIMIT 30").all();
  if (!rows.length) return ctx.editMessageText('Pending: empty', menu());
  const buttons = rows.map(r => [Markup.button.callback(`#${r.id} • ${r.device_id.slice(0, 18)}`, `req:${r.id}`)]);
  return ctx.editMessageText('📥 Pending requests', Markup.inlineKeyboard([...buttons, [Markup.button.callback('Back', 'tab:home')]]));
}
async function showActive(ctx) {
  const rows = db.prepare('SELECT * FROM licenses WHERE revoked = 0 ORDER BY id DESC LIMIT 30').all();
  if (!rows.length) return ctx.editMessageText('Active: empty', menu());
  const buttons = rows.map(r => [Markup.button.callback(`${r.device_id.slice(0, 15)} • ${dateLabel(r.expires_at)}`, `lic:${r.id}`)]);
  return ctx.editMessageText('✅ Active licenses', Markup.inlineKeyboard([...buttons, [Markup.button.callback('Back', 'tab:home')]]));
}
async function showAdmins(ctx) {
  if (!isOwner(ctx.from.id)) return ctx.answerCbQuery('Owner only');
  const rows = db.prepare('SELECT * FROM admins ORDER BY role DESC, telegram_id').all();
  const buttons = rows.map(r => [Markup.button.callback(`${r.role === 'owner' ? '👑' : '👤'} ${r.telegram_id}`, r.role === 'owner' ? 'noop' : `deladmin:${r.telegram_id}`)]);
  buttons.push([Markup.button.callback('➕ Add Admin', 'addadmin')], [Markup.button.callback('Back', 'tab:home')]);
  return ctx.editMessageText('👥 Admin Management\nTap an admin to remove.', Markup.inlineKeyboard(buttons));
}
async function approveRequest(ctx, requestId, exp) {
  const req = db.prepare("SELECT * FROM requests WHERE id = ? AND status = 'pending'").get(requestId);
  if (!req) return ctx.reply('Request is no longer pending.');
  const code = newCode();
  db.prepare('INSERT INTO licenses (request_id, telegram_id, chat_id, device_id, code, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)').run(req.id, req.telegram_id, req.chat_id, req.device_id, code, exp, now());
  db.prepare("UPDATE requests SET status = 'approved', updated_at = ? WHERE id = ?").run(now(), req.id);
  await ctx.reply(`Approved #${req.id}\nDevice: ${req.device_id}\nExpiry: ${dateLabel(exp)}\nCode: ${code}`);
  try { await bot.telegram.sendMessage(req.chat_id, `VIP approved ✅\nDevice ID: ${req.device_id}\nCode: ${code}\nExpiry: ${dateLabel(exp)}`); } catch {}
}

bot.action('noop', ctx => ctx.answerCbQuery());
bot.action('tab:home', ctx => { ctx.answerCbQuery(); return ctx.editMessageText('VIP Admin Panel', menu()); });
bot.action('tab:pending', ctx => { if (!isAdmin(ctx.from.id)) return ctx.answerCbQuery('Admin only'); ctx.answerCbQuery(); return showPending(ctx); });
bot.action('tab:active', ctx => { if (!isAdmin(ctx.from.id)) return ctx.answerCbQuery('Admin only'); ctx.answerCbQuery(); return showActive(ctx); });
bot.action('tab:admins', ctx => { ctx.answerCbQuery(); return showAdmins(ctx); });
bot.action(/^req:(\d+)$/, ctx => {
  if (!isAdmin(ctx.from.id)) return ctx.answerCbQuery('Admin only');
  const id = Number(ctx.match[1]); const r = db.prepare("SELECT * FROM requests WHERE id = ? AND status = 'pending'").get(id);
  if (!r) return ctx.answerCbQuery('Not pending');
  return ctx.editMessageText(`Request #${r.id}\nDevice ID: ${r.device_id}\nChoose expiry:`, Markup.inlineKeyboard([
    [Markup.button.callback('1 day', `exp:${id}:1`), Markup.button.callback('7 days', `exp:${id}:7`), Markup.button.callback('30 days', `exp:${id}:30`)],
    [Markup.button.callback('Custom date', `custom:${id}`)], [Markup.button.callback('Back', 'tab:pending')]
  ]));
});
bot.action(/^exp:(\d+):(\d+)$/, async ctx => { if (!isAdmin(ctx.from.id)) return ctx.answerCbQuery('Admin only'); ctx.answerCbQuery(); const exp = new Date(Date.now() + Number(ctx.match[2]) * 86400000).toISOString(); return approveRequest(ctx, Number(ctx.match[1]), exp); });
bot.action(/^custom:(\d+)$/, ctx => { if (!isAdmin(ctx.from.id)) return ctx.answerCbQuery('Admin only'); awaiting.set(String(ctx.from.id), { type: 'custom_expiry', requestId: Number(ctx.match[1]) }); return ctx.reply('Send expiry in Myanmar time: 2026-10-27 23:00:00'); });
bot.action(/^lic:(\d+)$/, async ctx => { if (!isAdmin(ctx.from.id)) return ctx.answerCbQuery('Admin only'); const id = Number(ctx.match[1]); const r = db.prepare('SELECT * FROM licenses WHERE id = ?').get(id); if (!r) return ctx.answerCbQuery('Not found'); return ctx.editMessageText(`Device: ${r.device_id}\nExpiry: ${dateLabel(r.expires_at)}\nCode: ${r.code}`, Markup.inlineKeyboard([[Markup.button.callback('Revoke', `revoke:${id}`)], [Markup.button.callback('Back', 'tab:active')]])); });
bot.action(/^revoke:(\d+)$/, async ctx => { if (!isAdmin(ctx.from.id)) return ctx.answerCbQuery('Admin only'); db.prepare('UPDATE licenses SET revoked = 1 WHERE id = ?').run(Number(ctx.match[1])); await ctx.answerCbQuery('Revoked'); return showActive(ctx); });
bot.action('addadmin', ctx => { if (!isOwner(ctx.from.id)) return ctx.answerCbQuery('Owner only'); awaiting.set(String(ctx.from.id), { type: 'add_admin' }); return ctx.reply('Send the new admin Telegram numeric User ID.'); });
bot.action(/^deladmin:(\d+)$/, async ctx => { if (!isOwner(ctx.from.id)) return ctx.answerCbQuery('Owner only'); db.prepare('DELETE FROM admins WHERE telegram_id = ? AND role != \'owner\'').run(ctx.match[1]); await ctx.answerCbQuery('Admin removed'); return showAdmins(ctx); });

app.listen(port, () => console.log(`HTTP listening on ${port}`));
bot.launch().then(() => console.log('Telegram bot started'));
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
