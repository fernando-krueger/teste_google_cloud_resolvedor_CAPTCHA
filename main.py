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

# Inicializa Clientes
client_ai = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
storage_client = storage.Client(project=PROJECT_ID)

@app.get("/testar")
async def testar_automacao():
    id_exec = f"COMBO-{int(time.time())}"
    print(f"\n🚀 [{id_exec}] INICIANDO RESOLVEDOR DE COMBINAÇÕES", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        
        try:
            print(f"🌐 [DEBUG] Acessando site...", flush=True)
            await page.goto("https://john.fun/captcha-game", timeout=60000)
            
            historico_tentativas = [] # Lista de strings ordenadas: ["7,8,9", "1,4"]
            sucesso_final = False

            for rodada in range(1, 7): # Aumentado para 6 tentativas
                print(f"\n--- 🔄 RODADA {rodada} ---", flush=True)
                
                # 1. Captura de Dados
                await page.wait_for_selector("div.captchaInstructions")
                await asyncio.sleep(2)
                pergunta = (await page.inner_text("div.captchaInstructions")).replace('\n', ' ').strip()
                print(f"❓ [DEBUG] Pergunta: {pergunta}", flush=True)
                
                grid_element = await page.query_selector(".captchaGrid")
                screenshot_bytes = await grid_element.screenshot()
                
                # Salva no Storage para conferência
                hora_f = datetime.now().strftime("%H:%M:%S")
                blob_name = f"{id_exec}_R{rodada}_{hora_f}.png"
                storage_client.bucket(BUCKET_NAME).blob(blob_name).upload_from_string(screenshot_bytes, content_type='image/png')

                # 2. IA com Memória de Erros
                # Criamos um texto claro das falhas para a IA não repetir
                instrucao_memoria = ""
                if historico_tentativas:
                    falhas = "\n".join([f"- Combinação {h} (ERRADA)" for h in historico_tentativas])
                    instrucao_memoria = f"\n⚠️ VOCÊ JÁ TENTOU ESTAS E FALHOU:\n{falhas}\nNÃO REPITA NENHUMA DELAS!"

                prompt = f"""
                Analise a imagem de captcha (grid de quadrados numerados).
                Pergunta: "{pergunta}"
                {instrucao_memoria}
                
                PASSO A PASSO:
                1. analise a imagem como um todo, ela pode estar dividida como se fosse um quebra-cabeça
                1. Descreva o que vê em cada quadrado relevante.
                2. Identifique a combinação de quadrados que responde à pergunta.
                3. Garanta que essa combinação é diferente das que já falharam.
                
                No final, escreva no formato: RESULTADO: n1, n2, n3
                """
                
                print(f"🧠 [DEBUG] IA processando...", flush=True)
                response = client_ai.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=[prompt, types.Part.from_bytes(data=screenshot_bytes, mime_type='image/png')]
                )
                
                texto_ia = response.text
                print(f"💬 [DEBUG] Pensamento IA:\n{texto_ia}", flush=True)

                # 3. Extração e Validação dos Números
                try:
                    resultado_bruto = texto_ia.split("RESULTADO:")[-1].strip()
                    numeros_atuais = re.findall(r'\d+', resultado_bruto)
                    numeros_atuais.sort(key=int) # Ordena numericamente: 7,8,9
                    combo_str = ",".join(numeros_atuais)
                    
                    if combo_str in historico_tentativas:
                        print(f"⚠️ [DEBUG] AVISO: IA sugeriu {combo_str} novamente mesmo estando no histórico!", flush=True)
                except Exception as e:
                    print(f"❌ [DEBUG] Erro ao extrair números: {e}", flush=True)
                    continue

                if not numeros_atuais:
                    print("⚠️ [DEBUG] IA não retornou números.", flush=True)
                    continue

                # 4. Execução: Clica nos quadrados
                for num in numeros_atuais:
                    print(f"🖱️ [DEBUG] Clicando no {num}...", flush=True)
                    # Seletor body > ... > div.captchaGrid > div:nth-child(X)
                    await page.click(f".captchaGrid > div:nth-child({num})")
                    await asyncio.sleep(0.4) # Delay para o site registrar

                # 5. Clique em Verificar
                print(f"🔘 [DEBUG] Clicando em Verificar...", flush=True)
                await page.click("div.captchaBottomBar > div.verifyButton")
                await asyncio.sleep(2.5)

                # 6. Analisa se houve Erro
                erro_visivel = await page.is_visible("div.captchaBottomBar > div.redText")
                if erro_visivel:
                    msg_erro = await page.inner_text("div.captchaBottomBar > div.redText")
                    print(f"❌ [DEBUG] REJEITADO: {msg_erro}", flush=True)
                    
                    # Salva no histórico para não repetir
                    if combo_str not in historico_tentativas:
                        historico_tentativas.append(combo_str)
                    
                    # DESMARCAR os botões clicados para a próxima rodada
                    print(f"🧹 [DEBUG] Desmarcando {numeros_atuais} para limpar o grid...", flush=True)
                    for num in numeros_atuais:
                        await page.click(f".captchaGrid > div:nth-child({num})")
                        await asyncio.sleep(0.2)
                else:
                    print(f"✨ [DEBUG] SUCESSO! O texto vermelho não apareceu.", flush=True)
                    sucesso_final = True
                    break

            return {
                "id": id_exec,
                "resultado": "venceu" if sucesso_final else "falhou",
                "tentativas": historico_tentativas
            }

        except Exception as e:
            print(f"🔥 [DEBUG] ERRO CRÍTICO: {e}", flush=True)
            return {"status": "erro", "detalhes": str(e)}
        finally:
            print(f"🧹 [DEBUG] Fechando navegador.", flush=True)
            await browser.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

