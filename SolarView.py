"""
SolarView.py
=============
Coleta dados de monitoramento e inversores do SolarView.
Le cookies do session.py (Playwright) e usa Camoufox headless para coleta.

USO:
  python session.py    <- so na primeira vez
  python SolarView.py
"""

import json
import asyncio
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from camoufox.async_api import AsyncCamoufox

COOKIES_FILE = Path("cookies.json")
SESSION_FILE = Path("session_data.json")
OUTPUT_FILE = Path("dados.json")
URL_MONITORAMENTO = "https://my.solarview.com.br/monitoramento?und=23192"
URL_INVERSORES = "https://my.solarview.com.br/inversores?und=23192"
INTERVALO = 60

LABELS = {
    "Economizou":         "economizou_reais",
    "Produziu":           "produziu_kwh",
    "Desempenho":         "desempenho_pct",
    "CO2 Evitado":        "co2_evitado_kg",
    "Injetou na Rede":    "injetou_kwh",
    "Consumiu":           "consumiu_kwh",
    "Consumiu da Rede":   "consumiu_rede_kwh",
    "Gastou":             "gastou_reais",
    "Autossuficiencia":   "autossuficiencia_pct",
    "Arvores Cultivadas": "arvores",
    "Potencia":           "potencia_kw",
    "Potencia Atual":     "potencia_kw",
}

STATUS_ICONES = {
    "icon-status-normal-2": "Injetando",
    "icon-status-normal":   "Normal",
    "icon-status-offline":  "Offline",
    "icon-status-warning":  "Alerta",
    "icon-status-error":    "Erro",
    "icon-status-nodata":   "Sem dados",
    "icon-status-waiting":  "Aguardando",
}


# ─── COOKIES ─────────────────────────────────────────────────────────────────

def carregar_cookies() -> list:
    for f in [COOKIES_FILE, SESSION_FILE]:
        if not f.exists():
            continue
        conteudo = f.read_text(encoding="utf-8").strip()
        if not conteudo:
            continue
        try:
            data = json.loads(conteudo)
        except Exception:
            continue
        cookies = data.get("cookies", data) if isinstance(data, dict) else data
        if isinstance(cookies, list) and cookies:
            print(f"[auth] {len(cookies)} cookies de '{f.name}'")
            return cookies
    print("[ERRO] cookies.json nao encontrado. Rode session.py primeiro.")
    return []


def para_camoufox(cookies: list) -> list:
    resultado = []
    for c in cookies:
        entry = {
            "name":   c.get("name", ""),
            "value":  c.get("value", ""),
            "domain": c.get("domain", ".solarview.com.br"),
            "path":   c.get("path", "/"),
        }
        if c.get("secure"):
            entry["secure"] = True
        if c.get("httpOnly"):
            entry["httpOnly"] = True
        ss = c.get("sameSite", "")
        if ss in ("Strict", "Lax", "None"):
            entry["sameSite"] = ss
        expires = c.get("expires", -1)
        if expires and float(expires) > 0:
            entry["expires"] = int(float(expires))
        resultado.append(entry)
    return resultado


# ─── EXTRACAO ────────────────────────────────────────────────────────────────

