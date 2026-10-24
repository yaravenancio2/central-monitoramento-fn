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
    page_title="FN Distribuidora | Gestão Operacional & RV",
    page_icon="▪",
    layout="wide",
    initial_sidebar_state="expanded"
)

VALOR_BASE_RV = 250.0

# ================= ESTILO VISUAL CORPORATIVO (ENTERPRISE DARK) =================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 2rem;
        max-width: 98%;
    }
    /* Barra Lateral */
    [data-testid="stSidebar"] {
        background-color: #0b0f19;
        border-right: 1px solid #1e293b;
    }
    .sidebar-brand {
        padding: 12px 0 16px 0;
        border-bottom: 1px solid #1e293b;
        margin-bottom: 16px;
    }
    .sidebar-brand-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f8fafc;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .sidebar-brand-sub {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 2px;
    }
    .user-badge {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 6px;
        padding: 10px 12px;
        margin-bottom: 12px;
    }
    .user-badge-name {
        font-size: 0.85rem;
        font-weight: 600;
        color: #e2e8f0;
    }
    .user-badge-role {
        font-size: 0.70rem;
        color: #3b82f6;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        font-weight: 600;
    }
    .nav-label {
        font-size: 0.70rem;
        font-weight: 700;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin: 14px 0 6px 0;
    }
    /* Cabeçalhos de Página */
    .page-header {
        border-bottom: 1px solid #1e293b;
        padding-top: 4px;
        padding-bottom: 12px;
        margin-bottom: 20px;
    }
    .page-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #f8fafc;
        line-height: 1.3;
        margin: 0;
    }
    .page-subtitle {
        font-size: 0.82rem;
        color: #94a3b8;
        margin-top: 4px;
    }
    /* Cards de Indicadores (KPIs) */
    .kpi-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-left: 3px solid #3b82f6;
        border-radius: 6px;
        padding: 14px 16px;
        margin-bottom: 12px;
    }
    .kpi-title {
        font-size: 0.72rem;
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        font-size: 1.55rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 4px 0 2px 0;
        font-variant-numeric: tabular-nums;
    }
    .kpi-sub {
        font-size: 0.73rem;
        color: #64748b;
    }
    /* Títulos de Seção */
    .section-header {
        font-size: 0.88rem;
        font-weight: 600;
        color: #e2e8f0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 8px 12px;
        background: #0f172a;
        border-left: 3px solid #3b82f6;
        border-top: 1px solid #1e293b;
        border-right: 1px solid #1e293b;
        border-bottom: 1px solid #1e293b;
        border-radius: 4px;
        margin: 18px 0 12px 0;
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
    {"motivo": "ATRASO NA SAÍDA / HORÁRIO LIMITE NO CLIENTE", "prioridade": "Média", "impacta_rv": "Não", "p1": 0, "p2": 0},
    {"motivo": "POSTURA INADEQUADA NO CLIENTE OU COM A TORRE", "prioridade": "Média", "impacta_rv": "Não", "p1": 0, "p2": 0},
    {"motivo": "NÃO SEGUIU ROTA PLANEJADA", "prioridade": "Média", "impacta_rv": "Não", "p1": 0, "p2": 0},
    {"motivo": "DIFICULDADE OPERACIONAL EM ROTA", "prioridade": "Baixa", "impacta_rv": "Não", "p1": 0, "p2": 0},
    {"motivo": "AÇÃO POSITIVA / ELOGIO OPERACIONAL", "prioridade": "Positivo", "impacta_rv": "Não", "p1": 0, "p2": 0}
]

