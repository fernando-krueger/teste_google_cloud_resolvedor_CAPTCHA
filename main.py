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
    id_exec = f"MULTI-{int(time.time())}"
    print(f"\n🚀 [{id_exec}] >>> INICIANDO SESSÃO MULTI-ETAPAS <<<", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            print(f"🌐 [DEBUG] Navegando para o site...", flush=True)
            await page.goto("https://john.fun/captcha-game", timeout=60000)
            
            total_resolvidos = 0
            while total_resolvidos < 15:
                print(f"\n🧩 [DESAFIO {total_resolvidos + 1}] Localizando elementos...", flush=True)
                
                try:
                    await page.wait_for_selector("div.captchaInstructions", timeout=15000)
                except:
                    print(f"🏁 [FIM] Instruções não encontradas. Verifique se o captcha acabou.", flush=True)
                    break

                # Memória desta imagem específica
                historico_da_etapa = set() # Usando set para busca rápida
                sucesso_na_etapa = False

                for rodada in range(1, 10): # Aumentado para 10 tentativas por imagem
                    print(f"--- 🔄 Etapa {total_resolvidos+1} | Rodada {rodada} ---", flush=True)
                    
                    # Captura pergunta e imagem
                    await asyncio.sleep(2)
                    pergunta = (await page.inner_text("div.captchaInstructions")).replace('\n', ' ').strip()
                    grid_element = await page.query_selector(".captchaGrid")
                    screenshot_bytes = await grid_element.screenshot()
                    
                    # Log Visual no Storage
                    hora_f = datetime.now().strftime("%H:%M:%S")
                    blob_name = f"{id_exec}_E{total_resolvidos+1}_R{rodada}_{hora_f}.png"
                    storage_client.bucket(BUCKET_NAME).blob(blob_name).upload_from_string(screenshot_bytes, content_type='image/png')

                    # Monta prompt com histórico de falhas
                    falhas_str = " Nenhuma ainda" if not historico_da_etapa else " | ".join(list(historico_da_etapa))
                    print(f"📡 [DEBUG] Enviando para IA. Falhas registradas: {falhas_str}", flush=True)

                    prompt = f"""
                    Pergunta: {pergunta}
                    COMBINAÇÕES QUE JÁ FALHARAM NESTA IMAGEM: [{falhas_str}]
                    
                    Analise a imagem e forneça uma NOVA combinação (diferente das falhas acima).
                    Escreva apenas: RESULTADO: n1, n2, n3
                    """
                    
                    response = client_ai.models.generate_content(
                        model='gemini-2.0-flash',
                        contents=[prompt, types.Part.from_bytes(data=screenshot_bytes, mime_type='image/png')]
                    )
                    
                    # Extração robusta
                    try:
                        texto_ia = response.text
                        resultado_bruto = texto_ia.split("RESULTADO:")[-1].strip()
                        numeros_lista = re.findall(r'\d+', resultado_bruto)
                        numeros_lista.sort(key=int)
                        combo_str = ",".join(numeros_lista)
                        
                        print(f"🧠 [IA] Pensamento extraído: {combo_str}", flush=True)
                    except:
                        print(f"⚠️ [ERRO] IA enviou formato inválido. Texto: {texto_ia[:100]}", flush=True)
                        continue

                    # FILTRO DE REPETIÇÃO NO PYTHON (Se a IA teimar, o código ignora e tenta de novo)
                    if combo_str in historico_da_etapa:
                        print(f"⛔ [FILTRO] IA repetiu a combinação {combo_str}! Ignorando clique e pedindo nova...", flush=True)
                        continue 

                    # Execução dos Cliques
                    print(f"🖱️ [AÇÃO] Clicando nos quadrados: {numeros_lista}", flush=True)
                    for num in numeros_lista:
                        await page.click(f".captchaGrid > div:nth-child({num})")
                        await asyncio.sleep(0.3)

                    # Verificar
                    print(f"🔘 [AÇÃO] Clicando em Verificar...", flush=True)
                    await page.click("div.captchaBottomBar > div.verifyButton")
                    await asyncio.sleep(3)

                    # Checagem de Erro
                    if await page.is_visible("div.captchaBottomBar > div.redText"):
                        erro_msg = await page.inner_text("div.captchaBottomBar > div.redText")
                        print(f"❌ [LOG] Falhou: {erro_msg}. Adicionando {combo_str} ao histórico.", flush=True)
                        historico_da_etapa.add(combo_str)
                        
                        # Limpa seleção clicando novamente
                        print(f"🧹 [AÇÃO] Limpando seleção anterior...", flush=True)
                        for num in numeros_lista:
                            await page.click(f".captchaGrid > div:nth-child({num})")
                    else:
                        print(f"✅ [SUCESSO] Etapa {total_resolvidos+1} vencida!", flush=True)
                        sucesso_na_etapa = True
                        total_resolvidos += 1
                        break # Sai do loop de rodadas e vai para a próxima imagem

                if not sucesso_na_etapa:
                    print(f"🛑 [PARADA] Não foi possível resolver a etapa {total_resolvidos+1} após várias tentativas.", flush=True)
                    break

            return {"sessao": id_exec, "total_etapas": total_resolvidos, "status": "concluido"}

        except Exception as e:
            print(f"🔥 [ERRO CRÍTICO] {str(e)}", flush=True)
            return {"erro": str(e)}
        finally:
            print(f"🧹 [DEBUG] Fechando sessão.", flush=True)
            await browser.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
