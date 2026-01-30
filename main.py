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

PROJECT_ID = "numeric-skill-484321-a5" 
LOCATION = "us-central1"
BUCKET_NAME = "imagem-captcha"

client_ai = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
storage_client = storage.Client(project=PROJECT_ID)

@app.get("/testar")
async def testar_automacao():
    id_exec = f"COMBO-{int(time.time())}"
    print(f"🚀 [{id_exec}] Iniciando resolução de combinações...", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            await page.goto("https://john.fun/captcha-game", timeout=60000)
            
            historico_tentativas = [] # Lista de listas: [[1, 2], [1, 3]]
            sucesso_final = False

            for rodada in range(1, 6):
                print(f"\n--- RODADA {rodada} ---", flush=True)
                
                await page.wait_for_selector("div.captchaInstructions")
                pergunta = (await page.inner_text("div.captchaInstructions")).replace('\n', ' ').strip()
                
                grid_element = await page.query_selector(".captchaGrid")
                screenshot_bytes = await grid_element.screenshot()

                # IA com instrução estrita de formato
                rejeitados_str = " | ".join([str(h) for h in historico_tentativas])
                prompt = f"""
                Pergunta: {pergunta}
                Combine os quadrados numerados que respondem à pergunta.
                JÁ TENTADOS E ERRADOS: [{rejeitados_str}]
                
                Analise a imagem e forneça uma NOVA combinação.
                Escreva exatamente neste formato no final: RESULTADO: n1, n2, n3
                """
                
                print(f"🧠 [DEBUG] Solicitando análise...", flush=True)
                response = client_ai.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=[prompt, types.Part.from_bytes(data=screenshot_bytes, mime_type='image/png')]
                )
                
                texto_ia = response.text
                print(f"💬 [DEBUG] IA pensou: {texto_ia.split('RESULTADO:')[0][-150:]}", flush=True)

                # --- CORREÇÃO NA EXTRAÇÃO ---
                # Busca todos os números após a palavra RESULTADO
                try:
                    resultado_bruto = texto_ia.split("RESULTADO:")[-1]
                    # Encontra todos os números (mesmo com 2 dígitos como '16')
                    numeros_atuais = re.findall(r'\d+', resultado_bruto)
                    print(f"🎯 [DEBUG] Combinação extraída: {numeros_atuais}", flush=True)
                except:
                    print(f"⚠️ Falha ao extrair números. Pulando rodada.", flush=True)
                    continue

                if not numeros_atuais:
                    print("⚠️ IA não retornou números válidos.", flush=True)
                    continue

                # 3. Execução dos Cliques
                for num in numeros_atuais:
                    print(f"🖱️ Clicando no quadrado {num}...", flush=True)
                    # nth-child(16) agora funciona corretamente para grids grandes
                    await page.click(f".captchaGrid > div:nth-child({num})")
                
                # 4. Verificar
                print(f"🔘 Verificando...", flush=True)
                await page.click("div.captchaBottomBar > div.verifyButton")
                await asyncio.sleep(2)

                # 5. Checar Erro
                erro_visivel = await page.is_visible("div.captchaBottomBar > div.redText")
                if erro_visivel:
                    print(f"❌ Erro detectado. Salvando {numeros_atuais} no histórico.", flush=True)
                    historico_tentativas.append(numeros_atuais)
                    
                    # Limpa o grid clicando novamente nos mesmos botões
                    print(f"🧹 Desmarcando botões...", flush=True)
                    for num in numeros_atuais:
                        await page.click(f".captchaGrid > div:nth-child({num})")
                else:
                    print(f"✨ Sucesso na rodada!", flush=True)
                    sucesso_final = True
                    break

            return {"id": id_exec, "status": "venceu" if sucesso_final else "tentativas_esgotadas"}

        except Exception as e:
            print(f"🔥 ERRO: {e}", flush=True)
            return {"erro": str(e)}
        finally:
            await browser.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
