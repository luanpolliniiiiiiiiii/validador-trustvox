import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Trustvox Studio | Online Migration", page_icon="📚", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0f1117; color: #e6e6e6; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("📚 Fontes & Empresa")
    
    email_trustvox = st.text_input("E-mail Trustvox:", value="luan.araujo@reclameaqui.com.br")
    senha_trustvox = st.text_input("Senha Trustvox:", type="password")
    
    slug_empresa = st.text_input("Slug da Empresa no Trustvox:", value="coty").strip().lower()

    st.divider()
    st.subheader("🌐 Configuração de Proxy")
    usar_proxy = st.checkbox("Ativar Proxy de Saída", value=True)
    proxy_ip_porta = st.text_input("IP:Porta do Proxy:", value="31.59.20.176:6754")
    proxy_user = st.text_input("Usuário do Proxy:", value="mxjcpfer")
    proxy_pass = st.text_input("Senha do Proxy:", type="password", value="f080q5vj4ys9")

    st.divider()
    arquivo_enviado = st.file_uploader("Carregar Planilha De/Para", type=["xlsx", "csv"])

    modo_validacao = st.radio(
        "Escopo de Validação",
        ["Validar 100% dos Produtos", "Amostragem em Blocos (~40%)"],
        index=0
    )

st.title("🛡️ Trustvox Migration Studio — Execução Online (Sessão HTTP)")

if arquivo_enviado and slug_empresa:
    if arquivo_enviado.name.endswith('.csv'):
        df_input = pd.read_csv(arquivo_enviado)
    else:
        df_input = pd.read_excel(arquivo_enviado)

    cols_lista = list(df_input.columns)
    
    col_antigo_default = next(
        (c for c in cols_lista if any(k in str(c).lower() for k in ['cod_antigo', 'código antigo', 'codigo antigo', 'id antigo', 'id_antigo'])),
        cols_lista[0]
    )
    
    col_novo_default = next(
        (c for c in cols_lista if any(k in str(c).lower() for k in ['cod_novo', 'código novo', 'codigo novo', 'id novo', 'id_novo'])),
        cols_lista[1] if len(cols_lista) > 1 else cols_lista[0]
    )

    col1_sel, col2_sel = st.columns(2)
    with col1_sel:
        col_antigo = st.selectbox("Coluna CÓDIGO ANTIGO (Trustvox):", cols_lista, index=cols_lista.index(col_antigo_default))
    with col2_sel:
        col_novo = st.selectbox("Coluna CÓDIGO NOVO (Site):", cols_lista, index=cols_lista.index(col_novo_default))

    btn_iniciar = st.button("🚀 Iniciar Processamento Online", type="primary", use_container_width=True)
    
    status_box = st.empty()
    progress_bar = st.progress(0)
    log_box = st.container(height=350)

    def rodar_validacao_http():
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

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        if usar_proxy and proxy_ip_porta:
            proxy_str = f"http://{proxy_user.strip()}:{proxy_pass.strip()}@{proxy_ip_porta.strip()}"
            session.proxies = {"http": proxy_str, "https": proxy_str}

        status_box.info("🌐 Autenticando na Trustvox...")

        # Autenticação via POST
        url_login = "https://app.trustvox.com.br/auth/login"
        payload_login = {"email": email_trustvox, "password": senha_trustvox}

        try:
            res = session.post(url_login, data=payload_login, timeout=15)
            status_box.info(f"🚀 Iniciando validação na empresa {slug_empresa}...")
        except Exception as e:
            status_box.error(f"Erro na conexão de login: {e}")
            return df_input

        url_produtos = f"https://app.trustvox.com.br/{slug_empresa}/products"

        for cont, idx in enumerate(indices, start=1):
            val_raw = df_input.at[idx, col_antigo_name]
            cod_antigo = str(int(val_raw)).strip() if pd.notna(val_raw) and isinstance(val_raw, (int, float)) else str(val_raw).strip()

            val_novo_raw = df_input.at[idx, col_novo_name]
            cod_novo = str(int(val_novo_raw)).strip() if pd.notna(val_novo_raw) and isinstance(val_novo_raw, (int, float)) else str(val_novo_raw).strip()

            linha_excel = idx + 2
            status_val = "REPROVADO"
            obs = ""

            try:
                # Realiza a busca no painel do Trustvox
                res_busca = session.get(f"{url_produtos}?search={cod_antigo}", timeout=10)
                
                if res_busca.status_code == 200 and cod_antigo in res_busca.text:
                    status_val = "APROVADO"
                    obs = f"Código {cod_antigo} localizado no catálogo"
                else:
                    obs = f"Código {cod_antigo} não encontrado na busca"

            except Exception as e:
                obs = f"Erro na requisição: {str(e).splitlines()[0]}"

            if status_val == "APROVADO":
                aprovados_count += 1
                log_box.success(f"Linha {linha_excel} | ID {cod_antigo} ➔ {cod_novo} | ✅ APROVADO")
            else:
                reprovados_count += 1
                log_box.error(f"Linha {linha_excel} | ID {cod_antigo} ➔ {cod_novo} | ❌ REPROVADO ({obs})")

            df_input.at[idx, 'Status Validação'] = status_val
            df_input.at[idx, 'Observação Validação'] = obs

            progress_bar.progress(cont / len(indices))

        return df_input

    if btn_iniciar:
        with st.spinner("Executando validação rápida..."):
            df_final = rodar_validacao_http()

            status_box.success("🎉 Validação concluída com sucesso!")
            st.dataframe(df_final[['Status Validação', col_antigo, col_novo, 'Observação Validação']], use_container_width=True)
