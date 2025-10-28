from playwright.sync_api import sync_playwright

def test_abrir_google():
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=False) 

        page = browser.new_page()


        page.goto("https://www.mercadolibre.com.co")
    

        print("Test completado: Google abrió correctamente")
        delay = 5000  
        page.wait_for_timeout(delay)  


if __name__ == "__main__":
    test_abrir_google()
