# অফিসিয়াল Python ইমেজ — সব ডিপেন্ডেন্সি সাথে আছে
FROM python:3.11-slim-bookworm

# ওয়ার্কিং ডিরেক্টরি
WORKDIR /app

# সিস্টেম আপডেট ও প্রয়োজনীয় প্যাকেজ
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# পাইপ আপগ্রেড
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Python ডিপেন্ডেন্সি ইনস্টল
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# সম্পূর্ণ প্রোজেক্ট কপি
COPY . .

# ডাটাবেজের জন্য ভলিউম মাউন্ট পয়েন্ট
RUN mkdir -p /data
VOLUME ["/data"]

# পোর্ট এক্সপোজ
EXPOSE $PORT

# কমান্ড — gunicorn দিয়ে Flask চালানো
CMD gunicorn server:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1 --threads 2 --access-logfile - --error-logfile -
