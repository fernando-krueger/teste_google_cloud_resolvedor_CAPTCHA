import asyncio
import os
import time
from fastapi import FastAPI, Request
from playwright.async_api import async_playwright
import vertexai
from vertexai.generative_models import GenerativeModel, Part

app = FastAPI()

# --- CONFIGURAÇÕES GOOGLE CLOUD (ESTÁVEIS) ---
# Usando us-central1 para garantir que o modelo gemini-1.5-flash seja encontrado
PROJECT_ID = "numeric-skill-484321-a5" 
LOCATION = "us-central1" 

# Inicializa o Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)
# Definimos o modelo com o nome padrão estável
model = GenerativeModel("gemini-1.5-flash")

async def analisar_captcha_com_ia(image_bytes, pergunta_texto):
    """Envia o print e a pergunta para o Gemini no Vertex AI"""
    image_part = Part.from_data(data=image_bytes, mime_type="image/png")
    
    prompt = f"""
    Instrução do captcha: "{pergunta_texto}"
    A imagem contém quadrados numerados. 
    Qual o NÚMERO do quadrado que responde corretamente à instrução?
    Responda APENAS o número puro.
    """
    
    # Chamada ao modelo
    response = await model.generate_content_async([prompt, image_part])
    return response.text.strip()

@app.get("/testar")
async def testar_automacao():
    id_exec = f"EXEC-{int(time.time())}"
    print(f"🚀 [{id_exec}] Iniciando automação em {LOCATION}...", flush=True)
    
    async with async_playwright() as p:
        print(f"🌐 [{id_exec}] Abrindo navegador Chromium...", flush=True)
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            # 1. Acesso ao site
            print(f"📍 [{id_exec}] Acessando o jogo de captcha...", flush=True)
            await page.goto("https://john.fun/captcha-game", timeout=60000)
            
            # 2. Captura da pergunta com espera para renderização
            selector_pergunta = "div.captchaInstructions"
            await page.wait_for_selector(selector_pergunta, timeout=20000)
            
            # Espera 3 segundos para a imagem/ícone da pergunta carregar totalmente
            await asyncio.sleep(3) 
            
            pergunta = await page.inner_text(selector_pergunta)
            pergunta_limpa = pergunta.replace('\n', ' ').strip()
            print(f"❓ [{id_exec}] Pergunta Detectada: {pergunta_limpa}", flush=True)

            # 3. Print focado no Grid do Captcha
            selector_grid = ".captchaGrid"
            grid_element = await page.query_selector(selector_grid)
            
            if not grid_element:
                raise Exception("Não foi possível localizar o grid do captcha na página.")
                
            screenshot_bytes = await grid_element.screenshot()
            print(f"📸 [{id_exec}] Screenshot do grid realizado com sucesso.", flush=True)

            # 4. Análise pela Inteligência Artificial
            print(f"🧠 [{id_exec}] Enviando para análise no Vertex AI...", flush=True)
            resposta_ia = await analisar_captcha_com_ia(screenshot_bytes, pergunta_limpa)
            print(f"🎯 [{id_exec}] IA respondeu: Quadrado {resposta_ia}", flush=True)

            # 5. Execução do Clique no Quadrado Escolhido
            print(f"🖱️ [{id_exec}] Tentando clicar no quadrado {resposta_ia}...", flush=True)
            try:
                # O seletor de texto do Playwright é excelente para encontrar o número dentro do grid
                await page.click(f"text='{resposta_ia}'", timeout=5000)
                print(f"✅ [{id_exec}] Clique efetuado!", flush=True)
                status_clique = "Sucesso"
            except Exception as e_click:
                print(f"⚠️ [{id_exec}] Falha ao clicar: {e_click}", flush=True)
                status_clique = "Falha no clique"

            return {
                "id": id_exec,
                "status": "finalizado",
                "pergunta": pergunta_limpa,
                "ia_decisao": resposta_ia,
                "clique": status_clique
            }

        except Exception as e:
            print(f"❌ [{id_exec}] ERRO NA EXECUÇÃO: {str(e)}", flush=True)
            return {"status": "erro", "detalhes": str(e)}
        finally:
            await browser.close()
            print(f"🧹 [{id_exec}] Sessão encerrada.", flush=True)

@app.get("/")
async def home():
    return {"mensagem": "Servidor de Captcha Ativo", "endpoint": "/testar"}

if __name__ == "__main__":
    import uvicorn
    # Cloud Run usa a porta 8080 por padrão
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
