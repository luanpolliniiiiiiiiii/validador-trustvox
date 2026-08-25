import os
import sys
import subprocess
import asyncio
import pandas as pd
import streamlit as st

try:
    from playwright.async_api import async_playwright
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
    from playwright.async_api import async_playwright

st.set_page_config(page_title="Trustvox Studio Online", page_icon="🛡️", layout="wide")

st.title("🛡️ Trustvox Migration Studio — Execução Online com Login")

with st.sidebar:
    st.title("🔑 Credenciais Trustvox")
    email_trustvox = st.text_input("E-mail Trustvox:", value="luan.araujo@reclameaqui.com.br")
    senha_trustvox = st.text_input("Senha Trustvox:", type="password")
    slug_empresa = st.text_input("Slug da Empresa:", value="coty").strip().lower()
    
    st.divider()
    st.subheader("🌐 Configurações de Proxy")
    usar_proxy = st.checkbox("Ativar Proxy de Saída", value=True)
    proxy_ip_porta = st.text_input("IP:Porta do Proxy:", value="31.59.20.176:6754")
    proxy_user = st.text_input("Usuário do Proxy:", value="mxjcpfer")
    proxy_pass = st.text_input("Senha do Proxy:", type="password", value="f080q5vj4ys9")

    st.divider()
    arquivo_enviado = st.file_uploader("Carregar Planilha De/Para", type=["xlsx", "csv"])

if arquivo_enviado and slug_empresa:
    if arquivo_enviado.name.endswith('.csv'):
        df_input = pd.read_csv(arquivo_enviado)
    else:
        df_input = pd.read_excel(arquivo_enviado)

    cols_lista = list(df_input.columns)
    col_antigo_default = next((c for c in cols_lista if any(k in str(c).lower() for k in ['cod', 'código', 'codigo', 'id_antigo'])), cols_lista[0])
    col_novo_default = next((c for c in cols_lista if any(k in str(c).lower() for k in ['novo', 'para', 'id_novo'])), cols_lista[1] if len(cols_lista) > 1 else cols_lista[0])

    col1_sel, col2_sel = st.columns(2)
    with col1_sel:
        col_antigo = st.selectbox("Selecione a coluna do CÓDIGO ANTIGO (IDs):", cols_lista, index=cols_lista.index(col_antigo_default))
    with col2_sel:
        col_novo = st.selectbox("Selecione a coluna do CÓDIGO NOVO (IDs):", cols_lista, index=cols_lista.index(col_novo_default))

    btn_iniciar = st.button("🚀 Iniciar Processamento Online", type="primary", use_container_width=True)
    
    status_box = st.empty()
    progress_bar = st.progress(0)
    log_box = st.container(height=300)

    async def rodar_validacao_com_login():
        df_input['Status Validação'] = 'Não Testado'
        df_input['Observação'] = '-'

        total_rows = len(df_input)
        aprovados_count = 0
        reprovados_count = 0

        url_login = f"https://app.trustvox.com.br/empresas/{slug_empresa}/produtos"

        async with async_playwright() as p:
            launch_kwargs = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            }

            if usar_proxy and proxy_ip_porta:
                launch_kwargs["proxy"] = {
                    "server": f"http://{proxy_ip_porta.strip()}",
                    "username": proxy_user.strip(),
                    "password": proxy_pass.strip()
                }

            browser = await p.chromium.launch(**launch_kwargs)
            context = await browser.new_context()
            page = await context.new_page()

            status_box.info("🌐 Conectando à Trustvox...")
            
            try:
                await page.goto(url_login, wait_until="domcontentloaded", timeout=35000)
                await page.wait_for_timeout(2000)

                if "login" in page.url or await page.locator("input[name='email']").is_visible():
                    await page.fill("input[name='email']", email_trustvox)
                    await page.fill("input[name='password']", senha_trustvox)
                    await page.click("button[type='submit']")
                    await page.wait_for_timeout(4000)

                if "login" in page.url:
                    status_box.error("❌ Falha na autenticação: Verifique credenciais ou o Proxy.")
                    await browser.close()
                    return df_input

                status_box.success("🎉 Autenticado com sucesso!")

            except Exception as e:
                status_box.error(f"Erro ao conectar: {e}")
                await browser.close()
                return df_input

            url_loja = f"https://app.trustvox.com.br/{slug_empresa}/products"

            for idx in range(total_rows):
                val_antigo = str(df_input.at[idx, col_antigo]).strip()
                val_novo = str(df_input.at[idx, col_novo]).strip()
                linha_excel = idx + 2

                status_val = "REPROVADO"
                obs = ""

                try:
                    await page.goto(url_loja, wait_until="domcontentloaded")
                    await page.wait_for_timeout(1000)

                    btn_filtrar = page.locator("button:has-text('Filtrar')").first
                    await btn_filtrar.click(timeout=6000)

                    opcao_codigo = page.locator("text=Código do Produto").first
                    await opcao_codigo.click(timeout=6000)

                    input_popup = page.locator("div[class*='popover'] input, div[class*='filter'] input").first
                    await input_popup.fill(val_antigo)

                    btn_confirmar = page.locator("button:has-text('Confirmar')").first
                    await btn_confirmar.click(timeout=6000)
                    await page.wait_for_timeout(2000)

                    page_content = await page.content()
                    if val_antigo in page_content or val_novo in page_content:
                        status_val = "APROVADO"
                        obs = "Código localizado"
                    else:
                        obs = f"Código {val_antigo} não localizado"

                except Exception as err:
                    obs = f"Falha na busca: {str(err)}"

                if status_val == "APROVADO":
                    aprovados_count += 1
                    log_box.success(f"Linha {linha_excel} | ID {val_antigo} ➔ {val_novo} | ✅ APROVADO")
                else:
                    reprovados_count += 1
                    log_box.error(f"Linha {linha_excel} | ID {val_antigo} ➔ {val_novo} | ❌ REPROVADO ({obs})")

                df_input.at[idx, 'Status Validação'] = status_val
                df_input.at[idx, 'Observação'] = obs

                progress_bar.progress((idx + 1) / total_rows)

            await browser.close()
            return df_input

    if btn_iniciar:
        if not email_trustvox or not senha_trustvox:
            st.warning("Preencha seu E-mail e Senha na barra lateral.")
        else:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                df_final = loop.run_until_complete(rodar_validacao_com_login())
            else:
                df_final = asyncio.run(rodar_validacao_com_login())

            status_box.success("🎉 Validação concluída!")
            nome_saida = f"relatorio_{slug_empresa}_online.xlsx"
            df_final.to_excel(nome_saida, index=False)

            st.dataframe(df_final[['Status Validação', col_antigo, col_novo, 'Observação']], use_container_width=True)

            with open(nome_saida, "rb") as file:
                st.download_button(
                    label="📥 Baixar Relatório Consolidado (Excel)",
                    data=file,
                    file_name=nome_saida,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                    
