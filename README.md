# SolarView Scraper

Coleta dados de monitoramento solar do SolarView em tempo real e salva em dados.json.


## Problema

O site my.solarview.com.br e a API api-v2.solarview.com.br sao protegidos por:

- Cloudflare Managed Challenge (verificacao "Verificando se voce e humano")
- CAPTCHA no login
- Deteccao de automacao via fingerprint de browser (webdriver, plugins, WebGL, etc.)
- Token de sessao ckTkU com validade curta
- Iframe React em sandbox (allow-same-origin) que bloqueia acesso cross-origin direto


## Solucao

O login e feito com Playwright puro (Chrome visivel, maximizado) onde o usuario resolve
o CAPTCHA manualmente. Os cookies sao salvos em cookies.json.

A coleta de dados usa Camoufox, um fork do Firefox com anti-fingerprint implementado
em C++ (nao em JavaScript). Isso significa que as modificacoes acontecem antes de
qualquer script do site executar, tornando a deteccao praticamente impossivel.
O Camoufox roda em modo headless e passa pelo Cloudflare automaticamente.

Os dados sao extraidos do HTML renderizado pelo React dentro do iframe, usando
BeautifulSoup para parsear as classes CSS dos cards.


## Por que Camoufox e nao Playwright stealth

playwright-stealth foi descontinuado em fevereiro de 2025 e nao funciona mais contra
o Cloudflare atual. Chromium headless deixa rastros de timing em JavaScript que o
Cloudflare identifica mesmo com patches de stealth. Camoufox resolve isso no nivel
do engine do browser.


## Estrutura dos arquivos

    session.py      Login manual. Abre Chrome maximizado, usuario loga e resolve
                    captcha. Salva cookies em cookies.json. Rodar so na primeira vez
                    ou quando a sessao expirar.

    SolarView.py    Coleta continua. Le cookies.json, abre Camoufox headless,
                    navega para as paginas de monitoramento e inversores, extrai
                    os dados dos cards e salva em dados.json a cada 60 segundos.

    cookies.json    Gerado pelo session.py. Contem todos os cookies da sessao
                    incluindo cf_clearance (Cloudflare) e ckTkU (token da API).
                    Atualizado automaticamente a cada coleta.

    dados.json      Gerado pelo SolarView.py. Resultado da ultima coleta.


## Instalacao

    pip install camoufox[geoip] beautifulsoup4 playwright
    python -m camoufox fetch
    playwright install chromium


## Uso

Primeira vez:

    python session.py

O Chrome abre maximizado. Faca o login normalmente no site. Apos chegar em /home
o script detecta e fecha sozinho. cookies.json e gerado.

Coleta continua:

    python SolarView.py

Atualiza dados.json a cada 60 segundos.


## Formato do dados.json

    {
      "timestamp": "2026-03-22T14:30:00",
      "ciclo": 1,
      "monitoramento": {
        "produziu_kwh": "651,0",
        "economizou_reais": "R$ 520,80",
        "desempenho_pct": "5.022,6%",
        "co2_evitado_kg": "80,98",
        "injetou_kwh": "...",
        "consumiu_kwh": "...",
        "gastou_reais": "...",
        "autossuficiencia_pct": "...",
        "arvores": "..."
      },
      "inversores": [
        { "nome": "Inversor 1", "status": "Injetando" },
        { "nome": "Inversor 2", "status": "Injetando" }
      ]
    }


## Quando renovar a sessao

O token ckTkU expira. Quando o SolarView.py comecar a retornar dados vazios
ou erros 401, delete cookies.json e rode session.py novamente:

    del cookies.json
    python session.py


## Paginas coletadas

    /monitoramento?und=23192    Cards de energia (producao, economia, CO2, etc.)
    /inversores?und=23192       Status de cada inversor (Injetando, Offline, etc.)


## Dependencias

    camoufox[geoip]    Browser anti-detect baseado em Firefox
    beautifulsoup4     Parser de HTML para extrair os cards
    playwright         Usado apenas no session.py para o login visivel

## requirements.txt

pip install -r requirements.txt
python -m camoufox fetch
playwright install chromium

Os dois comandos extras são necessários porque camoufox
e playwright precisam baixar os binários do browser separadamente após o pip install.
