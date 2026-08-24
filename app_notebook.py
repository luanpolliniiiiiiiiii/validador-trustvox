import os
import time
import pandas as pd
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

# Configuração da página estilo NotebookLM Studio
st.set_page_config(
    page_title="Trustvox Studio | NotebookLM Style",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
# PAINEL ESQUERDO (SIDEBAR)
# ---------------------------------------------------------
with st.sidebar:
    st.title("🔑 Acesso ao Trustvox")
    usuario_trustvox = st.text_input("E-mail do Trustvox:", placeholder="seu-email@empresa.com")
    senha_trustvox = st.text_input("Senha do Trustvox:", type="password")

    st.divider()
    st.title("📚 Empresa & Planilha")
    slug_empresa = st.text_input(
        "Slug da Empresa no Trustvox:",
        value="coty",
        help="Exemplo: coty, alpfilm, etc."
    ).strip().lower()

    arquivo_enviado = st.file_uploader(
        "Carregar Planilha De/Para",
        type=["xlsx", "csv"]
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
st.caption("Validação automática de migração de produtos via Injeção de JS")

if arquivo_enviado is None or not slug_empresa or not usuario_trustvox or not senha_trustvox:
    st.info("👈 **Para começar:** Preencha o e-mail, a senha, o slug da empresa e suba a planilha na barra lateral.")
else:
    if arquivo_enviado.name.endswith('.csv'):
        df_input = pd.read_csv(arquivo_enviado)
    else:
        df_input = pd.read_excel(arquivo_enviado)

    cols_lista = list(df_input.columns)
    col_antigo_default = next((c for c in cols_lista if any(k in str(c).lower() for k in ['cod_antigo', 'código antigo', 'codigo antigo', 'id antigo', 'id_antigo'])), cols_lista[0])
    col_novo_default = next((c for c in cols_lista if any(k in str(c).lower() for k in ['cod_novo', 'código novo', 'codigo novo', 'id novo', 'id_novo'])), cols_lista[1] if len(cols_lista) > 1 else cols_lista[0])

    col_execucao, col_analytics = st.columns([1.1, 0.9], gap="large")

    with col_execucao:
        st.markdown("### 🎯 Central de Execução")
        col1_sel, col2_sel = st.columns(2)
        with col1_sel:
            col_antigo = st.selectbox("Coluna CÓDIGO ANTIGO:", cols_lista, index=cols_lista.index(col_antigo_default))
        with col2_sel:
            col_novo = st.selectbox("Coluna CÓDIGO NOVO:", cols_lista, index=cols_lista.index(col_novo_default))

        st.markdown(f"**Empresa:** `{slug_empresa}` | **Arquivo:** `{arquivo_enviado.name}`")
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

    def rodar_validacao():
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

        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()), options=options)
        except Exception:
            driver = webdriver.Chrome(options=options)

        wait = WebDriverWait(driver, 15)

        try:
            # 1. LOGIN AUTOMÁTICO
            status_box.warning("🔑 Efetuando login no Trustvox...")
            driver.get("https://app.trustvox.com.br/users/sign_in")
            time.sleep(3)

            try:
                email_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#user_email, input[type='email']")))
                email_field.clear()
                email_field.send_keys(usuario_trustvox)

                pass_field = driver.find_element(By.CSS_SELECTOR, "input#user_password, input[type='password']")
                pass_field.clear()
                pass_field.send_keys(senha_trustvox)

                submit_btn = driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
                driver.execute_script("arguments[0].click();", submit_btn)
                time.sleep(5)
            except Exception as login_err:
                status_box.error(f"Erro no login: {str(login_err)}")

            if "sign_in" in driver.current_url:
                status_box.error("❌ Falha na autenticação do Trustvox! Verifique as credenciais.")
                driver.quit()
                return df_input

            status_box.info(f"🚀 **Login concluído! Analisando {len(indices)} produtos...**")

            for cont, idx in enumerate(indices, start=1):
                val_raw = df_input.at[idx, col_antigo]
                cod_antigo = str(int(val_raw)).strip() if pd.notna(val_raw) and isinstance(val_raw, (int, float)) else str(val_raw).strip() if pd.notna(val_raw) else ""

                val_novo_raw = df_input.at[idx, col_novo]
                cod_novo = str(int(val_novo_raw)).strip() if pd.notna(val_novo_raw) and isinstance(val_novo_raw, (int, float)) else str(val_novo_raw).strip() if pd.notna(val_novo_raw) else ""

                linha_excel = idx + 2
                status_val = "REPROVADO"
                obs = ""

                try:
                    driver.get(url_loja)
                    time.sleep(3.5)

                    # INJEÇÃO JS 1: Botão Filtrar
                    driver.execute_script("""
                        let btns = Array.from(document.querySelectorAll('button'));
                        let b = btns.find(x => x.innerText && x.innerText.includes('Filtrar'));
                        if (b) b.click();
                    """)
                    time.sleep(1.5)

                    # INJEÇÃO JS 2: Botão Código do Produto
                    driver.execute_script("""
                        let els = Array.from(document.querySelectorAll('*'));
                        let el = els.find(x => x.children.length === 0 && x.innerText && x.innerText.includes('Código do Produto'));
                        if (el) el.click();
                    """)
                    time.sleep(1.5)

                    # INJEÇÃO JS 3: Input do Modal (Forçando atualização no Framework React)
                    preencheu = driver.execute_script("""
                        let inputs = Array.from(document.querySelectorAll('input'));
                        let modalInput = inputs.find(i => i.closest('[class*="popover"], [class*="modal"], [role="dialog"], [class*="menu"], [class*="filter"]'));
                        if (!modalInput) modalInput = inputs.find(i => !i.closest('header') && i.type === 'text');
                        
                        if (modalInput) {
                            let setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                            setter.call(modalInput, arguments[0]);
                            modalInput.dispatchEvent(new Event('input', { bubbles: true }));
                            modalInput.dispatchEvent(new Event('change', { bubbles: true }));
                            return true;
                        }
                        return false;
                    """, cod_antigo)

                    if not preencheu:
                        raise Exception("Input do pop-up não localizado pela injeção JS.")
                    time.sleep(1)

                    # INJEÇÃO JS 4: Botão Confirmar
                    driver.execute_script("""
                        let btns = Array.from(document.querySelectorAll('button'));
                        let b = btns.find(x => x.innerText && x.innerText.includes('Confirmar'));
                        if (b) b.click();
                    """)
                    time.sleep(4)

                    # 5. Localizar linha na tabela
                    linhas = driver.find_elements(By.XPATH, f"//tr[contains(.,'{cod_antigo}')]")
                    if linhas:
                        driver.execute_script("arguments[0].click();", linhas[0])
                        time.sleep(3)

                        # INJEÇÃO JS 5: Link Original
                        handles_antes = driver.window_handles
                        clicou_link = driver.execute_script("""
                            let els = Array.from(document.querySelectorAll('a, button, span, div'));
                            let link = els.find(x => x.innerText && x.innerText.includes('Link original'));
                            if (link) {
                                link.click();
                                return true;
                            }
                            return false;
                        """)
                        
                        if not clicou_link:
                            raise Exception("Botão 'Link original' não foi encontrado na aba lateral.")
                            
                        time.sleep(4)
                        handles_depois = driver.window_handles

                        if len(handles_depois) > len(handles_antes):
                            driver.switch_to.window(handles_depois[-1])
                            time.sleep(4)

                            product_id_console = driver.execute_script("""
                                if (window._trustvox && Array.isArray(window._trustvox)) {
                                    for (let item of window._trustvox) {
                                        if (Array.isArray(item) && item[0] === '_productId') return String(item[1]);
                                    }
                                }
                                if (window._trustvox && typeof window._trustvox === 'object') {
                                    return String(window._trustvox._productId || window._trustvox.product_id || '');
                                }
                                return null;
                            """)

                            html_site = driver.page_source
                            driver.close()
                            driver.switch_to.window(handles_antes[0])

                            if product_id_console and product_id_console.strip() == cod_novo:
                                status_val = "APROVADO"
                                obs = f"_productId ({product_id_console}) verificado no site"
                            elif cod_novo in html_site:
                                status_val = "APROVADO"
                                obs = "Código novo localizado no HTML da página"
                            else:
                                obs = f"Esperado: {cod_novo} | Retornado: {product_id_console}"
                        else:
                            obs = "Nova aba da loja externa não abriu (Possível bloqueio de pop-up)."
                    else:
                        obs = f"Produto {cod_antigo} não retornado na tabela após aplicar filtro."

                except Exception as e:
                    # Formata erros genéricos retirando o stacktrace monstruoso
                    erro_str = str(e).split("\n")[0].split("Stacktrace:")[0].strip()
                    obs = f"Erro JS/Navegação: {erro_str}"

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

        finally:
            driver.quit()

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
