import asyncio
import os
import time
import httpx
from fastapi import FastAPI, Request
from playwright.async_api import async_playwright
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from PIL import Image
import io

app = FastAPI()

# --- CONFIGURAÇÕES GOOGLE CLOUD ---
# O ID do projeto e a localização são detectados ou definidos aqui
PROJECT_ID = "numeric-skill-484321-a5" 
LOCATION = "us-east1"

# Inicializa o Vertex AI (Gemini 1.5 Flash)
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel("gemini-1.5-flash")

async def analisar_captcha_com_ia(image_bytes, pergunta_texto):
    """Envia o print focado e a pergunta para o Vertex AI"""
    image_part = Part.from_data(data=image_bytes, mime_type="image/png")
    
    prompt = f"""
    A instrução do captcha é: "{pergunta_texto}"
    A imagem contém um grid de quadrados numerados. 
    Qual o NÚMERO do quadrado que corresponde à instrução dada?
    Responda APENAS o número puro (ex: 3).
    """
    
    response = await model.generate_content_async([prompt, image_part])
    return response.text.strip()

@app.get("/testar")
async def testar_automacao():
    id_teste = f"EXEC-{int(time.time())}"
    print(f"🚀 [{id_teste}] Iniciando resolvedor de captcha...", flush=True)
    
    async with async_playwright() as p:
        print(f"🌐 [{id_teste}] Abrindo navegador Chromium...", flush=True)
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            # 1. Acesso ao site
            url = "https://john.fun/captcha-game"
            print(f"📍 [{id_teste}] Navegando para {url}", flush=True)
            await page.goto(url, timeout=60000)
            
            # 2. Aguarda e captura a pergunta (com delay para carregar ícones/imagens da pergunta)
            selector_pergunta = "div.captchaInstructions"
            print(f"🔍 [{id_teste}] Aguardando instruções visíveis...", flush=True)
            await page.wait_for_selector(selector_pergunta, timeout=20000)
            
            # Pequena pausa para garantir que a imagem do objeto na pergunta carregou
            await asyncio.sleep(3) 
            
            pergunta = await page.inner_text(selector_pergunta)
            pergunta_limpa = pergunta.replace('\n', ' ').strip()
            print(f"❓ [{id_teste}] Pergunta Completa: {pergunta_limpa}", flush=True)

            # 3. Print da área do Grid de Captcha
            selector_grid = ".captchaGrid"
            print(f"📸 [{id_teste}] Capturando área do grid...", flush=True)
            await page.wait_for_selector(selector_grid)
            grid_element = await page.query_selector(selector_grid)
            
            if not grid_element:
                raise Exception("Grid de imagens não encontrado!")
                
            screenshot_bytes = await grid_element.screenshot()

            # 4. Chamada à Inteligência Artificial (Vertex AI)
            print(f"🧠 [{id_teste}] Solicitando análise ao Vertex AI...", flush=True)
            start_ia = time.time()
            resposta_ia = await analisar_captcha_com_ia(screenshot_bytes, pergunta_limpa)
            fim_ia = round(time.time() - start_ia, 2)
            print(f"🎯 [{id_teste}] IA decidiu pelo quadrado: {resposta_ia} (Tempo: {fim_ia}s)", flush=True)

            # 5. Ação de Clique
            print(f"🖱️ [{id_teste}] Tentando clicar no número {resposta_ia}...", flush=True)
            try:
                # Usa seletor de texto para encontrar o número dentro do grid
                # 'force=True' ajuda se houver algum overlay transparente
                await page.click(f"text='{resposta_ia}'", timeout=5000, force=True)
                print(f"✅ [{id_teste}] Clique efetuado com sucesso!", flush=True)
                resultado_final = f"Sucesso: Quadrado {resposta_ia} clicado."
            except Exception as e_click:
                print(f"⚠️ [{id_teste}] Erro no clique: {str(e_click)}", flush=True)
                resultado_final = f"Erro no clique: {str(e_click)}"

            return {
                "id_execucao": id_teste,
                "pergunta": pergunta_limpa,
                "ia_escolheu": resposta_ia,
                "resultado": resultado_final,
                "tempo_ia": fim_ia
            }

        except Exception as e:
            print(f"❌ [{id_teste}] ERRO GERAL: {str(e)}", flush=True)
            return {"status": "erro", "mensagem": str(e)}
        finally:
            print(f"🧹 [{id_teste}] Encerrando sessão do navegador.", flush=True)
            await browser.close()

@app.get("/")
async def home():
    return {
        "servico": "Resolvedor de Captcha Vertex AI",
        "status": "online",
        "endpoint_de_teste": "/testar"
    }

if __name__ == "__main__":
    import uvicorn
    # Cloud Run define a porta via variável de ambiente
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
