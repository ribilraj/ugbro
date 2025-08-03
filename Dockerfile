# ✅ Base image: Best stable Python version
FROM python:3.10.13-slim

# ✅ Set working directory
WORKDIR /app

# ✅ Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    aria2 \
    libffi-dev \
    build-essential \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ✅ Copy all source code to container
COPY . .

# ✅ Make mp4decrypt executable (if present)
RUN chmod +x /app/tools/mp4decrypt || true

# ✅ Upgrade pip and install Python packages
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r ugbots.txt \
    && pip install --no-cache-dir -U yt-dlp

# ✅ Remove pyrofork if accidentally included
RUN pip uninstall -y pyrofork || true

# ✅ Explicitly install stable Pyrogram + TgCrypto
RUN pip install --no-cache-dir -U pyrogram==2.0.106 tgcrypto==1.2.5

# ✅ Final command: start Flask + Bot together
CMD ["sh", "-c", "gunicorn app:app & python3 main.py"]
