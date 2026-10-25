# VIP Telegram Bot - simple Python version

GitHub root ထဲမှာ `run.py`, `requirements.txt`, `render.yaml` ဖိုင် ၃ ခုတင်ပါ။ Render settings:

- Runtime: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `python run.py`
- Plan: Free

Environment Variables:

```text
BOT_TOKEN=BotFather token
OWNER_TELEGRAM_ID=8607494475
APP_API_KEY=long-random-secret
DB_PATH=vip.sqlite3
```

Bot menu: Pending, Active, Admins, Refresh. Pending request ကိုနှိပ်ပြီး 1/7/30 days, 1/3/6 months, 1 year သို့မဟုတ် Custom date/time ရွေးပါ။ Admins မှာ Owner က Admin ထည့်/ဖျက်နိုင်ပါတယ်။ User က Device ID ပို့ပြီး approve လုပ်တဲ့အခါ code ကို Telegram ကနေ ပြန်ရပါမယ်။ Custom date/time format က `2026-12-31 23:59:59` ဖြစ်ပြီး Myanmar Time (`UTC+06:30`) နဲ့ စစ်ပါတယ်။

UptimeRobot URL: `https://YOUR-RENDER-URL/health`

Free Render service က idle 15 minutes နောက် sleep ဖြစ်နိုင်ပြီး local SQLite file က restart/redeploy ဖြစ်ရင် ပျောက်နိုင်ပါတယ်။ စမ်းသပ်အသုံးအတွက်သာ သင့်တော်ပါတယ်။
