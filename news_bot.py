import logging
import asyncio
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
TOKEN = "8004880517:AAE9CCfc1L-ORWLj7oU6tRYF98CZZIEf6MQ"  # Thay bằng token bot của bạn

# ====== GIÁ TRỊ LƯU LẠI CHO SO SÁNH GIÁ ======
last_prices = {
    "gold": None,
    "gas": None,
    "usd": None
}

subscribed_users = set()
event_loop = asyncio.get_event_loop()

# ====================== LẤY TIN RSS + SCRAPE ======================
def get_rss_news(url, source_name="📰", count=3):
    try:
        feed = feedparser.parse(url)
        entries = feed.entries[:count]
        return [f"{source_name} <b>{e.title}</b>\n{e.link}" for e in entries]
    except Exception as e:
        print(f"Lỗi khi lấy RSS từ {url}: {e}")
        return []

def scrape_baomoi(count=3):
    url = "https://baomoi.com/"
    try:
        resp = requests.get(url)
        resp.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("h3 a")[:count]
        return [f"📰 <b>Báo Mới: {a.text.strip()}</b>\nhttps://baomoi.com{a['href']}" for a in articles]
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi scrape Báo Mới: {e}")
        return []

def scrape_tukigroup(count=3):
    url = "https://tukigroup.vn/"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select(".elementor-post__title a")[:count]
        return [f"📌 <b>Tuki Group: {a.text.strip()}</b>\n{a['href']}" for a in articles]
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi scrape Tuki Group: {e}")
        return []

def scrape_gia_vang_24h():
    url = "https://www.24h.com.vn/gia-vang-hom-nay-c425.html"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        title_element = soup.find("h1")
        box = soup.select_one(".cate-24h-foot-new") or soup.select_one(".text-conent")
        if title_element and box:
            title = title_element.text.strip()
            return [f"💰 <b>{title}</b>\n{url}\n\n{box.text.strip()[:300]}..."]
        else:
            return []
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi scrape giá vàng 24h: {e}")
        return []
    except Exception as e:
        print(f"Lỗi khác khi xử lý giá vàng 24h: {e}")
        return []

def scrape_petrolimex():
    url = "https://www.petrolimex.com.vn/"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        price_table = soup.find("table")
        return [f"⛽ <b>Giá xăng mới nhất</b>\n{url}"] if price_table else []
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi scrape Petrolimex: {e}")
        return []

def scrape_gamek(count=3):
    url = "https://gamek.vn/"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select(".knswli a.knswli-title", limit=count)
        return [f"🎮 <b>Gamek: {a.text.strip()}</b>\nhttps://gamek.vn{a['href']}" for a in articles]
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi scrape Gamek: {e}")
        return []

def scrape_zingnews(count=3):
    url = "https://zingnews.vn/"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select(".article-title a", limit=count)
        return [f"📰 <b>Zing News: {a.text.strip()}</b>\nhttps://zingnews.vn{a['href']}" for a in articles]
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi scrape Zing News: {e}")
        return []

def scrape_thue(count=2):
    url = "https://www.gdt.gov.vn/wps/portal/home/tin-tuc/thong-bao-moi"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select(".portlet-body ul li a", limit=count)
        return [f"⚖️ <b>Thuế: {a.text.strip()}</b>\nhttps://www.gdt.gov.vn{a['href']}" for a in articles]
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi scrape thông tin thuế: {e}")
        return []

def get_all_news():
    news = []
    news += get_rss_news("https://vnexpress.net/rss/tin-moi-nhat.rss", "📰 VNExpress")
    news += get_rss_news("https://feeds.feedburner.com/TheHackersNews", "🛡️ THN")
    news += scrape_baomoi()
    news += scrape_tukigroup()
    news += scrape_gia_vang_24h()
    news += scrape_petrolimex()
    news += get_rss_news("http://feeds.reuters.com/reuters/worldNews", "🌍 Reuters World", count=2)
    news += get_rss_news("http://feeds.bbci.co.uk/news/world/rss.xml", "🌍 BBC World", count=2)
    news += get_rss_news("https://www.theverge.com/rss/pc/index.xml", "💻 The Verge (PC)", count=2)
    news += get_rss_news("https://openai.com/blog/rss.xml", "🤖 OpenAI Blog", count=2)
    news += get_rss_news("https://www.gamedeveloper.com/rss.xml", "🎮 Gamasutra", count=2)
    news += scrape_gamek(count=2)
    news += scrape_zingnews(count=2)
    news += scrape_thue(count=2)
    return "\n\n".join(news)

# ====================== LẤY GIÁ ======================
def get_gold_price():
    url = "https://www.24h.com.vn/gia-vang-hom-nay-c425.html"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        price_element = soup.find("strong")
        return price_element.text.strip() if price_element else None
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi lấy giá vàng: {e}")
        return None

def get_usd_price():
    try:
        url = "https://www.google.com/search?q=giá+đô"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        usd_element = soup.select_one("span.DFlfde")
        return usd_element.text.strip() if usd_element else None
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi lấy giá USD: {e}")
        return None

def get_gas_price():
    try:
        url = "https://www.petrolimex.com.vn/"
        r = requests.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if table:
            first_price_element = table.find_all("td")[1]
            return first_price_element.text.strip() if first_price_element else None
        return None
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi lấy giá xăng: {e}")
        return None

# ====================== HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    subscribed_users.add(user_id)
    await update.message.reply_text("✅ Bạn đã đăng ký nhận tin mỗi sáng và cảnh báo giá.\nGõ /news để xem tin mới nhất.")

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Đang cập nhật tin tức...")
    message = get_all_news()
    await update.message.reply_text(message, parse_mode='HTML')

async def send_daily_news(bot_app):
    message = get_all_news()
    for user_id in subscribed_users:
        try:
            await bot_app.bot.send_message(chat_id=user_id, text=message, parse_mode='HTML')
        except Exception as e:
            print(f"Lỗi gửi tin: {e}")

async def check_price_change(bot_app):
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
                await bot_app.bot.send_message(chat_id=user_id, text=message, parse_mode='HTML')
            except Exception as e:
                print(f"Lỗi gửi cảnh báo: {e}")

# ====================== LẬP LỊCH ======================
def schedule_jobs(bot_app):
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(send_daily_news(bot_app), event_loop),
        trigger='cron', hour=7, minute=0, timezone='Asia/Ho_Chi_Minh'
    )

    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(check_price_change(bot_app), event_loop),
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
