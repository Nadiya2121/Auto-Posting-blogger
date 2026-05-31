# bot.py
import sqlite3
import time
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import feedparser
import telebot
from telebot import types
import config

# টেলিগ্রাম বট ইনিশিয়ালাইজ করা
bot = telebot.TeleBot(config.BOT_TOKEN)

# ডাটাবেজ কানেকশন এবং টেবিল তৈরি
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # ইউজার টেবিল
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (telegram_id INTEGER PRIMARY KEY, email TEXT)''')
    # সেটিংস টেবিল
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings
                      (key TEXT PRIMARY KEY, value TEXT)''')
    # সিঙ্ক হিস্টোরি টেবিল
    cursor.execute('''CREATE TABLE IF NOT EXISTS sync_history
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       telegram_id INTEGER,
                       post_title TEXT,
                       status TEXT,
                       timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# প্রধান মেনু বাটন (৪টি বাটন লেআউট)
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🔌 Connect Blogger")
    btn2 = types.KeyboardButton("📊 My Status")
    btn3 = types.KeyboardButton("📈 Sync History")
    btn4 = types.KeyboardButton("❌ Disconnect")
    
    markup.row(btn1)           # প্রথম লাইনে কানেক্ট বাটন
    markup.row(btn2, btn3)     # দ্বিতীয় লাইনে স্ট্যাটাস এবং হিস্টোরি বাটন
    markup.row(btn4)           # তৃতীয় লাইনে ডিসকানেক্ট বাটন
    return markup

# /start কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "স্বাগতম! মুভি সিঙ্ক বটে আপনাকে অভিনন্দন।\n\n"
        "নিচের বাটনগুলো ব্যবহার করে আপনার ব্লগের সিক্রেট ইমেইলটি যুক্ত করুন।"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_keyboard())

# কানেক্ট বাটন হ্যান্ডলার
@bot.message_handler(func=lambda message: message.text == "🔌 Connect Blogger")
def ask_email(message):
    msg = bot.send_message(
        message.chat.id, 
        "দয়া করে আপনার ব্লগারের পোস্ট করার গোপন ইমেইলটি দিন (যেমন: username.secret@blogger.com):"
    )
    bot.register_next_step_handler(msg, save_email)

def save_email(message):
    email = message.text.strip()
    if not email.endswith("@blogger.com"):
        bot.send_message(message.chat.id, "ভুল ইমেইল! ইমেইলটি অবশ্যই '@blogger.com' দিয়ে শেষ হতে হবে। আবার চেষ্টা করুন।")
        return

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO users (telegram_id, email) VALUES (?, ?)", (message.chat.id, email))
        conn.commit()
        bot.send_message(message.chat.id, f"অভিনন্দন! আপনার ইমেইলটি সফলভাবে যুক্ত হয়েছে।\nসংযুক্ত ইমেইল: {email}")
    except Exception as e:
        bot.send_message(message.chat.id, "দুঃখিত, কোনো সমস্যা হয়েছে। আবার চেষ্টা করুন।")
    finally:
        conn.close()

# স্ট্যাটাস বাটন হ্যান্ডলার
@bot.message_handler(func=lambda message: message.text == "📊 My Status")
def check_status(message):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE telegram_id = ?", (message.chat.id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        bot.send_message(message.chat.id, f"আপনার ব্লগের সাথে সিঙ্ক সচল আছে।\nসংযুক্ত ইমেইল: {row[0]}")
    else:
        bot.send_message(message.chat.id, "আপনার কোনো ইমেইল কানেক্ট করা নেই। '🔌 Connect Blogger' বাটনে ক্লিক করুন।")

# সিঙ্ক হিস্টোরি বাটন হ্যান্ডলার (নতুন ফিচার)
@bot.message_handler(func=lambda message: message.text == "📈 Sync History")
def show_history(message):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # শেষ ১০টি পোস্টের হিস্টোরি দেখাবে
    cursor.execute("""SELECT post_title, status, timestamp 
                      FROM sync_history 
                      WHERE telegram_id = ? 
                      ORDER BY id DESC LIMIT 10""", (message.chat.id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.send_message(message.chat.id, "এখনো কোনো পোস্ট সিঙ্ক করা হয়নি। আপনার মেইন ব্লগে নতুন পোস্ট করলে এখানে হিস্টোরি দেখতে পাবেন।")
        return

    history_text = "📊 **আপনার ব্লগের সিঙ্ক হিস্টোরি (সর্বশেষ ১০টি):**\n\n"
    for row in rows:
        title = row[0]
        status = "✅ সফল" if row[1] == "Success" else "❌ ব্যর্থ"
        time_stamp = row[2]
        history_text += f"🎬 **মুভি:** {title}\n**স্ট্যাটাস:** {status}\n**সময়:** {time_stamp}\n----------------------\n"

    bot.send_message(message.chat.id, history_text, parse_mode="Markdown")

# ডিসকানেক্ট বাটন হ্যান্ডলার
@bot.message_handler(func=lambda message: message.text == "❌ Disconnect")
def disconnect_blogger(message):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE telegram_id = ?", (message.chat.id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "আপনার ইমেইলটি ডিসকানেক্ট করা হয়েছে। এখন আর কোনো পোস্ট যাবে না।")


# --- ইমেইল এবং সিঙ্ক সেকশন (ব্যাকগ্রাউন্ড থ্রেড) ---

def save_sync_log(telegram_id, post_title, status):
    """ডাটাবেজে সিঙ্ক হিস্টোরি সংরক্ষণ করার ফাংশন"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sync_history (telegram_id, post_title, status) VALUES (?, ?, ?)", 
                   (telegram_id, post_title, status))
    conn.commit()
    conn.close()

def send_posts_via_email(title, html_content):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, email FROM users")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return

    try:
        # SMTP সার্ভারে লগইন (উন্নত হেডার সহ)
        server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
        server.starttls()
        server.login(config.SENDER_EMAIL, config.SENDER_PASSWORD)

        for tg_id, receiver_email in rows:
            try:
                msg = MIMEMultipart()
                msg['From'] = config.SENDER_EMAIL
                msg['To'] = receiver_email
                msg['Subject'] = Header(title, 'utf-8')

                # মেইল ফিল্টারিং সমস্যা দূর করতে উন্নত বডি টেক্সট
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))
                
                # মেইল পাঠানো
                server.sendmail(config.SENDER_EMAIL, receiver_email, msg.as_string())
                print(f"Sent successfully to: {receiver_email}")
                
                # সফল হিস্টোরি সেভ করা
                save_sync_log(tg_id, title, "Success")
            except Exception as e:
                print(f"Failed to send to {receiver_email}: {e}")
                # ব্যর্থ হিস্টোরি সেভ করা
                save_sync_log(tg_id, title, f"Failed: {str(e)}")
                
        server.quit()
    except Exception as e:
        print(f"SMTP Error: {e}")

def rss_sync_worker():
    """১ মিনিট পর পর মেইন সাইট চেক করার ব্যাকগ্রাউন্ড ফাংশন"""
    print("RSS checking thread started...")
    while True:
        try:
            feed = feedparser.parse(config.SOURCE_RSS_URL)
            if feed.entries:
                latest_post = feed.entries[0]
                latest_link = latest_post.link
                latest_title = latest_post.title
                
                # পোস্টের HTML বডি নেওয়া
                latest_html_content = latest_post.get('content', [{}])[0].get('value', latest_post.summary)

                # ডাটাবেজ থেকে সর্বশেষ সেভ করা পোস্টের লিংক চেক করা
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = 'last_post_link'")
                row = cursor.fetchone()
                last_saved_link = row[0] if row else None

                # যদি নতুন পোস্ট পাওয়া যায়
                if last_saved_link != latest_link:
                    print(f"New post found: {latest_title}")
                    # সবাইকে মেইল পাঠানো
                    send_posts_via_email(latest_title, latest_html_content)
                    
                    # সর্বশেষ পোস্টের লিংক ডাটাবেজে আপডেট করা
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('last_post_link', ?)", (latest_link,))
                    conn.commit()
                conn.close()
        except Exception as e:
            print(f"Error during RSS check: {e}")

        # ১ মিনিট পর আবার চেক করবে (৬০ সেকেন্ড) - আপনার রিকোয়েস্ট অনুযায়ী ৬০ সেকেন্ড করা হয়েছে
        time.sleep(60)

# ব্যাকগ্রাউন্ড থ্রেড রান করা
threading.Thread(target=rss_sync_worker, daemon=True).start()

# টেলিগ্রাম বট চালু করা
print("Telegram Bot is running...")
bot.infinity_polling()
