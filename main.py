import asyncio
import os
import time
from fastapi import FastAPI, Request
from playwright.async_api import async_playwright
import vertexai
from vertexai.generative_models import GenerativeModel, Part

app = FastAPI()

# --- CONFIGURAÇÕES GOOGLE CLOUD ---
PROJECT_ID = "seu-projeto-id" # Substitua pelo seu ID do projeto
LOCATION = "us-central1"

# Inicializa o Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel("gemini-1.5-flash")

async def analisar_captcha_com_ia(image_bytes, pergunta_texto):
    """Envia o print e a pergunta para o Gemini no Vertex AI"""
    image_part = Part.from_data(data=image_bytes, mime_type="image/png")
    
    prompt = f"""
    A instrução do captcha é: "{pergunta_texto}"
    Com base na imagem anexa que contém quadrados numerados, qual o NÚMERO do quadrado correto?
    Responda apenas o número puro.
    """
    
    response = await model.generate_content_async([prompt, image_part])
    return response.text.strip()

@app.get("/testar")
async def testar_automacao():
    id_teste = f"TESTE-{int(time.time())}"
    print(f"🚀 [{id_teste}] Iniciando teste de captcha...", flush=True)
    
    async with async_playwright() as p:
        print(f"🌐 [{id_teste}] Abrindo navegador...", flush=True)
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            # 1. Acesso ao site do jogo
            url = "https://john.fun/captcha-game"
            await page.goto(url, timeout=60000)
            print(f"📍 [{id_teste}] Site carregado.", flush=True)
            
            # 2. Captura da pergunta
            selector_pergunta = "div.captchaInstructions"
            await page.wait_for_selector(selector_pergunta, timeout=10000)
            pergunta = await page.inner_text(selector_pergunta)
            print(f"❓ [{id_teste}] Pergunta: {pergunta}", flush=True)

            # 3. Print da área do desafio
            # Este seletor pega especificamente o container das imagens
            selector_grid = "body > div > div > div:nth-child(3) > div > div"
            grid_element = await page.query_selector(selector_grid)
            
            if not grid_element:
                return {"erro": "Não encontrei o grid do captcha"}
                
            screenshot = await grid_element.screenshot()
            print(f"📸 [{id_teste}] Screenshot da área do captcha realizado.", flush=True)

            # 4. Análise com Vertex AI
            print(f"🧠 [{id_teste}] Solicitando análise ao Vertex AI...", flush=True)
            resposta = await analisar_captcha_com_ia(screenshot, pergunta)
            print(f"🎯 [{id_teste}] Resultado da IA: {resposta}", flush=True)

            return {
                "id_execucao": id_teste,
                "pergunta_detectada": pergunta,
                "resposta_da_ia": resposta,
                "status": "sucesso"
            }

        except Exception as e:
            print(f"❌ [{id_teste}] Erro no teste: {str(e)}", flush=True)
            return {"status": "erro", "detalhes": str(e)}
        finally:
            await browser.close()
            print(f"🧹 [{id_teste}] Navegador fechado.", flush=True)

@app.get("/")
async def home():
    return {"mensagem": "Servidor de Teste Ativo. Use o endpoint /testar para rodar a automação."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
