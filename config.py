import os

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN or BOT_TOKEN == '8711805117:AAHaGPcfFsiwd1bneA57BVAXoQdldGjHKi0':
    raise ValueError("❌ BOT_TOKEN environment variable is not set!")

CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME', '@saniedit9')
if not CHANNEL_USERNAME.startswith('@'):
    CHANNEL_USERNAME = '@' + CHANNEL_USERNAME.lstrip('@')

REQUIRED_REFS = int(os.environ.get('REQUIRED_REFS', '2'))
FREE_LINKS = int(os.environ.get('FREE_LINKS', '2'))
MAX_LINKS_PER_HOUR = int(os.environ.get('MAX_LINKS_PER_HOUR', '5'))

# Railway Persistent Volume — /data তে মাউন্ট হবে
DB_DIR = '/data'
DB_PATH = os.path.join(DB_DIR, 'database.sqlite')

# লোকাল টেস্টিং এর জন্য ফ্যালব্যাক
if not os.path.exists('/data'):
    DB_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(DB_DIR, 'database.sqlite')

BASE_URL = os.environ.get('BASE_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = 'http://localhost:5000'

PORT = int(os.environ.get('PORT', 5000))