def extrair_cards(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    dados = {}

    cards = soup.find_all(class_=lambda c: c and "info-card" in c
                          and "value" not in c and "title" not in c and "unit" not in c)
    for card in cards:
        t = card.find(class_=lambda c: c and "title" in c)
        v = card.find(class_=lambda c: c and "value" in c)
        u = card.find(class_=lambda c: c and "unit" in c)
        if not t or not v:
            continue
        titulo = t.get_text(strip=True)
        valor = v.get_text(strip=True)
        unidade = u.get_text(strip=True) if u else ""
        chave = LABELS.get(titulo, titulo.lower().replace(" ", "_"))
        dados[chave] = f"{valor} {unidade}".strip() if unidade else valor

    if not dados:
        titulos = soup.find_all(class_=lambda c: c and "info-card__title" in c)
        valores = soup.find_all(class_=lambda c: c and "info-card__value" in c)
        unidades = soup.find_all(class_=lambda c: c and "info-card__unit" in c)
        umap = {i: u.get_text(strip=True) for i, u in enumerate(unidades)}
        for i, (t, v) in enumerate(zip(titulos, valores)):
            titulo = t.get_text(strip=True)
            valor = v.get_text(strip=True)
            chave = LABELS.get(titulo, titulo.lower().replace(" ", "_"))
            dados[chave] = f"{valor} {umap.get(i, '')}".strip(
            ) if umap.get(i) else valor

    return dados


def extrair_inversores(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    inversores, vistos = [], set()

    for icone in soup.find_all("i", class_=lambda c: c and "icon-status" in c):
        classes = icone.get("class", [])
        title = icone.get("title", "")
        status = title if title else next(
            (STATUS_ICONES[c]
             for c in classes if c in STATUS_ICONES), "Desconhecido"
        )
        nome, pai = "", icone.find_parent()
        for _ in range(5):
            if not pai:
                break
            cands = pai.find_all(
                ["span", "div", "td", "p", "h4", "h5"],
                class_=lambda c: c and any(x in (c or "")
                                           for x in ["nome", "name", "title", "inversor", "serial", "label", "device"])
            )
            if cands:
                nome = cands[0].get_text(strip=True)
                break
            txt = pai.get_text(separator=" ", strip=True)
            if txt and 2 < len(txt) < 60:
                nome = txt
                break
            pai = pai.find_parent()

        nome = nome or f"Inversor {len(inversores)+1}"
        chave = (nome, status)
        if chave not in vistos:
            vistos.add(chave)
            inversores.append({"nome": nome, "status": status})

    return inversores


# ─── NAVEGACAO ───────────────────────────────────────────────────────────────

async def pegar_html(page, url: str, seletor: str) -> str:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=40_000)
    except Exception as e:
        print(f"  [nav] {e}")

    await asyncio.sleep(4)

    titulo = await page.title()
    if "moment" in titulo.lower() or "verificando" in titulo.lower():
        print("  [CF] Aguardando challenge...")
        await asyncio.sleep(12)

    for tentativa in range(3):
        await asyncio.sleep(5)
        try:
            frame = next(
                (f for f in page.frames if "build" in f.url and not f.is_detached()),
                None
            )
            if not frame:
                print(
                    f"  [iframe] tentativa {tentativa+1}: nao encontrado, aguardando...")
                continue
            try:
                await frame.wait_for_selector(seletor, timeout=20_000)
            except Exception:
                pass
            if frame.is_detached():
                print(
                    f"  [iframe] tentativa {tentativa+1}: frame detached, tentando novamente...")
                continue
            return await frame.content()
        except Exception as e:
            print(f"  [iframe] tentativa {tentativa+1}: {e}")
            continue

    print("  [iframe] usando HTML da pagina principal como fallback")
    try:
        return await page.content()
    except Exception:
        return ""


# ─── MAIN ────────────────────────────────────────────────────────────────────

async def main():
    cookies = carregar_cookies()
    if not cookies:
        return

    cookies_cf = para_camoufox(cookies)
    print(f"[INFO] Coletando a cada {INTERVALO}s | Ctrl+C para parar\n")

    ciclo = 0
    while True:
        ciclo += 1
        print(f"{'─'*45}")
        print(
            f"Coleta #{ciclo} -- {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"{'─'*45}")

        try:
            async with AsyncCamoufox(
                headless=True,
                humanize=True,
                os="windows",
                disable_coop=True,
                i_know_what_im_doing=True,
            ) as browser:

                page = await browser.new_page()

                for c in cookies_cf:
                    try:
                        await page.context.add_cookies([c])
                    except Exception:
                        pass

                print("[1/2] Monitoramento...")
                html_mon = await pegar_html(page, URL_MONITORAMENTO, "[class*='info-card']")
                cards = extrair_cards(html_mon)

                print("[2/2] Inversores...")
                html_inv = await pegar_html(page, URL_INVERSORES, "[class*='icon-status']")
                inversores = extrair_inversores(html_inv)

                cookies_novos = await page.context.cookies()
                if cookies_novos:
                    COOKIES_FILE.write_text(
                        json.dumps(cookies_novos, indent=2, ensure_ascii=True),
                        encoding="utf-8"
                    )
                    cookies_cf = para_camoufox(cookies_novos)

            resultado = {
                "timestamp":     datetime.now().isoformat(),
                "ciclo":         ciclo,
                "monitoramento": cards,
                "inversores":    inversores,
            }

            OUTPUT_FILE.write_text(
                json.dumps(resultado, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            if cards:
                print("\n  Monitoramento:")
                for k, v in cards.items():
                    print(f"    {k}: {v}")
            if inversores:
                print("\n  Inversores:")
                for inv in inversores:
                    print(f"    {inv['nome']}: {inv['status']}")
            print(f"\n  Salvo em dados.json")

        except KeyboardInterrupt:
            print("\n[INFO] Encerrado.")
            break
        except Exception as e:
            print(f"[ERRO] {e}")
            import traceback
            traceback.print_exc()

        print(f"\n  Proxima coleta em {INTERVALO}s...\n")
        try:
            await asyncio.sleep(INTERVALO)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[INFO] Encerrado.")
            break


if __name__ == "__main__":
    asyncio.run(main())
