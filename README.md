# Rastreador Inteligente de Ofertas en MercadoLibre
Monitoreo de productos en tiempo real con Web Scraping (Playwright), API (FastAPI) y notificaciones por Telegram.

## 🚀 Características
- Scraping dinámico con Playwright (navegador real).
- API REST con FastAPI (/search, /subscribe, /register_chat).
- Frontend HTML/CSS/JS con formulario y resultados.
- Auto-refresh configurable y muestra solo productos nuevos.
- Notificaciones por Telegram (texto + imagen) solo la primera vez.
- Persistencia en JSON para evitar repetidos.
- Normalización de URLs (sin tracking_id).
- Exposición pública con Ngrok o Cloudflare Tunnel.
- Scheduler APScheduler para ejecutar tareas automáticas.

## 📁 Estructura del proyecto
```
Proyecto_Producto_SW/
├─ main.py
├─ scraper.py
├─ notifier.py
├─ requirements.txt
├─ .env
├─ seen_store.json
├─ watches_store.json
├─ phone_map.json
└─ static/
   ├─ index.html
   ├─ style.css
   └─ script.js
```

## ⚙️ Instalación
```bash
pip install -r requirements.txt
playwright install
```

Crea archivo `.env`:
```
TELEGRAM_BOT_TOKEN=TU_TOKEN
STORE_DIR=./data
```

## ▶️ Ejecución local
```bash
uvicorn main:app --reload
```
Accede a: http://127.0.0.1:8000

## 🌐 Exposición pública (Ngrok)
```bash
ngrok http 8000
```
Obtendrás una URL pública para compartir.

## 🔌 Endpoints
### GET /search
Busca artículos filtrando palabra clave, precio, estado, envío, sitio y delta.

### POST /register_chat
Registra relación teléfono–chat_id para enviar notificaciones por Telegram.

### POST /subscribe
Crea suscripción para monitoreo periódico.

## 💻 Frontend
Formulario con campos para búsqueda, filtros, teléfono y refresco.  
Muestra resultados en tarjetas con imagen, título, precio y estado.

## 🤖 Telegram
1. Crea bot con @BotFather y obtén token.  
2. Envíale /start.  
3. Obtén chat_id con `getUpdates`.  
4. Registra el chat con `/register_chat`.

## 🗃️ Persistencia
Archivos JSON guardan productos vistos, suscripciones activas y relación phone→chat_id.

## 🛡️ Seguridad
Protege `/register_chat` con token ADMIN_TOKEN si lo expones públicamente.

## 🐳 Dockerfile sugerido
```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000"]
```

## 🧪 Pruebas
- Buscar en web.
- Delta devuelve solo nuevos.
- Telegram recibe notificaciones con imagen.

## 📈 Roadmap
- Dashboard con históricos.
- Integración con Amazon/eBay.
- Panel multiusuario.
- Exportación CSV/Excel.
- Hosting 24/7.

## 📝 Licencia
MIT License

---
Desarrollado por **Miguel**.
