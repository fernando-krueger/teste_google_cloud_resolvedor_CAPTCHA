import asyncio
import os
import time
from datetime import datetime
from fastapi import FastAPI
from playwright.async_api import async_playwright
from google import genai
from google.genai import types
from google.cloud import storage

app = FastAPI()

# --- CONFIGURAÇÕES ---
PROJECT_ID = "numeric-skill-484321-a5" 
LOCATION = "us-central1"
BUCKET_NAME = "imagem-captcha"

# Criando os clientes
client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION
)
storage_client = storage.Client(project=PROJECT_ID)

def salvar_no_storage(image_bytes):
    """Gera o nome com a hora e envia para o bucket"""
    try:
        # Formata a hora exatamente como pedido: captcha 11:32:05
        hora_atual = datetime.now().strftime("%H:%M:%S")
        nome_arquivo = f"captcha {hora_atual}.png"
        
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(nome_arquivo)
        
        # Faz o upload dos bytes diretamente
        blob.upload_from_string(image_bytes, content_type='image/png')
        print(f"☁️ [STORAGE] Imagem salva: {nome_arquivo}", flush=True)
        return nome_arquivo
    except Exception as e:
        print(f"❌ [STORAGE] Erro ao salvar: {str(e)}", flush=True)
        return None

@app.get("/testar")
async def testar_automacao():
    id_exec = f"EXEC-{int(time.time())}"
    print(f"🚀 [{id_exec}] Iniciando com o novo SDK google-genai...", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            await page.goto("https://john.fun/captcha-game", timeout=60000)
            
            # 1. Captura Instrução
            selector_pergunta = "div.captchaInstructions"
            await page.wait_for_selector(selector_pergunta)
            await asyncio.sleep(3) 
            pergunta = await page.inner_text(selector_pergunta)
            pergunta = pergunta.replace('\n', ' ').strip()

            # 2. Screenshot do Grid
            grid_element = await page.query_selector(".captchaGrid")
            screenshot_bytes = await grid_element.screenshot()

            # --- NOVA PARTE: SALVAR NO STORAGE ---
            arquivo_salvo = salvar_no_storage(screenshot_bytes)
            # -------------------------------------

            # 3. Chamada à IA usando o novo padrão 'gemini-2.0-flash'
            print(f"🧠 [{id_exec}] Chamando Gemini 2.0 Flash via Vertex...", flush=True)
            
            response = client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=[
                    f"A instrução é: {pergunta}. Responda apenas o número do quadrado correto na imagem.",
                    types.Part.from_bytes(data=screenshot_bytes, mime_type='image/png')
                ]
            )
            
            resposta_ia = response.text.strip()
            print(f"🎯 [{id_exec}] Resposta da IA: {resposta_ia}", flush=True)

            # 4. Clique
            await page.click(f"text='{resposta_ia}'", timeout=5000)
            print(f"✅ [{id_exec}] Clique realizado no {resposta_ia}", flush=True)

            return {
                "pergunta": pergunta, 
                "ia": resposta_ia, 
                "status": "sucesso", 
                "arquivo_no_storage": arquivo_salvo
            }

        except Exception as e:
            print(f"❌ [{id_exec}] Erro: {str(e)}", flush=True)
            return {"status": "erro", "detalhes": str(e)}
        finally:
            await browser.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
