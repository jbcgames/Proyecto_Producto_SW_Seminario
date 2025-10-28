# scrape_worker.py
import sys, json, re
from urllib.parse import quote_plus

# Política de asyncio (por si Playwright interno la usa)
import asyncio
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from playwright.sync_api import sync_playwright

def parse_price(text):
    if not text:
        return None
    text = re.sub(r"[^\d]", "", text)
    return int(text) if text else None

def construir_url(query, site_domain="mercadolibre.com.co",
                  min_price=None, max_price=None,
                  condition=None, envio=None):
    query_slug = quote_plus(query.replace(" ", "-"))
    cond_slug = ""
    if condition:
        c = condition.lower()
        if c == "nuevo":
            cond_slug = "_ITEM*CONDITION_2230284"
        elif c == "usado":
            cond_slug = "_ITEM*CONDITION_2230581"
    envio_slug = "_CostoEnvio_Gratis" if (envio and envio.lower() in ["gratis","si","free"]) else ""
    rango_slug = f"_PriceRange_{min_price or 0}-{max_price or ''}" if (min_price or max_price) else ""
    return f"https://listado.{site_domain}/{query_slug}{cond_slug}{envio_slug}{rango_slug}_NoIndex_True"


def scrape_once(query, site_domain, min_price, max_price, condition, envio):
    url = construir_url(query, site_domain, min_price, max_price, condition, envio)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ))
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")

        # Esperas + scroll para asegurar carga de cards e imágenes
        page.wait_for_timeout(2500)
        for _ in range(3):
            page.mouse.wheel(0, 25000)
            page.wait_for_timeout(800)

        # Intentar esperar la lista principal (no romper si falla)
        try:
            page.wait_for_selector("li.ui-search-layout__item, ol.ui-search-layout", timeout=10000)
        except Exception:
            pass

        # 1) Cards por li clásico
        cards = page.query_selector_all("li.ui-search-layout__item")

        # 2) Respaldo si no hay li (algunas variantes)
        if not cards:
            cards = page.query_selector_all("div.ui-search-result__content-wrapper, div.poly-card")

        items = []
        for card in cards:
            # Título + link (varios selectores de respaldo)
            title_el = (
                card.query_selector("a.poly-component__title")
                or card.query_selector("h3.poly-component__title-wrapper a")
                or card.query_selector("a.ui-search-link")
            )
            title = title_el.inner_text().strip() if title_el else None
            link = title_el.get_attribute("href") if title_el else None

            # Precio (respaldo)
            price_el = (
                card.query_selector("span.andes-money-amount__fraction")
                or card.query_selector("span.poly-price__fraction")
                or card.query_selector("[data-testid='item-price'] span")
            )
            price_text = price_el.inner_text().strip() if price_el else None
            price = parse_price(price_text)

            # Condición
            cond_el = card.query_selector("span.poly-component__item-condition")
            cond_text = cond_el.inner_text().strip() if cond_el else None
            if not cond_text:
                cond_text = "Nuevo"

            # Envío
            ship_el = card.query_selector("div.poly-component__shipping")
            shipping = ship_el.inner_text().strip() if ship_el else None

            # Imagen (src / data-src)
            img_el = card.query_selector("img.poly-component__picture") or card.query_selector("img")
            image = None
            if img_el:
                src = img_el.get_attribute("src")
                data_src = img_el.get_attribute("data-src")
                if src and src.startswith("http"):
                    image = src
                elif data_src and data_src.startswith("http"):
                    image = data_src

            if not title or not link or not price:
                continue

            items.append({
                "title": title,
                "price": price,
                "condition": cond_text,
                "shipping": shipping,
                "link": link,
                "image": image
            })

        # Dump de diagnóstico si quedó vacío
        if not items:
            try:
                html = page.content()
                with open("worker_dump.html", "w", encoding="utf-8") as f:
                    f.write(html)
            except Exception:
                pass

        context.close()
        browser.close()
    return {"url": url, "results": items}


if __name__ == "__main__":
    import traceback, os, json, sys, asyncio
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    out = {"url": None, "results": [], "error": ""}
    try:
        query = sys.argv[1]
        site = sys.argv[2] if len(sys.argv) > 2 else "mercadolibre.com.co"
        min_price = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else None
        max_price = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else None
        condition = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5].strip() else None
        envio = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6].strip() else None

        out = scrape_once(query, site, min_price, max_price, condition, envio)

        # Si no encontró nada, deja una pista en `error`
        if not out.get("results"):
            out["error"] = (
                "No se detectaron cards. Se guardó 'worker_dump.html' con el HTML "
                "para inspección de selectores / bloqueos."
            )

    except Exception as e:
        out["error"] = f"{e.__class__.__name__}: {e}\n{traceback.format_exc()}"

    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0)
