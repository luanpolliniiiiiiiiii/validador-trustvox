import streamlit as st
import pandas as pd
import time
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

st.set_page_config(
    page_title="Validador de Migração Trustvox (Teste Online)",
    page_icon="🧪",
    layout="wide"
)

st.title("🧪 Teste de Validação Online — Trustvox")
st.markdown("Execução remota no Streamlit Cloud para teste de autenticação e navegação Selenium.")

# --- BARRA LATERAL (CREDENCIAIS DE LOGIN) ---
with st.sidebar:
    st.header("🔑 Credenciais Trustvox")
    email = st.text_input("E-mail Trustvox")
    senha = st.text_input("Senha Trustvox", type="password")
    slug_empresa = st.text_input("Slug da Empresa (URL)", value="coty")

# --- UPLOAD DE ARQUIVO ---
uploaded_file = st.file_uploader("Selecione a planilha De/Para (.xlsx ou .csv)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.subheader("📋 Prévia da Planilha")
        st.dataframe(df.head(5), use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            col_de = st.selectbox("Coluna Código ANTIGO (De):", df.columns)
        with col2:
            col_para = st.selectbox("Coluna Código NOVO (Para):", df.columns)
            
    except Exception as e:
        st.error(f"Erro ao carregar planilha: {e}")

# --- FUNÇÃO PARA INICIALIZAR CHROME NO STREAMLIT CLOUD ---
def criar_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Localiza o binário do Chromium no ambiente Debian do Streamlit Cloud
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

# --- PROCESSAMENTO ONLINE ---
if uploaded_file and st.button("🚀 Testar Login e Processamento Online", type="primary"):
    if not email or not senha:
        st.warning("Por favor, preencha o **E-mail** e a **Senha** na barra lateral.")
    else:
        st.info("Iniciando navegador Chromium no servidor da nuvem...")
        driver = None
        
        try:
            driver = criar_driver()
            wait = WebDriverWait(driver, 15)
            
            # Step 1: Acessar Tela de Login
            st.text("1/4: Acessando tela de login...")
            login_url = f"https://app.trustvox.com.br/empresas/{slug_empresa}/produtos"
            driver.get(login_url)
            time.sleep(3)
            
            # Verificar se foi redirecionado para a tela de autenticação
            if "auth/login" in driver.current_url or "login" in driver.current_url or len(driver.find_elements(By.NAME, "email")) > 0:
                st.text("2/4: Inserindo credenciais...")
                
                campo_email = wait.until(EC.presence_of_element_located((By.NAME, "email")))
                campo_senha = driver.find_element(By.NAME, "password")
                
                campo_email.clear()
                campo_email.send_keys(email)
                campo_senha.clear()
                campo_senha.send_keys(senha)
                
                btn_entrar = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Entrar')]")
                btn_entrar.click()
                time.sleep(5)
            
            # Step 2: Checar se o Login Passou ou Travou
            url_atual = driver.current_url
            st.write(f"**URL Atual do Navegador Remoto:** `{url_atual}`")
            
            if "auth/login" in url_atual or "login" in url_atual:
                st.error("❌ O Login travou ou falhou no servidor da nuvem! O Cloudflare/Trustvox recusou o acesso vindo deste IP.")
                st.stop()
            else:
                st.success("🎉 Login realizado com sucesso no servidor Cloud sem bloqueios de IP!")
                
            # Step 3: Processamento dos Itens
            st.text("3/4: Iniciando validação dos itens...")
            resultados = []
            progresso = st.progress(0)
            status_text = st.empty()
            total = len(df)
            
            for idx, row in df.iterrows():
                cod_antigo = str(row[col_de]).strip()
                cod_novo = str(row[col_para]).strip()
                
                status_text.text(f"Processando {idx + 1}/{total}: Código Novo '{cod_novo}'...")
                
                # Exemplo de navegação para o produto
                prod_url = f"https://app.trustvox.com.br/empresas/{slug_empresa}/produtos?search={cod_novo}"
                driver.get(prod_url)
                time.sleep(2)
                
                # Exemplo de verificação simples na página
                page_source = driver.page_source
                encontrado = cod_novo in page_source
                
                resultados.append({
                    "Código Antigo (De)": cod_antigo,
                    "Código Novo (Para)": cod_novo,
                    "Encontrado no Trustvox": "Sim" if encontrado else "Não",
                    "URL Final": driver.current_url
                })
                
                progresso.progress((idx + 1) / total)
                
            status_text.text("4/4: ✅ Processamento concluído!")
            
            # Step 4: Exibir Resultados e Permitir Download
            df_resultado = pd.DataFrame(resultados)
            st.subheader("📊 Relatório da Execução Remota")
            st.dataframe(df_resultado, use_container_width=True)
            
            output_name = "relatorio_teste_online.xlsx"
            df_resultado.to_excel(output_name, index=False)
            
            with open(output_name, "rb") as file:
                st.download_button(
                    label="📥 Baixar Relatório Gerado",
                    data=file,
                    file_name=output_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"⚠️ Ocorreu um erro durante a execução Selenium: {e}")
            if driver:
                st.text("Captura de tela do momento do erro (se disponível):")
                st.text(f"URL de Erro: {driver.current_url}")
        finally:
            if driver:
                driver.quit()
