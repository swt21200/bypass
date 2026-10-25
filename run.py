import os, re, json, time, sqlite3, secrets, threading
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
import requests

TOKEN = os.environ.get('BOT_TOKEN', '')
OWNER = str(os.environ.get('OWNER_TELEGRAM_ID', ''))
API_KEY = os.environ.get('APP_API_KEY', '')
PORT = int(os.environ.get('PORT', '10000'))
DB = os.environ.get('DB_PATH', 'vip.sqlite3')
TG = f'https://api.telegram.org/bot{TOKEN}'
app = Flask(__name__)
lock = threading.Lock()
state = {}

def conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def setup():
    c = conn()
    c.executescript('''CREATE TABLE IF NOT EXISTS admins(id TEXT PRIMARY KEY, role TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, tg TEXT, chat TEXT, device TEXT, status TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS licenses(id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER, tg TEXT, chat TEXT, device TEXT, code TEXT UNIQUE, expires TEXT, revoked INTEGER DEFAULT 0, created TEXT);''')
    if OWNER: c.execute('INSERT OR IGNORE INTO admins VALUES(?,?,?)', (OWNER, 'owner', now()))
    c.commit(); c.close()

def now(): return datetime.now(timezone.utc).isoformat()
def local_date(iso):
    try: return datetime.fromisoformat(iso).astimezone(timezone(timedelta(hours=6, minutes=30))).strftime('%Y-%m-%d %H:%M:%S')
    except: return iso
def send(chat, text, keyboard=None):
    data = {'chat_id': chat, 'text': text}
    if keyboard: data['reply_markup'] = json.dumps({'inline_keyboard': keyboard})
    try: requests.post(TG + '/sendMessage', data=data, timeout=20)
    except Exception as e: print('send:', e)
def send_menu(chat, text='VIP Admin Panel'):
    data = {'chat_id': chat, 'text': text, 'reply_markup': json.dumps({
        'keyboard': [[{'text':'📥 Pending'}, {'text':'✅ Active'}], [{'text':'👥 Admins'}, {'text':'🔄 Refresh'}]],
        'resize_keyboard': True, 'is_persistent': True, 'input_field_placeholder': 'Choose an admin menu'
    })}
    try: requests.post(TG + '/sendMessage', data=data, timeout=20)
    except Exception as e: print('menu:', e)
def edit(chat, msg, text, keyboard=None):
    data = {'chat_id': chat, 'message_id': msg, 'text': text}
    if keyboard: data['reply_markup'] = json.dumps({'inline_keyboard': keyboard})
    try: requests.post(TG + '/editMessageText', data=data, timeout=20)
    except: pass
def answer(cid, text=''): 
    try: requests.post(TG + '/answerCallbackQuery', data={'callback_query_id': cid, 'text': text}, timeout=10)
    except: pass
def admin(uid):
    c=conn(); r=c.execute('SELECT 1 FROM admins WHERE id=?',(str(uid),)).fetchone(); c.close(); return bool(r)
def owner(uid): return str(uid) == OWNER
def menu(): return [[('📥 Pending','pending'),('✅ Active','active')],[('👥 Admins','admins'),('🔄 Refresh','home')]]
def kb(rows): return [[{'text':a,'callback_data':b} for a,b in row] for row in rows]
def code(): return 'VIP-' + secrets.token_hex(3).upper() + '-' + secrets.token_hex(2).upper()
def expiry(days): return (datetime.now(timezone.utc)+timedelta(days=days)).isoformat()

def approve(chat, rid, days):
    c=conn(); r=c.execute("SELECT * FROM requests WHERE id=? AND status='pending'",(rid,)).fetchone()
    if not r: c.close(); send(chat,'Request is no longer pending.'); return
    ex = days if isinstance(days, str) else expiry(days)
    co=code(); c.execute('INSERT INTO licenses(request_id,tg,chat,device,code,expires,created) VALUES(?,?,?,?,?,?,?)',(rid,r['tg'],r['chat'],r['device'],co,ex,now())); c.execute("UPDATE requests SET status='approved' WHERE id=?",(rid,)); c.commit(); c.close()
    copy_button = [[{'text':'📋 Copy Code','copy_text':{'text':co}}]]
    send(chat, f'Approved #{rid}\nDevice: {r["device"]}\nExpiry: {local_date(ex)}\nCode: {co}', copy_button)
    send(r['chat'], f'VIP approved ✅\nDevice ID: {r["device"]}\nCode: {co}\nExpiry: {local_date(ex)}', copy_button)

