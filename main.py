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
    id_exec = f"COMBO-{int(time.time())}"
    print(f"🚀 [{id_exec}] Iniciando resolvedor de combinações...", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            await page.goto("https://john.fun/captcha-game", timeout=60000)
            
            combinacoes_rejeitadas = []
            sucesso_final = False

            for rodada in range(1, 6):
                print(f"\n🔄 [DEBUG] RODADA {rodada}", flush=True)
                
                # 1. Preparação: Aguarda pergunta e captura imagem
                await page.wait_for_selector("div.captchaInstructions")
                await asyncio.sleep(2)
                pergunta = (await page.inner_text("div.captchaInstructions")).replace('\n', ' ').strip()
                
                grid_element = await page.query_selector(".captchaGrid")
                screenshot_bytes = await grid_element.screenshot()
                
                # Salva imagem para conferência
                hora_f = datetime.now().strftime("%H:%M:%S")
                storage_client.bucket(BUCKET_NAME).blob(f"{id_exec}_R{rodada}.png").upload_from_string(screenshot_bytes, content_type='image/png')

                # 2. IA decide a combinação (excluindo as que já falharam)
                rejeitadas_str = ", ".join([str(c) for c in combinacoes_rejeitadas])
                prompt = f"""
                Pergunta: "{pergunta}"
                A imagem tem um grid de 1 a 9. Você deve selecionar TODOS os quadrados que correspondem à pergunta.
                
                IMPORTANTE: As seguintes combinações de números já foram tentadas e estão ERRADAS: [{rejeitadas_str}]
                Analise a imagem e forneça uma NOVA combinação que você acredita estar correta.
                
                Pense passo a passo e no final escreva apenas: RESULTADO: [números separados por vírgula]
                Exemplo: RESULTADO: 1, 4, 9
                """
                
                print(f"🧠 [DEBUG] Solicitando nova combinação (evitando as falhas)...", flush=True)
                response = client_ai.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=[prompt, types.Part.from_bytes(data=screenshot_bytes, mime_type='image/png')]
                )
                
                texto_ia = response.text
                print(f"💬 [DEBUG] Pensamento IA: {texto_ia[:150]}...", flush=True)
                
                try:
                    # Extrai os números (ex: "1, 4, 9")
                    parte_resultado = texto_ia.split("RESULTADO:")[-1].strip()
                    numeros_atuais = [n.strip() for n in parte_resultado.split(",") if n.strip().isdigit()]
                    print(f"🎯 [DEBUG] IA escolheu a combinação: {numeros_atuais}", flush=True)
                except:
                    print(f"⚠️ Erro ao extrair. Abortando rodada.", flush=True)
                    continue

                # 3. Execução: Clica nos quadrados escolhidos
                for num in numeros_atuais:
                    print(f"🖱️ Clicando no {num}...", flush=True)
                    await page.click(f".captchaGrid > div:nth-child({num})")
                    await asyncio.sleep(0.3)

                # 4. Verifica
                print(f"🔘 Clicando em Verificar...", flush=True)
                await page.click("div.captchaBottomBar > div.verifyButton")
                await asyncio.sleep(2)

                # 5. Lógica de Erro ou Sucesso
                erro_selector = "div.captchaBottomBar > div.redText"
                if await page.is_visible(erro_selector):
                    print(f"❌ [DEBUG] Combinação {numeros_atuais} REJEITADA.", flush=True)
                    combinacoes_rejeitadas.append(numeros_atuais)
                    
                    # DESMARCAR: Clica novamente nos mesmos números para limpar o grid
                    print(f"🧹 Desmarcando para tentar novamente...", flush=True)
                    for num in numeros_atuais:
                        await page.click(f".captchaGrid > div:nth-child({num})")
                else:
                    print(f"✨ [DEBUG] SUCESSO! Desafio vencido ou avançado.", flush=True)
                    sucesso_final = True
                    break

            return {
                "id": id_exec,
                "resultado": "venceu" if sucesso_final else "falhou",
                "historico_tentativas": combinacoes_rejeitadas
            }

        except Exception as e:
            print(f"🔥 [DEBUG] ERRO: {e}", flush=True)
            return {"erro": str(e)}
        finally:
            await browser.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
