import logging
import feedparser
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from apscheduler.schedulers.background import BackgroundScheduler

# ====================== CONFIG ======================
TOKEN = "8004880517:AAE9CCfc1L-ORWLj7oU6tRYF98CZZIEf6MQ"

# ====== GIÁ TRỊ LƯU LẠI CHO SO SÁNH GIÁ ======
last_prices = {
    "gold": None,
    "gas": None,
    "usd": None
}

# Danh sách người đã dùng /start
subscribed_users = set()

# ====================== LẤY TIN RSS + SCRAPE ======================
def get_rss_news(url, count=3):
    feed = feedparser.parse(url)
    entries = feed.entries[:count]
    return [f"📰 <b>{e.title}</b>\n{e.link}" for e in entries]

def scrape_baomoi(count=3):
    url = "https://baomoi.com/"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.select("h3 a")[:count]
    return [f"📰 <b>{a.text.strip()}</b>\nhttps://baomoi.com{a['href']}" for a in articles]

def scrape_tukigroup(count=3):
    url = "https://tukigroup.vn/"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.select(".elementor-post__title a")[:count]
    return [f"📌 <b>{a.text.strip()}</b>\n{a['href']}" for a in articles]

def scrape_gia_vang_24h():
    url = "https://www.24h.com.vn/gia-vang-hom-nay-c425.html"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    try:
        title = soup.find("h1").text
        box = soup.select_one(".cate-24h-foot-new") or soup.select_one(".text-conent")
        return [f"💰 <b>{title}</b>\n{url}\n\n{box.text.strip()[:300]}..."] if box else []
    except Exception:
        return []

def scrape_petrolimex():
    url = "https://www.petrolimex.com.vn/"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    price_table = soup.find("table")
    return [f"⛽ <b>Giá xăng mới nhất</b>\n{url}"] if price_table else []

def get_all_news():
    news = []
    news += get_rss_news("https://vnexpress.net/rss/tin-moi-nhat.rss")
    news += get_rss_news("https://feeds.feedburner.com/TheHackersNews")
    news += scrape_baomoi()
    news += scrape_tukigroup()
    news += scrape_gia_vang_24h()
    news += scrape_petrolimex()
    return "\n\n".join(news)

# ====================== LẤY GIÁ RIÊNG ======================
def get_gold_price():
    url = "https://www.24h.com.vn/gia-vang-hom-nay-c425.html"
    try:
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        price = soup.find("strong").text.strip()
        return price
    except:
        return None

def get_usd_price():
    try:
        url = "https://www.google.com/search?q=giá+đô"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        usd = soup.select_one("span.DFlfde").text.strip()
        return usd
    except:
        return None

def get_gas_price():
    try:
        url = "https://www.petrolimex.com.vn/"
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if table:
            first_price = table.find_all("td")[1].text.strip()
            return first_price
        return None
    except:
        return None

# ====================== BOT HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    subscribed_users.add(user_id)
    await update.message.reply_text("✅ Bạn đã đăng ký nhận tin mỗi sáng và cảnh báo giá.\nGõ /news để xem tin mới nhất.")

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Đang cập nhật tin tức...")
    message = get_all_news()
    await update.message.reply_text(message, parse_mode='HTML')

async def send_daily_news(context: ContextTypes.DEFAULT_TYPE):
    message = get_all_news()
    for user_id in subscribed_users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message, parse_mode='HTML')
        except Exception as e:
            print(f"Lỗi gửi tin: {e}")

async def check_price_change(context: ContextTypes.DEFAULT_TYPE):
    global last_prices
    gold = get_gold_price()
    usd = get_usd_price()
    gas = get_gas_price()

    changes = []

    if gold and gold != last_prices["gold"]:
        changes.append(f"💰 Giá vàng thay đổi: {last_prices['gold']} → {gold}")
        last_prices["gold"] = gold

    if usd and usd != last_prices["usd"]:
        changes.append(f"💵 Giá USD thay đổi: {last_prices['usd']} → {usd}")
        last_prices["usd"] = usd

    if gas and gas != last_prices["gas"]:
        changes.append(f"⛽ Giá xăng thay đổi: {last_prices['gas']} → {gas}")
        last_prices["gas"] = gas

    if changes:
        message = "🔔 <b>Cập nhật giá thay đổi:</b>\n" + "\n".join(changes)
        for user_id in subscribed_users:
            try:
                await context.bot.send_message(chat_id=user_id, text=message, parse_mode='HTML')
            except Exception as e:
                print(f"Lỗi gửi cảnh báo: {e}")

# ====================== LẬP LỊCH ======================
def schedule_jobs(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: app.create_task(send_daily_news(app.bot)),
        trigger='cron', hour=7, minute=0
    )
    scheduler.add_job(
        lambda: app.create_task(check_price_change(app.bot)),
        trigger='interval', minutes=5
    )
    scheduler.start()

# ====================== MAIN ======================
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))

    schedule_jobs(app)

    print("🤖 Bot đang chạy...")
    app.run_polling()