def show_pending(chat, msg=None):
    c=conn(); rows=c.execute("SELECT * FROM requests WHERE status='pending' ORDER BY id DESC LIMIT 30").fetchall(); c.close()
    rows = rows or []
    buttons = [[(f'#{r["id"]} • {r["device"][:18]}', f'req:{r["id"]}')] for r in rows] or [[('Empty','noop')]]
    buttons.append([('Back','home')]); text='📥 Pending requests\nChoose a request:'
    (edit(chat,msg,text,kb(buttons)) if msg else send(chat,text,kb(buttons)))

def show_active(chat,msg=None):
    c=conn(); rows=c.execute('SELECT * FROM licenses WHERE revoked=0 ORDER BY id DESC LIMIT 30').fetchall(); c.close()
    buttons=[[(f'{r["device"][:15]} • {local_date(r["expires"])}',f'lic:{r["id"]}')] for r in rows] or [[('Empty','noop')]]
    buttons.append([('Back','home')]); text='✅ Active licenses'
    (edit(chat,msg,text,kb(buttons)) if msg else send(chat,text,kb(buttons)))

def show_admins(chat,msg):
    c=conn(); rows=c.execute('SELECT * FROM admins ORDER BY role DESC,id').fetchall(); c.close()
    buttons=[[(('👑 ' if r['role']=='owner' else '👤 ')+r['id'], 'noop' if r['role']=='owner' else 'del:'+r['id'])] for r in rows]
    buttons += [[('➕ Add Admin','add')],[('Back','home')]]
    edit(chat,msg,'👥 Admin Management\nTap an admin to remove.',kb(buttons))

def handle_message(m):
    chat=str(m['chat']['id']); uid=str(m['from']['id']); text=m.get('text','').strip()
    if text == '/start' or text == '/admin':
        if admin(uid): send_menu(chat)
        else: send(chat,'Send your Device ID here.')
        return
    if not text or text.startswith('/'): return
    if admin(uid) and text in ('📥 Pending', '✅ Active', '👥 Admins', '🔄 Refresh'):
        if text == '📥 Pending': show_pending(chat)
        elif text == '✅ Active': show_active(chat)
        elif text == '👥 Admins':
            if owner(uid): send(chat, '👥 Admin Management', kb([[('➕ Add Admin','add')]]))
            else: send(chat, 'Owner only')
        else: send_menu(chat)
        return
    if admin(uid) and state.get(uid) == 'add_admin' and owner(uid):
        target=re.sub(r'[^0-9]','',text)
        if target:
            c=conn(); c.execute('INSERT OR IGNORE INTO admins VALUES(?,?,?)',(target,'admin',now())); c.commit(); c.close(); state.pop(uid,None); send_menu(chat,'Admin added: '+target)
        else: send(chat,'Send numeric Telegram User ID.')
        return
    if admin(uid) and isinstance(state.get(uid), dict) and state[uid].get('type') == 'custom_expiry':
        value=text.strip()
        try:
            dt=datetime.strptime(value, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=6, minutes=30)))
            if dt <= datetime.now(dt.tzinfo): raise ValueError()
            rid=state[uid]['request_id']; state.pop(uid,None); approve(chat, rid, (dt.astimezone(timezone.utc)).isoformat())
        except ValueError:
            send(chat,'Invalid date. Use: 2026-12-31 23:59:59')
        return
    if not re.fullmatch(r'[-A-Za-z0-9_:.]{4,100}',text): send(chat,'Please send a valid Device ID.'); return
    c=conn(); existing=c.execute("SELECT id FROM requests WHERE tg=? AND status='pending'",(uid,)).fetchone()
    if existing: c.close(); send(chat,f'Request #{existing["id"]} is already pending.'); return
    cur=c.execute('INSERT INTO requests(tg,chat,device,status,created) VALUES(?,?,?,?,?)',(uid,chat,text,'pending',now())); rid=cur.lastrowid; c.commit(); admins=c.execute('SELECT id FROM admins').fetchall(); c.close(); send(chat,f'Device ID received. Request #{rid} is waiting for approval.')
    for a in admins: send(a['id'],f'New VIP request #{rid}\nDevice ID: {text}',kb([[('Review / Approve',f'req:{rid}')]]))

