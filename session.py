"""
session.py — Login no SolarView com Playwright puro.
Salva cookies em cookies.json para o SolarView.py usar.
"""

import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

COOKIES_FILE = Path("cookies.json")
LOGIN_URL = "https://my.solarview.com.br/login"


async def login():
    if COOKIES_FILE.exists():
        print("[session] cookies.json ja existe. Delete-o para refazer o login.")
        return

    print("[session] Abrindo browser para login...")
    print("[session] Faca o login normalmente. Fecha sozinho apos /home.\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await browser.new_context(
            no_viewport=True,   # usa o tamanho real da janela maximizada
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
        )

        # Remove sinais de automacao
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()
        await page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print("[session] Aguardando login (ate 5 minutos)...")
        for _ in range(300):
            await asyncio.sleep(1)
            try:
                if "/home" in page.url or "/monitoramento" in page.url:
                    print(f"[session] Login detectado!")
                    await asyncio.sleep(2)
                    break
            except Exception:
                break

        # Salva cookies
        cookies = await context.cookies()
        COOKIES_FILE.write_text(
            json.dumps(cookies, indent=2, ensure_ascii=True),
            encoding="utf-8"
        )
        print(f"[session] {len(cookies)} cookies salvos em {COOKIES_FILE}")
        await browser.close()

    print("[session] Pronto. Rode python SolarView.py")


if __name__ == "__main__":
    asyncio.run(login())
