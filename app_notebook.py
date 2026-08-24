import os
import pandas as pd
import streamlit as st
from playwright.sync_api import sync_playwright

# Configuração da página estilo NotebookLM Studio
st.set_page_config(
    page_title="Trustvox Studio | NotebookLM Style",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS customizada
st.markdown("""
<style>
    .stApp { background-color: #0f1117; color: #e6e6e6; }
    .metric-card {
        background-color: #1a1d24;
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #2d313e;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# PAINEL ESQUERDO (SIDEBAR - CREDENCIAIS & CONFIGURAÇÕES)
# ---------------------------------------------------------
with st.sidebar:
    st.title("🔑 Acesso ao Trustvox")
    
    usuario_trustvox = st.text_input("E-mail do Trustvox:", placeholder="seu-email@empresa.com")
    senha_trustvox = st.text_input("Senha do Trustvox:", type="password")

    st.divider()
    st.title("📚 Empresa & Planilha")
    
    slug_empresa = st.text_input(
        "Slug da Empresa no Trustvox:",
        value="alpfilm",
        help="Exemplo: alpfilm, coty, etc."
    ).strip().lower()

    arquivo_enviado = st.file_uploader(
        "Carregar Planilha De/Para",
        type=["xlsx", "csv"],
        help="Suba a planilha com os códigos antigos e novos"
    )
    
    st.divider()
    st.subheader("⚙️ Parâmetros")
    
    modo_validacao = st.radio(
        "Escopo de Validação",
        ["Amostragem em Blocos (~40%)", "Validar 100% dos Produtos"],
        index=0
    )

# ---------------------------------------------------------
# CORPO PRINCIPAL
# ---------------------------------------------------------
st.title("🛡️ Trustvox Migration Studio")
st.caption("Validação automática de migração de produtos")

if arquivo_enviado is None or not slug_empresa or not usuario_trustvox or not senha_trustvox:
    st.info("👈 **Para começar:** Preencha o e-mail, a senha, o slug da empresa e suba a planilha na barra lateral.")
else:
    if arquivo_enviado.name.endswith('.csv'):
        df_input = pd.read_csv(arquivo_enviado)
    else:
        df_input = pd.read_excel(arquivo_enviado)

    cols_lista = list(df_input.columns)
    
    col_antigo_default = next(
        (c for c in cols_lista if any(k in str(c).lower() for k in ['cod_antigo', 'código antigo', 'codigo antigo', 'id antigo', 'id_antigo'])),
        next((c for c in cols_lista if any(k in str(c).lower() for k in ['antigo', 'de', 'old'])), cols_lista[0])
    )
    
    col_novo_default = next(
        (c for c in cols_lista if any(k in str(c).lower() for k in ['cod_novo', 'código novo', 'codigo novo', 'id novo', 'id_novo'])),
        next((c for c in cols_lista if any(k in str(c).lower() for k in ['novo', 'para', 'new'])), cols_lista[1] if len(cols_lista) > 1 else cols_lista[0])
    )

    col_execucao, col_analytics = st.columns([1.1, 0.9], gap="large")

    with col_execucao:
        st.markdown("### 🎯 Central de Execução")
        
        col1_sel, col2_sel = st.columns(2)
        with col1_sel:
            col_antigo = st.selectbox("Coluna CÓDIGO ANTIGO:", cols_lista, index=cols_lista.index(col_antigo_default))
        with col2_sel:
            col_novo = st.selectbox("Coluna CÓDIGO NOVO:", cols_lista, index=cols_lista.index(col_novo_default))

        st.markdown(f"**Empresa:** `{slug_empresa}`")
        st.markdown(f"**Arquivo:** `{arquivo_enviado.name}` ({len(df_input)} registros)")

        btn_iniciar = st.button("🚀 Iniciar Processamento", type="primary", use_container_width=True)
        
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
        st.markdown("### 📝 Tabela ao Vivo")
        tabela_live = st.empty()

    # --- LÓGICA DE AUTOMAÇÃO SÍNCRONA ---
    def rodar_validacao():
        col_antigo_name = col_antigo
        col_novo_name = col_novo

        df_input['Status Validação'] = 'Não Testado'
        df_input['Observação Validação'] = '-'

        total_rows = len(df_input)

        if "100%" in modo_validacao:
            indices = list(range(total_rows))
        else:
            indices = []
            for inicio in range(0, total_rows, 25):
                indices.extend(range(inicio, min(inicio + 10, total_rows)))

        aprovados_count = 0
        reprovados_count = 0

        url_loja = f"https://app.trustvox.com.br/{slug_empresa}/products"

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--single-process"]
            )
            context = browser.new_context()
            page = context.new_page()

            # 1. LOGIN NO TRUSTVOX
            status_box.warning("🔑 Efetuando login no Trustvox...")
            page.goto("https://app.trustvox.com.br/users/sign_in", wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            if page.locator("input[type='email'], input[name*='email']").first.is_visible():
                page.fill("input[type='email'], input[name*='email']", usuario_trustvox)
                page.fill("input[type='password'], input[name*='password']", senha_trustvox)
                page.click("button[type='submit'], input[type='submit']")
                page.wait_for_timeout(3000)

            status_box.info(f"🚀 **Iniciando validação na loja {slug_empresa}...**")

            for cont, idx in enumerate(indices, start=1):
                val_raw = df_input.at[idx, col_antigo_name]
                if pd.notna(val_raw):
                    cod_antigo = str(int(val_raw)).strip() if isinstance(val_raw, (int, float)) and val_raw == val_raw else str(val_raw).strip()
                else:
                    cod_antigo = ""

                val_novo_raw = df_input.at[idx, col_novo_name]
                if pd.notna(val_novo_raw):
                    cod_novo = str(int(val_novo_raw)).strip() if isinstance(val_novo_raw, (int, float)) and val_novo_raw == val_novo_raw else str(val_novo_raw).strip()
                else:
                    cod_novo = ""

                linha_excel = idx + 2
                status_val = "REPROVADO"
                obs = ""

                try:
                    page.goto(url_loja, wait_until="domcontentloaded")
                    page.wait_for_timeout(1000)

                    btn_filtrar = page.locator("button:has-text('Filtrar')").first
                    btn_filtrar.click(timeout=8000)
                    page.wait_for_timeout(500)

                    opcao_codigo = page.locator("text=Código do Produto").first
                    opcao_codigo.click(timeout=8000)
                    page.wait_for_timeout(500)

                    input_popup = page.locator("div[class*='popover'] input, div[class*='modal'] input, div[class*='filter'] input").first
                    if not input_popup.is_visible():
                        input_popup = page.locator("input").filter(has_not=page.locator("header input")).last

                    input_popup.click(timeout=5000)
                    input_popup.fill(cod_antigo)
                    page.wait_for_timeout(400)

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

                        if product_id_console and product_id_console.strip() == cod_novo:
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
                    obs = f"Falha na navegação: {str(e)}"

                if status_val == "APROVADO":
                    aprovados_count += 1
                    log_box.success(f"Linha {linha_excel} | ID {cod_antigo} ➔ {cod_novo} | ✅ APROVADO")
                else:
                    reprovados_count += 1
                    log_box.error(f"Linha {linha_excel} | ID {cod_antigo} ➔ {cod_novo} | ❌ REPROVADO ({obs})")

                df_input.at[idx, 'Status Validação'] = status_val
                df_input.at[idx, 'Observação Validação'] = obs

                kpi_total.metric("Analisados", f"{cont}/{len(indices)}")
                kpi_ok.metric("Aprovados", f"{aprovados_count}")
                kpi_err.metric("Reprovados", f"{reprovados_count}")

                progress_bar.progress(cont / len(indices))

            browser.close()
            return df_input

    if btn_iniciar:
        with st.spinner("Conectando ao servidor e processando..."):
            df_final = rodar_validacao()
            status_box.success("🎉 Validação concluída com sucesso!")

            nome_saida = f"relatorio_{slug_empresa}_validado.xlsx"
            df_final.to_excel(nome_saida, index=False)

            with open(nome_saida, "rb") as file:
                st.download_button(
                    label="📥 Baixar Relatório Consolidado (Excel)",
                    data=file,
                    file_name=nome_saida,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            tabela_live.dataframe(
                df_final[['Status Validação', col_antigo, col_novo, 'Observação Validação']],
                use_container_width=True
            )