LISTA_MEDIDAS_GESTOR = [
    "Feedback Aplicado",
    "Orientação / Reciclagem",
    "Advertência Verbal",
    "Advertência Escrita",
    "Suspensão Disciplinar",
    "Abono / Justificativa Aceita",
    "Elogio / Reconhecimento"
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
                    tem_anexo VARCHAR(10) DEFAULT 'Não',
                    medida_gestor VARCHAR(100) DEFAULT 'Pendente'
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
            conn.execute(text("ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS medida_gestor VARCHAR(100) DEFAULT 'Pendente'"))

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

# ================= 2. CONTROLE DE AUTENTICAÇÃO E PERMISSÕES (RBAC) =================
usuarios_cadastrados = {
    "Cheila": "torre123",
    "Caroline": "torre123",
    "Gleidiene (Manutenção)": "manut123",
    "Breno (Manutenção)": "manut123",
    "Rennan": "gestao123",
    "Tiago": "gestao123",
    "Kennia": "gestao123",
    "Yara": "gestao123",
    "Diretoria": "dir123"
}

mapa_perfis = {
    "Cheila": "Torre de Controle",
    "Caroline": "Torre de Controle",
    "Gleidiene (Manutenção)": "Manutenção / Frota",
    "Breno (Manutenção)": "Manutenção / Frota",
    "Rennan": "Gestão Operacional",
    "Tiago": "Gestão Operacional",
    "Kennia": "Gestão Operacional",
    "Yara": "Gestão / PMO",
    "Diretoria": "Diretoria Executiva"
}

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = None

if not st.session_state["autenticado"]:
    st.markdown("<div style='height: 8vh;'></div>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1.2, 1, 1.2])
    with col_l2:
        st.markdown("""
        <div style='background:#0f172a; border:1px solid #1e293b; border-top:3px solid #3b82f6; border-radius:8px; padding:24px; margin-bottom:15px;'>
            <div style='font-size:1.15rem; font-weight:700; color:#f8fafc;'>FN DISTRIBUIDORA</div>
            <div style='font-size:0.80rem; color:#64748b; margin-top:4px;'>Sistema Integrado de Monitoramento, Tratativas e RV</div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("form_login_seguro"):
            user_escolhido = st.selectbox("Operador / Gestor:", list(usuarios_cadastrados.keys()))
            senha_digitada = st.text_input("Credencial de Acesso:", type="password")
            submitted = st.form_submit_button("Autenticar Acesso", use_container_width=True, type="primary")
            
            if submitted:
                if senha_digitada == usuarios_cadastrados.get(user_escolhido):
                    st.session_state["autenticado"] = True
                    st.session_state["usuario"] = user_escolhido
                    st.rerun()
                else:
                    st.error("Credencial inválida.")
    st.stop()

usuario_logado = st.session_state["usuario"]
perfil_usuario = mapa_perfis.get(usuario_logado, "Operação")

# Definição estrita de permissões de acesso por perfil
is_manutencao = (perfil_usuario == "Manutenção / Frota")
is_gestor = (perfil_usuario in ["Gestão Operacional", "Gestão / PMO"])
is_diretoria = (perfil_usuario == "Diretoria Executiva")

if is_manutencao:
    # Gleidiene e Breno veem exclusivamente a tela de registro de ocorrências
    opcoes_menu = ["02. Registro de Ocorrências"]
elif is_diretoria:
    # Diretoria visualiza apenas os painéis de resultados (sem alterar validações)
    opcoes_menu = [
        "01. Painel Executivo & Cadências",
        "04. Fechamento Variável (RV)",
        "05. Avaliação 360º (Dossiê)"
    ]
elif is_gestor:
    # Gestores possuem acesso total a todos os módulos, incluindo Mesa do Gestor e Parâmetros
    opcoes_menu = [
        "01. Painel Executivo & Cadências",
        "02. Registro de Ocorrências",
        "03. Validação & Tratativas",
        "04. Fechamento Variável (RV)",
        "05. Avaliação 360º (Dossiê)",
        "06. Cadastros & Parâmetros"
    ]
else:
    # Torre de Controle: registra ocorrências e acompanha painéis, mas não acessa a Mesa do Gestor
    opcoes_menu = [
        "01. Painel Executivo & Cadências",
        "02. Registro de Ocorrências",
        "05. Avaliação 360º (Dossiê)"
    ]

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
        "Status", "Acao_Gestor", "Data_Tratativa", "Registrado_Por", "Prioridade",
        "Impacta_RV", "Tem_Anexo", "Medida_Gestor"
    ]
    if engine:
        try:
            query = """
                SELECT id, data, colaborador, funcao, rota, tipo, motivo, detalhe,
                       status, acao_gestor, data_tratativa, COALESCE(registrado_por, 'Torre') AS registrado_por,
                       COALESCE(prioridade, tipo, 'Média') AS prioridade,
                       COALESCE(impacta_rv, 'Não') AS impacta_rv,
                       COALESCE(tem_anexo, 'Não') AS tem_anexo,
                       COALESCE(medida_gestor, 'Pendente') AS medida_gestor
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

                def padronizar_medida(row):
                    med = str(row["Medida_Gestor"]).strip()
                    st_atual = str(row["Status"]).strip()
                    if st_atual == "Pendente de Validação":
                        return "Pendente de Avaliação"
                    if med in ["", "None", "Pendente"]:
                        if st_atual == "Justificado / Abonado":
                            return "Abono / Justificativa Aceita"
                        return "Feedback Aplicado"
                    return med

                df_o["Medida_Gestor"] = df_o.apply(padronizar_medida, axis=1)
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
        df_pendentes = df_ocorr_periodo[df_ocorr_periodo["Status"] == "Pendente de Validação"]
    else:
        df_rv_validas = pd.DataFrame()
        df_pendentes = pd.DataFrame()

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

        contagem_incidencias = {col: 0 for col in colunas_oficiais_rv}
        contagem_incidencias["DIVERSOS"] = 0

        perda_pct_total = 0
        detalhes_motivos = []

        if not ocorr_colab.empty:
            contagem_por_motivo = ocorr_colab["Motivo"].value_counts().to_dict()
            for mot, qtd in contagem_por_motivo.items():
                regra = regras_dict.get(mot, {"impacta": "Sim", "p1": 20, "p2": 100})
                perda_mot = regra["p1"] if qtd == 1 else regra["p2"]
                perda_pct_total += perda_mot
                detalhes_motivos.append(f"{mot} ({qtd}x: -{perda_mot}%)")

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
            status_rv = "100% ELEGÍVEL"
        elif perda_pct_final < 100:
            status_rv = f"PARCIAL (-{perda_pct_final}%)"
        else:
            status_rv = "PERDA TOTAL (0%)"

        linha_dict = {
            "COLABORADOR": nome,
            "FUNÇÃO": funcao,
        }
        for col_oficial in colunas_oficiais_rv:
            linha_dict[col_oficial] = contagem_incidencias[col_oficial]
        linha_dict["DIVERSOS"] = contagem_incidencias["DIVERSOS"]

        linha_dict.update({
            "DETALHAMENTO DE INCIDENCIAS RV": " | ".join(detalhes_motivos) if detalhes_motivos else "Sem apontamentos",
            "PENDENTES ANÁLISE": pend_colab,
            "% PERDA RV": perda_pct_final,
            "DESCONTO R$": valor_desconto,
            "VALOR A PAGAR R$": valor_receber,
            "STATUS ELEGIBILIDADE": status_rv
        })
        resultado.append(linha_dict)

    return pd.DataFrame(resultado)

# ================= INICIALIZAÇÃO DOS DADOS =================
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

# ================= BARRA LATERAL ESTRUTURADA =================
st.sidebar.markdown("""
<div class="sidebar-brand">
    <div class="sidebar-brand-title">FN Distribuidora</div>
    <div class="sidebar-brand-sub">Torre de Controle & Performance</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown(f"""
<div class="user-badge">
    <div class="user-badge-role">{perfil_usuario}</div>
    <div class="user-badge-name">{usuario_logado}</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown('<div class="nav-label">Módulos Autorizados</div>', unsafe_allow_html=True)
pagina = st.sidebar.radio("Módulos", opcoes_menu, label_visibility="collapsed")

# Oculta filtros globais para o perfil Manutenção (pois acessam apenas o formulário de registro)
if not is_manutencao:
    st.sidebar.markdown('<div class="nav-label">Filtros Globais</div>', unsafe_allow_html=True)
    with st.sidebar.expander("Parâmetros de Filtro", expanded=True):
        funcao_filtro = st.multiselect(
            "Cargo:",
            options=["Motorista", "Ajudante"],
            default=["Motorista", "Ajudante"]
        )
        hoje = date.today()
        inicio_mes = date(hoje.year, hoje.month, 1)
        usar_filtro_data = st.checkbox("Filtrar por Período", value=False)
        if usar_filtro_data:
            dt_ini = st.date_input("De:", value=inicio_mes)
            dt_fim = st.date_input("Até:", value=hoje)
        else:
            dt_ini, dt_fim = None, None
else:
    funcao_filtro = ["Motorista", "Ajudante"]
    usar_filtro_data = False
    dt_ini, dt_fim = None, None

st.sidebar.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
if st.sidebar.button("Encerrar Sessão", use_container_width=True):
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = None
    st.rerun()

# Aplica filtros
df_filtrado = df[df["Funcao"].isin(funcao_filtro)].copy() if not df.empty else df.copy()
if usar_filtro_data and not df_filtrado.empty and df_filtrado["Data_DT"].notna().any():
    df_filtrado = df_filtrado[
        (df_filtrado["Data_DT"].dt.date >= dt_ini) &
        (df_filtrado["Data_DT"].dt.date <= dt_fim)
    ]

CORES_PRIORIDADE = {
    "Alta": "#ef4444",
    "Média": "#f59e0b",
    "Baixa": "#3b82f6",
    "Positivo": "#10b981"
}

CORES_MEDIDAS = {
    "Pendente de Avaliação": "#64748b",
    "Feedback Aplicado": "#3b82f6",
    "Orientação / Reciclagem": "#0ea5e9",
    "Advertência Verbal": "#f59e0b",
    "Advertência Escrita": "#f97316",
    "Suspensão Disciplinar": "#ef4444",
    "Abono / Justificativa Aceita": "#10b981",
    "Elogio / Reconhecimento": "#8b5cf6"
}


# ==============================================================================
# 01. PAINEL EXECUTIVO & CADÊNCIAS
# ==============================================================================
if pagina == "01. Painel Executivo & Cadências":
    st.markdown("""
    <div class="page-header">
        <div class="page-title">Painel Executivo & Indicadores de Cadência</div>
        <div class="page-subtitle">Monitoramento de prioridades operacionais, medidas disciplinares e governança de tratativas</div>
    </div>
    """, unsafe_allow_html=True)

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
        st.markdown(f"""<div class="kpi-card" style="border-left-color: #64748b;">
            <div class="kpi-title">Total Registrado</div>
            <div class="kpi-value">{len(df_filtrado)}</div>
            <div class="kpi-sub">{qtd_pendentes} pendentes de validação</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card" style="border-left-color: #ef4444;">
            <div class="kpi-title">Prioridade Alta</div>
            <div class="kpi-value" style="color:#ef4444;">{pct_alta:.1f}%</div>
            <div class="kpi-sub">{qtd_alta} ocorrências validadas</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card" style="border-left-color: #f59e0b;">
            <div class="kpi-title">Prioridade Média</div>
            <div class="kpi-value" style="color:#f59e0b;">{pct_media:.1f}%</div>
            <div class="kpi-sub">{qtd_media} ocorrências validadas</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card" style="border-left-color: #3b82f6;">
            <div class="kpi-title">Prioridade Baixa</div>
            <div class="kpi-value" style="color:#3b82f6;">{pct_baixa:.1f}%</div>
            <div class="kpi-sub">{qtd_baixa} ocorrências validadas</div>
        </div>""", unsafe_allow_html=True)
    with k5:
        qtd_rv_conf = len(df_filtrado[df_filtrado["Status"] == "Validado (Impacta RV)"]) if not df_filtrado.empty else 0
        qtd_op_conf = len(df_filtrado[df_filtrado["Status"] == "Validado (Operacional Sem Impacto RV)"]) if not df_filtrado.empty else 0
        st.markdown(f"""<div class="kpi-card" style="border-left-color: #10b981;">
            <div class="kpi-title">Tratativas Concluídas</div>
            <div class="kpi-value">{qtd_rv_conf + qtd_op_conf + qtd_abonadas}</div>
            <div class="kpi-sub">{qtd_rv_conf} c/ impacto RV | {qtd_abonadas} abonos</div>
        </div>""", unsafe_allow_html=True)

    # --- SEÇÃO 1: CADÊNCIA TEMPORAL E MEDIDAS DO GESTOR ---
    st.markdown('<div class="section-header">Análise de Cadência Temporal & Medidas Aplicadas</div>', unsafe_allow_html=True)
    if not df_filtrado.empty and df_filtrado["Data_DT"].notna().any():
        col_c1, col_c2 = st.columns([1, 3])
        agrupamento_tempo = col_c1.SegmentedControl(
            "Periodicidade:",
            options=["Diária", "Semanal", "Mensal"],
            default="Diária"
        ) if hasattr(st, "SegmentedControl") else col_c1.radio("Periodicidade:", ["Diária", "Semanal", "Mensal"], horizontal=True)

        df_cad = df_filtrado.dropna(subset=["Data_DT"]).copy()
        if agrupamento_tempo == "Semanal":
            df_cad["Ordem"] = df_cad["Data_DT"].dt.to_period("W").apply(lambda r: r.start_time.date())
            df_cad["Periodo"] = df_cad["Ordem"].apply(lambda d: f"Sem {d.strftime('%d/%m')}")
        elif agrupamento_tempo == "Mensal":
            df_cad["Ordem"] = df_cad["Data_DT"].dt.to_period("M").apply(lambda r: r.start_time.date())
            df_cad["Periodo"] = df_cad["Data_DT"].dt.strftime("%m/%Y")
        else:
            df_cad["Periodo"] = df_cad["Data_DT"].dt.strftime("%d/%m/%Y")
            df_cad["Ordem"] = df_cad["Data_DT"].dt.date

        g_cad1, g_cad2 = st.columns(2)

        with g_cad1:
            df_cad_prio = df_cad.groupby(["Ordem", "Periodo", "Prioridade"]).size().reset_index(name="Qtd").sort_values("Ordem")
            fig_cad_prio = px.bar(
                df_cad_prio,
                x="Periodo",
                y="Qtd",
                color="Prioridade",
                color_discrete_map=CORES_PRIORIDADE,
                title="Cadência por Nível de Prioridade",
                text_auto=True,
                barmode="stack"
            )
            fig_cad_prio.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=340,
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis_title="",
                yaxis_title="Ocorrências",
                legend_title_text="Prioridade"
            )
            st.plotly_chart(fig_cad_prio, use_container_width=True)

        with g_cad2:
            df_cad_med = df_cad.groupby(["Ordem", "Periodo", "Medida_Gestor"]).size().reset_index(name="Qtd").sort_values("Ordem")
            fig_cad_med = px.bar(
                df_cad_med,
                x="Periodo",
                y="Qtd",
                color="Medida_Gestor",
                color_discrete_map=CORES_MEDIDAS,
                title="Cadência de Tratativas & Medidas do Gestor (Inclui Pendentes)",
                text_auto=True,
                barmode="stack"
            )
            fig_cad_med.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=340,
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis_title="",
                yaxis_title="Registros",
                legend_title_text="Medida / Status"
            )
            st.plotly_chart(fig_cad_med, use_container_width=True)
    else:
        st.info("Sem registros no período selecionado.")

    # --- SEÇÃO 2: DISTRIBUIÇÃO DE PRIORIDADES POR COLABORADOR ---
    st.markdown('<div class="section-header">Matriz de Incidência por Colaborador (% Alta, Média e Baixa)</div>', unsafe_allow_html=True)
    if not df_prio_neg.empty:
        modo_visao_mot = st.radio(
            "Métrica de Visualização:",
            ["Distribuição Percentual (%)", "Volume Absoluto (Qtd)"],
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
            if "Percentual" in modo_visao_mot:
                df_melt = tab_mot.melt(id_vars=["Colaborador", "Total"], value_vars=["% Alta", "% Média", "% Baixa"], var_name="Nível", value_name="Percentual")
                df_melt["Prioridade"] = df_melt["Nível"].str.replace("% ", "")
                fig_mot = px.bar(
                    df_melt,
                    y="Colaborador",
                    x="Percentual",
                    color="Prioridade",
                    orientation="h",
                    color_discrete_map=CORES_PRIORIDADE,
                    text=df_melt["Percentual"].apply(lambda x: f"{x:.0f}%" if x > 6 else "")
                )
                fig_mot.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=max(340, len(tab_mot) * 30),
                    margin=dict(l=10, r=10, t=20, b=10),
                    xaxis_title="Proporção (%)",
                    yaxis_title=""
                )
            else:
                df_melt = tab_mot.melt(id_vars=["Colaborador", "Total"], value_vars=["Alta", "Média", "Baixa"], var_name="Prioridade", value_name="Qtd")
                fig_mot = px.bar(
                    df_melt,
                    y="Colaborador",
                    x="Qtd",
                    color="Prioridade",
                    orientation="h",
                    color_discrete_map=CORES_PRIORIDADE,
                    text_auto=True
                )
                fig_mot.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=max(340, len(tab_mot) * 30),
                    margin=dict(l=10, r=10, t=20, b=10),
                    xaxis_title="Quantidade de Ocorrências",
                    yaxis_title=""
                )
            st.plotly_chart(fig_mot, use_container_width=True)

        with c_m2:
            df_exib_mot = tab_mot.sort_values(by=["Alta", "Total"], ascending=False)[
                ["Colaborador", "Total", "% Alta", "% Média", "% Baixa", "Alta", "Média", "Baixa"]
            ]
            st.dataframe(df_exib_mot, use_container_width=True, hide_index=True, height=340)
    else:
        st.info("Não há ocorrências validadas para cálculo de distribuição por colaborador.")

    # --- SEÇÃO 3: PARETO DE MOTIVOS E RESUMO DE MEDIDAS DISCIPLINARES ---
    st.markdown('<div class="section-header">Incidências por Motivo & Distribuição de Medidas do Gestor</div>', unsafe_allow_html=True)
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
                color_discrete_map={"Sim": "#ef4444", "Não": "#3b82f6"},
                title="Volume por Motivo (Vermelho = Afeta RV | Azul = Operacional)",
                text_auto=True
            )
            fig_mot_rank.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=360,
                margin=dict(l=10, r=10, t=40, b=10),
                yaxis_title="",
                legend_title_text="Impacta RV"
            )
            st.plotly_chart(fig_mot_rank, use_container_width=True)

        with g_inf2:
            df_med_tot = df_filtrado["Medida_Gestor"].value_counts().reset_index()
            df_med_tot.columns = ["Medida", "Quantidade"]
            fig_med = px.pie(
                df_med_tot,
                names="Medida",
                values="Quantidade",
                hole=0.5,
                title="Proporção de Tratativas / Medidas",
                color="Medida",
                color_discrete_map=CORES_MEDIDAS
            )
            fig_med.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=360,
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_med, use_container_width=True)


