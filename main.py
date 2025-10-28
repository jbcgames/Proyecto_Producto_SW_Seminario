from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from scraper import scrape_meli
import asyncio, hashlib, time

app = FastAPI(title="MercadoLibre Scraper API", version="1.1.0")

# Memoria en servidor: por firma de búsqueda guardamos los "links" ya vistos
SEEN = {}  # dict[firma] = set(links)
LAST_TS = {}  # dict[firma] = last update timestamp

def firma_busqueda(q, min_price, max_price, condition, envio, site, session_id=None):
    # session_id opcional por si quieres separar sesiones cliente; si no, se comparte por criterios
    base = f"{q}|{min_price}|{max_price}|{condition}|{envio}|{site}|{session_id or ''}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

@app.get("/search")
async def search_items(
    q: str = Query(..., description="Palabra clave"),
    min_price: int | None = Query(None),
    max_price: int | None = Query(None),
    condition: str | None = Query(None, description="nuevo/usado"),
    envio: str | None = Query(None, description="gratis/no"),
    site: str = Query("mercadolibre.com.co"),
    delta: bool = Query(False, description="Si true, devolver solo resultados nuevos"),
    session_id: str | None = Query(None, description="ID de sesión opcional para segmentar 'nuevos'")
):
    try:
        # Ejecutar scraper en hilo para evitar conflictos de event loop
        data = await asyncio.to_thread(
            asyncio.run,
            scrape_meli(q, site_domain=site,
                        min_price=min_price,
                        max_price=max_price,
                        condition=condition,
                        envio=envio)
        )
        results = data.get("results", [])
        # Identificador único de búsqueda
        key = firma_busqueda(q, min_price, max_price, condition, envio, site, session_id)
        vistos = SEEN.setdefault(key, set())

        # Determinar "solo nuevos" por link (ID práctico)
        nuevos = [r for r in results if r.get("link") and r["link"] not in vistos]

        # Actualizar memoria con todo lo visto en esta llamada
        for r in nuevos:
            vistos.add(r["link"])
        LAST_TS[key] = int(time.time())

        if delta:
            payload = {
                "url": data.get("url"),
                "new_results": nuevos,
                "new_count": len(nuevos),
                "total_seen": len(vistos),
                "key": key,
                "last_update": LAST_TS[key]
            }
        else:
            payload = {
                "url": data.get("url"),
                "results": results,
                "returned": len(results),
                "total_seen": len(vistos),
                "key": key,
                "last_update": LAST_TS[key]
            }
        return payload

    except Exception as e:
        import traceback
        print("🔥 ERROR:", traceback.format_exc())
        return {"error": str(e)}

# Servir frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")
