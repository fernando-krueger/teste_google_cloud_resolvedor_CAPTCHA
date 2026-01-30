import asyncio
import os
import httpx
import time
from fastapi import FastAPI, Request
from playwright.async_api import async_playwright
import vertexai
from vertexai.generative_models import GenerativeModel, Part

app = FastAPI()

# --- CONFIGURAÇÕES ---
PROJECT_ID = "seu-projeto-id" 
LOCATION = "us-central1"
N8N_WEBHOOK_URL = "https://projetosave-n8n.c20rpn.easypanel.host/webhook/receber-dados-recuperatax"

# Inicializa Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel("gemini-1.5-flash")

async def enviar_para_n8n(payload, id_log):
    """Envia o resultado para o n8n com log de confirmação"""
    print(f"📡 [{id_log}] Enviando payload ao n8n...", flush=True)
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(N8N_WEBHOOK_URL, json=payload, timeout=30)
            print(f"✅ [{id_log}] n8n respondeu Status: {res.status_code}", flush=True)
    except Exception as e:
        print(f"❌ [{id_log}] Erro ao comunicar com n8n: {e}", flush=True)

async def executar_automacao_captcha(cnpj):
    id_log = f"CNPJ-{cnpj[-4:]}-{int(time.time())}" # ID único para este log
    print(f"🚀 [{id_log}] Início da automação para CNPJ: {cnpj}", flush=True)
    
    async with async_playwright() as p:
        print(f"🌐 [{id_log}] Lançando navegador Chromium...", flush=True)
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # 1. Acesso ao Site
            url = "https://john.fun/captcha-game"
            print(f"📍 [{id_log}] Navegando para {url}", flush=True)
            await page.goto(url, timeout=60000)
            
            # 2. Captura da Pergunta
            print(f"🔍 [{id_log}] Aguardando pergunta (captchaInstructions)...", flush=True)
            selector_instrucao = "div.captchaInstructions"
            await page.wait_for_selector(selector_instrucao, timeout=20000)
            pergunta = await page.inner_text(selector_instrucao)
            print(f"❓ [{id_log}] Pergunta lida: '{pergunta}'", flush=True)

            # 3. Print do Grid
            print(f"📸 [{id_log}] Capturando screenshot do grid...", flush=True)
            grid_selector = "body > div > div > div:nth-child(3) > div > div"
            grid_element = await page.query_selector(grid_selector)
            
            if not grid_element:
                raise Exception("Grid de imagens não encontrado na página.")
                
            screenshot_bytes = await grid_element.screenshot()
            print(f"🖼️ [{id_log}] Screenshot capturado com sucesso ({len(screenshot_bytes)} bytes)", flush=True)

            # 4. Processamento Vertex AI
            print(f"🧠 [{id_log}] Enviando para o Vertex AI (Gemini 1.5 Flash)...", flush=True)
            image_part = Part.from_data(data=screenshot_bytes, mime_type="image/png")
            prompt = f"Pergunta: '{pergunta}'. Com base na imagem, qual o número do quadrado correto? Responda apenas o número."
            
            start_time = time.time()
            response = await model.generate_content_async([prompt, image_part])
            ia_duration = round(time.time() - start_time, 2)
            
            resposta_ia = response.text.strip()
            print(f"🎯 [{id_log}] Vertex AI respondeu: '{resposta_ia}' (Tempo: {ia_duration}s)", flush=True)
            
            # 5. Finalização
            await enviar_para_n8n({
                "status": "sucesso",
                "cnpj": cnpj,
                "pergunta": pergunta,
                "resposta_ia": resposta_ia,
                "id_processo": id_log
            }, id_log)

        except Exception as e:
            print(f"❌ [{id_log}] ERRO DURANTE EXECUÇÃO: {str(e)}", flush=True)
            await enviar_para_n8n({"status": "erro", "cnpj": cnpj, "erro": str(e), "id_processo": id_log}, id_log)
        finally:
            print(f"🧹 [{id_log}] Fechando navegador e limpando recursos.", flush=True)
            await browser.close()

@app.post("/trigger")
async def trigger(request: Request):
    try:
        dados = await request.json()
        cnpj = str(dados.get("cnpj", "00000000000000"))
        print(f"📥 [SISTEMA] Nova requisição recebida para CNPJ: {cnpj}", flush=True)
        
        # Dispara a tarefa assíncrona
        asyncio.create_task(executar_automacao_captcha(cnpj))
        
        return {"status": "🤖 Robô em processamento", "cnpj": cnpj}
    except Exception as e:
        print(f"⚠️ [SISTEMA] Erro ao processar trigger: {e}", flush=True)
        return {"erro": "Payload inválido"}, 400

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)