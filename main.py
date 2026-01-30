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

client_ai = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
storage_client = storage.Client(project=PROJECT_ID)

@app.get("/testar")
async def testar_automacao():
    id_exec = f"LOOP-{int(time.time())}"
    print(f"🚀 [{id_exec}] Iniciando ciclo de resolução inteligente...", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            await page.goto("https://john.fun/captcha-game", timeout=60000)
            
            tentativas_bloqueadas = []
            sucesso_final = False

            # Loop de até 5 tentativas para vencer o desafio
            for rodada in range(1, 6):
                print(f"\n🔄 [DEBUG][{id_exec}] RODADA {rodada} - Números já tentados: {tentativas_bloqueadas}", flush=True)
                
                # 1. Captura Pergunta e Imagem
                await page.wait_for_selector("div.captchaInstructions")
                await asyncio.sleep(2)
                pergunta = (await page.inner_text("div.captchaInstructions")).replace('\n', ' ').strip()
                
                grid_element = await page.query_selector("div.captchaGrid")
                screenshot_bytes = await grid_element.screenshot()
                
                # Salva no Storage para log visual
                hora_f = datetime.now().strftime("%H:%M:%S")
                blob_name = f"captcha {hora_f} rodada {rodada}.png"
                storage_client.bucket(BUCKET_NAME).blob(blob_name).upload_from_string(screenshot_bytes, content_type='image/png')

                # 2. IA com Memória de Erros
                prompt = f"""
                Analise a imagem. Pergunta: "{pergunta}"
                Números que você NÃO pode escolher (já deram erro): {tentativas_bloqueadas}
                
                Explique o que vê e decida o melhor quadrado restante.
                No final escreva apenas: RESULTADO: X
                """
                
                response = client_ai.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=[prompt, types.Part.from_bytes(data=screenshot_bytes, mime_type='image/png')]
                )
                
                pensamento = response.text
                print(f"🧠 [DEBUG] IA Pensou: {pensamento[:200]}...", flush=True)
                
                # Extrai número (ex: "RESULTADO: 4")
                try:
                    escolha = "".join(filter(str.isdigit, pensamento.split("RESULTADO:")[-1]))[0]
                except:
                    print(f"⚠️ Erro ao extrair número, tentando o primeiro dígito disponível...", flush=True)
                    escolha = "".join(filter(str.isdigit, pensamento))[-1]

                # 3. Ação: Clicar no Quadrado
                # Seletor dinâmico baseado no número (nth-child)
                # Nota: Em grids, o número costuma bater com o nth-child
                selector_quadrado = f".captchaGrid > div:nth-child({escolha})"
                print(f"🖱️ [DEBUG] Clicando no quadrado {escolha}...", flush=True)
                await page.click(selector_quadrado)
                
                # 4. Clicar em Verificar
                btn_verificar = "div.captchaBottomBar > div.verifyButton"
                print(f"🔘 [DEBUG] Clicando em Verificar...", flush=True)
                await page.click(btn_verificar)
                await asyncio.sleep(2)

                # 5. Checar Resultado
                erro_selector = "div.captchaBottomBar > div.redText"
                is_erro = await page.is_visible(erro_selector)

                if is_erro:
                    msg_erro = await page.inner_text(erro_selector)
                    print(f"❌ [DEBUG] ERRO DETECTADO: {msg_erro}. Desmarcando {escolha}...", flush=True)
                    tentativas_bloqueadas.append(escolha)
                    # Clica de novo no mesmo quadrado para desmarcar antes da próxima rodada
                    await page.click(selector_quadrado)
                else:
                    print(f"✨ [DEBUG] SEM ERRO! Verificando se avançou ou concluiu...", flush=True)
                    # Se o grid sumiu ou mudou, consideramos sucesso da rodada
                    sucesso_final = True
                    break

            return {
                "status": "sucesso" if sucesso_final else "limite_atingido",
                "tentativas_bloqueadas": tentativas_bloqueadas,
                "ultima_escolha": escolha
            }

        except Exception as e:
            print(f"🔥 [DEBUG] ERRO GERAL: {str(e)}", flush=True)
            return {"erro": str(e)}
        finally:
            await browser.close()
            print(f"🧹 [DEBUG] Navegador fechado.", flush=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
