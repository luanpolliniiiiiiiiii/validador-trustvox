import os
import sys
import time
import pandas as pd
import streamlit as st
from playwright.sync_api import sync_playwright

st.set_page_config(
    page_title="Trustvox Studio | Online Migration",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #0f1117; color: #e6e6e6; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("📚 Fontes & Empresa")
    
    st.subheader("🔑 Credenciais Trustvox")
    col_usr, col_dom = st.columns([1.3, 1.7])
    with col_usr:
        user_email = st.text_input("E-mail:", value="luan.araujo")
    with col_dom:
        dom_email = st.text_input("Domínio:", value="@reclameaqui.com.br", disabled=True)
    
    email_trustvox = f"{user_email.strip()}{dom_email.strip()}"
    senha_trustvox = st.text_input("Senha Trustvox:", type="password")
    
    slug_empresa = st.text_input(
        "Slug da Empresa no Trustvox:",
        value="coty"
    ).strip().lower()

    st.divider()
    arquivo_enviado = st.file_uploader(
        "Carregar Planilha De/Para",
        type=["xlsx", "csv"]
    )

    modo_validacao = st.radio(
        "Escopo de Validação",
        ["Validar 100% dos Produtos", "Amostragem em Blocos (~40%)"],
        index=0
    )

st.title("🛡️ Trustvox Migration Studio — Execução Direct Connection")

if arquivo_enviado is None or not slug_empresa:
    st.info("👈 Informe suas credenciais, slug e suba a planilha na barra lateral para iniciar.")
else:
    if arquivo_enviado.name.endswith('.csv'):
        df_input = pd.read_csv(arquivo_enviado)
    else:
        df_input = pd.read_excel(arquivo_enviado)

    cols_lista = list(df_input.columns)
    
    col_antigo_default = next(
        (c for c in cols_lista if any(k in str(c).lower() for k in ['cod_antigo', 'código antigo', 'codigo antigo', 'id antigo', 'id_antigo', 'código antigo do produto'])),
        cols_lista[0]
    )
    
    col_novo_default = next(
        (c for c in cols_lista if any(k in str(c).lower() for k in ['cod_novo', 'código novo', 'codigo novo', 'id novo', 'id_novo', 'novo código do produto'])),
        cols_lista[1] if len(cols_lista) > 1 else cols_lista[0]
    )

    col_execucao, col_analytics = st.columns([1.1, 0.9], gap="large")

    with col_execucao:
        st.markdown("### 🎯 Central de Execução")
        col1_sel, col2_sel = st.columns(2)
        with col1_sel:
            col_antigo = st.selectbox("Coluna CÓDIGO ANTIGO (Trustvox):", cols_lista, index=cols_lista.index(col_antigo_default))
        with col2_sel:
            col_novo = st.selectbox("Coluna CÓDIGO NOVO (Site):", cols_lista, index=cols_lista.index(col_novo_default))

        btn_iniciar = st.button("🚀 Iniciar Processamento Online", type="primary", use_container_width=True)
        
        status_box = st.empty()
        progress_bar = st.progress(0)
        log_box = st.container(height=350)

    with col_analytics:
        st.markdown("### 📊 Painel de Insights")
        m1, m2, m3 = st.columns(3)
        with m1:
            kpi_total = st.empty()
            kpi_total.metric("Analisados", "0")
        with m2:
            kpi_ok = st.empty()
            kpi_ok.metric("Aprovados", "0")
        with m3:
            kpi_err = st.empty()
            kpi_err.metric("Reprovados", "0")

        st.divider()
        tabela_live = st.empty()

    def rodar_validacao_real():
        col_antigo_name = col_antigo
        col_novo_name = col_novo

        col_status_nome = 'Status Validação'
        col_obs_nome = 'Observação Validação'

        df_input[col_status_nome] = 'Não Testado'
        df_input[col_obs_nome] = '-'

        total_rows = len(df_input)

        if "100%" in modo_validacao:
            indices = list(range(total_rows))
        else:
            indices = []
            for inicio in range(0, total_rows, 25):
                indices.extend(range(inicio, min(inicio + 10, total_rows)))

        aprovados_count = 0
        reprovados_count = 0

        url_login = "https://app.trustvox.com.br/auth/login"
        url_products = f"https://app.trustvox.com.br/{slug_empresa}/products"

        with sync_playwright() as p:
            status_box.info("🌐 Inicializando Chromium em conexão direta...")

            browser = p.chromium.launch(
                headless=True,
                timeout=30000,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )

            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                status_box.info(f"🔑 Carregando formulário de login e digitando {email_trustvox}...")
                page.goto(url_login, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(2000)

                page.fill("input[name='email']", email_trustvox)
                page.wait_for_timeout(400)
                page.fill("input[name='password']", senha_trustvox)
                page.wait_for_timeout(400)

                status_box.info("🔑 Clicando em 'Entrar' e aguardando autenticação...")
                page.click("button[type='submit']")
                page.wait_for_timeout(5000)

                if "company-selection" in page.url or "company_selection" in page.url or page.locator("input[placeholder*='empresa']").is_visible():
                    status_box.info(f"🏢 Selecionando a empresa '{slug_empresa}'...")
                    inp_company = page.locator("input[placeholder*='empresa'], input[type='text']").first
                    inp_company.fill(slug_empresa)
                    page.wait_for_timeout(1500)

                    opcao_empresa = page.locator(f"text={slug_empresa}").first
                    opcao_empresa.click()
                    page.wait_for_timeout(3500)

                status_box.info(f"🚀 Sessão confirmada! Acessando {url_products}...")
                page.goto(url_products, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

            except Exception as login_err:
                status_box.error(f"❌ Erro durante a navegação de login: {login_err}")
                browser.close()
                return df_input

            for cont, idx in enumerate(indices, start=1):
                val_raw = df_input.at[idx, col_antigo_name]
                cod_antigo = str(int(val_raw)).strip() if pd.notna(val_raw) and isinstance(val_raw, (int, float)) else str(val_raw).strip()

                val_novo_raw = df_input.at[idx, col_novo_name]
                cod_novo = str(int(val_novo_raw)).strip() if pd.notna(val_novo_raw) and isinstance(val_novo_raw, (int, float)) else str(val_novo_raw).strip()

                linha_excel = idx + 2
                status_val = "REPROVADO"
                obs = ""

                try:
                    if page.url != url_products:
                        page.goto(url_products, wait_until="domcontentloaded")
                        page.wait_for_timeout(1500)

                    btn_filtrar = page.locator("button:has-text('Filtrar')").first
                    btn_filtrar.click(timeout=8000)
                    page.wait_for_timeout(800)

                    opcao_codigo = page.locator("text=Código do Produto").first
                    opcao_codigo.click(timeout=8000)
                    page.wait_for_timeout(800)

                    input_popup = page.locator("div[class*='popover'] input, div[class*='modal'] input, div[class*='filter'] input").first
                    if not input_popup.is_visible():
                        input_popup = page.locator("input").filter(has_not=page.locator("header input")).last

                    input_popup.click(timeout=5000)
                    input_popup.fill(cod_antigo)
                    page.wait_for_timeout(600)

                    btn_confirmar = page.locator("button:has-text('Confirmar')").first
                    btn_confirmar.click(timeout=5000)
                    page.wait_for_timeout(2500)

                    linha_produto = page.locator(f"tr:has-text('{cod_antigo}'), tbody tr").first

                    if linha_produto.is_visible():
                        linha_produto.click(timeout=8000)
                        page.wait_for_timeout(2000)

                        with context.expect_page(timeout=12000) as new_page_info:
                            page.click("text=Link original", timeout=8000)
                        
                        page_site = new_page_info.value
                        page_site.wait_for_load_state("domcontentloaded")
                        page_site.wait_for_timeout(2500)

                        product_id_console = page_site.evaluate("""
                            () => {
                                if (window._trustvox && Array.isArray(window._trustvox)) {
                                    for (let item of window._trustvox) {
                                        if (Array.isArray(item) && item[0] === '_productId') {
                                            return String(item[1]);
                                        }
                                    }
                                }
                                if (window._trustvox && typeof window._trustvox === 'object') {
                                    return String(window._trustvox._productId || window._trustvox.product_id || '');
                                }
                                return null;
                            }
                        """)

                        html_site = page_site.content()
                        page_site.close()

                        if product_id_console and str(product_id_console).strip() == cod_novo:
                            status_val = "APROVADO"
                            obs = f"_productId ({product_id_console}) verificado no site"
                        elif cod_novo in html_site:
                            status_val = "APROVADO"
                            obs = "Código novo localizado no HTML da página"
                        else:
                            obs = f"Esperado: {cod_novo} | Retornado: {product_id_console}"
                    else:
                        obs = f"Código {cod_antigo} não encontrado na busca"

                except Exception as e:
                    obs = f"Falha no filtro: {str(e).splitlines()[0]}"

                if status_val == "APROVADO":
                    aprovados_count += 1
                    log_box.success(f"Linha {linha_excel} | ID {cod_antigo} ➔ {cod_novo} | ✅ APROVADO")
                else:
                    reprovados_count += 1
                    log_box.error(f"Linha {linha_excel} | ID {cod_antigo} ➔ {cod_novo} | ❌ REPROVADO ({obs})")

                df_input.at[idx, col_status_nome] = status_val
                df_input.at[idx, col_obs_nome] = obs

                kpi_total.metric("Analisados", f"{cont}/{len(indices)}")
                kpi_ok.metric("Aprovados", f"{aprovados_count}")
                kpi_err.metric("Reprovados", f"{reprovados_count}")

                progress_bar.progress(cont / len(indices))

            browser.close()
            return df_input

    if btn_iniciar:
        if not senha_trustvox:
            st.warning("Preencha sua Senha do Trustvox na barra lateral.")
        else:
            with st.spinner("Iniciando login e processamento no navegador..."):
                df_final = rodar_validacao_real()

                status_box.success("🎉 Validação concluída com sucesso!")

                nome_saida = f"relatorio_{slug_empresa}_online_validado.xlsx"
                df_final.to_excel(nome_saida, index=False)

                with open(nome_saida, "rb") as file:
                    st.download_button(
                        label="📥 Baixar Relatório Consolidado (Excel)",
                        data=file,
                        file_name=nome_saida,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                colunas_exibicao = []
                for col in ['Status Validação', col_antigo, col_novo, 'Observação Validação']:
                    if col not in colunas_exibicao:
                        colunas_exibicao.append(col)

                tabela_live.dataframe(df_final[colunas_exibicao], use_container_width=True)
