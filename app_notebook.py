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
    page_title="Validador Trustvox Online (via Proxy)",
    page_icon="🌐",
    layout="wide"
)

st.title("🌐 Validador de Migração De/Para — Trustvox Online")
st.markdown("Execução em nuvem com rota por Proxy de saída e validação de 100% da planilha.")

# --- BARRA LATERAL (PROXIES E CREDENCIAIS) ---
with st.sidebar:
    st.header("🔑 Credenciais Trustvox")
    email = st.text_input("E-mail Trustvox", value="luan.araujo@reclameaqui.com.br")
    senha = st.text_input("Senha Trustvox", type="password")
    slug_empresa = st.text_input("Slug da Empresa (URL)", value="coty")
    
    st.divider()
    st.header("🌐 Configuração de Proxy")
    usar_proxy = st.checkbox("Ativar Proxy de Saída", value=True)
    
    # Preencha aqui com o IP:Porta do seu Proxy capturado
    proxy_server = st.text_input("Servidor Proxy (IP:Porta)", value="104.28.26.92:80", help="Exemplo: IP:Porta ou usuario:senha@IP:Porta")

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

# --- CRIAR DRIVER DO SELENIUM COM PROXY ---
def criar_driver_com_proxy(proxy_str):
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

    # Configuração do Proxy no Chrome
    if proxy_str:
        chrome_options.add_argument(f"--proxy-server={proxy_str}")

    # Localização do binário do Chromium no Streamlit Cloud (Linux)
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

# --- PROCESSAMENTO DOS 100% DOS DADOS ---
if uploaded_file and st.button("🚀 Iniciar Validação Online (100% da Planilha)", type="primary"):
    if not email or not senha:
        st.warning("Por favor, preencha o **E-mail** e a **Senha** do Trustvox.")
    else:
        st.info("Iniciando navegador no servidor da nuvem via Proxy...")
        driver = None
        
        try:
            proxy_config = proxy_server.strip() if usar_proxy else None
            driver = criar_driver_com_proxy(proxy_config)
            wait = WebDriverWait(driver, 15)
            
            # Step 1: Login via Proxy
            st.text("1/3: Acessando Trustvox via Proxy...")
            login_url = f"https://app.trustvox.com.br/empresas/{slug_empresa}/produtos"
            driver.get(login_url)
            time.sleep(3)
            
            if "auth/login" in driver.current_url or len(driver.find_elements(By.NAME, "email")) > 0:
                st.text("Efetuando autenticação...")
                campo_email = wait.until(EC.presence_of_element_located((By.NAME, "email")))
                campo_senha = driver.find_element(By.NAME, "password")
                
                campo_email.clear()
                campo_email.send_keys(email)
                campo_senha.clear()
                campo_senha.send_keys(senha)
                
                btn_entrar = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Entrar')]")
                btn_entrar.click()
                time.sleep(5)
            
            if "auth/login" in driver.current_url:
                st.error("❌ O Cloudflare/Trustvox bloqueou a conexão mesmo com o Proxy informado. Verifique o status/IP do servidor de Proxy.")
                st.stop()
            else:
                st.success("🎉 Autenticação realizada com sucesso via Proxy!")
                
            # Step 2: Validação de 100% da Planilha
            st.text("2/3: Validando 100% dos produtos...")
            resultados = []
            progresso = st.progress(0)
            status_text = st.empty()
            total = len(df)
            
            for idx, row in df.iterrows():
                cod_antigo = str(row[col_de]).strip()
                cod_novo = str(row[col_para]).strip()
                
                status_text.text(f"Validando item {idx + 1} de {total}: Código Novo '{cod_novo}'...")
                
                try:
                    prod_url = f"https://app.trustvox.com.br/empresas/{slug_empresa}/produtos?search={cod_novo}"
                    driver.get(prod_url)
                    time.sleep(1.5)
                    
                    page_source = driver.page_source
                    encontrado = cod_novo in page_source
                    
                    resultados.append({
                        "Linha": idx + 1,
                        "Código Antigo (De)": cod_antigo,
                        "Código Novo (Para)": cod_novo,
                        "Status Validação": "✅ Ativo / Encontrado" if encontrado else "⚠️ Não Localizado",
                        "Detalhes": "Encontrado no catálogo Trustvox" if encontrado else "ID não retornou resultados na busca"
                    })
                except Exception as err_item:
                    resultados.append({
                        "Linha": idx + 1,
                        "Código Antigo (De)": cod_antigo,
                        "Código Novo (Para)": cod_novo,
                        "Status Validação": "Erro de Leitura",
                        "Detalhes": f"Falha na busca: {str(err_item)}"
                    })
                
                progresso.progress((idx + 1) / total)
                
            status_text.text("3/3: ✅ Validação de 100% da planilha concluída!")
            
            # Step 3: Resultados e Download
            df_resultado = pd.DataFrame(resultados)
            st.subheader("📊 Relatório Final da Planilha Validada")
            st.dataframe(df_resultado, use_container_width=True)
            
            output_name = "relatorio_validacao_online_proxy.xlsx"
            df_resultado.to_excel(output_name, index=False)
            
            with open(output_name, "rb") as file:
                st.download_button(
                    label="📥 Baixar Relatório Completo em Excel",
                    data=file,
                    file_name=output_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"⚠️ Erro durante a execução online via Proxy: {e}")
        finally:
            if driver:
                driver.quit()
