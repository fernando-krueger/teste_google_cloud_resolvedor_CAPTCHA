import asyncio
import os
import time
from fastapi import FastAPI, Request
from playwright.async_api import async_playwright
import vertexai
from vertexai.generative_models import GenerativeModel, Part

app = FastAPI()

# --- CONFIGURAÇÃO REAL ---
# Use exatamente este ID. Não use "seu-projeto-id" em nenhum lugar.
MEU_PROJETO = "numeric-skill-484321-a5" 
MINHA_REGIAO = "us-east1"

# Inicialização Forçada
vertexai.init(project=MEU_PROJETO, location=MINHA_REGIAO)
# Forçamos o modelo a saber em qual projeto ele está rodando
model = GenerativeModel("gemini-1.5-flash")

async def analisar_captcha_com_ia(image_bytes, pergunta_texto):
    image_part = Part.from_data(data=image_bytes, mime_type="image/png")
    prompt = f"Pergunta: {pergunta_texto}. Responda apenas o número do quadrado correto."
    
    # Chamada assíncrona
    response = await model.generate_content_async([prompt, image_part])
    return response.text.strip()

@app.get("/testar")
async def testar_automacao():
    id_teste = f"EXEC-{int(time.time())}"
    print(f"🚀 [{id_teste}] Iniciando no projeto: {MEU_PROJETO}", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            await page.goto("https://john.fun/captcha-game", timeout=60000)
            
            # Aguarda pergunta
            selector_pergunta = "div.captchaInstructions"
            await page.wait_for_selector(selector_pergunta)
            await asyncio.sleep(2)
            pergunta = await page.inner_text(selector_pergunta)
            
            # Screenshot
            grid_element = await page.query_selector(".captchaGrid")
            screenshot = await grid_element.screenshot()

            # IA
            print(f"🧠 [{id_teste}] Chamando Vertex AI...", flush=True)
            # AQUI: Se der erro 403 de novo, é falta de permissão IAM na conta de serviço
            resposta = await analisar_captcha_com_ia(screenshot, pergunta)
            print(f"🎯 [{id_teste}] Resposta: {resposta}", flush=True)

            return {"status": "sucesso", "ia_disse": resposta}

        except Exception as e:
            print(f"❌ [{id_teste}] Erro: {str(e)}", flush=True)
            return {"status": "erro", "detalhes": str(e)}
        finally:
            await browser.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
