# Python 3.11 ইমেজ ব্যবহার
FROM python:3.11-slim

# ওয়ার্কিং ডিরেক্টরি
WORKDIR /app

# সিস্টেম ডিপেন্ডেন্সি
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python ডিপেন্ডেন্সি
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# প্রোজেক্ট ফাইল কপি
COPY . .

# Volume mount for database
VOLUME /data

# পোর্ট
EXPOSE $PORT

# স্টার্ট কমান্ড
CMD gunicorn server:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1 --threads 2
