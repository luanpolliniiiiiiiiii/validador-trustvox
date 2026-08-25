import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Trustvox Studio Online", page_icon="🛡️", layout="wide")

st.title("🛡️ Trustvox Migration Studio — Execução Online")

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

    def rodar_validacao_http():
        df_input['Status Validação'] = 'Não Testado'
        df_input['Observação'] = '-'

        total_rows = len(df_input)
        aprovados_count = 0
        reprovados_count = 0

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        if usar_proxy and proxy_ip_porta:
            proxy_url = f"http://{proxy_user.strip()}:{proxy_pass.strip()}@{proxy_ip_porta.strip()}"
            session.proxies = {
                "http": proxy_url,
                "https": proxy_url
            }

        status_box.info("🌐 Conectando e autenticando via HTTP Session...")

        # 1. Autenticação na Trustvox
        login_url = "https://app.trustvox.com.br/auth/login"
        try:
            res_page = session.get(login_url, timeout=20)
            payload = {
                "email": email_trustvox,
                "password": senha_trustvox
            }
            res_login = session.post(login_url, data=payload, timeout=20)
            
            if res_login.status_code != 200 and "login" in res_login.url:
                status_box.error("❌ Falha na autenticação HTTP. Verifique credenciais ou o Proxy.")
                return df_input
            
            status_box.success("🎉 Autenticado com sucesso via sessão leve!")
        except Exception as e:
            status_box.error(f"Erro de conexão no login: {e}")
            return df_input

        # 2. Varredura da Planilha
        url_busca_base = f"https://app.trustvox.com.br/{slug_empresa}/products"

        for idx in range(total_rows):
            val_antigo = str(df_input.at[idx, col_antigo]).strip()
            val_novo = str(df_input.at[idx, col_novo]).strip()
            linha_excel = idx + 2

            status_val = "REPROVADO"
            obs = ""

            try:
                params = {"search": val_antigo}
                res = session.get(url_busca_base, params=params, timeout=15)
                
                if res.status_code == 200 and (val_antigo in res.text or val_novo in res.text):
                    status_val = "APROVADO"
                    obs = "Código localizado nos dados da página"
                else:
                    obs = f"Código {val_antigo} não localizado na busca"

            except Exception as err:
                obs = f"Falha na requisição: {str(err)}"

            if status_val == "APROVADO":
                aprovados_count += 1
                log_box.success(f"Linha {linha_excel} | ID {val_antigo} ➔ {val_novo} | ✅ APROVADO")
            else:
                reprovados_count += 1
                log_box.error(f"Linha {linha_excel} | ID {val_antigo} ➔ {val_novo} | ❌ REPROVADO ({obs})")

            df_input.at[idx, 'Status Validação'] = status_val
            df_input.at[idx, 'Observação'] = obs

            progress_bar.progress((idx + 1) / total_rows)

        return df_input

    if btn_iniciar:
        if not email_trustvox or not senha_trustvox:
            st.warning("Preencha seu E-mail e Senha na barra lateral.")
        else:
            with st.spinner("Executando validação via sessão leve HTTP..."):
                df_final = rodar_validacao_http()

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
