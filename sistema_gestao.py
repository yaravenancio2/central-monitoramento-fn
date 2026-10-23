import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import os
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Central de Monitoramento | FN Distribuidora", page_icon="🚚", layout="wide")

# ================= ESTILIZAÇÃO VISUAL =================
st.markdown("""
    <style>
    .stApp { background-color: #0b0f19; color: #f0f2f6; }
    [data-testid="stSidebar"] { background-color: #0b1c2c; border-right: 2px solid #1261A3; }
    .stButton>button {
        background-color: #F5A623 !important; color: #000000 !important;
        font-weight: bold !important; border: none !important; border-radius: 6px !important;
    }
    .stButton>button:hover { background-color: #e0961b !important; color: white !important; }
    div[data-testid="metric-container"] {
        background: linear-gradient(145deg, #121826, #1a2333);
        border-top: 3px solid #1261A3; padding: 15px 20px; border-radius: 8px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }
    .titulo-secao {
        font-size: 18px; font-weight: 600; color: #e2e8f0;
        margin-top: 15px; margin-bottom: 15px; border-left: 4px solid #F5A623; padding-left: 10px;
    }
    .card-ocorrencia { background-color: #161e2e; border-left: 5px solid #ef4444; padding: 15px; border-radius: 6px; margin-bottom: 12px; }
    .card-positivo { background-color: #161e2e; border-left: 5px solid #10b981; padding: 15px; border-radius: 6px; margin-bottom: 12px; }
    .badge-funcao { background-color: #1261A3; color: white; padding: 6px 14px; border-radius: 6px; font-weight: bold; display: inline-block; margin-top: 28px; }
    </style>
""", unsafe_allow_html=True)

ARQUIVO_LOGO = "logo_fn.jpg"
# ================= 1. CONEXÃO DE ALTA PERFORMANCE COM POOLING =================
@st.cache_resource
def get_engine():
    try:
        # Tenta ler do secrets.toml; se não achar, usa a string direta sem channel_binding (mais rápida no pooler)
        if "database" in st.secrets and "url" in st.secrets["database"]:
            db_url = st.secrets["database"]["url"]
        else:
            db_url = "postgresql://neondb_owner:npg_lIF7viVRP1wr@ep-calm-glitter-b6dn9ffv-pooler.c-2.sa-east-1.aws.neon.tech/neondb?sslmode=require"
        
        return create_engine(
            db_url,
            pool_size=5,           # Mantém até 5 conexões prontas na memória
            max_overflow=10,       # Suporta picos de acessos simultâneos
            pool_pre_ping=True,    # Testa se a conexão está viva antes de usar (evita travamentos)
            pool_recycle=300       # Renova conexões a cada 5 min para evitar quedas do Neon
        )
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados PostgreSQL: {e}")
        return None

engine = get_engine()

# ================= 2. LEITURA EM CACHE (ZERO LATÊNCIA NOS CLIQUES) =================
@st.cache_data(ttl=120, show_spinner=False)
def carregar_colaboradores():
    if engine:
        try:
            query = "SELECT colaborador, funcao FROM colaboradores ORDER BY colaborador"
            df_c = pd.read_sql(query, engine)
            if not df_c.empty:
                df_c.columns = ["Colaborador", "Funcao"]
                return df_c
        except Exception:
            pass
    return pd.DataFrame([{"Colaborador": "Carlos Eduardo", "Funcao": "Motorista"}])

@st.cache_data(ttl=300, show_spinner=False)
def carregar_naturezas():
    if engine:
        try:
            query = "SELECT natureza FROM naturezas ORDER BY id"
            df_n = pd.read_sql(query, engine)
            if not df_n.empty:
                return df_n["natureza"].tolist()
        except Exception:
            pass
    return ["Negligência Grave", "Devolução por Falha", "Comportamental", "Dificuldade Operacional", "Ação Positiva (Elogio)"]

@st.cache_data(ttl=300, show_spinner=False)
def carregar_motivos():
    if engine:
        try:
            query = "SELECT motivo FROM motivos ORDER BY id"
            df_m = pd.read_sql(query, engine)
            if not df_m.empty:
                return df_m["motivo"].tolist()
        except Exception:
            pass
    return [
        "Voltou com devolução sem acionar a Torre",
        "Falta de conferência (Avaria / Falta de mercadoria)",
        "Atraso na saída / Horário limite perdido no cliente",
        "Postura inadequada no cliente ou com a Torre",
        "Erro de manuseio no App (maxMotorista)",
        "Não seguiu rota planejada",
        "Otimização de processo / Salvou entrega difícil",
        "Outros"
    ]

