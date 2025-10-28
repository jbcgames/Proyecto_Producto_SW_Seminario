# main.py
from fastapi import FastAPI, Query, Body
from fastapi.staticfiles import StaticFiles
from scraper import scrape_meli
from notifier import send_telegram_message, send_telegram_photo
import asyncio, hashlib, time, json, os
from threading import Lock
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

app = FastAPI(title="MercadoLibre Scraper API", version="2.0.0")

# --- archivos de persistencia ---
SEEN_FILE     = "seen_store.json"       # { key: {links:[], last_update:int} }
WATCHES_FILE  = "watches_store.json"    # { watch_id: { params, phone, interval, last_run } }
PHONEMAP_FILE = "phone_map.json"        # { phone: chat_id }

_store_lock = Lock()
SEEN   = {}   # mem: dict[key] -> set(links)
LAST_TS= {}   # mem: dict[key] -> int
WATCHES= {}   # mem: dict[watch_id] -> dict
PHONEMAP = {} # mem: dict[phone] -> chat_id

scheduler = AsyncIOScheduler()


# ------------ utilidades de persistencia ------------
def _load_json(path):
    if not os.path.exists(path): return {}
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def _save_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _sync_mem_from_disk():
    global SEEN, LAST_TS, WATCHES, PHONEMAP
    disk_seen = _load_json(SEEN_FILE)
    for k, v in disk_seen.items():
        SEEN[k] = set(v.get("links", []))
        LAST_TS[k] = v.get("last_update", 0)
    WATCHES = _load_json(WATCHES_FILE)
    PHONEMAP = _load_json(PHONEMAP_FILE)

def _sync_seen_to_disk():
    disk = {}
    for k, s in SEEN.items():
        disk[k] = {"links": list(s), "last_update": LAST_TS.get(k, int(time.time()))}
    _save_json_atomic(SEEN_FILE, disk)

def _sync_watches_to_disk():
    _save_json_atomic(WATCHES_FILE, WATCHES)

def _sync_phonemap_to_disk():
    _save_json_atomic(PHONEMAP_FILE, PHONEMAP)


# ------------ normalización de URL ------------
def limpiar_url(url: str) -> str:
    if not url: return url
    try:
        parsed = urlparse(url)
        query_params = dict(parse_qsl(parsed.query))
        params_ignorar = {"tracking_id", "wid", "sid", "position", "type", "search_layout", "polycard_client"}
        query_limpia = {k: v for k, v in query_params.items() if k not in params_ignorar}
        nueva_query = urlencode(query_limpia, doseq=True)
        cleaned = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, nueva_query, ""))  # sin fragmento
        return cleaned
    except:
        return url


# ------------ claves de “búsqueda” (para SEEN) y de “watch” ------------
def firma_busqueda(q, min_price, max_price, condition, envio, site, phone=None):
    base = f"{q}|{min_price}|{max_price}|{condition}|{envio}|{site}|{phone or ''}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

def watch_id_from_params(q, min_price, max_price, condition, envio, site, phone):
    # teléfono obligatorio ahora
    base = f"WATCH|{q}|{min_price}|{max_price}|{condition}|{envio}|{site}|{phone}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


# ------------ endpoint original /search (sigue funcionando) ------------
@app.get("/search")
async def search_items(
    q: str = Query(..., description="Palabra clave"),
    min_price: int | None = Query(None),
    max_price: int | None = Query(None),
    condition: str | None = Query(None, description="nuevo/usado"),
    envio: str | None = Query(None, description="gratis/no"),
    site: str = Query("mercadolibre.com.co"),
    delta: bool = Query(False, description="Si true, devuelve solo nuevos"),
    phone: str | None = Query(None, description="Teléfono (ahora puede usarse como ID)")
):
    try:
        data = await asyncio.to_thread(
            asyncio.run,
            scrape_meli(q, site_domain=site,
                        min_price=min_price,
                        max_price=max_price,
                        condition=condition,
                        envio=envio)
        )
        results = data.get("results", [])

        # limpiar URLs
        for r in results:
            if r.get("link"):
                r["link"] = limpiar_url(r["link"])

        key = firma_busqueda(q, min_price, max_price, condition, envio, site, phone)
        with _store_lock:
            vistos = SEEN.setdefault(key, set())
            nuevos = [r for r in results if r.get("link") and r["link"] not in vistos]
            for r in nuevos: vistos.add(r["link"])
            LAST_TS[key] = int(time.time())
            _sync_seen_to_disk()

        return ({"url": data.get("url"), "new_results": nuevos, "new_count": len(nuevos),
                 "total_seen": len(SEEN[key]), "key": key, "last_update": LAST_TS[key]}
                if delta else
                {"url": data.get("url"), "results": results, "returned": len(results),
                 "total_seen": len(SEEN[key]), "key": key, "last_update": LAST_TS[key]})
    except Exception as e:
        import traceback; print("🔥 ERROR /search:", traceback.format_exc())
        return {"error": str(e)}


# ------------ registrar chat_id para un teléfono ------------
@app.post("/register_chat")
def register_chat(phone: str = Body(...), chat_id: str = Body(...)):
    """
    Registra la relación phone -> chat_id. El usuario debe haber hablado al bot.
    (En producción conviene hacerlo por Webhook /getUpdates y capturar automáticamente)
    """
    with _store_lock:
        PHONEMAP[phone] = chat_id
        _sync_phonemap_to_disk()
    return {"ok": True, "phone": phone, "chat_id": chat_id}


