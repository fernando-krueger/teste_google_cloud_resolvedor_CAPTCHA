import asyncio
import os
import time
import re
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
    id_exec = f"MULTI-{int(time.time())}"
    print(f"\n🚀 [{id_exec}] INICIANDO RESOLUÇÃO MULTI-ETAPAS", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            print(f"🌐 [DEBUG] Acessando site...", flush=True)
            await page.goto("https://john.fun/captcha-game", timeout=60000)
            
            total_resolvidos = 0
            # Loop Principal: Continua enquanto houver desafios na tela
            while total_resolvidos < 15: 
                print(f"\n🧩 --- DESAFIO ATUAL: {total_resolvidos + 1} ---", flush=True)
                
                # Verifica se o captcha ainda existe na tela
                try:
                    await page.wait_for_selector("div.captchaInstructions", timeout=10000)
                except:
                    print(f"🏁 [DEBUG] Seletor de instrução não encontrado. Desafio completo!", flush=True)
                    break

                historico_tentativas = [] 
                sucesso_na_etapa = False

                # Loop de Tentativas para o MESMO desafio (caso erre a combinação)
                for rodada in range(1, 6):
                    await asyncio.sleep(2) # Espera renderizar nova imagem
                    pergunta = (await page.inner_text("div.captchaInstructions")).replace('\n', ' ').strip()
                    
                    grid_element = await page.query_selector(".captchaGrid")
                    if not grid_element: break
                    
                    screenshot_bytes = await grid_element.screenshot()
                    
                    # Salva para log
                    hora_f = datetime.now().strftime("%H:%M:%S")
                    storage_client.bucket(BUCKET_NAME).blob(f"{id_exec}_E{total_resolvidos}_R{rodada}.png").upload_from_string(screenshot_bytes, content_type='image/png')

                    # Prompt com memória de erros da rodada atual
                    instrucao_memoria = ""
                    if historico_tentativas:
                        falhas = " | ".join(historico_tentativas)
                        instrucao_memoria = f"\n⚠️ COMBINAÇÕES QUE JÁ FALHARAM NESTE DESAFIO: [{falhas}]"

                    prompt = f"Pergunta: {pergunta}{instrucao_memoria}\nResponda apenas com RESULTADO: n1, n2..."
                    
                    response = client_ai.models.generate_content(
                        model='gemini-2.0-flash',
                        contents=[prompt, types.Part.from_bytes(data=screenshot_bytes, mime_type='image/png')]
                    )
                    
                    try:
                        resultado_bruto = response.text.split("RESULTADO:")[-1].strip()
                        numeros_atuais = re.findall(r'\d+', resultado_bruto)
                        numeros_atuais.sort(key=int)
                        combo_str = ",".join(numeros_atuais)
                    except: continue

                    # Clica nos quadrados
                    for num in numeros_atuais:
                        await page.click(f".captchaGrid > div:nth-child({num})")
                        await asyncio.sleep(0.3)

                    # Verifica
                    await page.click("div.captchaBottomBar > div.verifyButton")
                    await asyncio.sleep(2.5)

                    # Checa erro (texto vermelho)
                    if await page.is_visible("div.captchaBottomBar > div.redText"):
                        print(f"❌ Errou a combinação {combo_str}. Tentando novamente...", flush=True)
                        historico_tentativas.append(combo_str)
                        # Desmarca
                        for num in numeros_atuais:
                            await page.click(f".captchaGrid > div:nth-child({num})")
                    else:
                        print(f"✅ Etapa {total_resolvidos + 1} concluída com sucesso!", flush=True)
                        sucesso_na_etapa = True
                        total_resolvidos += 1
                        break # Sai do loop de tentativas e volta para o loop principal (próxima imagem)

                if not sucesso_na_etapa:
                    print("🚫 Falha persistente nesta etapa. Abortando.", flush=True)
                    break

            return {"id": id_exec, "total_resolvidos": total_resolvidos, "status": "finalizado"}

        except Exception as e:
            print(f"🔥 ERRO: {e}", flush=True)
            return {"erro": str(e)}
        finally:
            await browser.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
