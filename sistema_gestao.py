import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from sqlalchemy import create_engine, text
import base64
import io

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ================= CONFIGURAÇÃO DA PÁGINA =================
st.set_page_config(
    page_title="Central de Monitoramento & RV - FN Distribuidora",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

VALOR_BASE_RV = 250.0

# ================= ESTILO VISUAL (DARK EXECUTIVE) =================
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    .kpi-card {
        background: linear-gradient(145deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        margin-bottom: 10px;
    }
    .kpi-title { font-size: 0.82rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-value { font-size: 1.75rem; font-weight: 800; color: #f8fafc; margin: 6px 0; }
    .kpi-sub { font-size: 0.78rem; color: #cbd5e1; }
    .titulo-secao {
        font-size: 1.15rem;
        font-weight: 700;
        color: #f8fafc;
        background: #1e293b;
        padding: 10px 15px;
        border-left: 5px solid #3b82f6;
        border-radius: 6px;
        margin: 15px 0 12px 0;
    }
</style>
""", unsafe_allow_html=True)

# ================= 1. CONEXÃO DE ALTA PERFORMANCE COM AUTO-MIGRAÇÃO =================
MOTIVOS_OFICIAIS_PADRAO = [
    {"motivo": "FALTA COLABORADOR", "prioridade": "Alta", "impacta_rv": "Sim", "p1": 100, "p2": 100},
    {"motivo": "ADVERTENCIA", "prioridade": "Alta", "impacta_rv": "Sim", "p1": 100, "p2": 100},
    {"motivo": "SINISTRO", "prioridade": "Alta", "impacta_rv": "Sim", "p1": 100, "p2": 100},
    {"motivo": "MULTA DE TRANSITO", "prioridade": "Alta", "impacta_rv": "Sim", "p1": 100, "p2": 100},
    {"motivo": "DEVOLUÇÃO", "prioridade": "Alta", "impacta_rv": "Sim", "p1": 20, "p2": 100},
    {"motivo": "PENDÊNCIA", "prioridade": "Alta", "impacta_rv": "Sim", "p1": 20, "p2": 100},
    {"motivo": "ACERTO CORRETO", "prioridade": "Média", "impacta_rv": "Sim", "p1": 20, "p2": 100},
    {"motivo": "CHECKLIST DIÁRIO", "prioridade": "Média", "impacta_rv": "Sim", "p1": 20, "p2": 100},
    {"motivo": "ROTEIRIZADOR (BAIXAS, CANHOTOS, CHECK IN E CHECK OUT)", "prioridade": "Média", "impacta_rv": "Sim", "p1": 20, "p2": 100},
    {"motivo": "REGISTRO JORNADA E SOLIDES", "prioridade": "Média", "impacta_rv": "Sim", "p1": 20, "p2": 100},
    {"motivo": "CHECK LIST HIGIENIZAÇÃO", "prioridade": "Baixa", "impacta_rv": "Sim", "p1": 20, "p2": 100},
    {"motivo": "DEVOLUÇÃO DOS PALETES", "prioridade": "Média", "impacta_rv": "Sim", "p1": 20, "p2": 100},
    # Operacionais / Comportamentais
    {"motivo": "ATRASO NA SAÍDA / HORÁRIO LIMITE NO CLIENTE", "prioridade": "Média", "impacta_rv": "Não", "p1": 0, "p2": 0},
    {"motivo": "POSTURA INADEQUADA NO CLIENTE OU COM A TORRE", "prioridade": "Média", "impacta_rv": "Não", "p1": 0, "p2": 0},
    {"motivo": "NÃO SEGUIU ROTA PLANEJADA", "prioridade": "Média", "impacta_rv": "Não", "p1": 0, "p2": 0},
    {"motivo": "DIFICULDADE OPERACIONAL EM ROTA", "prioridade": "Baixa", "impacta_rv": "Não", "p1": 0, "p2": 0},
    {"motivo": "AÇÃO POSITIVA / ELOGIO OPERACIONAL", "prioridade": "Positivo", "impacta_rv": "Não", "p1": 0, "p2": 0}
]

@st.cache_resource
def get_engine():
    try:
        db_url = "postgresql://neondb_owner:npg_lIF7viVRP1wr@ep-calm-glitter-b6dn9ffv-pooler.c-2.sa-east-1.aws.neon.tech/neondb?sslmode=require"
        eng = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300
        )
        with eng.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS colaboradores (
                    id SERIAL PRIMARY KEY,
                    colaborador VARCHAR(255) UNIQUE NOT NULL,
                    funcao VARCHAR(50) NOT NULL
                );
                CREATE TABLE IF NOT EXISTS motivos (
                    id SERIAL PRIMARY KEY,
                    motivo TEXT UNIQUE NOT NULL,
                    prioridade VARCHAR(30) DEFAULT 'Média',
                    impacta_rv VARCHAR(10) DEFAULT 'Não',
                    perda_1_ocorr INT DEFAULT 0,
                    perda_2_ou_mais INT DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS ocorrencias (
                    id INT PRIMARY KEY,
                    data VARCHAR(50),
                    colaborador VARCHAR(255),
                    funcao VARCHAR(50),
                    rota VARCHAR(255),
                    tipo VARCHAR(255),
                    motivo TEXT,
                    detalhe TEXT,
                    pontos INT DEFAULT 0,
                    status VARCHAR(100),
                    acao_gestor TEXT,
                    data_tratativa VARCHAR(50),
                    registrado_por VARCHAR(100),
                    prioridade VARCHAR(30) DEFAULT 'Média',
                    impacta_rv VARCHAR(10) DEFAULT 'Não',
                    tem_anexo VARCHAR(10) DEFAULT 'Não'
                );
                CREATE TABLE IF NOT EXISTS ocorrencias_anexos (
                    id_ocorrencia INT PRIMARY KEY,
                    nome_arquivo VARCHAR(255),
                    tipo_mime VARCHAR(100),
                    dados_base64 TEXT
                );
            """))
            conn.execute(text("ALTER TABLE motivos ADD COLUMN IF NOT EXISTS prioridade VARCHAR(30) DEFAULT 'Média'"))
            conn.execute(text("ALTER TABLE motivos ADD COLUMN IF NOT EXISTS impacta_rv VARCHAR(10) DEFAULT 'Não'"))
            conn.execute(text("ALTER TABLE motivos ADD COLUMN IF NOT EXISTS perda_1_ocorr INT DEFAULT 0"))
            conn.execute(text("ALTER TABLE motivos ADD COLUMN IF NOT EXISTS perda_2_ou_mais INT DEFAULT 0"))

            conn.execute(text("ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS prioridade VARCHAR(30) DEFAULT 'Média'"))
            conn.execute(text("ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS impacta_rv VARCHAR(10) DEFAULT 'Não'"))
            conn.execute(text("ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS tem_anexo VARCHAR(10) DEFAULT 'Não'"))
            conn.execute(text("ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS registrado_por VARCHAR(100)"))

            for m in MOTIVOS_OFICIAIS_PADRAO:
                conn.execute(text("""
                    INSERT INTO motivos (motivo, prioridade, impacta_rv, perda_1_ocorr, perda_2_ou_mais)
                    VALUES (:m, :pr, :rv, :p1, :p2)
                    ON CONFLICT (motivo) DO NOTHING
                """), {"m": m["motivo"], "pr": m["prioridade"], "rv": m["impacta_rv"], "p1": m["p1"], "p2": m["p2"]})
        return eng
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados PostgreSQL: {e}")
        return None

engine = get_engine()

# ================= 2. CONTROLE DE AUTENTICAÇÃO (LOGIN SEGURO) =================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = None

if not st.session_state["autenticado"]:
    st.markdown("<h2 style='text-align: center;'>🚛 Central de Monitoramento & RV - FN Distribuidora</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #94a3b8;'>Faça login com suas credenciais para acessar o sistema</h4>", unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        with st.form("form_login_seguro"):
            user_escolhido = st.selectbox(
                "Selecionar Usuário:", 
                ["Caroline", "Cheila", "Yara", "Kennia", "Tiago", "Gleidiene (Manutenção)", "Rennan", "Breno (Manutenção)"]
            )
            senha_digitada = st.text_input("Senha de Acesso:", type="password")
            submitted = st.form_submit_button("Entrar no Sistema", use_container_width=True, type="primary")
            
            if submitted:
                # Dicionário de senhas dos usuários
                senhas_cadastradas = {
                    "Cheila": "torre123",
                    "Caroline": "torre123",
                    "Gleidiene (Manutenção)": "manut123",
                    "Breno (Manutenção)": "manut123",
                    "Rennan": "gestao123"
                    "Tiago": "gestao123"
                    "Kennia": "gestao123"
                    "Yara": "gestao123"
                }
                
                if senha_digitada == senhas_cadastradas.get(user_escolhido):
                    st.session_state["autenticado"] = True
                    st.session_state["usuario"] = user_escolhido
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta. Tente novamente.")
    st.stop() # Interrompe a execução do app até que o login seja efetuado

# Recupera o usuário logado com segurança na sessão
usuario_logado = st.session_state["usuario"]

# ================= 3. FUNÇÕES DE LEITURA EM CACHE =================
@st.cache_data(ttl=120, show_spinner=False)
def carregar_colaboradores():
    if engine:
        try:
            df_c = pd.read_sql("SELECT colaborador, funcao FROM colaboradores ORDER BY colaborador", engine)
            if not df_c.empty:
                df_c.columns = ["Colaborador", "Funcao"]
                return df_c
        except Exception:
            pass
    return pd.DataFrame([{"Colaborador": "Carlos Eduardo", "Funcao": "Motorista"}])

@st.cache_data(ttl=300, show_spinner=False)
def carregar_df_motivos():
    if engine:
        try:
            query = """
                SELECT motivo, 
                       COALESCE(prioridade, 'Média') AS prioridade, 
                       COALESCE(impacta_rv, 'Não') AS impacta_rv,
                       COALESCE(perda_1_ocorr, 0) AS perda_1_ocorr,
                       COALESCE(perda_2_ou_mais, 0) AS perda_2_ou_mais
                FROM motivos 
                ORDER BY impacta_rv DESC, prioridade ASC, motivo ASC
            """
            df_m = pd.read_sql(query, engine)
            if not df_m.empty:
                df_m.columns = ["Motivo", "Prioridade", "Impacta_RV", "Perda_1_Ocorr_%", "Perda_2_Mais_%"]
                return df_m
        except Exception:
            pass
    df_pad = pd.DataFrame(MOTIVOS_OFICIAIS_PADRAO)
    df_pad.columns = ["Motivo", "Prioridade", "Impacta_RV", "Perda_1_Ocorr_%", "Perda_2_Mais_%"]
    return df_pad

@st.cache_data(ttl=60, show_spinner=False)
def carregar_dados():
    colunas = [
        "ID", "Data", "Colaborador", "Funcao", "Rota", "Tipo", "Motivo", "Detalhe",
        "Status", "Acao_Gestor", "Data_Tratativa", "Registrado_Por", "Prioridade", "Impacta_RV", "Tem_Anexo"
    ]
    if engine:
        try:
            query = """
                SELECT id, data, colaborador, funcao, rota, tipo, motivo, detalhe,
                       status, acao_gestor, data_tratativa, COALESCE(registrado_por, 'Torre') AS registrado_por,
                       COALESCE(prioridade, tipo, 'Média') AS prioridade,
                       COALESCE(impacta_rv, 'Não') AS impacta_rv,
                       COALESCE(tem_anexo, 'Não') AS tem_anexo
                FROM ocorrencias
                ORDER BY id DESC
            """
            df_o = pd.read_sql(query, engine)
            if not df_o.empty:
                df_o.columns = colunas
                mapa_legado = {
                    "Negligência Grave": "Alta",
                    "Devolução por Falha": "Alta",
                    "Comportamental": "Média",
                    "Dificuldade Operacional": "Baixa",
                    "Ação Positiva (Elogio)": "Positivo"
                }
                df_o["Prioridade"] = df_o["Prioridade"].replace(mapa_legado)
                df_o["Prioridade"] = df_o["Prioridade"].apply(lambda x: x if x in ["Alta", "Média", "Baixa", "Positivo"] else "Média")
                return df_o
        except Exception:
            pass
    return pd.DataFrame(columns=colunas)

# ================= 4. FUNÇÕES AUXILIARES =================
def comprimir_e_codificar_arquivo(uploaded_file):
    if uploaded_file is None:
        return None, None, None
    nome = uploaded_file.name
    mime = uploaded_file.type
    bytes_brutos = uploaded_file.getvalue()

    if HAS_PIL and mime.startswith("image/"):
        try:
            img = Image.open(io.BytesIO(bytes_brutos))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((1200, 1200))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70, optimize=True)
            bytes_finais = buffer.getvalue()
            mime = "image/jpeg"
            if not nome.lower().endswith(".jpg"):
                nome = nome.rsplit(".", 1)[0] + ".jpg"
        except Exception:
            bytes_finais = bytes_brutos
    else:
        if len(bytes_brutos) > 1024 * 1024:
            return "ERRO_TAMANHO", None, None
        bytes_finais = bytes_brutos

    b64_str = base64.b64encode(bytes_finais).decode("utf-8")
    return nome, mime, b64_str

def buscar_anexo_no_banco(id_ocorr):
    if engine:
        try:
            df_a = pd.read_sql(text("SELECT nome_arquivo, tipo_mime, dados_base64 FROM ocorrencias_anexos WHERE id_ocorrencia = :id"), engine, params={"id": int(id_ocorr)})
            if not df_a.empty:
                return df_a.iloc[0]["nome_arquivo"], df_a.iloc[0]["tipo_mime"], df_a.iloc[0]["dados_base64"]
        except Exception:
            pass
    return None, None, None

def calcular_fechamento_rv(df_ocorr_periodo, df_colaboradores, df_regras_motivos):
    regras_dict = {}
    for _, r in df_regras_motivos.iterrows():
        regras_dict[r["Motivo"]] = {
            "impacta": r["Impacta_RV"],
            "p1": int(r["Perda_1_Ocorr_%"]),
            "p2": int(r["Perda_2_Mais_%"])
        }

    if not df_ocorr_periodo.empty:
        df_rv_validas = df_ocorr_periodo[df_ocorr_periodo["Status"] == "Validado (Impacta RV)"].copy()
        df_pendentes = df_ocorr_periodo[
            (df_ocorr_periodo["Status"] == "Pendente de Validação") &
            (df_ocorr_periodo["Impacta_RV"] == "Sim")
        ]
        df_abonadas = df_ocorr_periodo[df_ocorr_periodo["Status"] == "Justificado / Abonado"]
    else:
        df_rv_validas = pd.DataFrame()
        df_pendentes = pd.DataFrame()
        df_abonadas = pd.DataFrame()

    colunas_oficiais_rv = [
        "FALTA COLABORADOR", "ADVERTENCIA", "SINISTRO", "ACERTO CORRETO",
        "CHECKLIST DIÁRIO", "ROTEIRIZADOR (BAIXAS, CANHOTOS, CHECK IN E CHECK OUT)",
        "REGISTRO JORNADA E SOLIDES", "CHECK LIST HIGIENIZAÇÃO",
        "DEVOLUÇÃO DOS PALETES", "DEVOLUÇÃO", "PENDÊNCIA", "MULTA DE TRANSITO"
    ]

    resultado = []
    lista_efetivo = df_colaboradores.to_dict("records") if not df_colaboradores.empty else []

    for colab_info in lista_efetivo:
        nome = colab_info["Colaborador"]
        funcao = colab_info["Funcao"]

        ocorr_colab = df_rv_validas[df_rv_validas["Colaborador"] == nome] if not df_rv_validas.empty else pd.DataFrame()
        pend_colab = len(df_pendentes[df_pendentes["Colaborador"] == nome]) if not df_pendentes.empty else 0
        abon_colab = len(df_abonadas[df_abonadas["Colaborador"] == nome]) if not df_abonadas.empty else 0

        contagem_incidencias = {col: 0 for col in colunas_oficiais_rv}
        contagem_incidencias["DIVERSOS"] = 0

        perda_pct_total = 0
        detalhes_motivos = []

        if not ocorr_colab.empty:
            contagem_por_motivo = ocorr_colab["Motivo"].value_counts().to_dict()
            for mot, qtd in contagem_por_motivo.items():
                regra = regras_dict.get(mot, {"impacta": "Sim", "p1": 20, "p2": 100})
                if qtd == 1:
                    perda_mot = regra["p1"]
                else:
                    perda_mot = regra["p2"]
                perda_pct_total += perda_mot
                detalhes_motivos.append(f"{mot} ({qtd}x -> -{perda_mot}%)")

                mot_upper = mot.upper()
                encontrou = False
                for col_oficial in colunas_oficiais_rv:
                    if col_oficial in mot_upper or mot_upper in col_oficial:
                        contagem_incidencias[col_oficial] += qtd
                        encontrou = True
                        break
                if not encontrou:
                    contagem_incidencias["DIVERSOS"] += qtd

        perda_pct_final = min(100, perda_pct_total)
        valor_desconto = round(VALOR_BASE_RV * (perda_pct_final / 100.0), 2)
        valor_receber = round(VALOR_BASE_RV - valor_desconto, 2)

        if perda_pct_final == 0:
            status_rv = "🟢 100% Elegível (R$ 250)"
        elif perda_pct_final < 100:
            status_rv = f"🟡 Parcial (-{perda_pct_final}%)"
        else:
            status_rv = "🔴 Perda Total (R$ 0)"

        linha_dict = {
            "COLABORADOR": nome,
            "FUNÇÃO": funcao,
        }
        for col_oficial in colunas_oficiais_rv:
            linha_dict[col_oficial] = contagem_incidencias[col_oficial]
        linha_dict["DIVERSOS"] = contagem_incidencias["DIVERSOS"]

        linha_dict.update({
            "DETALHAMENTO DE INCIDENCIAS RV": " | ".join(detalhes_motivos) if detalhes_motivos else "Nenhuma incidência validada",
            "PENDENTES ANÁLISE": pend_colab,
            "% PERDA RV": perda_pct_final,
            "DESCONTO R$": valor_desconto,
            "VALOR A PAGAR R$": valor_receber,
            "STATUS ELEGIBILIDADE": status_rv
        })
        resultado.append(linha_dict)

    return pd.DataFrame(resultado)

# ================= INICIALIZAÇÃO DOS DADOS NA MEMÓRIA =================
df_colab = carregar_colaboradores()
df_motivos = carregar_df_motivos()
lista_motivos = df_motivos["Motivo"].tolist()
mapa_prioridade_motivo = dict(zip(df_motivos["Motivo"], df_motivos["Prioridade"]))
mapa_rv_motivo = dict(zip(df_motivos["Motivo"], df_motivos["Impacta_RV"]))

df = carregar_dados()

if not df.empty:
    df["Data_DT"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    mask_na = df["Data_DT"].isna()
    if mask_na.any():
        df.loc[mask_na, "Data_DT"] = pd.to_datetime(df.loc[mask_na, "Data"], errors="coerce")
else:
    df["Data_DT"] = pd.Series(dtype="datetime64[ns]")

# ================= BARRA LATERAL (NAVEGAÇÃO E SESSÃO DO USUÁRIO) =================
st.sidebar.markdown("## 🚛 Central FN Distribuidora")
st.sidebar.markdown(f"👤 **Logado como:** `{usuario_logado}`")

# Botão de Logout seguro
if st.sidebar.button("🚪 Sair do Sistema (Logout)", use_container_width=True):
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = None
    st.rerun()

st.sidebar.markdown("---")
pagina = st.sidebar.radio(
    "Navegação do Sistema:",
    [
        "📊 Dashboard & Cadências",
        "🚨 Registrar Ocorrência (Torre / Manutenção)",
        "⚖️ Mesa do Gestor & Backlog",
        "💰 Laudo Remuneração Variável",
        "📁 Dossiê 360º do Colaborador",
        "👥 Equipe & Parâmetros"
    ]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Filtros Globais")
funcao_filtro = st.sidebar.multiselect(
    "Filtrar Função:",
    options=["Motorista", "Ajudante"],
    default=["Motorista", "Ajudante"]
)

hoje = date.today()
inicio_mes = date(hoje.year, hoje.month, 1)
usar_filtro_data = st.sidebar.checkbox("Filtrar por Período", value=False)
if usar_filtro_data:
    col_d1, col_d2 = st.sidebar.columns(2)
    dt_ini = col_d1.date_input("Início:", value=inicio_mes)
    dt_fim = col_d2.date_input("Fim:", value=hoje)
else:
    dt_ini, dt_fim = None, None

df_filtrado = df[df["Funcao"].isin(funcao_filtro)].copy() if not df.empty else df.copy()
if usar_filtro_data and not df_filtrado.empty and df_filtrado["Data_DT"].notna().any():
    df_filtrado = df_filtrado[
        (df_filtrado["Data_DT"].dt.date >= dt_ini) &
        (df_filtrado["Data_DT"].dt.date <= dt_fim)
    ]

CORES_PRIORIDADE = {
    "Alta": "#EF4444",
    "Média": "#F59E0B",
    "Baixa": "#3B82F6",
    "Positivo": "#10B981"
}

# ==============================================================================
# PÁGINA 1: DASHBOARD EXECUTIVO, % DE PRIORIDADES & GRÁFICOS DE CADÊNCIA
# ==============================================================================
if pagina == "📊 Dashboard & Cadências":
    st.markdown("## 📊 Painel Executivo: Prioridades, Tratativas & Cadências")

    if not df_filtrado.empty:
        df_validadas = df_filtrado[df_filtrado["Status"].isin([
            "Validado (Impacta RV)",
            "Validado (Operacional Sem Impacto RV)",
            "Concluído", "Tratado"
        ])].copy()
        qtd_pendentes = len(df_filtrado[df_filtrado["Status"] == "Pendente de Validação"])
        qtd_abonadas = len(df_filtrado[df_filtrado["Status"] == "Justificado / Abonado"])
    else:
        df_validadas = pd.DataFrame()
        qtd_pendentes = 0
        qtd_abonadas = 0

    df_prio_neg = df_validadas[df_validadas["Prioridade"].isin(["Alta", "Média", "Baixa"])] if not df_validadas.empty else pd.DataFrame()
    total_prio = len(df_prio_neg)

    qtd_alta = len(df_prio_neg[df_prio_neg["Prioridade"] == "Alta"]) if total_prio > 0 else 0
    qtd_media = len(df_prio_neg[df_prio_neg["Prioridade"] == "Média"]) if total_prio > 0 else 0
    qtd_baixa = len(df_prio_neg[df_prio_neg["Prioridade"] == "Baixa"]) if total_prio > 0 else 0

    pct_alta = (qtd_alta / total_prio * 100) if total_prio > 0 else 0.0
    pct_media = (qtd_media / total_prio * 100) if total_prio > 0 else 0.0
    pct_baixa = (qtd_baixa / total_prio * 100) if total_prio > 0 else 0.0

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-title">Total Apontamentos</div>
            <div class="kpi-value">{len(df_filtrado)}</div>
            <div class="kpi-sub">⏳ {qtd_pendentes} Pendentes | 🛡️ {qtd_abonadas} Abonadas</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card" style="border-top: 4px solid #EF4444;">
            <div class="kpi-title">🔴 % Prioridade Alta</div>
            <div class="kpi-value" style="color:#EF4444;">{pct_alta:.1f}%</div>
            <div class="kpi-sub">{qtd_alta} ocorrências validadas</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card" style="border-top: 4px solid #F59E0B;">
            <div class="kpi-title">🟡 % Prioridade Média</div>
            <div class="kpi-value" style="color:#F59E0B;">{pct_media:.1f}%</div>
            <div class="kpi-sub">{qtd_media} ocorrências validadas</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card" style="border-top: 4px solid #3B82F6;">
            <div class="kpi-title">🔵 % Prioridade Baixa</div>
            <div class="kpi-value" style="color:#3B82F6;">{pct_baixa:.1f}%</div>
            <div class="kpi-sub">{qtd_baixa} ocorrências validadas</div>
        </div>""", unsafe_allow_html=True)
    with k5:
        qtd_rv_conf = len(df_filtrado[df_filtrado["Status"] == "Validado (Impacta RV)"]) if not df_filtrado.empty else 0
        qtd_op_conf = len(df_filtrado[df_filtrado["Status"] == "Validado (Operacional Sem Impacto RV)"]) if not df_filtrado.empty else 0
        st.markdown(f"""<div class="kpi-card" style="border-top: 4px solid #10B981;">
            <div class="kpi-title">⚖️ Ações Tratadas Gestor</div>
            <div class="kpi-value">{qtd_rv_conf + qtd_op_conf + qtd_abonadas}</div>
            <div class="kpi-sub">💰 {qtd_rv_conf} Afetam RV | 📋 {qtd_op_conf} Sem RV</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="titulo-secao">📈 1. Análise de Cadência (Evolução de Prioridades e Tratativas no Tempo)</div>', unsafe_allow_html=True)
    if not df_filtrado.empty and df_filtrado["Data_DT"].notna().any():
        col_cad_op, _ = st.columns([2, 3])
        agrupamento_tempo = col_cad_op.radio(
            "Visão de Cadência:",
            ["Diária", "Semanal", "Mensal"],
            horizontal=True
        )

        df_cad = df_filtrado.dropna(subset=["Data_DT"]).copy()
        if agrupamento_tempo == "Diária":
            df_cad["Periodo"] = df_cad["Data_DT"].dt.strftime("%d/%m/%Y")
            df_cad["Ordem"] = df_cad["Data_DT"].dt.date
        elif agrupamento_tempo == "Semanal":
            df_cad["Ordem"] = df_cad["Data_DT"].dt.to_period("W").apply(lambda r: r.start_time.date())
            df_cad["Periodo"] = df_cad["Ordem"].apply(lambda d: f"Sem. {d.strftime('%d/%m')}")
        else:
            df_cad["Ordem"] = df_cad["Data_DT"].dt.to_period("M").apply(lambda r: r.start_time.date())
            df_cad["Periodo"] = df_cad["Data_DT"].dt.strftime("%m/%Y")

        g_cad1, g_cad2 = st.columns(2)

        with g_cad1:
            df_cad_prio = df_cad.groupby(["Ordem", "Periodo", "Prioridade"]).size().reset_index(name="Quantidade").sort_values("Ordem")
            fig_cad_prio = px.bar(
                df_cad_prio,
                x="Periodo",
                y="Quantidade",
                color="Prioridade",
                color_discrete_map=CORES_PRIORIDADE,
                title=f"Cadência {agrupamento_tempo} por Nível de Prioridade",
                text_auto=True,
                barmode="stack"
            )
            fig_cad_prio.update_layout(template="plotly_dark", height=360, xaxis_title="Período", yaxis_title="Qtd Ocorrências")
            st.plotly_chart(fig_cad_prio, use_container_width=True)

        with g_cad2:
            df_cad_status = df_cad.groupby(["Ordem", "Periodo", "Status"]).size().reset_index(name="Quantidade").sort_values("Ordem")
            cores_status = {
                "Validado (Impacta RV)": "#EF4444",
                "Validado (Operacional Sem Impacto RV)": "#3B82F6",
                "Justificado / Abonado": "#10B981",
                "Pendente de Validação": "#94A3B8"
            }
            fig_cad_stat = px.line(
                df_cad_status,
                x="Periodo",
                y="Quantidade",
                color="Status",
                color_discrete_map=cores_status,
                markers=True,
                title=f"Cadência {agrupamento_tempo} de Tratativas (Com RV vs Sem RV vs Abonadas)"
            )
            fig_cad_stat.update_traces(line=dict(width=3), marker=dict(size=8))
            fig_cad_stat.update_layout(template="plotly_dark", height=360, xaxis_title="Período", yaxis_title="Qtd Registros")
            st.plotly_chart(fig_cad_stat, use_container_width=True)
    else:
        st.info("Ainda não há dados no período selecionado para gerar os gráficos de cadência.")

    st.markdown('<div class="titulo-secao">🎯 2. % dos Motoristas Frente às Prioridades (Alta, Média e Baixa)</div>', unsafe_allow_html=True)
    if not df_prio_neg.empty:
        modo_visao_mot = st.radio(
            "Como deseja visualizar o gráfico de motoristas?",
            ["📊 Proporção em % (100% Empilhado)", "🔢 Quantidade Absoluta de Ocorrências"],
            horizontal=True
        )

        tab_mot = df_prio_neg.groupby(["Colaborador", "Prioridade"]).size().unstack(fill_value=0)
        for col_p in ["Alta", "Média", "Baixa"]:
            if col_p not in tab_mot.columns:
                tab_mot[col_p] = 0
        tab_mot["Total"] = tab_mot["Alta"] + tab_mot["Média"] + tab_mot["Baixa"]
        tab_mot["% Alta"] = (tab_mot["Alta"] / tab_mot["Total"] * 100).round(1)
        tab_mot["% Média"] = (tab_mot["Média"] / tab_mot["Total"] * 100).round(1)
        tab_mot["% Baixa"] = (tab_mot["Baixa"] / tab_mot["Total"] * 100).round(1)
        tab_mot = tab_mot.sort_values(by=["% Alta", "Total"], ascending=[True, True]).reset_index()

        c_m1, c_m2 = st.columns([3, 2])
        with c_m1:
            if "Proporção em %" in modo_visao_mot:
                df_melt = tab_mot.melt(id_vars=["Colaborador", "Total"], value_vars=["% Alta", "% Média", "% Baixa"], var_name="Nível", value_name="Percentual")
                df_melt["Prioridade"] = df_melt["Nível"].str.replace("% ", "")
                fig_mot = px.bar(
                    df_melt,
                    y="Colaborador",
                    x="Percentual",
                    color="Prioridade",
                    orientation="h",
                    color_discrete_map=CORES_PRIORIDADE,
                    title="Distribuição % de Prioridades por Colaborador (Ocorrências Validadas)",
                    text=df_melt["Percentual"].apply(lambda x: f"{x:.0f}%" if x > 5 else "")
                )
                fig_mot.update_layout(template="plotly_dark", height=max(380, len(tab_mot) * 32), xaxis_title="% de Incidência", yaxis_title="")
            else:
                df_melt = tab_mot.melt(id_vars=["Colaborador", "Total"], value_vars=["Alta", "Média", "Baixa"], var_name="Prioridade", value_name="Qtd")
                fig_mot = px.bar(
                    df_melt,
                    y="Colaborador",
                    x="Qtd",
                    color="Prioridade",
                    orientation="h",
                    color_discrete_map=CORES_PRIORIDADE,
                    title="Volume de Ocorrências por Prioridade e Colaborador",
                    text_auto=True
                )
                fig_mot.update_layout(template="plotly_dark", height=max(380, len(tab_mot) * 32), xaxis_title="Quantidade", yaxis_title="")
            st.plotly_chart(fig_mot, use_container_width=True)

        with c_m2:
            st.markdown("##### 📋 Tabela Resumo (% e Volume por Colaborador)")
            df_exib_mot = tab_mot.sort_values(by=["Alta", "Total"], ascending=False)[
                ["Colaborador", "Total", "% Alta", "% Média", "% Baixa", "Alta", "Média", "Baixa"]
            ]
            st.dataframe(df_exib_mot, use_container_width=True, hide_index=True, height=360)
    else:
        st.info("Nenhuma ocorrência validada (Alta, Média ou Baixa) para exibir a matriz percentual por colaborador.")

    st.markdown('<div class="titulo-secao">🔍 3. Incidências por Motivo (Afeta RV vs Operacional Sem RV)</div>', unsafe_allow_html=True)
    if not df_filtrado.empty:
        g_inf1, g_inf2 = st.columns([3, 2])
        with g_inf1:
            df_mot_rank = df_filtrado.groupby(["Motivo", "Impacta_RV"]).size().reset_index(name="Qtd").sort_values("Qtd", ascending=True)
            fig_mot_rank = px.bar(
                df_mot_rank,
                y="Motivo",
                x="Qtd",
                color="Impacta_RV",
                orientation="h",
                color_discrete_map={"Sim": "#EF4444", "Não": "#3B82F6"},
                title="Ranking de Motivos Registrados (Vermelho = Afeta Variável | Azul = Não Afeta)",
                text_auto=True
            )
            fig_mot_rank.update_layout(template="plotly_dark", height=400)
            st.plotly_chart(fig_mot_rank, use_container_width=True)

        with g_inf2:
            df_gov = df_filtrado["Status"].value_counts().reset_index()
            df_gov.columns = ["Status", "Quantidade"]
            fig_gov = px.pie(
                df_gov,
                names="Status",
                values="Quantidade",
                hole=0.45,
                title="Funil de Governança (Status das Ocorrências)",
                color="Status",
                color_discrete_map={
                    "Validado (Impacta RV)": "#EF4444",
                    "Validado (Operacional Sem Impacto RV)": "#3B82F6",
                    "Justificado / Abonado": "#10B981",
                    "Pendente de Validação": "#94A3B8"
                }
            )
            fig_gov.update_layout(template="plotly_dark", height=400)
            st.plotly_chart(fig_gov, use_container_width=True)


# ==============================================================================
# PÁGINA 2: REGISTRAR OCORRÊNCIA (TORRE / MANUTENÇÃO TRAVADA)
# ==============================================================================
elif pagina == "🚨 Registrar Ocorrência (Torre / Manutenção)":
    is_manutencao = "Manutenção" in usuario_logado

    if is_manutencao:
        st.markdown(f"## 🔧 Novo Apontamento - Manutenção ({usuario_logado})")
        st.info("🔒 **Modo Manutenção Ativo:** Seu perfil está restrito exclusivamente a registros de ocorrências do tipo **CHECKLIST**. O apontamento será enviado diretamente para a validação do gestor.")
    else:
        st.markdown(f"## 🚨 Novo Apontamento Operacional (Torre / {usuario_logado})")
        st.caption("Registre o apontamento abaixo. Ele entrará como **'Pendente de Validação'** para análise do gestor.")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        lista_nomes = sorted(df_colab["Colaborador"].unique().tolist()) if not df_colab.empty else ["Carlos Eduardo"]
        colab_sel = st.selectbox("Colaborador:", lista_nomes)
        func_auto = "Motorista"
        if not df_colab.empty and colab_sel in df_colab["Colaborador"].values:
            func_auto = df_colab[df_colab["Colaborador"] == colab_sel]["Funcao"].iloc[0]
        st.text_input("Função:", value=func_auto, disabled=True)

    with col_f2:
        data_ocorr = st.date_input("Data do Ocorrido:", value=date.today())
        rota_ocorr = st.text_input("Rota / Placa / Veículo:", placeholder="Ex: Placa ABC-1234 / Rota Varginha")

    with col_f3:
        if is_manutencao:
            # Trava estritamente para checklists
            lista_motivos_disponiveis = [m for m in lista_motivos if "CHECKLIST" in m.upper() or "CHECK LIST" in m.upper()]
            if not lista_motivos_disponiveis:
                lista_motivos_disponiveis = ["CHECKLIST DIÁRIO", "CHECK LIST HIGIENIZAÇÃO"]
            motivo_sel = st.selectbox("Motivo / Incidência (Restrito Manutenção):", lista_motivos_disponiveis)
        else:
            motivo_sel = st.selectbox("Motivo / Incidência:", lista_motivos)

        prio_sugerida = mapa_prioridade_motivo.get(motivo_sel, "Média")
        rv_sugerido = mapa_rv_motivo.get(motivo_sel, "Não")

        opcoes_prio = ["Alta", "Média", "Baixa", "Positivo"]
        idx_prio = opcoes_prio.index(prio_sugerida) if prio_sugerida in opcoes_prio else 1
        prio_sel = st.selectbox("Prioridade do Acontecimento:", opcoes_prio, index=idx_prio)

    st.info(f"📌 **Classificação Automática do Motivo:** Prioridade **{prio_sel}** | Afeta Remuneração Variável? **{rv_sugerido}**")

    detalhe_ocorr = st.text_area("Descrição Detalhada do Fato / Falha constatada:", height=100, placeholder="Descreva o problema encontrado no checklist...")
    
    # Registrado por automático atrelado ao login seguro da sessão
    reg_por = st.text_input("Registrado por (Login Autenticado):", value=usuario_logado, disabled=True)

    if st.button("✅ Registrar Apontamento no Sistema", use_container_width=True, type="primary"):
        if engine:
            try:
                novo_id = 1
                if not df.empty and "ID" in df.columns:
                    novo_id = int(df["ID"].max()) + 1

                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO ocorrencias (
                            id, data, colaborador, funcao, rota, tipo, motivo, detalhe,
                            pontos, status, acao_gestor, data_tratativa, registrado_por,
                            prioridade, impacta_rv, tem_anexo
                        ) VALUES (
                            :id, :data, :colab, :func, :rota, :tipo, :mot, :det,
                            0, :status, '', '', :reg,
                            :prio, :rv, 'Não'
                        )
                    """), {
                        "id": novo_id,
                        "data": data_ocorr.strftime("%d/%m/%Y"),
                        "colab": colab_sel,
                        "func": func_auto,
                        "rota": rota_ocorr.strip() if rota_ocorr.strip() else "Não informada",
                        "tipo": prio_sel,
                        "mot": motivo_sel,
                        "det": detalhe_ocorr.strip(),
                        "status": "Pendente de Validação",
                        "reg": usuario_logado.strip(),
                        "prio": prio_sel,
                        "rv": rv_sugerido
                    })
                st.cache_data.clear()
                st.success(f"✅ Ocorrência #{novo_id} registrada por **{usuario_logado}** com sucesso! Enviada para a Mesa do Gestor.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar ocorrência: {e}")


# ==============================================================================
# PÁGINA 3: MESA DO GESTOR (VALIDAÇÃO, ANEXOS LEVES E BACKLOG DE TRATATIVAS)
# ==============================================================================
elif pagina == "⚖️ Mesa do Gestor & Backlog":
    st.markdown("## ⚖️ Mesa de Validação do Gestor & Histórico de Ações Tratadas")

    aba_pendentes, aba_backlog = st.tabs([
        "⏳ 1. Fila Pendente de Validação (Aprovar / Abonar / Tratar)",
        "🗂️ 2. Backlog Completo de Ocorrências Solucionadas e Justificadas"
    ])

    with aba_pendentes:
        df_pend = df[df["Status"] == "Pendente de Validação"].copy() if not df.empty else pd.DataFrame()
        st.markdown(f'<div class="titulo-secao">⏳ Ocorrências Aguardando Decisão do Gestor ({len(df_pend)})</div>', unsafe_allow_html=True)

        if df_pend.empty:
            st.success("🎉 Tudo em dia! Não há nenhuma ocorrência pendente de validação no momento.")
        else:
            st.dataframe(
                df_pend[["ID", "Data", "Colaborador", "Funcao", "Rota", "Motivo", "Prioridade", "Impacta_RV", "Registrado_Por", "Detalhe"]],
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")
            st.markdown("### ✍️ Validar e Registrar Tratativa do Gestor")
            c_g1, c_g2 = st.columns([1, 2])

            with c_g1:
                opcoes_id = df_pend.apply(
                    lambda r: f"#{r['ID']} - {r['Colaborador']} ({r['Motivo']} por {r['Registrado_Por']})", axis=1
                ).tolist()
                sel_item = st.selectbox("Selecione a Ocorrência para Tratar:", opcoes_id)
                id_escolhido = int(sel_item.split("#")[1].split(" -")[0])
                linha_atual = df_pend[df_pend["ID"] == id_escolhido].iloc[0]

                st.write(f"**Colaborador:** {linha_atual['Colaborador']}")
                st.write(f"**Registrado por:** {linha_atual['Registrado_Por']}")
                st.write(f"**Motivo:** {linha_atual['Motivo']}")
                st.write(f"**Prioridade Atual:** {linha_atual['Prioridade']} | **Afeta RV?** {linha_atual['Impacta_RV']}")
                st.caption(f"**Relato:** {linha_atual['Detalhe']}")

            with c_g2:
                if linha_atual["Impacta_RV"] == "Sim":
                    opcoes_decisao = [
                        "🔴 Aprovar Impacto -> Vai para o Laudo de Variável (Desconta RV)",
                        "🟢 Reprovar Impacto / Abonar -> Falta ou Evento Justificado (Vai para o Backlog sem descontar RV)",
                        "🔵 Converter em Tratativa Operacional -> Mantém no Dossiê mas isenta desconto na RV"
                    ]
                else:
                    opcoes_decisao = [
                        "🔵 Validar Tratativa Operacional (Sem Impacto na RV -> Entra no Dossiê e Cadência)",
                        "🟢 Abonar / Arquivar com Justificativa (Vai para o Backlog de Justificadas)",
                        "🔴 Forçar Impacto na Variável -> Entra em DIVERSOS no Laudo de Variável"
                    ]

                decisao_gestor = st.radio("Decisão do Gestor:", opcoes_decisao)
                nova_prio = st.selectbox(
                    "Confirmar ou Ajustar Prioridade:",
                    ["Alta", "Média", "Baixa", "Positivo"],
                    index=["Alta", "Média", "Baixa", "Positivo"].index(linha_atual["Prioridade"]) if linha_atual["Prioridade"] in ["Alta", "Média", "Baixa", "Positivo"] else 1
                )
                parecer_gestor = st.text_area(
                    "Registro Histórico / Parecer do Gestor (Obrigatório):",
                    placeholder="Ex: Apresentou atestado médico válido / Orientado em reunião / Confirmada devolução..."
                )
                arquivo_anexo = st.file_uploader(
                    "📎 Anexar Comprovante / Atestado / Evidência (Imagem ou PDF leve - Opcional):",
                    type=["jpg", "jpeg", "png", "webp", "pdf"]
                )

                if st.button("💾 Confirmar Validação do Gestor", type="primary", use_container_width=True):
                    if not parecer_gestor.strip():
                        st.warning("⚠️ Por favor, escreva o parecer/justificativa do gestor para manter o histórico completo.")
                    elif engine:
                        if "🔴" in decisao_gestor:
                            novo_status = "Validado (Impacta RV)"
                            novo_rv = "Sim"
                        elif "🟢" in decisao_gestor:
                            novo_status = "Justificado / Abonado"
                            novo_rv = "Não"
                        else:
                            novo_status = "Validado (Operacional Sem Impacto RV)"
                            if "Forçar Impacto" in decisao_gestor:
                                novo_status = "Validado (Impacta RV)"
                                novo_rv = "Sim"

                        tem_anexo_flag = "Não"
                        nome_arq, mime_arq, b64_arq = None, None, None
                        if arquivo_anexo is not None:
                            nome_arq, mime_arq, b64_arq = comprimir_e_codificar_arquivo(arquivo_anexo)
                            if nome_arq == "ERRO_TAMANHO":
                                st.error("O PDF excede 1 MB. Envie uma foto/print ou um PDF menor.")
                                st.stop()
                            tem_anexo_flag = "Sim"

                        try:
                            with engine.begin() as conn:
                                conn.execute(text("""
                                    UPDATE ocorrencias
                                    SET status = :st,
                                        acao_gestor = :acao,
                                        data_tratativa = :dt,
                                        prioridade = :prio,
                                        tipo = :prio,
                                        impacta_rv = :rv,
                                        tem_anexo = :anexo
                                    WHERE id = :id
                                """), {
                                    "st": novo_status,
                                    "acao": parecer_gestor.strip(),
                                    "dt": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                    "prio": nova_prio,
                                    "rv": novo_rv,
                                    "anexo": tem_anexo_flag,
                                    "id": id_escolhido
                                })

                                if tem_anexo_flag == "Sim" and b64_arq:
                                    conn.execute(text("""
                                        INSERT INTO ocorrencias_anexos (id_ocorrencia, nome_arquivo, tipo_mime, dados_base64)
                                        VALUES (:id, :nome, :mime, :b64)
                                        ON CONFLICT (id_ocorrencia) DO UPDATE
                                        SET nome_arquivo = :nome, tipo_mime = :mime, dados_base64 = :b64
                                    """), {
                                        "id": id_escolhido,
                                        "nome": nome_arq,
                                        "mime": mime_arq,
                                        "b64": b64_arq
                                    })
                            st.cache_data.clear()
                            st.success(f"✅ Ocorrência #{id_escolhido} validada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao validar ocorrência: {e}")

    with aba_backlog:
        st.markdown('<div class="titulo-secao">🗂️ Backlog de Todas as Ações Tratadas</div>', unsafe_allow_html=True)
        df_tratadas = df[df["Status"] != "Pendente de Validação"].copy() if not df.empty else pd.DataFrame()

        if df_tratadas.empty:
            st.info("Nenhuma ocorrência tratada até o momento.")
        else:
            f_status = st.multiselect(
                "Filtrar por Tipo de Decisão do Gestor:",
                options=df_tratadas["Status"].unique().tolist(),
                default=df_tratadas["Status"].unique().tolist()
            )
            df_b_view = df_tratadas[df_tratadas["Status"].isin(f_status)]

            st.dataframe(
                df_b_view[[
                    "ID", "Data", "Colaborador", "Motivo", "Prioridade",
                    "Status", "Impacta_RV", "Registrado_Por", "Acao_Gestor", "Data_Tratativa", "Tem_Anexo"
                ]],
                use_container_width=True,
                hide_index=True
            )

            col_anx, col_adm = st.columns(2)
            with col_anx:
                st.markdown("#### 📎 Visualizar / Baixar Anexo de Evidência")
                df_com_anexo = df_b_view[df_b_view["Tem_Anexo"] == "Sim"]
                if not df_com_anexo.empty:
                    id_anexo_sel = st.selectbox(
                        "Escolha a ocorrência com anexo:",
                        df_com_anexo.apply(lambda r: f"#{r['ID']} - {r['Colaborador']} ({r['Motivo']})", axis=1).tolist()
                    )
                    if st.button("🔍 Carregar Anexo do Banco"):
                        id_busca = int(id_anexo_sel.split("#")[1].split(" -")[0])
                        nome_a, mime_a, b64_a = buscar_anexo_no_banco(id_busca)
                        if b64_a:
                            bytes_arq = base64.b64decode(b64_a)
                            st.download_button(
                                label=f"⬇️ Baixar {nome_a}",
                                data=bytes_arq,
                                file_name=nome_a,
                                mime=mime_a
                            )
                            if mime_a.startswith("image/"):
                                st.image(bytes_arq, caption=f"Anexo da Ocorrência #{id_busca}", use_container_width=True)
                        else:
                            st.warning("Anexo não encontrado.")
                else:
                    st.caption("Nenhum registro filtrado possui anexo vinculado.")

            with col_adm:
                st.markdown("#### 🔄 Reabrir ou Excluir Registro")
                id_gerenciar = st.selectbox(
                    "Selecione o ID:",
                    df_b_view.apply(lambda r: f"#{r['ID']} - {r['Colaborador']} ({r['Motivo']})", axis=1).tolist(),
                    key="sel_reabrir_id"
                )
                id_alvo = int(id_gerenciar.split("#")[1].split(" -")[0])
                b_reab, b_excl = st.columns(2)
                if b_reab.button("↩️ Devolver para Pendente", use_container_width=True):
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE ocorrencias SET status = 'Pendente de Validação' WHERE id = :id"), {"id": id_alvo})
                    st.cache_data.clear()
                    st.rerun()
                if b_excl.button("🗑️ Excluir Registro", use_container_width=True):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM ocorrencias WHERE id = :id"), {"id": id_alvo})
                        conn.execute(text("DELETE FROM ocorrencias_anexos WHERE id_ocorrencia = :id"), {"id": id_alvo})
                    st.cache_data.clear()
                    st.rerun()


# ==============================================================================
# PÁGINA 4: LAUDO OFICIAL DE REMUNERAÇÃO VARIÁVEL
# ==============================================================================
elif pagina == "💰 Laudo Remuneração Variável":
    st.markdown("## 💰 Laudo de Fechamento da Remuneração Variável (Base: R$ 250,00)")
    st.caption("Regra Oficial: **20% de perda = -R$ 50,00** | **100% de perda = -R$ 250,00**. Apenas ocorrências validadas pelo gestor com impacto na RV compõem o laudo.")

    df_colab_filtrado = df_colab[df_colab["Funcao"].isin(funcao_filtro)] if not df_colab.empty else df_colab
    df_laudo = calcular_fechamento_rv(df_filtrado, df_colab_filtrado, df_motivos)

    pend_rv = df_filtrado[(df_filtrado["Status"] == "Pendente de Validação") & (df_filtrado["Impacta_RV"] == "Sim")] if not df_filtrado.empty else pd.DataFrame()
    if not pend_rv.empty:
        st.warning(f"⚠️ **Atenção antes de fechar a folha:** Existem **{len(pend_rv)} ocorrências que afetam a variável** aguardando aprovação na aba **'⚖️ Mesa do Gestor'**.")

    if not df_laudo.empty:
        total_descontos = df_laudo["DESCONTO R$"].sum()
        total_pagar = df_laudo["VALOR A PAGAR R$"].sum()

        qtd_100 = len(df_laudo[df_laudo["% PERDA RV"] == 0])
        qtd_parcial = len(df_laudo[(df_laudo["% PERDA RV"] > 0) & (df_laudo["% PERDA RV"] < 100)])
        qtd_zerado = len(df_laudo[df_laudo["% PERDA RV"] == 100])

        k_rv1, k_rv2, k_rv3, k_rv4 = st.columns(4)
        with k_rv1:
            st.markdown(f"""<div class="kpi-card" style="border-top: 4px solid #10B981;">
                <div class="kpi-title">🟢 100% Elegíveis (R$ 250)</div>
                <div class="kpi-value" style="color:#10B981;">{qtd_100}</div>
                <div class="kpi-sub">Recebem valor integral</div>
            </div>""", unsafe_allow_html=True)
        with k_rv2:
            st.markdown(f"""<div class="kpi-card" style="border-top: 4px solid #F59E0B;">
                <div class="kpi-title">🟡 Pagamento Parcial</div>
                <div class="kpi-value" style="color:#F59E0B;">{qtd_parcial}</div>
                <div class="kpi-sub">Perda de 20% a 80%</div>
            </div>""", unsafe_allow_html=True)
        with k_rv3:
            st.markdown(f"""<div class="kpi-card" style="border-top: 4px solid #EF4444;">
                <div class="kpi-title">🔴 Perda Total (R$ 0)</div>
                <div class="kpi-value" style="color:#EF4444;">{qtd_zerado}</div>
                <div class="kpi-sub">Perderam 100% da variável</div>
            </div>""", unsafe_allow_html=True)
        with k_rv4:
            st.markdown(f"""<div class="kpi-card" style="border-top: 4px solid #3B82F6;">
                <div class="kpi-title">💵 Total Líquido a Pagar</div>
                <div class="kpi-value">R$ {total_pagar:,.2f}</div>
                <div class="kpi-sub">Retenção Total: R$ {total_descontos:,.2f}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<div class="titulo-secao">📋 Matriz Oficial de Fechamento da Remuneração Variável</div>', unsafe_allow_html=True)
        st.dataframe(df_laudo, use_container_width=True, hide_index=True)

        csv_laudo = df_laudo.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="📥 Baixar Laudo de Remuneração Variável (Excel / CSV)",
            data=csv_laudo,
            file_name=f"laudo_remuneracao_variavel_{date.today().strftime('%Y_%m_%d')}.csv",
            mime="text/csv"
        )


# ==============================================================================
# PÁGINA 5: DOSSIÊ 360º DO COLABORADOR
# ==============================================================================
elif pagina == "📁 Dossiê 360º do Colaborador":
    st.markdown("## 📁 Dossiê 360º do Motorista / Ajudante")

    lista_nomes_d = sorted(df_colab["Colaborador"].unique().tolist()) if not df_colab.empty else ["Carlos Eduardo"]
    colab_dossie = st.selectbox("Selecione o Colaborador para abrir o Dossiê Completo:", lista_nomes_d)

    df_hist = df_filtrado[df_filtrado["Colaborador"] == colab_dossie].copy() if not df_filtrado.empty else pd.DataFrame()
    df_laudo_ind = calcular_fechamento_rv(df_filtrado, df_colab[df_colab["Colaborador"] == colab_dossie], df_motivos)

    valor_a_receber = df_laudo_ind["VALOR A PAGAR R$"].iloc[0] if not df_laudo_ind.empty else VALOR_BASE_RV
    desconto_ind = df_laudo_ind["DESCONTO R$"].iloc[0] if not df_laudo_ind.empty else 0.0

    df_val_ind = df_hist[df_hist["Status"].isin(["Validado (Impacta RV)", "Validado (Operacional Sem Impacto RV)"])] if not df_hist.empty else pd.DataFrame()
    df_prio_ind = df_val_ind[df_val_ind["Prioridade"].isin(["Alta", "Média", "Baixa"])] if not df_val_ind.empty else pd.DataFrame()
    tot_p_ind = len(df_prio_ind)

    p_alta_i = (len(df_prio_ind[df_prio_ind["Prioridade"] == "Alta"]) / tot_p_ind * 100) if tot_p_ind > 0 else 0.0
    p_med_i = (len(df_prio_ind[df_prio_ind["Prioridade"] == "Média"]) / tot_p_ind * 100) if tot_p_ind > 0 else 0.0
    p_bx_i = (len(df_prio_ind[df_prio_ind["Prioridade"] == "Baixa"]) / tot_p_ind * 100) if tot_p_ind > 0 else 0.0

    qtd_rv_i = len(df_hist[df_hist["Status"] == "Validado (Impacta RV)"]) if not df_hist.empty else 0
    qtd_op_i = len(df_hist[df_hist["Status"] == "Validado (Operacional Sem Impacto RV)"]) if not df_hist.empty else 0
    qtd_ab_i = len(df_hist[df_hist["Status"] == "Justificado / Abonado"]) if not df_hist.empty else 0

    d1, d2, d3, d4, d5 = st.columns(5)
    with d1:
        cor_saldo = "#10B981" if desconto_ind == 0 else ("#F59E0B" if valor_a_receber > 0 else "#EF4444")
        st.markdown(f"""<div class="kpi-card" style="border-top: 4px solid {cor_saldo};">
            <div class="kpi-title">💰 Saldo Variável</div>
            <div class="kpi-value" style="color:{cor_saldo};">R$ {valor_a_receber:,.2f}</div>
            <div class="kpi-sub">Desconto: R$ {desconto_ind:,.2f}</div>
        </div>""", unsafe_allow_html=True)
    with d2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-title">🔴 % Alta Prioridade</div>
            <div class="kpi-value" style="color:#EF4444;">{p_alta_i:.1f}%</div>
            <div class="kpi-sub">Do perfil validado</div>
        </div>""", unsafe_allow_html=True)
    with d3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-title">🟡 % Média Prioridade</div>
            <div class="kpi-value" style="color:#F59E0B;">{p_med_i:.1f}%</div>
            <div class="kpi-sub">Do perfil validado</div>
        </div>""", unsafe_allow_html=True)
    with d4:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-title">🔵 % Baixa Prioridade</div>
            <div class="kpi-value" style="color:#3B82F6;">{p_bx_i:.1f}%</div>
            <div class="kpi-sub">Do perfil validado</div>
        </div>""", unsafe_allow_html=True)
    with d5:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-title">⚖️ Resumo Histórico</div>
            <div class="kpi-value">{len(df_hist)}</div>
            <div class="kpi-sub">🚨 {qtd_rv_i} RV | 📋 {qtd_op_i} Sem RV | 🛡️ {qtd_ab_i} Abonos</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="titulo-secao">🚨 1. Ocorrências Validadas que Afetaram a Remuneração Variável</div>', unsafe_allow_html=True)
    df_d_rv = df_hist[df_hist["Status"] == "Validado (Impacta RV)"] if not df_hist.empty else pd.DataFrame()
    if not df_d_rv.empty:
        st.dataframe(df_d_rv[["ID", "Data", "Rota", "Motivo", "Prioridade", "Registrado_Por", "Detalhe", "Acao_Gestor", "Data_Tratativa"]], use_container_width=True, hide_index=True)
    else:
        st.success("Nenhuma ocorrência que afete a Remuneração Variável para este colaborador no período.")

    st.markdown('<div class="titulo-secao">📋 2. Ocorrências Operacionais Tratadas pelo Gestor (Não Afetam a Variável)</div>', unsafe_allow_html=True)
    df_d_op = df_hist[df_hist["Status"] == "Validado (Operacional Sem Impacto RV)"] if not df_hist.empty else pd.DataFrame()
    if not df_d_op.empty:
        st.dataframe(df_d_op[["ID", "Data", "Rota", "Motivo", "Prioridade", "Registrado_Por", "Detalhe", "Acao_Gestor", "Data_Tratativa"]], use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma ocorrência operacional sem impacto na variável registrada no período.")

    st.markdown('<div class="titulo-secao">🛡️ 3. Histórico de Ocorrências Justificadas / Abonadas pelo Gestor</div>', unsafe_allow_html=True)
    df_d_ab = df_hist[df_hist["Status"] == "Justificado / Abonado"] if not df_hist.empty else pd.DataFrame()
    if not df_d_ab.empty:
        st.dataframe(df_d_ab[["ID", "Data", "Rota", "Motivo", "Prioridade", "Registrado_Por", "Detalhe", "Acao_Gestor", "Data_Tratativa", "Tem_Anexo"]], use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhum abono/justificativa registrado para este colaborador no período.")


# ==============================================================================
# PÁGINA 6: EQUIPE & PARÂMETROS
# ==============================================================================
elif pagina == "👥 Equipe & Parâmetros":
    st.markdown("## 👥 Gestão de Equipe e Regras da Remuneração Variável")

    aba_lote, aba_ind, aba_regras, aba_limpar = st.tabs([
        "📋 1. Importar Equipe em Lote",
        "➕ 2. Adicionar/Remover Colaborador",
        "⚙️ 3. Motivos, Prioridades e Regras RV (R$ 250)",
        "🧹 4. Manutenção de Base"
    ])

    with aba_lote:
        st.markdown('<div class="titulo-secao">Importação Rápida de Colaboradores (Nome;Função)</div>', unsafe_allow_html=True)
        texto_lote = st.text_area("Cole sua lista (um por linha no formato Nome;Motorista ou Nome;Ajudante):", height=150)
        if st.button("🔄 Substituir Base de Colaboradores", use_container_width=True):
            if texto_lote.strip() and engine:
                linhas = [l.strip() for l in texto_lote.strip().split("\n") if l.strip()]
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
                            conn.execute(text("INSERT INTO colaboradores (colaborador, funcao) VALUES (:c, :f)"), novos_dados)
                    st.cache_data.clear()
                    st.success(f"✅ {len(novos_dados)} colaboradores salvos no Neon!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
        st.dataframe(df_colab, use_container_width=True, hide_index=True)

    with aba_ind:
        c_add, c_rem = st.columns(2)
        with c_add:
            st.markdown("#### ➕ Adicionar Colaborador")
            novo_nome = st.text_input("Nome Completo:")
            nova_func = st.selectbox("Função:", ["Motorista", "Ajudante"])
            if st.button("Salvar Colaborador", use_container_width=True) and novo_nome.strip() and engine:
                with engine.begin() as conn:
                    conn.execute(
                        text("INSERT INTO colaboradores (colaborador, funcao) VALUES (:c, :f) ON CONFLICT (colaborador) DO UPDATE SET funcao = :f"),
                        {"c": novo_nome.strip().title(), "f": nova_func}
                    )
                st.cache_data.clear()
                st.success("Colaborador salvo!")
                st.rerun()
        with c_rem:
            st.markdown("#### 🗑️ Remover Colaborador")
            lista_atuais = sorted(df_colab["Colaborador"].unique().tolist()) if not df_colab.empty else []
            if lista_atuais:
                rem_nome = st.selectbox("Selecione para remover:", lista_atuais)
                if st.button("Remover da Lista", use_container_width=True) and engine:
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM colaboradores WHERE colaborador = :c"), {"c": rem_nome})
                    st.cache_data.clear()
                    st.warning(f"{rem_nome} removido!")
                    st.rerun()

    with aba_regras:
        st.markdown('<div class="titulo-secao">⚙️ Configurar Motivos, Prioridades e % de Perda na Variável</div>', unsafe_allow_html=True)
        st.caption("💡 Dê **dois cliques** em qualquer célula da tabela abaixo para alterar a **Prioridade**, se **Impacta_RV (Sim/Não)**, ou a **% de perda na 1ª e 2+ ocorrências**.")

        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns([3, 1.5, 1.2, 1.2, 1.2])
        n_mot = col_m1.text_input("Novo Motivo:")
        n_prio = col_m2.selectbox("Prioridade:", ["Alta", "Média", "Baixa", "Positivo"])
        n_rv = col_m3.selectbox("Afeta RV?", ["Sim", "Não"])
        n_p1 = col_m4.number_input("% 1ª Ocorr:", min_value=0, max_value=100, value=20 if n_rv == "Sim" else 0, step=10)
        n_p2 = col_m5.number_input("% 2+ Ocorr:", min_value=0, max_value=100, value=100 if n_rv == "Sim" else 0, step=10)

        if st.button("➕ Adicionar Novo Motivo", use_container_width=True) and n_mot.strip() and engine:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO motivos (motivo, prioridade, impacta_rv, perda_1_ocorr, perda_2_ou_mais)
                    VALUES (:m, :pr, :rv, :p1, :p2)
                    ON CONFLICT (motivo) DO UPDATE
                    SET prioridade = :pr, impacta_rv = :rv, perda_1_ocorr = :p1, perda_2_ou_mais = :p2
                """), {"m": n_mot.strip().upper(), "pr": n_prio, "rv": n_rv, "p1": int(n_p1), "p2": int(n_p2)})
            st.cache_data.clear()
            st.success("Motivo adicionado!")
            st.rerun()

        df_mot_editado = st.data_editor(
            df_motivos,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Prioridade": st.column_config.SelectboxColumn("Prioridade", options=["Alta", "Média", "Baixa", "Positivo"], required=True),
                "Impacta_RV": st.column_config.SelectboxColumn("Afeta Variável?", options=["Sim", "Não"], required=True),
                "Perda_1_Ocorr_%": st.column_config.NumberColumn("% Perda (1ª Vez)", min_value=0, max_value=100, step=10),
                "Perda_2_Mais_%": st.column_config.NumberColumn("% Perda (2+ Vezes)", min_value=0, max_value=100, step=10),
            }
        )

        if st.button("💾 Salvar Alterações na Tabela de Motivos e Regras", type="primary", use_container_width=True) and engine:
            dados_m = []
            for _, row in df_mot_editado.iterrows():
                nome_m = str(row.get("Motivo", "")).strip()
                if nome_m and nome_m.lower() != "none":
                    dados_m.append({
                        "m": nome_m,
                        "pr": str(row.get("Prioridade", "Média")),
                        "rv": str(row.get("Impacta_RV", "Não")),
                        "p1": int(row.get("Perda_1_Ocorr_%", 0)) if pd.notna(row.get("Perda_1_Ocorr_%")) else 0,
                        "p2": int(row.get("Perda_2_Mais_%", 0)) if pd.notna(row.get("Perda_2_Mais_%")) else 0
                    })
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM motivos"))
                if dados_m:
                    conn.execute(text("""
                        INSERT INTO motivos (motivo, prioridade, impacta_rv, perda_1_ocorr, perda_2_ou_mais)
                        VALUES (:m, :pr, :rv, :p1, :p2)
                        ON CONFLICT (motivo) DO UPDATE
                        SET prioridade = :pr, impacta_rv = :rv, perda_1_ocorr = :p1, perda_2_ou_mais = :p2
                    """), dados_m)
            st.cache_data.clear()
            st.success("✅ Regras de motivos e porcentagens atualizadas!")
            st.rerun()

    with aba_limpar:
        st.warning("Atenção: Esta ação apaga todas as ocorrências registradas no banco de dados.")
        if st.button("🗑️ Zerar Todas as Ocorrências na Nuvem") and engine:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM ocorrencias"))
                conn.execute(text("DELETE FROM ocorrencias_anexos"))
            st.cache_data.clear()
            st.success("Base de ocorrências limpa!")
            st.rerun()