# ------------ crear/actualizar una suscripción con scheduler ------------
@app.post("/subscribe")
def subscribe(
    q: str = Body(...),
    phone: str = Body(...),
    min_price: int | None = Body(None),
    max_price: int | None = Body(None),
    condition: str | None = Body(None),
    envio: str | None = Body(None),
    site: str = Body("mercadolibre.com.co"),
    interval_sec: int = Body(300, embed=True)  # por defecto, 5 minutos
):
    """
    Crea una suscripción (watch) que ejecuta el scraper cada interval_sec y
    envía por Telegram SOLO los NUEVOS hallazgos (primera vez que aparezcan).
    phone es obligatorio y será el ID lógico de la suscripción.
    """
    wid = watch_id_from_params(q, min_price, max_price, condition, envio, site, phone)
    WATCHES[wid] = {
        "q": q, "phone": phone, "min_price": min_price, "max_price": max_price,
        "condition": condition, "envio": envio, "site": site,
        "interval_sec": max(30, int(interval_sec)),  # hard floor 30s
        "last_run": 0
    }
    _sync_watches_to_disk()

    # (Re)programar tarea
    try:
        scheduler.remove_job(wid)
    except Exception:
        pass
    scheduler.add_job(run_watch, "interval", seconds=WATCHES[wid]["interval_sec"], id=wid, args=[wid], replace_existing=True)

    return {"ok": True, "watch_id": wid, "interval_sec": WATCHES[wid]["interval_sec"]}


# ------------ tarea programada: ejecuta el scraper y notifica ------------
async def run_watch(wid: str):
    w = WATCHES.get(wid)
    if not w: return
    q, phone = w["q"], w["phone"]
    min_price, max_price = w["min_price"], w["max_price"]
    condition, envio, site = w["condition"], w["envio"], w["site"]

    # si no tenemos chat_id para ese teléfono, salimos (aún no habló al bot)
    chat_id = PHONEMAP.get(phone)
    if not chat_id:
        print(f"ℹ️ Sin chat_id para {phone}. Usa /register_chat para asociarlo.")
        return

    # scrape
    try:
        data = await asyncio.to_thread(
            asyncio.run,
            scrape_meli(q, site_domain=site,
                        min_price=min_price, max_price=max_price,
                        condition=condition, envio=envio)
        )
        results = data.get("results", [])
        for r in results:
            if r.get("link"): r["link"] = limpiar_url(r["link"])

        # clave SEEN por búsqueda+phone para que el "nuevo" sea por suscripción
        key = firma_busqueda(q, min_price, max_price, condition, envio, site, phone)
        with _store_lock:
            vistos = SEEN.setdefault(key, set())
            nuevos = [r for r in results if r.get("link") and r["link"] not in vistos]
            for r in nuevos: vistos.add(r["link"])
            LAST_TS[key] = int(time.time())
            _sync_seen_to_disk()

        # enviar sólo si hay nuevos
        if nuevos:
            for it in nuevos[:10]:  # enviar hasta 10 productos por ciclo
                caption = f"{it['title']}\n💰 ${it['price']:,}\n{it['link']}"
                if it.get("image"):
                    send_telegram_photo(chat_id, it["image"], caption)
                else:
                    send_telegram_message(chat_id, caption)
            if len(nuevos) > 10:
                send_telegram_message(chat_id, f"🔎 Hay {len(nuevos)-10} resultados adicionales para \"{q}\"…")
            print(f"Telegram a {phone} ({chat_id}) → {len(nuevos)} nuevos con imágenes")

            ok = send_telegram_message(chat_id, texto)
            print(f"Telegram a {phone} ({chat_id}) → {len(nuevos)} nuevos | ok={ok}")

        WATCHES[wid]["last_run"] = int(time.time())
        _sync_watches_to_disk()
    except Exception as e:
        import traceback; print("🔥 ERROR run_watch:", traceback.format_exc())


def build_message(query, items, site):
    lines = [f"🔎 Nuevos hallazgos para \"{query}\" ({site}):"]
    for it in items[:10]:  # envia hasta 10 por mensaje
        price = f"${it['price']:,}".replace(",", ".")
        lines.append(f"• {it['title']} — {price}\n  {it['link']}")
    if len(items) > 10:
        lines.append(f"… y {len(items)-10} más.")
    return "\n".join(lines)


# ------------ ciclo de vida de la app ------------
@app.on_event("startup")
async def on_startup():
    _sync_mem_from_disk()
    # reprogramar todas las suscripciones guardadas
    for wid, w in WATCHES.items():
        try:
            scheduler.add_job(run_watch, "interval", seconds=max(30, int(w.get("interval_sec", 300))),
                              id=wid, args=[wid], replace_existing=True)
        except Exception as e:
            print("No se pudo programar", wid, e)
    scheduler.start()

@app.on_event("shutdown")
async def on_shutdown():
    scheduler.shutdown(wait=False)

# ------- servir frontend ----------
app.mount("/", StaticFiles(directory="static", html=True), name="static")
