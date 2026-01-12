# ======================================
# دليل نشر وتشغيل VPN Tunnel API
# Complete Deployment Guide
# ======================================

## 📋 متطلبات النظام

### على جهازك (للتطوير):
- Python 3.10+
- PostgreSQL 15+
- Git

### على الخادم (للإنتاج):
- Ubuntu 22.04 LTS
- 2GB RAM minimum
- 20GB Storage

---

## 🚀 الخطوة 1: تثبيت PostgreSQL

### Windows:
```powershell
# حمّل من الموقع الرسمي
# https://www.postgresql.org/download/windows/

# بعد التثبيت، أنشئ قاعدة بيانات:
psql -U postgres
CREATE DATABASE vpn_tunnel;
CREATE USER vpn_user WITH PASSWORD 'your_strong_password';
GRANT ALL PRIVILEGES ON DATABASE vpn_tunnel TO vpn_user;
\q
```

### Ubuntu:
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo -u postgres psql
CREATE DATABASE vpn_tunnel;
CREATE USER vpn_user WITH PASSWORD 'your_strong_password';
GRANT ALL PRIVILEGES ON DATABASE vpn_tunnel TO vpn_user;
\q
```

---

## 🚀 الخطوة 2: إعداد Backend

```bash
# انتقل لمجلد Backend
cd d:\app_file\vpn_tunnel\backend

# أنشئ بيئة افتراضية
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# ثبّت المتطلبات
pip install -r requirements.txt
```

---

## 🚀 الخطوة 3: إعداد ملف .env

```bash
# انسخ ملف المثال
copy .env.example .env
```

**عدّل الملف `.env`:**

```env
# قاعدة البيانات
DATABASE_URL=postgresql+asyncpg://vpn_user:your_strong_password@localhost:5432/vpn_tunnel

# مفتاح التشفير (ولّد مفتاح عشوائي قوي!)
JWT_SECRET_KEY=اختر_مفتاح_سري_طويل_وعشوائي_جدا_هنا_123456789

# إعدادات JWT
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Admin الافتراضي (غيّرها!)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=كلمة_مرور_قوية_جدا

# إعدادات أخرى
DEBUG=false
ALLOWED_HOSTS=*
```

---

## 🚀 الخطوة 4: تشغيل الخادم

### للتطوير:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### للإنتاج:
```bash
# استخدم Gunicorn مع Uvicorn workers
pip install gunicorn

gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## 🚀 الخطوة 5: تجربة API

افتح المتصفح على:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### تسجيل دخول Admin:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "كلمة_المرور"}'
```

---

## 🌐 الخطوة 6: نشر على خادم إنتاج

### الخيار 1: VPS (مثل DigitalOcean, Vultr)

```bash
# على الخادم
sudo apt update
sudo apt install python3 python3-pip python3-venv nginx certbot

# انسخ الكود
git clone https://your-repo/vpn-tunnel.git
cd vpn-tunnel/backend

# اتبع خطوات التثبيت أعلاه
```

### إعداد Nginx:
```nginx
# /etc/nginx/sites-available/vpn-api
server {
    listen 80;
    server_name api.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### SSL Certificate:
```bash
sudo certbot --nginx -d api.your-domain.com
```

### الخيار 2: Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t vpn-api .
docker run -d -p 8000:8000 --env-file .env vpn-api
```

---

## 📱 الخطوة 7: ربط Android

عدّل `android/app/build.gradle.kts`:

```kotlin
// للتطوير المحلي
buildConfigField("String", "API_BASE_URL", "\"http://10.0.2.2:8000/api/\"")

// للإنتاج
buildConfigField("String", "API_BASE_URL", "\"https://api.your-domain.com/api/\"")
```

---

## 🔒 نصائح الأمان

1. **غيّر كلمات المرور الافتراضية**
2. **استخدم HTTPS دائماً**
3. **فعّل Firewall**:
   ```bash
   sudo ufw allow 22    # SSH
   sudo ufw allow 80    # HTTP
   sudo ufw allow 443   # HTTPS
   sudo ufw enable
   ```
4. **حدّث النظام**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

---

## 📊 مراقبة الخادم

### Logs:
```bash
# Uvicorn logs
journalctl -u vpn-api -f

# أو باستخدام Docker
docker logs -f vpn-api
```

### Systemd Service:
```ini
# /etc/systemd/system/vpn-api.service
[Unit]
Description=VPN Tunnel API
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/vpn-tunnel/backend
ExecStart=/var/www/vpn-tunnel/backend/venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable vpn-api
sudo systemctl start vpn-api
```

---

## ✅ قائمة التحقق النهائية

- [ ] PostgreSQL مثبت وقاعدة البيانات جاهزة
- [ ] ملف .env معدّل بقيم صحيحة
- [ ] الخادم يعمل بدون أخطاء
- [ ] API يستجيب على /docs
- [ ] Admin يمكنه تسجيل الدخول
- [ ] HTTPS مفعّل (للإنتاج)
- [ ] Android متصل بالـ API