# ==============================================================================
# 02. REGISTRO DE OCORRÊNCIAS (COM VÍNCULO DE DUPLA MOTORISTA + AJUDANTE)
# ==============================================================================
elif pagina == "02. Registro de Ocorrências":
    st.markdown(f"""
    <div class="page-header">
        <div class="page-title">Registro de Apontamento Operacional</div>
        <div class="page-subtitle">Operador autenticado: {usuario_logado} ({perfil_usuario})</div>
    </div>
    """, unsafe_allow_html=True)

    if is_manutencao:
        st.info("Acesso Restrito (Manutenção): Formulário habilitado exclusivamente para apontamentos de CHECKLIST.")

    mapa_funcao_colab = dict(zip(df_colab["Colaborador"], df_colab["Funcao"])) if not df_colab.empty else {"Carlos Eduardo": "Motorista"}
    lista_nomes = sorted(list(mapa_funcao_colab.keys()))

    with st.container():
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            colab_sel_1 = st.selectbox("1º Colaborador (Principal):", lista_nomes)
            func_auto_1 = mapa_funcao_colab.get(colab_sel_1, "Motorista")
            st.caption(f"Cargo: **{func_auto_1}**")

            # Opção para vincular o 2º colaborador (Dupla Motorista + Ajudante) na mesma ocorrência
            opcoes_segundo_colab = ["Nenhum (Individual)"] + [
                f"{n} ({mapa_funcao_colab.get(n, '')})" for n in lista_nomes if n != colab_sel_1
            ]
            colab_sel_2_raw = st.selectbox(
                "2º Colaborador Envolvido (Opcional - Dupla na Rota):",
                opcoes_segundo_colab
            )

        with col_f2:
            data_ocorr = st.date_input("Data da Ocorrência:", value=date.today())
            rota_ocorr = st.text_input("Rota / Veículo / Cidade:", placeholder="Ex: Placa ABC-1234 - Rota Sul de Minas")

        with col_f3:
            if is_manutencao:
                lista_motivos_disponiveis = [m for m in lista_motivos if "CHECKLIST" in m.upper() or "CHECK LIST" in m.upper()]
                if not lista_motivos_disponiveis:
                    lista_motivos_disponiveis = ["CHECKLIST DIÁRIO", "CHECK LIST HIGIENIZAÇÃO"]
                motivo_sel = st.selectbox("Incidência (Manutenção):", lista_motivos_disponiveis)
            else:
                motivo_sel = st.selectbox("Motivo / Incidência:", lista_motivos)

            prio_sugerida = mapa_prioridade_motivo.get(motivo_sel, "Média")
            rv_sugerido = mapa_rv_motivo.get(motivo_sel, "Não")

            opcoes_prio = ["Alta", "Média", "Baixa", "Positivo"]
            idx_prio = opcoes_prio.index(prio_sugerida) if prio_sugerida in opcoes_prio else 1
            prio_sel = st.selectbox("Nível de Prioridade:", opcoes_prio, index=idx_prio)

        c_info1, c_info2 = st.columns(2)
        c_info1.text_input("Impacto Previsto na Variável (RV):", value=rv_sugerido, disabled=True)
        c_info2.text_input("Autor do Registro:", value=usuario_logado, disabled=True)

        detalhe_ocorr = st.text_area("Relato Técnico da Ocorrência:", height=110, placeholder="Informe dados objetivos: NF, cliente, horário, descrição do desvio...")

        if st.button("Confirmar e Enviar para Validação", use_container_width=True, type="primary"):
            if engine:
                try:
                    proximo_id = 1
                    if not df.empty and "ID" in df.columns:
                        proximo_id = int(df["ID"].max()) + 1

                    # Monta a lista de envolvidos (1 ou 2 colaboradores)
                    envolvidos = [(colab_sel_1, func_auto_1)]
                    if colab_sel_2_raw != "Nenhum (Individual)":
                        nome_2 = colab_sel_2_raw.rsplit(" (", 1)[0]
                        func_2 = mapa_funcao_colab.get(nome_2, "Ajudante")
                        envolvidos.append((nome_2, func_2))

                    ids_gerados = []
                    with engine.begin() as conn:
                        for idx_env, (nome_env, func_env) in enumerate(envolvidos):
                            id_atual = proximo_id + idx_env
                            ids_gerados.append(f"#{id_atual} ({nome_env})")
                            conn.execute(text("""
                                INSERT INTO ocorrencias (
                                    id, data, colaborador, funcao, rota, tipo, motivo, detalhe,
                                    pontos, status, acao_gestor, data_tratativa, registrado_por,
                                    prioridade, impacta_rv, tem_anexo, medida_gestor
                                ) VALUES (
                                    :id, :data, :colab, :func, :rota, :tipo, :mot, :det,
                                    0, 'Pendente de Validação', '', '', :reg,
                                    :prio, :rv, 'Não', 'Pendente de Avaliação'
                                )
                            """), {
                                "id": id_atual,
                                "data": data_ocorr.strftime("%d/%m/%Y"),
                                "colab": nome_env,
                                "func": func_env,
                                "rota": rota_ocorr.strip() if rota_ocorr.strip() else "Não informada",
                                "tipo": prio_sel,
                                "mot": motivo_sel,
                                "det": detalhe_ocorr.strip(),
                                "reg": usuario_logado.strip(),
                                "prio": prio_sel,
                                "rv": rv_sugerido
                            })
                    st.cache_data.clear()
                    st.success(f"Ocorrência registrada com sucesso para: {', '.join(ids_gerados)}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")


