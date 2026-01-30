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

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
storage_client = storage.Client(project=PROJECT_ID)

def salvar_no_storage(image_bytes, exec_id):
    try:
        hora_atual = datetime.now().strftime("%H:%M:%S")
        nome_arquivo = f"captcha {hora_atual}.png"
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(nome_arquivo)
        blob.upload_from_string(image_bytes, content_type='image/png')
        print(f"✨ [DEBUG][{exec_id}] Imagem salva no Storage: {nome_arquivo}", flush=True)
        return nome_arquivo
    except Exception as e:
        print(f"⚠️ [DEBUG][{exec_id}] Erro Storage: {e}", flush=True)
        return None

@app.get("/testar")
async def testar_automacao():
    id_exec = f"RUN-{int(time.time())}"
    print(f"\n--- INICIANDO EXECUÇÃO COM ANÁLISE PRÉVIA {id_exec} ---", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            print(f"🌐 [DEBUG][{id_exec}] Acessando site...", flush=True)
            await page.goto("https://john.fun/captcha-game", timeout=60000)
            
            await page.wait_for_selector("div.captchaInstructions")
            await asyncio.sleep(3) 
            pergunta = (await page.inner_text("div.captchaInstructions")).replace('\n', ' ').strip()
            print(f"❓ [DEBUG][{id_exec}] Pergunta lida: {pergunta}", flush=True)

            grid_element = await page.query_selector(".captchaGrid")
            screenshot_bytes = await grid_element.screenshot()
            
            # Salva no Storage para conferência manual depois
            arquivo_salvo = salvar_no_storage(screenshot_bytes, id_exec)

            # --- NOVO PROMPT COM RACIOCÍNIO ---
            print(f"🧠 [DEBUG][{id_exec}] Solicitando análise e correlação à IA...", flush=True)
            
            prompt_logic = f"""
            Analise cuidadosamente esta imagem de captcha numerada de 1 a 16.
            A pergunta é: "{pergunta}"
            
            Siga estes passos:
            1. Faça a analize da imagem inteira, pode ser que ela seja uma imagem dividida em varias como um quebra-cabeça.
            2. Identifique o que aparece em cada um dos quadrados numerados.
            2. Verifique qual desses objetos corresponde à pergunta feita.
            3. Explique brevemente sua correlação.
            4. No final, escreva 'RESULTADO: X' onde X é apenas o número do quadrado correto.
            """
            
            ia_start = time.time()
            response = client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=[
                    prompt_logic,
                    types.Part.from_bytes(data=screenshot_bytes, mime_type='image/png')
                ]
            )
            ia_duration = time.time() - ia_start
            
            pensamento_ia = response.text
            print(f"💬 [DEBUG][{id_exec}] PENSAMENTO DA IA:\n{pensamento_ia}", flush=True)

            # Extração do número final (procura por 'RESULTADO: X')
            try:
                if "RESULTADO:" in pensamento_ia:
                    resposta_final = pensamento_ia.split("RESULTADO:")[-1].strip().replace('.', '')
                else:
                    # Fallback caso ela não siga o formato
                    resposta_final = "".join(filter(str.isdigit, pensamento_ia))[-1] 
                
                print(f"🎯 [DEBUG][{id_exec}] Número extraído para clique: {resposta_final}", flush=True)
            except Exception as e:
                print(f"❌ [DEBUG][{id_exec}] Erro ao extrair número: {e}", flush=True)
                resposta_final = "1" # Default seguro

            # Execução do clique
            print(f"🖱️ [DEBUG][{id_exec}] Clicando no quadrado {resposta_final}...", flush=True)
            await page.click(f"text='{resposta_final}'", timeout=5000)
            print(f"✅ [DEBUG][{id_exec}] Clique concluído.", flush=True)

            return {
                "pergunta": pergunta,
                "analise_ia": pensamento_ia,
                "numero_clicado": resposta_final,
                "tempo_ia": f"{ia_duration:.2f}s",
                "imagem": arquivo_salvo
            }

        except Exception as e:
            print(f"🔥 [DEBUG][{id_exec}] ERRO: {str(e)}", flush=True)
            return {"status": "erro", "detalhes": str(e)}
        finally:
            await browser.close()
            print(f"🧹 [DEBUG][{id_exec}] Navegador fechado.", flush=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))