@st.cache_data(ttl=60, show_spinner=False)
def carregar_dados():
    if engine:
        try:
            query = """
                SELECT id, data, colaborador, funcao, rota, tipo, motivo, 
                       detalhe, pontos, status, acao_gestor, data_tratativa, registrado_por 
                FROM ocorrencias 
                ORDER BY id DESC
            """
            df_o = pd.read_sql(query, engine)
            df_o.columns = ["ID", "Data", "Colaborador", "Funcao", "Rota", "Tipo", "Motivo", "Detalhe", "Pontos", "Status", "Acao_Gestor", "Data_Tratativa", "Registrado_Por"]
            return df_o
        except Exception:
            pass
    
    colunas = ["ID", "Data", "Colaborador", "Funcao", "Rota", "Tipo", "Motivo", "Detalhe", "Pontos", "Status", "Acao_Gestor", "Data_Tratativa", "Registrado_Por"]
    return pd.DataFrame(columns=colunas)

# Inicializa os dados na memória (O QUE ESTAVA FALTANDO)
df_colab = carregar_colaboradores()
lista_naturezas = carregar_naturezas()
lista_motivos = carregar_motivos()
df = carregar_dados()
if "Registrado_Por" not in df.columns and not df.empty:
    df["Registrado_Por"] = "Torre"

# ================= CONTROLE DE ACESSO (LOGIN) =================
USUARIOS = {
    "cheila": {"senha": "123", "perfil": "operacao", "nome": "Cheila"},
    "caroline": {"senha": "123", "perfil": "operacao", "nome": "Caroline"},
    "sonale": {"senha": "123", "perfil": "operacao", "nome": "Sonale"},
    "melissa": {"senha": "123", "perfil": "operacao", "nome": "Melissa"},
    "lucas": {"senha": "123", "perfil": "operacao", "nome": "Lucas Silva"},
    "yara": {"senha": "123", "perfil": "gestao", "nome": "Yara Venancio"},
    "rennan": {"senha": "456", "perfil": "gestao", "nome": "Rennan"},
    "tiago": {"senha": "456", "perfil": "gestao", "nome": "Tiago"},
    "kennia": {"senha": "456", "perfil": "gestao", "nome": "Kennia"},
    "diretoria": {"senha": "789", "perfil": "leitura", "nome": "Diretoria (Resultados)"}
}

if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["perfil"] = ""
    st.session_state["nome_usuario"] = ""

if not st.session_state["logado"]:
    col1, col2, col3 = st.columns([3, 4, 3])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists(ARQUIVO_LOGO):
            st.image(ARQUIVO_LOGO, use_container_width=True)
        st.markdown('<h2 style="text-align:center; color:#e2e8f0;">CENTRAL DE MONITORAMENTO</h2>', unsafe_allow_html=True)
        st.markdown('<p style="text-align:center; color:#94a3b8; margin-bottom:20px;">Acesso Restrito - FN Distribuidora</p>', unsafe_allow_html=True)
        
        with st.form("form_login"):
            usuario = st.text_input("Usuário").strip().lower()
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar no Sistema", use_container_width=True)
            
            if entrar:
                if usuario in USUARIOS and USUARIOS[usuario]["senha"] == senha:
                    st.session_state["logado"] = True
                    st.session_state["perfil"] = USUARIOS[usuario]["perfil"]
                    st.session_state["nome_usuario"] = USUARIOS[usuario]["nome"]
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    st.stop()

# ================= MENU LATERAL =================
with st.sidebar:
    if os.path.exists(ARQUIVO_LOGO):
        st.image(ARQUIVO_LOGO, use_container_width=True)
    else:
        st.markdown("## 🚚 **CENTRAL FN**")
        
    st.caption(f"👤 Logado como: **{st.session_state['nome_usuario']}**")
    if st.button("Sair / Logout", use_container_width=True):
        st.session_state["logado"] = False
        st.rerun()
        
    st.divider()
    
    if st.session_state["perfil"] == "gestao":
        paginas_disponiveis = [
            "📊 Dashboard Executivo (Visão Geral)", 
            "👤 Prontuário Individual (1 a 80)", 
            "⚡ Central de Tratativas (Gestor)", 
            "➕ Registrar Ocorrência (Torre)",
            "👥 Cadastrar Equipe & Parâmetros"
        ]
    elif st.session_state["perfil"] == "operacao":
        paginas_disponiveis = ["➕ Registrar Ocorrência (Torre)"]
    else:
        paginas_disponiveis = ["📊 Dashboard Executivo (Visão Geral)"]

    pagina = st.radio("MÓDULOS DO SISTEMA", paginas_disponiveis)
    st.divider()
    funcao_filtro = st.multiselect("Filtrar Função:", ["Motorista", "Ajudante"], default=["Motorista", "Ajudante"])
    df_filtrado = df[df["Funcao"].isin(funcao_filtro)] if not df.empty else df

