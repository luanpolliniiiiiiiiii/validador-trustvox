import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(
    page_title="Validador De/Para Trustvox",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Validador de Migração De/Para — Trustvox")
st.markdown("Validação automatizada de IDs e integração via API pública da Trustvox.")


with st.sidebar:
    st.header("⚙️ Configurações")
    store_id = st.text_input("ID da Loja Trustvox (Store ID)", help="ID numérico da sua loja na Trustvox").strip()
    
    st.divider()
    st.markdown("**Como obter o Store ID?**")
    st.caption("Você pode encontrar o Store ID nas configurações da conta Trustvox ou inspecionando o script do Widget no site.")


uploaded_file = st.file_uploader("Selecione a planilha De/Para (.xlsx ou .csv)", type=["xlsx", "csv"])

if uploaded_file:
   
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.subheader("📋 Prévia dos Dados")
        st.dataframe(df.head(5), use_container_width=True)
        
        col_de = st.selectbox("Selecione a coluna com o Código ANTIGO (De):", df.columns)
        col_para = st.selectbox("Selecione a coluna com o Código NOVO (Para):", df.columns)
        
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")


def validar_produto_trustvox(store_id, product_id):
    """
    Consulta o endpoint público da Trustvox para verificar se o produto existe
    e se possui avaliações/widget ativo.
    """
    url = f"https://rate.trustvox.com.br/widget/store/{store_id}/products/{product_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
           
            opinions_count = data.get("opinions_count", 0)
            return True, f"✅ Ativo no Trustvox ({opinions_count} avaliações)"
        elif response.status_code == 404:
            return False, "❌ Não encontrado no Trustvox (404)"
        else:
            return False, f"⚠️ Erro HTTP {response.status_code}"
    except Exception as e:
        return False, f"⚠️ Falha de Conexão: {str(e)}"


if uploaded_file and st.button("🚀 Iniciar Processamento Online", type="primary"):
    if not store_id:
        st.warning("Por favor, preencha o **Store ID** na barra lateral.")
    else:
        st.info("Iniciando validação em tempo real na nuvem...")
        
        resultados = []
        progresso = st.progress(0)
        status_text = st.empty()
        
        total = len(df)
        
        for idx, row in df.iterrows():
            cod_antigo = str(row[col_de]).strip()
            cod_novo = str(row[col_para]).strip()
            
            status_text.text(f"Validando item {idx + 1} de {total}: Código Novo '{cod_novo}'...")
            
            
            valido_novo, msg_novo = validar_produto_trustvox(store_id, cod_novo)
            
            resultados.append({
                "Código Antigo (De)": cod_antigo,
                "Código Novo (Para)": cod_novo,
                "Status Código Novo": msg_novo,
                "Validado": "Sim" if valido_novo else "Não"
            })
            
           
            progresso.progress((idx + 1) / total)
            time.sleep(0.1) 
            
        status_text.text("✅ Processamento concluído!")
        
       
        df_resultado = pd.DataFrame(resultados)
        st.subheader("📊 Relatório de Validação")
        st.dataframe(df_resultado, use_container_width=True)
        
        
        output_name = "relatorio_validacao_trustvox.xlsx"
        df_resultado.to_excel(output_name, index=False)
        
        with open(output_name, "rb") as file:
            st.download_button(
                label="📥 Baixar Relatório em Excel",
                data=file,
                file_name=output_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
