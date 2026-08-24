import os
import time
import requests
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Trustvox Studio | Hybrid Mode",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #0f1117; color: #e6e6e6; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# PAINEL ESQUERDO (SIDEBAR - CONFIGURAÇÕES)
# ---------------------------------------------------------
with st.sidebar:
    st.title("🔑 Acesso ao Trustvox")
    usuario_trustvox = st.text_input("E-mail do Trustvox:", placeholder="seu-email@empresa.com")
    senha_trustvox = st.text_input("Senha do Trustvox:", type="password")

    st.divider()
    st.title("🌐 Agente Local (Ngrok)")
    agent_url = st.text_input(
        "URL do Ngrok:",
        placeholder="ex: https://xxxx.ngrok-free.app",
        help="Cole a URL gerada pelo comando 'ngrok http 8000' no seu computador"
    ).strip()

    st.divider()
    st.title("📚 Empresa & Planilha")
    slug_empresa = st.text_input("Slug da Empresa no Trustvox:", value="coty").strip().lower()
    arquivo_enviado = st.file_uploader("Carregar Planilha De/Para", type=["xlsx", "csv"])

    st.divider()
    modo_validacao = st.radio("Escopo de Validação", ["Amostragem em Blocos (~40%)", "Validar 100% dos Produtos"], index=0)

# ---------------------------------------------------------
# CORPO PRINCIPAL
# ---------------------------------------------------------
st.title("🛡️ Trustvox Migration Studio")
st.caption("A equipe utiliza o painel Web online e o processamento roda no Chrome local sem bloqueios")

if arquivo_enviado is None or not slug_empresa or not usuario_trustvox or not senha_trustvox or not agent_url:
    st.info("👈 **Para começar:** Preencha as credenciais, a URL do Ngrok e suba a planilha na barra lateral.")