# ================= PÁGINA 1: DASHBOARD EXECUTIVO =================
if pagina == "📊 Dashboard Executivo (Visão Geral)":
    st.markdown("## 📊 Visão Executiva: Monitoramento de Performance e Devoluções")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    pendentes = len(df_filtrado[df_filtrado["Status"] == "Pendente"]) if not df_filtrado.empty else 0
    negligencias = len(df_filtrado[df_filtrado["Tipo"] == "Negligência Grave"]) if not df_filtrado.empty else 0
    devolucoes = len(df_filtrado[df_filtrado["Tipo"] == "Devolução por Falha"]) if not df_filtrado.empty else 0
    comportamental = len(df_filtrado[df_filtrado["Tipo"].isin(["Comportamental", "Dificuldade Operacional"])]) if not df_filtrado.empty else 0
    elogios = len(df_filtrado[df_filtrado["Tipo"] == "Ação Positiva (Elogio)"]) if not df_filtrado.empty else 0
    
    col1.metric("🔴 Pendentes Gestor", f"{pendentes} casos")
    col2.metric("⚠️ Negligências Graves", f"{negligencias} reg.")
    col3.metric("📦 Devoluções (Equipe)", f"{devolucoes} ocorr.")
    col4.metric("🗣️ Comportamento/App", f"{comportamental} ocorr.")
    col5.metric("🟢 Ações Positivas", f"{elogios} elogios")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    aba_ranking, aba_torre, aba_gestor, aba_cruzamento = st.tabs([
        "🎯 1. Ranking & Pontos Acumulados", 
        "📋 2. Registros da Torre (Fatos)", 
        "👔 3. Retorno da Gestão (Tratativas)",
        "📈 4. Análise Gráfica & Linha do Tempo"
    ])
    
    with aba_ranking:
        st.markdown('<div class="titulo-secao">🚨 Matriz de Pontuação Acumulada por Colaborador</div>', unsafe_allow_html=True)
        if not df_filtrado.empty:
            resumo_colab = df_filtrado.groupby(["Colaborador", "Funcao"]).agg(
                Score_Acumulado=("Pontos", "sum"),
                Total_Negligencias=("Tipo", lambda x: (x == "Negligência Grave").sum()),
                Total_Devolucoes=("Tipo", lambda x: (x == "Devolução por Falha").sum()),
                Total_Comportamental=("Tipo", lambda x: x.isin(["Comportamental", "Dificuldade Operacional"]).sum()),
                Total_Elogios=("Tipo", lambda x: (x == "Ação Positiva (Elogio)").sum()),
                Casos_Tratar=("Status", lambda x: (x == "Pendente").sum()),
                Casos_Resolvidos=("Status", lambda x: (x != "Pendente").sum())
            ).reset_index().sort_values(by="Score_Acumulado", ascending=False)
            
            def definir_alerta(pts):
                if pts >= 8: return "🔴 CRÍTICO (Advertência)"
                elif pts >= 4: return "🟡 ATENÇÃO (Feedback)"
                elif pts > 0: return "🔵 MONITORAR"
                else: return "🟢 DESTAQUE / REGULAR"
                
            resumo_colab["Situação Atual"] = resumo_colab["Score_Acumulado"].apply(definir_alerta)
            resumo_colab = resumo_colab[[
                "Colaborador", "Funcao", "Situação Atual", "Score_Acumulado", 
                "Total_Negligencias", "Total_Devolucoes", "Total_Comportamental", 
                "Total_Elogios", "Casos_Tratar", "Casos_Resolvidos"
            ]]
            
            st.dataframe(
                resumo_colab,
                column_config={
                    "Score_Acumulado": st.column_config.ProgressColumn("Pontos Acumulados", format="%d pts", min_value=-5, max_value=15),
                    "Total_Negligencias": st.column_config.NumberColumn("Negligências (+5)", format="%d ⚠️"),
                    "Total_Devolucoes": st.column_config.NumberColumn("Devoluções (+3)", format="%d 📦"),
                    "Total_Comportamental": st.column_config.NumberColumn("Comport./App (+2/+1)", format="%d 🗣️"),
                    "Total_Elogios": st.column_config.NumberColumn("Elogios (-3)", format="%d 🌟"),
                    "Casos_Tratar": st.column_config.NumberColumn("Pendentes Gestor", format="%d 🔴"),
                    "Casos_Resolvidos": st.column_config.NumberColumn("Já Tratados", format="%d ✔️")
                },
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Nenhuma ocorrência registrada na base ainda.")

    with aba_torre:
        st.markdown('<div class="titulo-secao">📋 Diário de Bordo da Torre</div>', unsafe_allow_html=True)
        if not df_filtrado.empty:
            st.dataframe(df_filtrado[["ID", "Data", "Colaborador", "Funcao", "Rota", "Tipo", "Motivo", "Detalhe", "Pontos", "Registrado_Por"]].sort_values(by="ID", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Sem registros.")

    with aba_gestor:
        st.markdown('<div class="titulo-secao">👔 Controle de Tratativas da Gestão</div>', unsafe_allow_html=True)
        if not df_filtrado.empty:
            filtro_status_gestor = st.radio("Visualizar casos:", ["Todos os Casos", "Apenas Já Tratados pelo Gestor", "Apenas Pendentes de Ação"], horizontal=True)
            df_aba_gestor = df_filtrado.copy()
            if filtro_status_gestor == "Apenas Já Tratados pelo Gestor":
                df_aba_gestor = df_aba_gestor[df_aba_gestor["Status"] != "Pendente"]
            elif filtro_status_gestor == "Apenas Pendentes de Ação":
                df_aba_gestor = df_aba_gestor[df_aba_gestor["Status"] == "Pendente"]
            st.dataframe(df_aba_gestor[["ID", "Colaborador", "Funcao", "Data", "Motivo", "Status", "Acao_Gestor", "Data_Tratativa"]].sort_values(by="ID", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Sem registros.")

    with aba_cruzamento:
        st.markdown('<div class="titulo-secao">📈 Linha do Tempo e Evolução Geral da Operação</div>', unsafe_allow_html=True)
        st.caption("Filtre por período, natureza ou motivo para analisar se a operação está melhorando ou piorando ao longo do tempo.")
        
        if not df_filtrado.empty:
            c_f1, c_f2, c_f3 = st.columns(3)
            df_filtrado["Data_Dt"] = pd.to_datetime(df_filtrado["Data"], errors="coerce")
            min_data = df_filtrado["Data_Dt"].min().date() if not df_filtrado["Data_Dt"].isna().all() else date.today()
            max_data = df_filtrado["Data_Dt"].max().date() if not df_filtrado["Data_Dt"].isna().all() else date.today()
            
            periodo = c_f1.date_input("Filtrar Período:", [min_data, max_data])
            naturezas_disponiveis = df_filtrado["Tipo"].unique().tolist()
            f_nat = c_f2.multiselect("Filtrar Natureza do Fato:", naturezas_disponiveis, default=naturezas_disponiveis)
            
            motivos_disponiveis = df_filtrado["Motivo"].unique().tolist()
            f_mot = c_f3.multiselect("Filtrar Motivo Padronizado:", motivos_disponiveis, default=motivos_disponiveis)
            
            df_graf = df_filtrado.copy()
            if len(periodo) == 2:
                d_ini, d_fim = periodo
                df_graf = df_graf[(df_graf["Data_Dt"].dt.date >= d_ini) & (df_graf["Data_Dt"].dt.date <= d_fim)]
            df_graf = df_graf[df_graf["Tipo"].isin(f_nat) & df_graf["Motivo"].isin(f_mot)]
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if not df_graf.empty:
                df_temporal = df_graf.groupby(["Data", "Tipo"]).agg(Pontos_Dia=("Pontos", "sum"), Ocorrencias=("ID", "count")).reset_index().sort_values("Data")
                
                fig_tempo = px.bar(
                    df_temporal, x="Data", y="Pontos_Dia", color="Tipo",
                    title="Evolução Diária de Gravidade (Pontos Acumulados por Dia)",
                    template="plotly_dark", height=320,
                    color_discrete_map={"Negligência Grave": "#ef4444", "Devolução por Falha": "#F5A623", "Comportamental": "#1261A3", "Dificuldade Operacional": "#8b5cf6", "Ação Positiva (Elogio)": "#10b981"}
                )
                fig_tempo.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_tempo, use_container_width=True)
                
                g_col1, g_col2 = st.columns(2)
                df_negativos = df_graf[df_graf["Pontos"] > 0]
                
                with g_col1:
                    if not df_negativos.empty:
                        fig_bar = px.bar(
                            df_negativos, y="Colaborador", x="Pontos", color="Tipo", orientation="h", 
                            title="Top Ofensores no Período", template="plotly_dark", height=320,
                            color_discrete_map={"Negligência Grave": "#ef4444", "Devolução por Falha": "#F5A623", "Comportamental": "#1261A3", "Dificuldade Operacional": "#8b5cf6"}
                        )
                        fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", yaxis={'categoryorder':'total ascending'})
                        st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        st.info("Sem ofensores no período selecionado.")

                with g_col2:
                    if not df_negativos.empty:
                        fig_pie = px.pie(df_negativos, names="Motivo", hole=0.55, title="Causas Raízes no Período", template="plotly_dark", height=320)
                        fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.info("Sem dados para o gráfico de causas.")
                        
                st.markdown("#### 📋 Histórico Cronológico Filtrado")
                st.dataframe(df_graf[["Data", "Colaborador", "Funcao", "Rota", "Tipo", "Motivo", "Detalhe", "Status"]].sort_values(by="Data", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.warning("Nenhum registro encontrado para os filtros selecionados.")
        else:
            st.info("Sem dados suficientes na base.")

# ================= PÁGINA 2: PRONTUÁRIO INDIVIDUAL =================
elif pagina == "👤 Prontuário Individual (1 a 80)":
    st.markdown("## 👤 Dossiê Individual do Colaborador")
    
    lista_nomes = sorted(df_colab["Colaborador"].unique())
    selecionado = st.selectbox("🔍 Pesquisar Motorista ou Ajudante:", lista_nomes)
    
    funcao_colab = df_colab[df_colab["Colaborador"] == selecionado]["Funcao"].iloc[0]
    df_ind = df[df["Colaborador"] == selecionado].copy() if not df.empty else pd.DataFrame()
    
    c1, c2 = st.columns([3, 7])
    with c1:
        score_atual = df_ind["Pontos"].sum() if not df_ind.empty else 0
        st.metric(f"Score Acumulado ({funcao_colab})", f"{score_atual} pts")
        if score_atual >= 8: st.error("⚠️ ALERTA: Limite crítico atingido.")
        elif score_atual == 0 and df_ind.empty: st.success("✔️ Ficha Limpa (Nenhuma ocorrência registrada).")
            
    with c2:
        st.markdown(f"### 📋 Linha do Tempo — {selecionado} ({funcao_colab})")
        if not df_ind.empty:
            for _, row in df_ind.sort_values(by="Data", ascending=False).iterrows():
                classe = "card-positivo" if row["Pontos"] < 0 else "card-ocorrencia"
                tratativa = row["Acao_Gestor"] if pd.notna(row["Acao_Gestor"]) and str(row["Acao_Gestor"]).strip() != "" else "⏳ Aguardando..."
                st.markdown(f'<div class="{classe}"><b>{row["Data"]} | {row["Tipo"]} - {row["Motivo"]}</b><br><small>Relato: {row["Detalhe"]}<br><b>Tratativa:</b> {tratativa}</small></div>', unsafe_allow_html=True)
        else:
            st.info("Este colaborador não possui ocorrências registradas até o momento.")

    st.markdown("---")
    st.markdown("### 📈 Curva de Comportamento (Antes e Depois do Feedback)")
    if not df_ind.empty:
        df_ind['Data_Grafico'] = pd.to_datetime(df_ind['Data'])
        df_ind = df_ind.sort_values('Data_Grafico')
        fig_evol = px.bar(df_ind, x='Data_Grafico', y='Pontos', color='Tipo', template='plotly_dark',
                          color_discrete_map={"Negligência Grave": "#ef4444", "Devolução por Falha": "#F5A623", "Comportamental": "#1261A3", "Dificuldade Operacional": "#8b5cf6", "Ação Positiva (Elogio)": "#10b981"})
        tratativas_feitas = df_ind[df_ind['Data_Tratativa'].notna() & (df_ind['Data_Tratativa'] != "")]
        for _, row in tratativas_feitas.iterrows():
            dt_trat = pd.to_datetime(row['Data_Tratativa'])
            fig_evol.add_vline(x=dt_trat, line_width=2, line_dash="dash", line_color="#F5A623")
            fig_evol.add_annotation(x=dt_trat, y=max(df_ind['Pontos'].max(), 5), text=f"👔 {row['Status']}", showarrow=False, yshift=15, font=dict(color="#F5A623", size=12))
        fig_evol.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_evol, use_container_width=True)

# ================= PÁGINA 3: CENTRAL DE TRATATIVAS (GESTOR) =================
elif pagina == "⚡ Central de Tratativas (Gestor)":
    st.markdown("## ⚡ Mesa de Decisão e Gestão de Ocorrências")
    
    aba_tratar, aba_excluir = st.tabs(["✍️ Dar Baixa / Tratativas", "🗑️ Excluir Registros Incorretos"])
    
    with aba_tratar:
        df_pend = df[df["Status"] == "Pendente"] if not df.empty else pd.DataFrame()
        if df_pend.empty:
            st.success("🎉 Não há ocorrências pendentes de tratativa no momento!")
        else:
            opcoes = df_pend.apply(lambda r: f"ID {r['ID']} | {r['Colaborador']} ({r['Funcao']}) - {r['Motivo']}", axis=1).tolist()
            escolha = st.selectbox("Selecione o caso para tratar:", opcoes)
            id_selecionado = int(escolha.split(" | ")[0].replace("ID ", ""))
            
            caso_atual = df[df["ID"] == id_selecionado].iloc[0]
            st.info(f"**Relato da Torre ({caso_atual['Data']} - Rota {caso_atual['Rota']}):** {caso_atual['Detalhe']}")
            
            with st.form("form_gestor"):
                novo_status = st.selectbox("Ação Aplicada:", ["Feedback Aplicado", "Advertência Verbal", "Advertência Escrita", "Encaminhado p/ Treinamento", "Suspensão", "Caso Justificado / Arquivado"])
                obs_gestor = st.text_area("O que foi conversado / definido com o colaborador?")
                if st.form_submit_button("💾 Salvar Tratativa", use_container_width=True):
                    if engine:
                        try:
                            with engine.begin() as conn:
                                conn.execute(
                                    text("UPDATE ocorrencias SET status = :status, acao_gestor = :acao, data_tratativa = :data WHERE id = :id"),
                                    {"status": novo_status, "acao": obs_gestor, "data": datetime.now().strftime("%Y-%m-%d"), "id": id_selecionado}
                                )
                            st.toast("✅ Salvo com sucesso no Neon PostgreSQL!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar no banco: {e}")

    with aba_excluir:
        st.markdown("### ⚠️ Área Restrita de Exclusão de Registros")
        if df.empty:
            st.info("Não há registros na base.")
        else:
            termo_busca = st.text_input("🔍 Digite o nome do colaborador ou motivo para filtrar:").strip().lower()
            df_excluir_filtrado = df.copy()
            if termo_busca:
                df_excluir_filtrado = df_excluir_filtrado[
                    df_excluir_filtrado["Colaborador"].str.lower().str.contains(termo_busca, na=False) |
                    df_excluir_filtrado["Motivo"].str.lower().str.contains(termo_busca, na=False) |
                    df_excluir_filtrado["Tipo"].str.lower().str.contains(termo_busca, na=False)
                ]
            
            if df_excluir_filtrado.empty:
                st.warning("Nenhuma ocorrência encontrada com esse termo de busca.")
            else:
                opcoes_excluir = df_excluir_filtrado.apply(lambda r: f"ID {r['ID']} | {r['Data']} - {r['Colaborador']} ({r['Tipo']}: {r['Motivo']})", axis=1).tolist()
                registro_escolhido = st.selectbox("Selecione a ocorrência:", opcoes_excluir)
                
                if registro_escolhido:
                    id_excluir = int(registro_escolhido.split(" | ")[0].replace("ID ", ""))
                    detalhe_exclusao = df[df["ID"] == id_excluir].iloc[0]
                    st.warning(f"Apagar registro de **{detalhe_exclusao['Colaborador']}** em **{detalhe_exclusao['Data']}**?")
                    
                    if st.button("🗑️ Confirmar Exclusão Definitiva", type="primary"):
                        if engine:
                            try:
                                with engine.begin() as conn:
                                    conn.execute(text("DELETE FROM ocorrencias WHERE id = :id"), {"id": id_excluir})
                                st.success("✅ Ocorrência apagada do banco!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")

# ================= PÁGINA 4: LANÇAMENTO DA TORRE =================
elif pagina == "➕ Registrar Ocorrência (Torre)":
    st.markdown("## ➕ Registro Diário — Central de Monitoramento")
    col_nome, col_funcao, col_rota = st.columns([5, 3, 4])
    lista_ordenada = sorted(df_colab["Colaborador"].unique())
    
    nome_selecionado = col_nome.selectbox("🔍 Pesquisar Motorista ou Ajudante:", lista_ordenada)
    funcao_automatica = df_colab[df_colab["Colaborador"] == nome_selecionado]["Funcao"].iloc[0]
    
    col_funcao.markdown(f'<div class="badge-funcao">🪪 Função: {funcao_automatica}</div>', unsafe_allow_html=True)
    rota_input = col_rota.text_input("Rota / Cidade (Ex: Varginha, Passos...)")
    
    with st.form("form_torre", clear_on_submit=True):
        c1, c2 = st.columns(2)
        tipo = c1.selectbox("Natureza do Fato", lista_naturezas)
        motivo = c2.selectbox("Motivo Padronizado", lista_motivos)
        detalhe = st.text_area("Relato detalhado do que aconteceu:")
        
        if st.form_submit_button("🚀 Registrar Ocorrência no Sistema", use_container_width=True):
            pontos = 5 if "Negligência" in tipo else (3 if "Devolução" in tipo else (-3 if "Elogio" in tipo or "Positiva" in tipo else 2))
            novo_id = int(df["ID"].max() + 1) if not df.empty and pd.notna(df["ID"].max()) else 101
            status_inicial = "Reconhecido" if "Elogio" in tipo or "Positiva" in tipo else "Pendente"
            
            if engine:
                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO ocorrencias (id, data, colaborador, funcao, rota, tipo, motivo, detalhe, pontos, status, acao_gestor, data_tratativa, registrado_por)
                                VALUES (:id, :data, :colab, :func, :rota, :tipo, :motivo, :detalhe, :pontos, :status, :acao, :data_trat, :reg)
                            """),
                            {
                                "id": novo_id,
                                "data": datetime.now().strftime("%Y-%m-%d"),
                                "colab": nome_selecionado,
                                "func": funcao_automatica,
                                "rota": rota_input if rota_input else "-",
                                "tipo": tipo,
                                "motivo": motivo,
                                "detalhe": detalhe if detalhe else "-",
                                "pontos": pontos,
                                "status": status_inicial,
                                "acao": "",
                                "data_trat": None,
                                "reg": st.session_state["nome_usuario"]
                            }
                        )
                    st.success(f"✅ Ocorrência salva no Neon PostgreSQL para **{nome_selecionado}**!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar no banco: {e}")

# ================= PÁGINA 5: CADASTRAR EQUIPE & PARÂMETROS =================
elif pagina == "👥 Cadastrar Equipe & Parâmetros":
    st.markdown("## 👥 Gestão de Equipe e Parâmetros do Sistema")
    
    aba_lote, aba_individual, aba_parametros, aba_limpar = st.tabs([
        "📋 1. Colaboradores", 
        "➕ 2. Adicionar/Remover", 
        "⚙️ 3. Naturezas e Motivos", 
        "🧹 4. Zerar Base"
    ])
    
    with aba_lote:
        st.markdown('<div class="titulo-secao">Importação de Colaboradores (Nome;Função)</div>', unsafe_allow_html=True)
        st.caption("Cole abaixo a lista dos colaboradores no formato Nome;Função (um por linha).")
        texto_lote = st.text_area("Cole sua lista aqui:", height=150, key="txt_lote_colab")
        
        if st.button("🔄 Substituir Base de Colaboradores", use_container_width=True):
            if texto_lote.strip() and engine:
                linhas = [l.strip() for l in texto_lote.strip().split("\n") if l.strip()]
                # Usa dicionário para evitar nomes duplicados na própria lista colada
                mapa_unicos = {}
                for l in linhas:
                    partes = l.replace("\t", ";").replace(",", ";").split(";")
                    nome_c = partes[0].strip().title()
                    func_c = "Ajudante" if len(partes) > 1 and "ajud" in partes[1].lower() else "Motorista"
                    if nome_c:
                        mapa_unicos[nome_c] = func_c
                
                novos_dados = [{"c": k, "f": v} for k, v in mapa_unicos.items()]
                
                try:
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM colaboradores"))
                        if novos_dados:
                            # ENVIO EM LOTE ÚNICO (100x mais rápido que o loop for)
                            conn.execute(
                                text("INSERT INTO colaboradores (colaborador, funcao) VALUES (:c, :f)"),
                                novos_dados
                            )
                    st.cache_data.clear()
                    st.success(f"✅ {len(novos_dados)} colaboradores gravados instantaneamente no Neon!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar: {e}")

        st.markdown("#### Efetivo Atual no Banco:")
        st.dataframe(df_colab.sort_values(by="Colaborador"), use_container_width=True, hide_index=True)

    with aba_individual:
        st.markdown('<div class="titulo-secao">Gerenciamento Individual de Efetivo</div>', unsafe_allow_html=True)
        c_add, c_rem = st.columns(2)
        
        with c_add:
            st.markdown("#### ➕ Adicionar Novo Colaborador")
            novo_nome = st.text_input("Nome Completo:", key="input_novo_nome_ind")
            nova_func = st.selectbox("Função:", ["Motorista", "Ajudante"], key="select_nova_func_ind")
            if st.button("Salvar Colaborador", key="btn_salvar_ind_unico"):
                if novo_nome.strip() and engine:
                    try:
                        with engine.begin() as conn:
                            conn.execute(
                                text("INSERT INTO colaboradores (colaborador, funcao) VALUES (:c, :f) ON CONFLICT (colaborador) DO UPDATE SET funcao = :f"),
                                {"c": novo_nome.strip().title(), "f": nova_func}
                            )
                        st.cache_data.clear()
                        st.success(f"✅ {novo_nome.strip().title()} adicionado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
                        
        with c_rem:
            st.markdown("#### 🗑️ Remover Colaborador")
            lista_atuais = sorted(df_colab["Colaborador"].unique()) if not df_colab.empty else []
            if lista_atuais:
                rem_nome = st.selectbox("Selecione para remover:", lista_atuais, key="select_rem_colab_unico")
                if st.button("Remover da Lista", key="btn_remover_ind_unico"):
                    if engine:
                        try:
                            with engine.begin() as conn:
                                conn.execute(text("DELETE FROM colaboradores WHERE colaborador = :c"), {"c": rem_nome})
                            st.cache_data.clear()
                            st.warning(f"⚠️ Colaborador {rem_nome} removido do banco!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao remover: {e}")
            else:
                st.info("Nenhum colaborador cadastrado na base.")

    with aba_parametros:
        st.markdown('<div class="titulo-secao">⚙️ Gerenciar Naturezas e Motivos</div>', unsafe_allow_html=True)
        c_nat, c_mot = st.columns(2)
        with c_nat:
            nova_nat = st.text_input("Nova Natureza:", key="input_nova_nat")
            if st.button("Salvar Natureza", key="btn_salvar_nat") and nova_nat.strip() and engine:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("INSERT INTO naturezas (natureza) VALUES (:n) ON CONFLICT (natureza) DO NOTHING"), {"n": nova_nat.strip()})
                    st.cache_data.clear()
                    st.success("Natureza salva!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
            st.write("Atuais:", lista_naturezas)
            
        with c_mot:
            novo_mot = st.text_input("Novo Motivo:", key="input_novo_mot")
            if st.button("Salvar Motivo", key="btn_salvar_mot") and novo_mot.strip() and engine:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("INSERT INTO motivos (motivo) VALUES (:m) ON CONFLICT (motivo) DO NOTHING"), {"m": novo_mot.strip()})
                    st.cache_data.clear()
                    st.success("Motivo salvo!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
            st.write("Atuais:", lista_motivos)

    with aba_limpar:
        st.markdown('<div class="titulo-secao">🧹 Limpeza de Base</div>', unsafe_allow_html=True)
        st.warning("Atenção: Esta ação apaga todas as ocorrências cadastradas na nuvem.")
        if st.button("🗑️ Zerar Ocorrências na Nuvem", key="btn_zerar_nuvem") and engine:
            try:
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM ocorrencias"))
                st.cache_data.clear()
                st.success("✅ Ocorrências zeradas no banco!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
