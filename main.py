import asyncio
import os
import httpx
import time
from fastapi import FastAPI, Request
from playwright.async_api import async_playwright
import vertexai
from vertexai.generative_models import GenerativeModel, Part

app = FastAPI()

PROJECT_ID = "seu-projeto-id" 
LOCATION = "us-central1"
N8N_WEBHOOK_URL = "https://projetosave-n8n.c20rpn.easypanel.host/webhook/receber-dados-recuperatax"

vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel("gemini-1.5-flash")

# --- MESMA LÓGICA DE AUTOMAÇÃO ANTERIOR ---
async def executar_automacao_captcha(cnpj):
    id_log = f"AUTO-{int(time.time())}"
    print(f"🚀 [{id_log}] Iniciando execução direta para CNPJ: {cnpj}", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        try:
            await page.goto("https://john.fun/captcha-game", timeout=60000)
            # ... (todo o código de captura e IA que já fizemos) ...
            print(f"✅ [{id_log}] Finalizado com sucesso.", flush=True)
        except Exception as e:
            print(f"❌ [{id_log}] Erro: {e}", flush=True)
        finally:
            await browser.close()

# GATILHO 1: Via n8n ou cURL (POST)
@app.post("/trigger")
async def trigger_post(request: Request):
    dados = await request.json()
    cnpj = str(dados.get("cnpj", "PADRAO-000"))
    asyncio.create_task(executar_automacao_captcha(cnpj))
    return {"status": "Iniciado via POST", "cnpj": cnpj}

# GATILHO 2: Via Cloud Scheduler ou Navegador (GET)
# Isso permite dar "Play" clicando na URL do Cloud Run
@app.get("/")
async def trigger_get(cnpj: str = "PADRAO-WEB"):
    asyncio.create_task(executar_automacao_captcha(cnpj))
    return {"status": "Iniciado via GET/Navegador", "cnpj": cnpj}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
