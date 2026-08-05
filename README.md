# Boisar Welfare Chemist Association (BCWA) Portal 🏥

An enterprise-grade document management, pharmacist tracking, compliance scoring, and license renewal portal for the Boisar Welfare Chemist Association (BCWA), powered by **Flask** and **Supabase PostgreSQL & Storage**.

---

## 🚀 Quick Start Local Setup (< 5 Minutes)

### 1. Prerequisites
- Python 3.9+
- Git

### 2. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/Omkaringale96/BCWA.git
cd BCWA

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On macOS / Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env.development`:
```bash
cp .env.example .env.development
```

Open `.env.development` and add your **Supabase credentials** (obtained from **Supabase Dashboard &rarr; Project Settings &rarr; API**):
```env
FLASK_ENV=development
DEBUG=True
PORT=5000

FLASK_SECRET_KEY=bcwa_portal_dev_secret_key_2026

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=sb_publishable_your_anon_key
SUPABASE_SERVICE_KEY=sb_secret_your_service_role_key
```

### 5. Run Local Server
You can launch the portal locally using either command:

```bash
python app.py
```
or
```bash
flask run
```

Open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)** or **[http://localhost:5000](http://localhost:5000)**

---

## 🛠️ Local Development Features

- **⚡ Live Code Auto-Reload**: Modifying Python, HTML, or CSS files automatically triggers instant reloads.
- **🔍 Debug Console & Stack Traces**: Full un-truncated stack trace logging for troubleshooting.
- **☁️ Live Supabase Connection**: Uploads documents and syncs database changes immediately to your Supabase cloud backend.
- **🔒 Relaxed Session Cookies**: Allows testing on `http://localhost:5000` without requiring HTTPS certificates.

---

## 🔒 Security & Environment Architecture

| Feature | Development (`localhost`) | Production (`Render`) |
| :--- | :--- | :--- |
| **`FLASK_ENV`** | `development` | `production` |
| **`DEBUG`** | `True` (Live Reload & Tracebacks) | `False` (Internal Error Masking) |
| **Session Cookies** | `HttpOnly=True`, `Secure=False` | `HttpOnly=True`, `Secure=True`, `SameSite=Lax` |
| **Security Headers** | `X-Frame-Options: DENY`, `nosniff` | `X-Frame-Options: DENY`, `nosniff`, `CSP` |
| **Credentials** | Read from `.env.development` | Read from Render Environment Variables |

---

## 🌐 Deploying to Production (Render)

Production deployment is fully automated. Pushing your changes to `main` branch triggers auto-deployment on Render:

```bash
git add .
git commit -m "Add new feature"
git push origin main
```

No code changes or environment adjustments are required when deploying. Render automatically uses `ProductionConfig` via environment variables.

---

## 🧪 Running Unit Tests

Run the full automated test suite (10 test modules):
```bash
python3 test_app.py
```
