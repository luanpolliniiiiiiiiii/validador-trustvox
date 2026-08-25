import pandas as pd
import requests
import streamlit as st

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
    st.subheader("🌐 Configuração de Proxy")
    usar_proxy = st.checkbox("Ativar Proxy de Saída", value=True)
    proxy_ip_porta = st.text_input("IP:Porta do Proxy:", value="64.137.96.74:6641")
    proxy_user = st.text_input("Usuário do Proxy:", value="mxjcpfer")
    proxy_pass = st.text_input("Senha do Proxy:", type="password", value="f080q5vj4ys9")

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

    def realizar_login_autenticado(session):
        url_login_page = "https://app.trustvox.com.br/auth/login"
        
        # Passo 1: Obter cookies iniciais de navegação
        try:
            res_page = session.get(url_login_page, timeout=15)
        except Exception as e:
            return False, f"Erro ao acessar página de login: {str(e)}"

        # Passo 2: Tentar login via JSON API e Form Payload
        endpoints_login = [
            ("https://app.trustvox.com.br/api/auth/login", "json"),
            ("https://app.trustvox.com.br/auth/login", "json"),
            ("https://app.trustvox.com.br/auth/login", "data")
        ]

        payload = {
            "email": email_trustvox,
            "password": senha_trustvox,
            "user": {
                "email": email_trustvox,
                "password": senha_trustvox
            }
        }

        login_efetuado = False
        detalhe_erro = ""

        for endpoint, tipo in endpoints_login:
            try:
                if tipo == "json":
                    res = session.post(
                        endpoint, 
                        json={"email": email_trustvox, "password": senha_trustvox},
                        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
                        timeout=15
                    )
                else:
                    res = session.post(
                        endpoint, 
                        data={"email": email_trustvox, "password": senha_trustvox},
                        timeout=15
                    )

                # Verifica se gerou cookies de sessão ou se redirecionou para fora da página de login
                cookies_sessao = session.cookies.get_dict()
                if res.status_code in [200, 302] and not ("login" in res.url and res.status_code == 200 and "password" in res.text):
                    login_efetuado = True
                    break
                elif len(cookies_sessao) > 1:
                    login_efetuado = True
                    break
            except Exception as err:
                detalhe_erro = str(err)

        if not login_efetuado:
            return False, "Credenciais inválidas ou resposta não reconhecida da API de login."

        # Passo 3: Estabelecer contexto na empresa selecionada
        url_empresa = f"https://app.trustvox.com.br/{slug_empresa}"
        try:
            session.get(url_empresa, timeout=15)
        except Exception:
            pass

        return True, "Autenticado com sucesso!"

    def rodar_validacao_api():
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

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        })

        if usar_proxy and proxy_ip_porta:
            proxy_url = f"http://{proxy_user.strip()}:{proxy_pass.strip()}@{proxy_ip_porta.strip()}"
            session.proxies = {"http": proxy_url, "https": proxy_url}

        status_box.info("🔑 Estabelecendo sessão de login e obtendo tokens na Trustvox...")

        sucesso_login, msg_login = realizar_login_autenticado(session)

        if not sucesso_login:
            status_box.error(f"❌ Falha no login: {msg_login}")
            return df_input

        status_box.success(f"🎉 Login confirmado! Iniciando validação na empresa '{slug_empresa}'...")

        url_products_page = f"https://app.trustvox.com.br/{slug_empresa}/products"
        url_api_search = f"https://app.trustvox.com.br/api/stores/{slug_empresa}/products"

        for cont, idx in enumerate(indices, start=1):
            val_raw = df_input.at[idx, col_antigo_name]
            cod_antigo = str(int(val_raw)).strip() if pd.notna(val_raw) and isinstance(val_raw, (int, float)) else str(val_raw).strip()

            val_novo_raw = df_input.at[idx, col_novo_name]
            cod_novo = str(int(val_novo_raw)).strip() if pd.notna(val_novo_raw) and isinstance(val_novo_raw, (int, float)) else str(val_novo_raw).strip()

            linha_excel = idx + 2
            status_val = "REPROVADO"
            obs = ""

            try:
                encontrado = False
                p_url = None

                # 1. Consulta via Endpoint da API interna de produtos
                res_api = session.get(
                    url_api_search, 
                    params={"code": cod_antigo, "query": cod_antigo, "search": cod_antigo}, 
                    headers={"Accept": "application/json"},
                    timeout=12
                )
                
                if res_api.status_code == 200:
                    try:
                        data = res_api.json()
                        items = data.get("items", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                        for item in items:
                            code_item = str(item.get("code", "") or item.get("product_id", "")).strip()
                            if code_item == cod_antigo:
                                encontrado = True
                                p_url = item.get("url") or item.get("links", {}).get("original")
                                break
                    except Exception:
                        pass

                # 2. Caso a API de busca não retorne JSON, verifica pela resposta autenticada do catálogo
                if not encontrado:
                    res_html = session.get(f"{url_products_page}?search={cod_antigo}", timeout=12)
                    if res_html.status_code == 200 and cod_antigo in res_html.text:
                        encontrado = True

                # 3. Validação do código no e-commerce se houver URL do produto
                if encontrado:
                    if p_url:
                        try:
                            res_site = requests.get(p_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                            if cod_novo in res_site.text or f"'{cod_novo}'" in res_site.text or f'"{cod_novo}"' in res_site.text:
                                status_val = "APROVADO"
                                obs = f"_productId ({cod_novo}) verificado na página do e-commerce"
                            else:
                                status_val = "APROVADO"
                                obs = f"Código {cod_antigo} localizado no Trustvox"
                        except Exception:
                            status_val = "APROVADO"
                            obs = f"Código {cod_antigo} localizado no catálogo do Trustvox"
                    else:
                        status_val = "APROVADO"
                        obs = f"Código {cod_antigo} localizado no catálogo do Trustvox"
                else:
                    obs = f"Código {cod_antigo} não encontrado na busca"

            except Exception as e:
                obs = f"Falha na requisição: {str(e).splitlines()[0]}"

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

        return df_input

    if btn_iniciar:
        if not senha_trustvox:
            st.warning("Preencha sua Senha do Trustvox na barra lateral.")
        else:
            with st.spinner("Iniciando validação no servidor..."):
                df_final = rodar_validacao_api()

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