def callback(q):
    uid=str(q['from']['id']); chat=str(q['message']['chat']['id']); msg=q['message']['message_id']; data=q.get('data',''); cid=q['id']
    if data=='noop': answer(cid); return
    if not admin(uid): answer(cid,'Admin only'); return
    answer(cid)
    if data=='home': edit(chat,msg,'VIP Admin Panel',kb(menu()))
    elif data=='pending': show_pending(chat,msg)
    elif data=='active': show_active(chat,msg)
    elif data=='admins': show_admins(chat,msg) if owner(uid) else answer(cid,'Owner only')
    elif data=='add': state[uid]='add_admin'; send(chat,'Send the new admin Telegram numeric User ID.') if owner(uid) else answer(cid,'Owner only')
    elif data.startswith('del:') and owner(uid):
        c=conn(); c.execute("DELETE FROM admins WHERE id=? AND role!='owner'",(data[4:],)); c.commit(); c.close(); show_admins(chat,msg)
    elif data.startswith('req:'):
        rid=data[4:]; c=conn(); r=c.execute("SELECT * FROM requests WHERE id=? AND status='pending'",(rid,)).fetchone(); c.close()
        if r: edit(chat,msg,f'Request #{rid}\nDevice ID: {r["device"]}\nChoose expiry:',kb([[('1 day',f'app:{rid}:1'),('7 days',f'app:{rid}:7'),('30 days',f'app:{rid}:30')],[('1 month',f'month:{rid}:1'),('3 months',f'month:{rid}:3'),('6 months',f'month:{rid}:6')],[('1 year',f'year:{rid}:1'),('Custom date/time',f'custom:{rid}')],[('Back','pending')]]))
    elif data.startswith('app:'):
        _,rid,days=data.split(':'); approve(chat,int(rid),int(days))
    elif data.startswith('month:'):
        _,rid,months=data.split(':'); approve(chat,int(rid),int(months)*30)
    elif data.startswith('year:'):
        _,rid,years=data.split(':'); approve(chat,int(rid),int(years)*365)
    elif data.startswith('custom:'):
        rid=int(data.split(':')[1]); state[uid]={'type':'custom_expiry','request_id':rid}; send(chat,'Send expiry in Myanmar time: 2026-12-31 23:59:59')
    elif data.startswith('lic:'):
        c=conn(); r=c.execute('SELECT * FROM licenses WHERE id=?',(data[4:],)).fetchone(); c.close()
        if r: edit(chat,msg,f'Device: {r["device"]}\nExpiry: {local_date(r["expires"])}\nCode: {r["code"]}',kb([[('Revoke',f'rev:{r["id"]}')],[('Back','active')]]))
    elif data.startswith('rev:'):
        c=conn(); c.execute('UPDATE licenses SET revoked=1 WHERE id=?',(data[4:],)); c.commit(); c.close(); show_active(chat,msg)

def poll():
    offset=0
    while True:
        try:
            r=requests.get(TG+'/getUpdates',params={'timeout':25,'offset':offset},timeout=35).json()
            for u in r.get('result',[]):
                offset=u['update_id']+1
                if 'message' in u: handle_message(u['message'])
                elif 'callback_query' in u: callback(u['callback_query'])
        except Exception as e: print('poll:',e); time.sleep(3)

@app.get('/health')
def health(): return jsonify(ok=True, service='vip-telegram-python', time=now())
@app.post('/api/activate')
def activate():
    if not API_KEY or request.headers.get('x-api-key') != API_KEY: return jsonify(ok=False,error='unauthorized'),401
    body=request.get_json(silent=True) or {}; device=str(body.get('deviceId','')).strip(); co=str(body.get('code','')).strip(); c=conn(); r=c.execute('SELECT * FROM licenses WHERE device=? AND code=? AND revoked=0 ORDER BY id DESC LIMIT 1',(device,co)).fetchone(); c.close()
    if not r: return jsonify(ok=False,error='invalid_device_or_code'),403
    if datetime.fromisoformat(r['expires']).timestamp() <= time.time(): return jsonify(ok=False,error='expired'),403
    return jsonify(ok=True,deviceId=device,expiresAt=r['expires'])

if __name__=='__main__':
    setup()
    if not TOKEN: raise SystemExit('BOT_TOKEN is missing')
    threading.Thread(target=poll,daemon=True).start()
    app.run(host='0.0.0.0',port=PORT)
