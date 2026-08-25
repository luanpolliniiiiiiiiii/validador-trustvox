import os
import time
import pandas as pd
import streamlit as st

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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

st.title("🛡️ Trustvox Migration Studio — Execução Online")

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

    def criar_driver_direto():
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        for path in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]:
            if os.path.exists(path):
                chrome_options.binary_location = path
                break

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception:
            driver = webdriver.Chrome(options=chrome_options)
            
        return driver

    def rodar_validacao_selenium():
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

        url_products = f"https://app.trustvox.com.br/{slug_empresa}/products"
        url_login = "https://app.trustvox.com.br/auth/login"

        status_box.info("🌐 Conectando diretamente aos servidores do Trustvox...")
        driver = criar_driver_direto()
        wait = WebDriverWait(driver, 20)

        try:
            # 1. Preenchimento de Login
            status_box.info(f"🔑 Realizando login como {email_trustvox}...")
            driver.get(url_login)
            time.sleep(3)

            campo_email = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            campo_senha = driver.find_element(By.NAME, "password")
            
            campo_email.clear()
            campo_email.send_keys(email_trustvox)
            campo_senha.clear()
            campo_senha.send_keys(senha_trustvox)
            
            btn_entrar = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Entrar')]")
            btn_entrar.click()
            time.sleep(5)

            # 2. Transição de Seleção de Empresa (company-selection)
            if "company-selection" in driver.current_url or "company_selection" in driver.current_url or len(driver.find_elements(By.XPATH, "//input[contains(@placeholder, 'empresa')]")) > 0:
                status_box.info(f"🏢 Selecionando a empresa '{slug_empresa}'...")
                try:
                    inp_search = wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'empresa') or @type='text']")))
                    inp_search.clear()
                    inp_search.send_keys(slug_empresa)
                    time.sleep(1.5)

                    opcao_empresa = wait.until(EC.element_to_be_clickable((By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{slug_empresa}')]")))
                    opcao_empresa.click()
                    time.sleep(4)
                except Exception as err_comp:
                    status_box.warning(f"Navegando diretamente após login: {err_comp}")

            status_box.info(f"🚀 Acessando {url_products}...")
            driver.get(url_products)
            time.sleep(3)

        except Exception as login_err:
            status_box.error(f"❌ Falha de login/autenticação: {login_err}")
            driver.quit()
            return df_input

        # 3. Processamento de Produtos
        for cont, idx in enumerate(indices, start=1):
            val_raw = df_input.at[idx, col_antigo_name]
            cod_antigo = str(int(val_raw)).strip() if pd.notna(val_raw) and isinstance(val_raw, (int, float)) else str(val_raw).strip()

            val_novo_raw = df_input.at[idx, col_novo_name]
            cod_novo = str(int(val_novo_raw)).strip() if pd.notna(val_novo_raw) and isinstance(val_novo_raw, (int, float)) else str(val_novo_raw).strip()

            linha_excel = idx + 2
            status_val = "REPROVADO"
            obs = ""

            try:
                driver.get(url_products)
                time.sleep(2)

                # A. Clicar em Filtrar
                btn_filtrar = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Filtrar')]")))
                driver.execute_script("arguments[0].click();", btn_filtrar)
                time.sleep(0.8)

                # B. Clicar em Código do Produto
                opcao_codigo = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Código do Produto')]")))
                driver.execute_script("arguments[0].click();", opcao_codigo)
                time.sleep(0.8)

                # C. Inserir Código Antigo no campo flutuante
                campo_input = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'popover') or contains(@class, 'modal') or contains(@class, 'filter')]//input | //input[not(@type='hidden')]")))
                campo_input.click()
                campo_input.send_keys(Keys.CONTROL + "a")
                campo_input.send_keys(Keys.DELETE)
                campo_input.send_keys(cod_antigo)
                time.sleep(0.5)

                # D. Clicar em Confirmar
                btn_confirmar = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Confirmar')]")))
                driver.execute_script("arguments[0].click();", btn_confirmar)
                time.sleep(2.5)

                # E. Clicar na linha do resultado
                linha_prod = driver.find_elements(By.XPATH, f"//tr[contains(., '{cod_antigo}')] | //tbody/tr")
                
                if len(linha_prod) > 0:
                    driver.execute_script("arguments[0].click();", linha_prod[0])
                    time.sleep(2)

                    # F. Clicar em 'Link original'
                    janela_original = driver.current_window_handle
                    btn_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Link original')]")))
                    driver.execute_script("arguments[0].click();", btn_link)
                    time.sleep(3)

                    novas_janelas = [j for j in driver.window_handles if j != janela_original]
                    if len(novas_janelas) > 0:
                        driver.switch_to.window(novas_janelas[0])

                    # G. Ler _productId via Console JS da nova aba
                    product_id_console = driver.execute_script("""
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
                    """)

                    html_site = driver.page_source

                    if len(novas_janelas) > 0:
                        driver.close()
                        driver.switch_to.window(janela_original)

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
                obs = f"Erro na navegação: {str(e).splitlines()[0]}"

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

        driver.quit()
        return df_input

    if btn_iniciar:
        with st.spinner("Iniciando validação direta no servidor..."):
            df_final = rodar_validacao_selenium()

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