# ==============================================================================
# 03. VALIDAÇÃO DO GESTOR, MEDIDAS DISCIPLINARES & BACKLOG (EXCLUSIVO GESTORES)
# ==============================================================================
elif pagina == "03. Validação & Tratativas":
    if not is_gestor:
        st.error("Acesso não autorizado para o seu perfil.")
        st.stop()

    st.markdown("""
    <div class="page-header">
        <div class="page-title">Mesa de Validação Gerencial & Controle de Tratativas</div>
        <div class="page-subtitle">Aprovação de impacto em Remuneração Variável, aplicação de medidas disciplinares e auditoria</div>
    </div>
    """, unsafe_allow_html=True)

    aba_pendentes, aba_backlog = st.tabs([
        "Fila Pendente de Validação",
        "Histórico de Ocorrências Tratadas (Backlog)"
    ])

    with aba_pendentes:
        df_pend = df[df["Status"] == "Pendente de Validação"].copy() if not df.empty else pd.DataFrame()
        st.markdown(f'<div class="section-header">Registros Aguardando Parecer do Gestor ({len(df_pend)})</div>', unsafe_allow_html=True)

        if df_pend.empty:
            st.info("Não há ocorrências pendentes de validação no momento.")
        else:
            st.dataframe(
                df_pend[["ID", "Data", "Colaborador", "Funcao", "Rota", "Motivo", "Prioridade", "Impacta_RV", "Registrado_Por", "Detalhe"]],
                use_container_width=True,
                hide_index=True
            )

            st.markdown('<div class="section-header">Formulário de Decisão e Tratativa</div>', unsafe_allow_html=True)
            c_g1, c_g2 = st.columns([1, 2])

            with c_g1:
                opcoes_id = df_pend.apply(
                    lambda r: f"#{r['ID']} | {r['Colaborador']} ({r['Funcao']}) - {r['Motivo']}", axis=1
                ).tolist()
                sel_item = st.selectbox("Selecionar Registro:", opcoes_id)
                id_escolhido = int(sel_item.split("#")[1].split(" |")[0])
                linha_atual = df_pend[df_pend["ID"] == id_escolhido].iloc[0]

                st.markdown(f"""
                <div style="background:#0f172a; border:1px solid #1e293b; border-radius:6px; padding:14px; font-size:0.84rem;">
                    <div style="color:#94a3b8; font-size:0.72rem; text-transform:uppercase;">Resumo do Apontamento</div>
                    <div style="margin-top:8px;"><b>Colaborador:</b> {linha_atual['Colaborador']} ({linha_atual['Funcao']})</div>
                    <div style="margin-top:4px;"><b>Data / Rota:</b> {linha_atual['Data']} | {linha_atual['Rota']}</div>
                    <div style="margin-top:4px;"><b>Motivo:</b> {linha_atual['Motivo']}</div>
                    <div style="margin-top:4px;"><b>Prioridade:</b> {linha_atual['Prioridade']} | <b>Afeta RV?</b> {linha_atual['Impacta_RV']}</div>
                    <div style="margin-top:4px;"><b>Autor:</b> {linha_atual['Registrado_Por']}</div>
                    <div style="margin-top:8px; padding-top:8px; border-top:1px solid #1e293b; color:#cbd5e1;"><b>Relato:</b> {linha_atual['Detalhe']}</div>
                </div>
                """, unsafe_allow_html=True)

            with c_g2:
                if linha_atual["Impacta_RV"] == "Sim":
                    opcoes_decisao = [
                        "Validar Impacto na Variável (Desconta no Laudo RV)",
                        "Abonar / Justificar Ocorrência (Isenta desconto na RV)",
                        "Converter em Registro Operacional (Mantém no Dossiê s/ desconto RV)"
                    ]
                else:
                    opcoes_decisao = [
                        "Validar Registro Operacional (Sem impacto na RV)",
                        "Abonar / Arquivar com Justificativa",
                        "Forçar Impacto na Variável (Aloca em DIVERSOS no Laudo RV)"
                    ]

                col_d1, col_d2, col_d3 = st.columns([2, 1.5, 1])
                decisao_gestor = col_d1.selectbox("1. Decisão de Impacto:", opcoes_decisao)
                medida_aplicada = col_d2.selectbox("2. Medida / Tratativa Aplicada:", LISTA_MEDIDAS_GESTOR)
                nova_prio = col_d3.selectbox(
                    "3. Prioridade:",
                    ["Alta", "Média", "Baixa", "Positivo"],
                    index=["Alta", "Média", "Baixa", "Positivo"].index(linha_atual["Prioridade"]) if linha_atual["Prioridade"] in ["Alta", "Média", "Baixa", "Positivo"] else 1
                )

                parecer_gestor = st.text_area(
                    "4. Detalhamento da Tratativa / Parecer Gerencial (Obrigatório):",
                    placeholder="Descreva a tratativa realizada, motivo do abono ou termos da advertência/feedback..."
                )
                arquivo_anexo = st.file_uploader(
                    "5. Anexar Evidência / Documento Comprobatório (Imagem ou PDF até 1MB):",
                    type=["jpg", "jpeg", "png", "webp", "pdf"]
                )

                if st.button("Salvar Validação e Tratativa", type="primary", use_container_width=True):
                    if not parecer_gestor.strip():
                        st.warning("Informe o parecer gerencial para concluir a validação.")
                    elif engine:
                        if "Validar Impacto" in decisao_gestor or "Forçar Impacto" in decisao_gestor:
                            novo_status = "Validado (Impacta RV)"
                            novo_rv = "Sim"
                        elif "Abonar" in decisao_gestor:
                            novo_status = "Justificado / Abonado"
                            novo_rv = "Não"
                        else:
                            novo_status = "Validado (Operacional Sem Impacto RV)"
                            novo_rv = "Não"

                        tem_anexo_flag = "Não"
                        nome_arq, mime_arq, b64_arq = None, None, None
                        if arquivo_anexo is not None:
                            nome_arq, mime_arq, b64_arq = comprimir_e_codificar_arquivo(arquivo_anexo)
                            if nome_arq == "ERRO_TAMANHO":
                                st.error("O arquivo PDF excede 1 MB.")
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
                                        tem_anexo = :anexo,
                                        medida_gestor = :med
                                    WHERE id = :id
                                """), {
                                    "st": novo_status,
                                    "acao": parecer_gestor.strip(),
                                    "dt": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                    "prio": nova_prio,
                                    "rv": novo_rv,
                                    "anexo": tem_anexo_flag,
                                    "med": medida_aplicada,
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
                            st.success(f"Ocorrência #{id_escolhido} validada com a medida '{medida_aplicada}'.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao validar: {e}")

    with aba_backlog:
        st.markdown('<div class="section-header">Histórico Geral de Ocorrências Tratadas</div>', unsafe_allow_html=True)
        df_tratadas = df[df["Status"] != "Pendente de Validação"].copy() if not df.empty else pd.DataFrame()

        if df_tratadas.empty:
            st.info("Nenhum registro tratado até o momento.")
        else:
            col_fb1, col_fb2 = st.columns(2)
            f_status = col_fb1.multiselect(
                "Filtrar por Status de Impacto:",
                options=df_tratadas["Status"].unique().tolist(),
                default=df_tratadas["Status"].unique().tolist()
            )
            f_medida = col_fb2.multiselect(
                "Filtrar por Medida Aplicada:",
                options=df_tratadas["Medida_Gestor"].unique().tolist(),
                default=df_tratadas["Medida_Gestor"].unique().tolist()
            )
            df_b_view = df_tratadas[
                (df_tratadas["Status"].isin(f_status)) &
                (df_tratadas["Medida_Gestor"].isin(f_medida))
            ]

            st.dataframe(
                df_b_view[[
                    "ID", "Data", "Colaborador", "Motivo", "Prioridade",
                    "Status", "Medida_Gestor", "Impacta_RV", "Registrado_Por", "Acao_Gestor", "Data_Tratativa", "Tem_Anexo"
                ]],
                use_container_width=True,
                hide_index=True
            )

            col_anx, col_adm = st.columns(2)
            with col_anx:
                st.markdown('<div class="section-header">Consulta de Anexos Comprobatórios</div>', unsafe_allow_html=True)
                df_com_anexo = df_b_view[df_b_view["Tem_Anexo"] == "Sim"]
                if not df_com_anexo.empty:
                    id_anexo_sel = st.selectbox(
                        "Registro com anexo:",
                        df_com_anexo.apply(lambda r: f"#{r['ID']} - {r['Colaborador']} ({r['Motivo']})", axis=1).tolist()
                    )
                    if st.button("Carregar Arquivo Anexo"):
                        id_busca = int(id_anexo_sel.split("#")[1].split(" -")[0])
                        nome_a, mime_a, b64_a = buscar_anexo_no_banco(id_busca)
                        if b64_a:
                            bytes_arq = base64.b64decode(b64_a)
                            st.download_button(label=f"Baixar {nome_a}", data=bytes_arq, file_name=nome_a, mime=mime_a)
                            if mime_a.startswith("image/"):
                                st.image(bytes_arq, caption=f"Evidência #{id_busca}", use_container_width=True)
                        else:
                            st.warning("Arquivo não localizado.")
                else:
                    st.caption("Nenhum anexo disponível nos filtros atuais.")

            with col_adm:
                st.markdown('<div class="section-header">Gerenciamento de Registro</div>', unsafe_allow_html=True)
                if not df_b_view.empty:
                    id_gerenciar = st.selectbox(
                        "Selecionar Registro:",
                        df_b_view.apply(lambda r: f"#{r['ID']} - {r['Colaborador']} ({r['Motivo']})", axis=1).tolist(),
                        key="sel_reabrir_id"
                    )
                    id_alvo = int(id_gerenciar.split("#")[1].split(" -")[0])
                    b_reab, b_excl = st.columns(2)
                    if b_reab.button("Retornar para Pendente", use_container_width=True):
                        with engine.begin() as conn:
                            conn.execute(text("UPDATE ocorrencias SET status = 'Pendente de Validação', medida_gestor = 'Pendente de Avaliação' WHERE id = :id"), {"id": id_alvo})
                        st.cache_data.clear()
                        st.rerun()
                    if b_excl.button("Excluir Registro", use_container_width=True):
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM ocorrencias WHERE id = :id"), {"id": id_alvo})
                            conn.execute(text("DELETE FROM ocorrencias_anexos WHERE id_ocorrencia = :id"), {"id": id_alvo})
                        st.cache_data.clear()
                        st.rerun()


# ==============================================================================
# 04. LAUDO DE REMUNERAÇÃO VARIÁVEL (RV)
# ==============================================================================
elif pagina == "04. Fechamento Variável (RV)":
    st.markdown("""
    <div class="page-header">
        <div class="page-title">Laudo de Apuração da Remuneração Variável</div>
        <div class="page-subtitle">Base de Cálculo: R$ 250,00 | Penalidades: 20% (R$ 50,00) ou 100% (R$ 250,00) conforme matriz de incidências validadas</div>
    </div>
    """, unsafe_allow_html=True)

    df_colab_filtrado = df_colab[df_colab["Funcao"].isin(funcao_filtro)] if not df_colab.empty else df_colab
    df_laudo = calcular_fechamento_rv(df_filtrado, df_colab_filtrado, df_motivos)

    pend_rv = df_filtrado[(df_filtrado["Status"] == "Pendente de Validação") & (df_filtrado["Impacta_RV"] == "Sim")] if not df_filtrado.empty else pd.DataFrame()
    if not pend_rv.empty:
        st.warning(f"Atenção: Existem {len(pend_rv)} ocorrências com impacto potencial na variável aguardando validação gerencial.")

    if not df_laudo.empty:
        total_descontos = df_laudo["DESCONTO R$"].sum()
        total_pagar = df_laudo["VALOR A PAGAR R$"].sum()

        qtd_100 = len(df_laudo[df_laudo["% PERDA RV"] == 0])
        qtd_parcial = len(df_laudo[(df_laudo["% PERDA RV"] > 0) & (df_laudo["% PERDA RV"] < 100)])
        qtd_zerado = len(df_laudo[df_laudo["% PERDA RV"] == 100])

        k_rv1, k_rv2, k_rv3, k_rv4 = st.columns(4)
        with k_rv1:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #10b981;">
                <div class="kpi-title">100% Elegíveis (Integral)</div>
                <div class="kpi-value" style="color:#10b981;">{qtd_100}</div>
                <div class="kpi-sub">Pagamento de R$ 250,00</div>
            </div>""", unsafe_allow_html=True)
        with k_rv2:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #f59e0b;">
                <div class="kpi-title">Elegibilidade Parcial</div>
                <div class="kpi-value" style="color:#f59e0b;">{qtd_parcial}</div>
                <div class="kpi-sub">Redução de 20% a 80%</div>
            </div>""", unsafe_allow_html=True)
        with k_rv3:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #ef4444;">
                <div class="kpi-title">Perda Total (Zerados)</div>
                <div class="kpi-value" style="color:#ef4444;">{qtd_zerado}</div>
                <div class="kpi-sub">Redução de 100% da RV</div>
            </div>""", unsafe_allow_html=True)
        with k_rv4:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #3b82f6;">
                <div class="kpi-title">Folha Líquida Variável</div>
                <div class="kpi-value">R$ {total_pagar:,.2f}</div>
                <div class="kpi-sub">Valor Retido: R$ {total_descontos:,.2f}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-header">Matriz Nominal de Fechamento da Remuneração Variável</div>', unsafe_allow_html=True)
        st.dataframe(df_laudo, use_container_width=True, hide_index=True, height=460)

        csv_laudo = df_laudo.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="Exportar Laudo de Fechamento (CSV / Excel)",
            data=csv_laudo,
            file_name=f"laudo_rv_fn_{date.today().strftime('%Y_%m_%d')}.csv",
            mime="text/csv",
            type="primary"
        )


