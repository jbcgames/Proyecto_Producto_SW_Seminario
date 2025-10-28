# scraper_sync.py
import re
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright

def parse_price(text: str | None) -> int | None:
    if not text:
        return None
    text = re.sub(r"[^\d]", "", text)
    return int(text) if text else None

def construir_url(query, site_domain="mercadolibre.com.co",
                  min_price=None, max_price=None,
                  condition=None, envio=None) -> str:
    query_slug = quote_plus(query.replace(" ", "-"))

    cond_slug = ""
    if condition:
        c = condition.lower()
        if c == "nuevo":
            cond_slug = "_ITEM*CONDITION_2230284"
        elif c == "usado":
            cond_slug = "_ITEM*CONDITION_2230581"

    envio_slug = "_CostoEnvio_Gratis" if (envio and envio.lower() in ["gratis", "si", "free"]) else ""

    rango_slug = ""
    if (min_price or max_price):
        rango_slug = f"_PriceRange_{min_price or 0}-{max_price or ''}"

    return f"https://listado.{site_domain}/{query_slug}{cond_slug}{envio_slug}{rango_slug}_NoIndex_True"

def scrape_meli_sync(query, site_domain="mercadolibre.com.co",
                     min_price=None, max_price=None,
                     condition=None, envio=None):
    """Versión síncrona para usar en hilos (ideal para el rastreador)."""
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
        page.wait_for_timeout(2500)
        page.wait_for_selector("li.ui-search-layout__item", timeout=20000)

        cards = page.query_selector_all("li.ui-search-layout__item")
        items = []

        for card in cards:
            title_el = card.query_selector("a.poly-component__title")
            title = title_el.inner_text().strip() if title_el else None
            link = title_el.get_attribute("href") if title_el else None

            price_el = card.query_selector("span.andes-money-amount__fraction")
            price_text = price_el.inner_text().strip() if price_el else None
            price = parse_price(price_text)

            cond_el = card.query_selector("span.poly-component__item-condition")
            cond_text = cond_el.inner_text().strip() if cond_el else None
            if not cond_text:
                cond_text = "Nuevo"

            ship_el = card.query_selector("div.poly-component__shipping")
            shipping = ship_el.inner_text().strip() if ship_el else None

            img_el = card.query_selector("img.poly-component__picture")
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

        context.close()
        browser.close()

    return {"url": url, "results": items}
