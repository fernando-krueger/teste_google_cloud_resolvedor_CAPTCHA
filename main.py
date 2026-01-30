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

print(f"🛠️ [DEBUG] Inicializando Clientes Google Cloud...", flush=True)
try:
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    storage_client = storage.Client(project=PROJECT_ID)
    print(f"✅ [DEBUG] Clientes Google Cloud prontos.", flush=True)
except Exception as e:
    print(f"❌ [DEBUG] ERRO NA INICIALIZAÇÃO DOS CLIENTES: {e}", flush=True)

def salvar_no_storage(image_bytes, exec_id):
    """Gera o nome com a hora e envia para o bucket com debug de tamanho"""
    try:
        hora_atual = datetime.now().strftime("%H:%M:%S")
        nome_arquivo = f"captcha {hora_atual}.png"
        tamanho_kb = len(image_bytes) / 1024
        
        print(f"📤 [DEBUG][{exec_id}] Tentando Storage: {nome_arquivo} ({tamanho_kb:.2f} KB)", flush=True)
        
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(nome_arquivo)
        blob.upload_from_string(image_bytes, content_type='image/png')
        
        print(f"✨ [DEBUG][{exec_id}] Storage OK: {nome_arquivo}", flush=True)
        return nome_arquivo
    except Exception as e:
        print(f"⚠️ [DEBUG][{exec_id}] FALHA NO STORAGE: {str(e)}", flush=True)
        return f"ERRO: {str(e)}"

@app.get("/testar")
async def testar_automacao():
    id_exec = f"RUN-{int(time.time())}"
    print(f"\n--- INÍCIO DA EXECUÇÃO {id_exec} ---", flush=True)
    start_time = time.time()
    
    async with async_playwright() as p:
        print(f"🌐 [DEBUG][{id_exec}] Lançando navegador Chromium...", flush=True)
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        
        try:
            print(f"📍 [DEBUG][{id_exec}] Navegando para a URL...", flush=True)
            await page.goto("https://john.fun/captcha-game", timeout=60000, wait_until="networkidle")
            print(f"🔗 [DEBUG][{id_exec}] URL carregada: {page.url}", flush=True)
            
            # 1. Debug da Pergunta
            print(f"🔍 [DEBUG][{id_exec}] Aguardando seletor da pergunta...", flush=True)
            await page.wait_for_selector("div.captchaInstructions", timeout=20000)
            print(f"⏱️ [DEBUG][{id_exec}] Seletor encontrado. Aguardando 3s para renderização total...", flush=True)
            await asyncio.sleep(3) 
            
            pergunta = await page.inner_text("div.captchaInstructions")
            pergunta_limpa = pergunta.replace('\n', ' ').strip()
            print(f"📝 [DEBUG][{id_exec}] Texto da pergunta: '{pergunta_limpa}'", flush=True)

            # 2. Debug do Grid/Screenshot
            print(f"📸 [DEBUG][{id_exec}] Localizando grid de imagens...", flush=True)
            grid_element = await page.query_selector(".captchaGrid")
            if not grid_element:
                print(f"❌ [DEBUG][{id_exec}] GRID NÃO ENCONTRADO!", flush=True)
                raise Exception("Grid element .captchaGrid not found")
                
            screenshot_bytes = await grid_element.screenshot()
            print(f"🖼️ [DEBUG][{id_exec}] Screenshot capturado com sucesso.", flush=True)

            # 3. Debug do Storage
            arquivo_salvo = salvar_no_storage(screenshot_bytes, id_exec)

            # 4. Debug da IA
            print(f"🧠 [DEBUG][{id_exec}] Enviando dados para Gemini 2.0 Flash...", flush=True)
            ia_start = time.time()
            
            response = client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=[
                    f"Instrução: {pergunta_limpa}. Responda apenas o número do quadrado correto.",
                    types.Part.from_bytes(data=screenshot_bytes, mime_type='image/png')
                ]
            )
            
            ia_end = time.time()
            resposta_ia = response.text.strip()
            print(f"⚡ [DEBUG][{id_exec}] Resposta da IA recebida em {ia_end - ia_start:.2f}s: '{resposta_ia}'", flush=True)

            # 5. Debug do Clique
            print(f"🖱️ [DEBUG][{id_exec}] Tentando clicar no texto: '{resposta_ia}'", flush=True)
            try:
                await page.click(f"text='{resposta_ia}'", timeout=5000)
                print(f"🎯 [DEBUG][{id_exec}] Clique confirmado via seletor de texto.", flush=True)
                status_clique = "Sucesso"
            except Exception as e_click:
                print(f"⚠️ [DEBUG][{id_exec}] FALHA NO CLIQUE: {e_click}", flush=True)
                status_clique = f"Erro: {str(e_click)}"

            total_time = time.time() - start_time
            print(f"🏁 [DEBUG][{id_exec}] Execução finalizada em {total_time:.2f}s", flush=True)

            return {
                "id": id_exec,
                "pergunta": pergunta_limpa,
                "ia_escolheu": resposta_ia,
                "clique": status_clique,
                "imagem": arquivo_salvo,
                "tempo_total_seg": round(total_time, 2)
            }

        except Exception as e:
            print(f"🔥 [DEBUG][{id_exec}] ERRO CRÍTICO NA ROTA: {str(e)}", flush=True)
            return {"status": "erro", "detalhes": str(e)}
        finally:
            print(f"🧹 [DEBUG][{id_exec}] Fechando navegador...", flush=True)
            await browser.close()

if __name__ == "__main__":
    import uvicorn
    print("📡 [DEBUG] Iniciando Servidor Uvicorn na porta 8080...", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