# ==============================================================================
# 05. AVALIAÇÃO 360º DO COLABORADOR (DOSSIÊ COMPLETO + PENDENTES + MEDIDAS)
# ==============================================================================
elif pagina == "05. Avaliação 360º (Dossiê)":
    st.markdown("""
    <div class="page-header">
        <div class="page-title">Avaliação 360º & Prontuário do Colaborador</div>
        <div class="page-subtitle">Histórico individual de performance, medidas disciplinares, pendências de validação e extrato da variável</div>
    </div>
    """, unsafe_allow_html=True)

    lista_nomes_d = sorted(df_colab["Colaborador"].unique().tolist()) if not df_colab.empty else ["Carlos Eduardo"]
    colab_dossie = st.selectbox("Selecionar Colaborador:", lista_nomes_d)

    df_hist = df_filtrado[df_filtrado["Colaborador"] == colab_dossie].copy() if not df_filtrado.empty else pd.DataFrame()
    df_laudo_ind = calcular_fechamento_rv(df_filtrado, df_colab[df_colab["Colaborador"] == colab_dossie], df_motivos)

    valor_a_receber = df_laudo_ind["VALOR A PAGAR R$"].iloc[0] if not df_laudo_ind.empty else VALOR_BASE_RV
    desconto_ind = df_laudo_ind["DESCONTO R$"].iloc[0] if not df_laudo_ind.empty else 0.0

    df_pend_ind = df_hist[df_hist["Status"] == "Pendente de Validação"] if not df_hist.empty else pd.DataFrame()
    df_val_ind = df_hist[df_hist["Status"].isin(["Validado (Impacta RV)", "Validado (Operacional Sem Impacto RV)"])] if not df_hist.empty else pd.DataFrame()
    df_d_rv = df_hist[df_hist["Status"] == "Validado (Impacta RV)"] if not df_hist.empty else pd.DataFrame()
    df_d_op = df_hist[df_hist["Status"] == "Validado (Operacional Sem Impacto RV)"] if not df_hist.empty else pd.DataFrame()
    df_d_ab = df_hist[df_hist["Status"] == "Justificado / Abonado"] if not df_hist.empty else pd.DataFrame()

    df_prio_ind = df_val_ind[df_val_ind["Prioridade"].isin(["Alta", "Média", "Baixa"])] if not df_val_ind.empty else pd.DataFrame()
    tot_p_ind = len(df_prio_ind)

    p_alta_i = (len(df_prio_ind[df_prio_ind["Prioridade"] == "Alta"]) / tot_p_ind * 100) if tot_p_ind > 0 else 0.0
    p_med_i = (len(df_prio_ind[df_prio_ind["Prioridade"] == "Média"]) / tot_p_ind * 100) if tot_p_ind > 0 else 0.0
    p_bx_i = (len(df_prio_ind[df_prio_ind["Prioridade"] == "Baixa"]) / tot_p_ind * 100) if tot_p_ind > 0 else 0.0

    d1, d2, d3, d4, d5, d6 = st.columns(6)
    with d1:
        cor_saldo = "#10b981" if desconto_ind == 0 else ("#f59e0b" if valor_a_receber > 0 else "#ef4444")
        st.markdown(f"""<div class="kpi-card" style="border-left-color: {cor_saldo};">
            <div class="kpi-title">Saldo RV Previsto</div>
            <div class="kpi-value" style="color:{cor_saldo};">R$ {valor_a_receber:,.2f}</div>
            <div class="kpi-sub">Retido: R$ {desconto_ind:,.2f}</div>
        </div>""", unsafe_allow_html=True)
    with d2:
        cor_pend = "#f59e0b" if len(df_pend_ind) > 0 else "#64748b"
        st.markdown(f"""<div class="kpi-card" style="border-left-color: {cor_pend};">
            <div class="kpi-title">Pendentes Gestor</div>
            <div class="kpi-value" style="color:{cor_pend};">{len(df_pend_ind)}</div>
            <div class="kpi-sub">Aguardando avaliação</div>
        </div>""", unsafe_allow_html=True)
    with d3:
        st.markdown(f"""<div class="kpi-card" style="border-left-color: #ef4444;">
            <div class="kpi-title">% Prioridade Alta</div>
            <div class="kpi-value" style="color:#ef4444;">{p_alta_i:.1f}%</div>
            <div class="kpi-sub">Sobre validados</div>
        </div>""", unsafe_allow_html=True)
    with d4:
        st.markdown(f"""<div class="kpi-card" style="border-left-color: #f59e0b;">
            <div class="kpi-title">% Prioridade Média</div>
            <div class="kpi-value" style="color:#f59e0b;">{p_med_i:.1f}%</div>
            <div class="kpi-sub">Sobre validados</div>
        </div>""", unsafe_allow_html=True)
    with d5:
        st.markdown(f"""<div class="kpi-card" style="border-left-color: #3b82f6;">
            <div class="kpi-title">% Prioridade Baixa</div>
            <div class="kpi-value" style="color:#3b82f6;">{p_bx_i:.1f}%</div>
            <div class="kpi-sub">Sobre validados</div>
        </div>""", unsafe_allow_html=True)
    with d6:
        st.markdown(f"""<div class="kpi-card" style="border-left-color: #10b981;">
            <div class="kpi-title">Total de Eventos</div>
            <div class="kpi-value">{len(df_hist)}</div>
            <div class="kpi-sub">{len(df_d_rv)} RV | {len(df_d_op)} Oper | {len(df_d_ab)} Abonos</div>
        </div>""", unsafe_allow_html=True)

    if not df_hist.empty:
        col_g360_1, col_g360_2 = st.columns([2, 3])
        with col_g360_1:
            df_med_colab = df_hist["Medida_Gestor"].value_counts().reset_index()
            df_med_colab.columns = ["Medida / Status", "Qtd"]
            fig_m_ind = px.bar(
                df_med_colab.sort_values("Qtd", ascending=True),
                y="Medida / Status",
                x="Qtd",
                orientation="h",
                color="Medida / Status",
                color_discrete_map=CORES_MEDIDAS,
                title="Resumo de Tratativas & Medidas do Colaborador",
                text_auto=True
            )
            fig_m_ind.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=260,
                margin=dict(l=10, r=10, t=40, b=10),
                showlegend=False,
                yaxis_title=""
            )
            st.plotly_chart(fig_m_ind, use_container_width=True)

        with col_g360_2:
            df_mot_colab = df_hist.groupby(["Motivo", "Status"]).size().reset_index(name="Qtd").sort_values("Qtd", ascending=True)
            fig_mot_ind = px.bar(
                df_mot_colab,
                y="Motivo",
                x="Qtd",
                color="Status",
                orientation="h",
                title="Incidências Registradas para o Colaborador (Por Status)",
                text_auto=True
            )
            fig_mot_ind.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=260,
                margin=dict(l=10, r=10, t=40, b=10),
                yaxis_title=""
            )
            st.plotly_chart(fig_mot_ind, use_container_width=True)

    # 1. OCORRÊNCIAS PENDENTES DE AVALIAÇÃO DO GESTOR
    st.markdown(f'<div class="section-header">1. Ocorrências Pendentes de Avaliação do Gestor ({len(df_pend_ind)})</div>', unsafe_allow_html=True)
    if not df_pend_ind.empty:
        st.dataframe(
            df_pend_ind[["ID", "Data", "Rota", "Motivo", "Prioridade", "Impacta_RV", "Registrado_Por", "Detalhe"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.caption("Não há ocorrências pendentes de avaliação para este colaborador.")

    # 2. OCORRÊNCIAS QUE IMPACTARAM A REMUNERAÇÃO VARIÁVEL
    st.markdown(f'<div class="section-header">2. Ocorrências Validadas com Impacto na Variável ({len(df_d_rv)})</div>', unsafe_allow_html=True)
    if not df_d_rv.empty:
        st.dataframe(
            df_d_rv[["ID", "Data", "Rota", "Motivo", "Prioridade", "Medida_Gestor", "Registrado_Por", "Detalhe", "Acao_Gestor", "Data_Tratativa", "Tem_Anexo"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.caption("Nenhuma ocorrência com desconto na Remuneração Variável no período.")

    # 3. OCORRÊNCIAS OPERACIONAIS (SEM IMPACTO RV)
    st.markdown(f'<div class="section-header">3. Histórico Operacional e Disciplinar Sem Impacto na RV ({len(df_d_op)})</div>', unsafe_allow_html=True)
    if not df_d_op.empty:
        st.dataframe(
            df_d_op[["ID", "Data", "Rota", "Motivo", "Prioridade", "Medida_Gestor", "Registrado_Por", "Detalhe", "Acao_Gestor", "Data_Tratativa", "Tem_Anexo"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.caption("Nenhum registro operacional sem impacto na variável no período.")

    # 4. OCORRÊNCIAS ABONADAS / JUSTIFICADAS
    st.markdown(f'<div class="section-header">4. Ocorrências Justificadas / Abonadas ({len(df_d_ab)})</div>', unsafe_allow_html=True)
    if not df_d_ab.empty:
        st.dataframe(
            df_d_ab[["ID", "Data", "Rota", "Motivo", "Prioridade", "Medida_Gestor", "Registrado_Por", "Detalhe", "Acao_Gestor", "Data_Tratativa", "Tem_Anexo"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.caption("Nenhum abono registrado para este colaborador no período.")

    df_anexos_colab = df_hist[df_hist["Tem_Anexo"] == "Sim"] if not df_hist.empty else pd.DataFrame()
    if not df_anexos_colab.empty:
        st.markdown('<div class="section-header">Documentos e Evidências Anexadas ao Prontuário</div>', unsafe_allow_html=True)
        id_anx_360 = st.selectbox(
            "Selecionar documento do colaborador:",
            df_anexos_colab.apply(lambda r: f"#{r['ID']} - {r['Data']} | {r['Motivo']} ({r['Medida_Gestor']})", axis=1).tolist()
        )
        if st.button("Visualizar / Baixar Documento"):
            id_b360 = int(id_anx_360.split("#")[1].split(" -")[0])
            n_360, m_360, b_360 = buscar_anexo_no_banco(id_b360)
            if b_360:
                bytes_360 = base64.b64decode(b_360)
                st.download_button(label=f"Baixar {n_360}", data=bytes_360, file_name=n_360, mime=m_360)
                if m_360.startswith("image/"):
                    st.image(bytes_360, caption=f"Documento Ocorrência #{id_b360}", use_container_width=True)


# ==============================================================================
# 06. CADASTROS & PARÂMETROS (EXCLUSIVO GESTORES)
# ==============================================================================
elif pagina == "06. Cadastros & Parâmetros":
    if not is_gestor:
        st.error("Acesso não autorizado para o seu perfil.")
        st.stop()

    st.markdown("""
    <div class="page-header">
        <div class="page-title">Configurações de Efetivo & Regras de Negócio</div>
        <div class="page-subtitle">Gerenciamento de motoristas, ajudantes, matriz de motivos e pesos de desconto da Remuneração Variável</div>
    </div>
    """, unsafe_allow_html=True)

    aba_lote, aba_ind, aba_regras, aba_limpar = st.tabs([
        "Importação em Lote",
        "Cadastro Individual",
        "Matriz de Motivos & Regras RV",
        "Manutenção de Base"
    ])

    with aba_lote:
        st.markdown('<div class="section-header">Importação de Efetivo (Formato: Nome;Função)</div>', unsafe_allow_html=True)
        texto_lote = st.text_area("Lista de Colaboradores:", height=150, placeholder="Carlos Eduardo;Motorista\nJoão Silva;Ajudante")
        if st.button("Atualizar Efetivo Cadastrado", use_container_width=True, type="primary"):
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
                    st.success(f"{len(novos_dados)} colaboradores atualizados.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
        st.dataframe(df_colab, use_container_width=True, hide_index=True)

    with aba_ind:
        c_add, c_rem = st.columns(2)
        with c_add:
            st.markdown('<div class="section-header">Incluir Colaborador</div>', unsafe_allow_html=True)
            novo_nome = st.text_input("Nome Completo:")
            nova_func = st.selectbox("Cargo:", ["Motorista", "Ajudante"])
            if st.button("Salvar Cadastro", use_container_width=True) and novo_nome.strip() and engine:
                with engine.begin() as conn:
                    conn.execute(
                        text("INSERT INTO colaboradores (colaborador, funcao) VALUES (:c, :f) ON CONFLICT (colaborador) DO UPDATE SET funcao = :f"),
                        {"c": novo_nome.strip().title(), "f": nova_func}
                    )
                st.cache_data.clear()
                st.success("Colaborador cadastrado.")
                st.rerun()
        with c_rem:
            st.markdown('<div class="section-header">Remover Colaborador</div>', unsafe_allow_html=True)
            lista_atuais = sorted(df_colab["Colaborador"].unique().tolist()) if not df_colab.empty else []
            if lista_atuais:
                rem_nome = st.selectbox("Selecionar:", lista_atuais)
                if st.button("Excluir Colaborador", use_container_width=True) and engine:
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM colaboradores WHERE colaborador = :c"), {"c": rem_nome})
                    st.cache_data.clear()
                    st.warning(f"{rem_nome} removido.")
                    st.rerun()

    with aba_regras:
        st.markdown('<div class="section-header">Parametrização de Motivos, Prioridades e Penalidades RV</div>', unsafe_allow_html=True)
        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns([3, 1.5, 1.2, 1.2, 1.2])
        n_mot = col_m1.text_input("Descrição do Motivo:")
        n_prio = col_m2.selectbox("Prioridade Padrão:", ["Alta", "Média", "Baixa", "Positivo"])
        n_rv = col_m3.selectbox("Impacta RV?", ["Sim", "Não"])
        n_p1 = col_m4.number_input("Perda 1ª Ocorr (%):", min_value=0, max_value=100, value=20 if n_rv == "Sim" else 0, step=10)
        n_p2 = col_m5.number_input("Perda 2+ Ocorr (%):", min_value=0, max_value=100, value=100 if n_rv == "Sim" else 0, step=10)

        if st.button("Adicionar Motivo à Matriz", use_container_width=True) and n_mot.strip() and engine:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO motivos (motivo, prioridade, impacta_rv, perda_1_ocorr, perda_2_ou_mais)
                    VALUES (:m, :pr, :rv, :p1, :p2)
                    ON CONFLICT (motivo) DO UPDATE
                    SET prioridade = :pr, impacta_rv = :rv, perda_1_ocorr = :p1, perda_2_ou_mais = :p2
                """), {"m": n_mot.strip().upper(), "pr": n_prio, "rv": n_rv, "p1": int(n_p1), "p2": int(n_p2)})
            st.cache_data.clear()
            st.success("Motivo incluído.")
            st.rerun()

        df_mot_editado = st.data_editor(
            df_motivos,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Prioridade": st.column_config.SelectboxColumn("Prioridade", options=["Alta", "Média", "Baixa", "Positivo"], required=True),
                "Impacta_RV": st.column_config.SelectboxColumn("Impacta RV?", options=["Sim", "Não"], required=True),
                "Perda_1_Ocorr_%": st.column_config.NumberColumn("% Perda (1ª Vez)", min_value=0, max_value=100, step=10),
                "Perda_2_Mais_%": st.column_config.NumberColumn("% Perda (2+ Vezes)", min_value=0, max_value=100, step=10),
            }
        )

        if st.button("Salvar Alterações na Matriz de Motivos", type="primary", use_container_width=True) and engine:
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
            st.success("Matriz de motivos atualizada.")
            st.rerun()

    with aba_limpar:
        st.markdown('<div class="section-header">Redefinição de Base de Ocorrências</div>', unsafe_allow_html=True)
        st.warning("Ação irreversível: Remove todos os apontamentos e anexos registrados no banco de dados.")
        if st.button("Confirmar Limpeza Total de Ocorrências") and engine:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM ocorrencias"))
                conn.execute(text("DELETE FROM ocorrencias_anexos"))
            st.cache_data.clear()
            st.success("Registros removidos.")
            st.rerun()
