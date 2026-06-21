FROM python:3.11-slim-bookworm

WORKDIR /app

# সিস্টেম আপডেট
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# pip আপগ্রেড
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Python ডিপেন্ডেন্সি
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# সম্পূর্ণ প্রোজেক্ট কপি
COPY . .

# ডাটাবেজ ডিরেক্টরি (পরবর্তীতে Railway Volume mount করবে)
RUN mkdir -p /data

# পোর্ট
EXPOSE $PORT

# Start command
CMD gunicorn server:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1 --threads 2 --access-logfile - --error-logfile -
