FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for opencv and psycopg
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first
# (separate layer for better caching)
COPY requirements.txt .
# requirements.txt may be UTF-16 LE (Windows pip freeze default);
# convert to UTF-8 so pip can parse it on Linux.
RUN python3 -c "\
raw = open('requirements.txt','rb').read();\
text = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8-sig');\
open('requirements.txt','w',encoding='utf-8').write(text)"
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
