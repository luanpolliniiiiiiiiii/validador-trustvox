import asyncio
import os
import pandas as pd
import streamlit as st
from playwright.async_api import async_playwright

st.set_page_config(
    page_title="Trustvox Studio Online",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Trustvox Migration Studio — Execução Online")
st.caption("Validação remota via Playwright com suporte a Proxy de Saída")

# --- SIDEBAR: CONFIGURAÇÕES E PROXY ---
with st.sidebar:
    st.title("⚙️ Configurações")
    slug_empresa = st.text_input("Slug da Empresa:", value="coty").strip().lower()
    
    st.divider()
    st.subheader("🌐 Configurações de Proxy")
    usar_proxy = st.checkbox("Ativar Proxy de Saída", value=True)
    proxy_ip_porta = st.text_input("IP:Porta do Proxy:", value="31.59.20.176:6754")
    proxy_user = st.text_input("Usuário do Proxy:", value="mxjcpfer")
    proxy_pass = st.text_input("Senha do Proxy:", type="password", value="f080q5vj4ys9")

    arquivo_enviado = st.file_uploader("Carregar Planilha De/Para", type=["xlsx", "csv"])

if not arquivo_enviado or not slug_empresa:
    st.info("👈 **Para começar:** Informe o slug da empresa, configure o proxy e suba a planilha na barra lateral.")
else:
    if arquivo_enviado.name.endswith('.csv'):
        df_input = pd.read_csv(arquivo_enviado)
    else:
        df_input = pd.read_excel(arquivo_enviado)

    cols_lista = list(df_input.columns)
    
    # Mapeamento para tentar encontrar automaticamente as colunas de CÓDIGO (ignorando nomes)
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

    # --- LÓGICA DE AUTOMATION VIA PLAYWRIGHT + PROXY ---
    async def rodar_validacao_online():
        df_input['Status Validação'] = 'Não Testado'
        df_input['Observação'] = '-'

        total_rows = len(df_input)
        aprovados_count = 0
        reprovados_count = 0

        url_loja = f"https://app.trustvox.com.br/{slug_empresa}/products"

        async with async_playwright() as p:
            # Configuração das opções de inicialização do navegador
            launch_args = {
                "headless": True, # Headless obrigatório no Streamlit Cloud
                "args": ["--no-sandbox", "--disable-setuid-sandbox"]
            }

            # Injeção das credenciais do Proxy se ativado
            if usar_proxy and proxy_ip_porta:
                launch_args["proxy"] = {
                    "server": f"http://{proxy_ip_porta.strip()}",
                    "username": proxy_user.strip(),
                    "password": proxy_pass.strip()
                }

            browser = await p.chromium.launch(**launch_args)
            context = await browser.new_context()
            page = await context.new_page()

            status_box.info(f"🌐 Conectando à Trustvox via Proxy ({proxy_ip_porta})...")
            
            try:
                await page.goto(url_loja, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
            except Exception as e:
                status_box.error(f"Erro ao acessar Trustvox via Proxy: {e}")
                await browser.close()
                return df_input

            # Loop por 100% dos itens da planilha
            for idx in range(total_rows):
                val_antigo = str(df_input.at[idx, col_antigo]).strip()
                val_novo = str(df_input.at[idx, col_novo]).strip()
                linha_excel = idx + 2

                status_val = "REPROVADO"
                obs = ""

                try:
                    await page.goto(url_loja, wait_until="domcontentloaded")
                    await page.wait_for_timeout(1000)

                    # 1. Clicar em Filtrar
                    btn_filtrar = page.locator("button:has-text('Filtrar')").first
                    await btn_filtrar.click(timeout=6000)

                    # 2. Clicar em Código do Produto
                    opcao_codigo = page.locator("text=Código do Produto").first
                    await opcao_codigo.click(timeout=6000)

                    # 3. Preencher a caixa de texto
                    input_popup = page.locator("div[class*='popover'] input, div[class*='filter'] input").first
                    await input_popup.fill(val_antigo)

                    # 4. Confirmar Busca
                    btn_confirmar = page.locator("button:has-text('Confirmar')").first
                    await btn_confirmar.click(timeout=6000)
                    await page.wait_for_timeout(2000)

                    # 5. Avaliar Tabela de Resultados
                    page_content = await page.content()
                    if val_antigo in page_content or val_novo in page_content:
                        status_val = "APROVADO"
                        obs = "Código localizado na tabela do Trustvox"
                    else:
                        obs = f"Código {val_antigo} não retornou resultados na busca"

                except Exception as err:
                    obs = f"Falha ao processar item: {str(err)}"

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
        with st.spinner("Executando validação via Playwright com Proxy..."):
            df_final = asyncio.run(rodar_validacao_online())
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