else:
    df_input = pd.read_csv(arquivo_enviado) if arquivo_enviado.name.endswith('.csv') else pd.read_excel(arquivo_enviado)

    cols_unicas = []
    counts = {}
    for col in df_input.columns:
        col_str = str(col).strip()
        if col_str in counts:
            counts[col_str] += 1
            cols_unicas.append(f"{col_str}_{counts[col_str]}")
        else:
            counts[col_str] = 0
            cols_unicas.append(col_str)
    df_input.columns = cols_unicas

    cols_lista = list(df_input.columns)
    col_antigo_default = next((c for c in cols_lista if any(k in str(c).lower() for k in ['cod_antigo', 'código antigo', 'codigo antigo'])), cols_lista[0])
    col_novo_default = next((c for c in cols_lista if any(k in str(c).lower() for k in ['cod_novo', 'código novo', 'codigo novo'])), cols_lista[1] if len(cols_lista) > 1 else cols_lista[0])

    col_execucao, col_analytics = st.columns([1.1, 0.9], gap="large")

    with col_execucao:
        st.markdown("### 🎯 Central de Execução")
        c1, c2 = st.columns(2)
        with c1:
            col_antigo = st.selectbox("Coluna CÓDIGO ANTIGO:", cols_lista, index=cols_lista.index(col_antigo_default))
        with c2:
            col_novo = st.selectbox("Coluna CÓDIGO NOVO:", cols_lista, index=cols_lista.index(col_novo_default))

        btn_iniciar = st.button("🚀 Iniciar Processamento", type="primary", width="stretch")
        status_box = st.empty()
        progress_bar = st.progress(0)
        log_box = st.container(height=350)

    with col_analytics:
        st.markdown("### 📊 Painel de Insights")
        m1, m2, m3 = st.columns(3)
        kpi_total = m1.empty()
        kpi_ok = m2.empty()
        kpi_err = m3.empty()
        kpi_total.metric("Analisados", "0")
        kpi_ok.metric("Aprovados", "0")
        kpi_err.metric("Reprovados", "0")
        st.divider()
        tabela_live = st.empty()

    if btn_iniciar:
        # Adiciona o cabeçalho 'ngrok-skip-browser-warning' exigido pelo ngrok gratuito
        headers = {"ngrok-skip-browser-warning": "true"}
        
        status_box.warning("🔌 Conectando ao Agente Local no seu computador...")
        try:
            target_agent = agent_url.rstrip("/")
            resp_init = requests.post(f"{target_agent}/iniciar_sessao", json={"usuario": usuario_trustvox, "senha": senha_trustvox}, headers=headers, timeout=20)
            if resp_init.status_code != 200:
                st.error("Não foi possível conectar ao Agente Local. Verifique a URL do Ngrok e se o script `agente_local.py` está rodando.")
                st.stop()
        except Exception as err:
            st.error(f"Erro ao contactar o Agente em {agent_url}: {str(err)}")
            st.stop()

        status_box.success("✅ Conectado ao Chrome local com sucesso! Processando produtos...")

        df_input['Status Validação'] = 'Não Testado'
        df_input['Observação Validação'] = '-'

        total_rows = len(df_input)
        indices = list(range(total_rows)) if "100%" in modo_validacao else [i for inicio in range(0, total_rows, 25) for i in range(inicio, min(inicio + 10, total_rows))]

        aprovados = 0
        reprovados = 0

        for cont, idx in enumerate(indices, start=1):
            val_raw = df_input.at[idx, col_antigo]
            cod_antigo_val = str(int(val_raw)).strip() if pd.notna(val_raw) and isinstance(val_raw, (int, float)) else str(val_raw).strip() if pd.notna(val_raw) else ""

            val_novo_raw = df_input.at[idx, col_novo]
            cod_novo_val = str(int(val_novo_raw)).strip() if pd.notna(val_novo_raw) and isinstance(val_novo_raw, (int, float)) else str(val_novo_raw).strip() if pd.notna(val_novo_raw) else ""

            linha_excel = idx + 2

            payload = {
                "slug_empresa": slug_empresa,
                "cod_antigo": cod_antigo_val,
                "cod_novo": cod_novo_val,
                "usuario": usuario_trustvox,
                "senha": senha_trustvox
            }

            try:
                r = requests.post(f"{target_agent}/validar_produto", json=payload, headers=headers, timeout=60)
                res = r.json()
                st_val = res.get("status", "REPROVADO")
                obs_val = res.get("obs", "Sem resposta")
            except Exception as e:
                st_val = "REPROVADO"
                obs_val = f"Erro de comunicação com o Agente: {str(e)}"

            if st_val == "APROVADO":
                aprovados += 1
                log_box.success(f"Linha {linha_excel} | ID {cod_antigo_val} ➔ {cod_novo_val} | ✅ APROVADO")
            else:
                reprovados += 1
                log_box.error(f"Linha {linha_excel} | ID {cod_antigo_val} ➔ {cod_novo_val} | ❌ REPROVADO ({obs_val})")

            df_input.at[idx, 'Status Validação'] = st_val
            df_input.at[idx, 'Observação Validação'] = obs_val

            kpi_total.metric("Analisados", f"{cont}/{len(indices)}")
            kpi_ok.metric("Aprovados", f"{aprovados}")
            kpi_err.metric("Reprovados", f"{reprovados}")
            progress_bar.progress(cont / len(indices))

        status_box.success("🎉 Validação concluída com sucesso!")
        nome_saida = f"relatorio_{slug_empresa}_validado.xlsx"
        df_input.to_excel(nome_saida, index=False)

        with open(nome_saida, "rb") as file:
            st.download_button("📥 Baixar Relatório Consolidado (Excel)", data=file, file_name=nome_saida, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

        df_display = df_input.loc[:, ~df_input.columns.duplicated()][['Status Validação', col_antigo, col_novo, 'Observação Validação']]
        tabela_live.dataframe(df_display, width="stretch")
