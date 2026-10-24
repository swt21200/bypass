# VIP Telegram Activation

Render Web Service အတွက် Telegram VIP activation backend ဖြစ်ပါတယ်။ User က Bot ကို Device ID ပို့ပြီး request တင်နိုင်ပါတယ်။ Admin menu မှာ Pending, Active, Admins tabs တွေကနေ approve, expiry, revoke နဲ့ multi-admin စီမံနိုင်ပါတယ်။

## Bot menu flow

- User: Bot ကို Device ID ပို့ပါ။
- Admin: `Pending` tab → request ကိုနှိပ် → `1 day`, `7 days`, `30 days` သို့မဟုတ် `Custom date` ရွေးပါ။
- Custom date: `YYYY-MM-DD HH:mm:ss` ကို Myanmar time (`UTC+06:30`) နဲ့ ပို့ပါ။
- Code generate ပြီး user ဆီ Telegram ကနေ အလိုအလျောက်ပို့ပါမယ်။
- `Active` tab မှာ license ကြည့်ပြီး `Revoke` လုပ်နိုင်ပါတယ်။
- `Admins` tab မှာ Owner က Admin အရေအတွက်ကန့်သတ်ချက်မရှိ ထည့်/ဖျက်နိုင်ပါတယ်။ Owner ပဲ Admin management လုပ်နိုင်ပါတယ်။

## Render setup

1. ဒီ folder ကို GitHub repository အသစ်ထဲ push လုပ်ပါ။
2. Render မှာ **New Web Service** → repository ကိုရွေးပါ။
3. Build command: `npm install`
4. Start command: `npm start`
5. Environment Variables ထည့်ပါ:

```text
BOT_TOKEN=BotFather က ရတဲ့ token
OWNER_TELEGRAM_ID=သင့် Telegram numeric user ID
APP_API_KEY=ရှည်လျားတဲ့ random secret
DB_PATH=/var/data/vip.sqlite
```

Render Free Web Service ရဲ့ filesystem က persistent မဖြစ်နိုင်တဲ့အတွက် production သုံးမယ်ဆို persistent disk သို့မဟုတ် PostgreSQL ထည့်သုံးပါ။ `healthCheckPath` က `/health` ဖြစ်ပါတယ်။ UptimeRobot မှာ `https://YOUR-SERVICE.onrender.com/health` ကို HTTP monitor အဖြစ်ထည့်နိုင်ပါတယ်။ UptimeRobot ping လုပ်ပေမယ့် hosting plan ရဲ့ sleep/limits ကို အာမမခံနိုင်ပါ။

## App ချိတ်ရန်

App က `/api/activate` ကို POST လုပ်ရပါမယ်။ Header မှာ `x-api-key: APP_API_KEY` ထည့်ပြီး body ကို ဒီလိုပို့ပါ:

```json
{"deviceId":"ANDROID_ID","code":"VIP-XXXX-YYYY"}
```

Response `{"ok":true,"expiresAt":"..."}` ရရင် activation အောင်မြင်ပါတယ်။ APK ထဲက API URL ကို Render service URL နဲ့ build မလုပ်မီ အစားထိုးရပါမယ်။ `BOT_TOKEN` ကို APK ထဲ မထည့်ပါနှင့်။
