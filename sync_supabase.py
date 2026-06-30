"""
sync_supabase.py
Sincroniza clientes da região de São Carlos para o Supabase (tabela clientes).
Popula também a carteira do Johnny (SC01) com os clientes disponíveis.

Roda via Task Scheduler ou manualmente:
    python sync_supabase.py

Coloque na pasta:
    C:\\Users\\accrisci\\Desktop\\Artur\\Projetos\\Projeto_19_Mapa_Clientes_Sao_Carlos\\
"""

import logging
import sys
import os
from datetime import date, datetime

import pandas as pd
import psycopg2
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env", override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("sync_supabase.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── Configurações ──────────────────────────────────────────────────────────────

TOTVS_CSV = r"\\192.168.0.226\pdi\in\full\totvs_cliente.csv"

PG_MAPA = dict(host="192.168.0.242", port=5432, dbname="mapa_clientes",
               user="postgres", password="Postgres2025")
PG_ERP  = dict(host="192.168.0.242", port=5432, dbname="erp_progress",
               user="postgres", password="Postgres2025")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://pyiybinbsnouxdtnfcpe.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

IBGE_ALVO = {3548906, 3503208, 3519055, 3523404}
IBGE_CIDADE = {
    3548906: "São Carlos",
    3503208: "Araraquara",
    3519055: "Ibaté",
    3523404: "Itirapina",
}
NOMERC_VALIDOS   = {"DISPONIVEL - FS", ""}
NOMERC_EXCLUIDOS = {"EXPORTAÇÃO", "CLIENTE PLATAFORMA"}
DIAS_INATIVO     = 60

COD_VENDEDOR_JOHNNY = "SC01"


# ── Step 1: Carrega e filtra TOTVS ────────────────────────────────────────────

def carregar_totvs() -> pd.DataFrame:
    logger.info(f"Lendo CSV: {TOTVS_CSV}")
    df = pd.read_csv(TOTVS_CSV, encoding="latin1", sep=";", dtype=str)
    logger.info(f"  {len(df):,} clientes no CSV total.")

    ibge_str = {str(i) for i in IBGE_ALVO}
    mask_ibge      = df["cod-ibge"].str.strip().isin(ibge_str)
    mask_ativo     = df["status-cliente"].str.strip() == "Ativo"
    mask_nomerc    = df["NomERC"].fillna("").str.strip().isin(NOMERC_VALIDOS)
    mask_excluidos = df["NomERC"].fillna("").str.strip().isin(NOMERC_EXCLUIDOS)

    # Disponíveis (azul — carteira Johnny)
    df_disp = df[mask_ibge & mask_ativo & mask_nomerc].copy()
    df_disp["tipo_cliente"] = "disponivel"

    # Com representante (verde/laranja/vermelho)
    cods_disp = set(df_disp["cod-cliente"].str.strip())
    df_outros = df[mask_ibge & mask_ativo & ~mask_excluidos].copy()
    df_outros = df_outros[~df_outros["cod-cliente"].str.strip().isin(cods_disp)].copy()
    df_outros["tipo_cliente"] = "sem_compra"

    df_final = pd.concat([df_disp, df_outros], ignore_index=True)

    df_final = df_final.rename(columns={
        "cod-cliente":  "cod_cliente",
        "nome-cliente": "nome_cliente",
        "limite-disp":  "limite_disp",
        "lat-cliente":  "lat_totvs",
        "long-cliente": "lng_totvs",
        "endereco":     "endereco",
        "bairro":       "bairro",
        "cep":          "cep",
        "cod-ibge":     "cod_ibge",
        "telefone":     "telefone",
        "cnpj":         "cnpj",
    })

    df_final["cod_cliente"]  = df_final["cod_cliente"].str.strip()
    df_final["cod_ibge"]     = pd.to_numeric(df_final["cod_ibge"], errors="coerce").astype("Int64")
    df_final["limite_disp"]  = pd.to_numeric(df_final["limite_disp"], errors="coerce")
    df_final["cidade"]       = df_final["cod_ibge"].map(IBGE_CIDADE).fillna("Desconhecida")
    df_final["fonte"]        = "sao_carlos"

    df_final = df_final.drop_duplicates(subset="cod_cliente", keep="first")
    logger.info(f"  Após filtros: {len(df_final):,} clientes ({df_disp['cod-cliente'].nunique()} disponíveis)")
    return df_final


# ── Step 2: Coordenadas do checkpoint ─────────────────────────────────────────

def carregar_coordenadas() -> pd.DataFrame:
    logger.info("Carregando coordenadas do checkpoint...")
    conn = psycopg2.connect(**PG_MAPA)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cod_cliente,
                       lat_google  AS lat_final,
                       lng_google  AS lng_final
                FROM geocodificacao_checkpoint
                WHERE valido = true
            """)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        logger.info(f"  {len(df):,} coordenadas no checkpoint.")
        return df
    finally:
        conn.close()


# ── Step 3: Histórico de faturamento ──────────────────────────────────────────

def carregar_historico() -> pd.DataFrame:
    logger.info("Carregando histórico de faturamento...")
    conn = psycopg2.connect(**PG_ERP)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    cod_cliente,
                    MAX(data_emissao)  AS ultima_compra,
                    SUM(valor_item_nf) AS total_faturado
                FROM faturamento_nf
                GROUP BY cod_cliente
            """)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        df["cod_cliente"] = df["cod_cliente"].astype(str).str.strip()
        logger.info(f"  {len(df):,} clientes com faturamento.")
        return df
    finally:
        conn.close()


# ── Step 4: Calcula status_compra ─────────────────────────────────────────────

def calcular_status(df: pd.DataFrame) -> pd.DataFrame:
    hoje = pd.Timestamp(date.today())
    df["ultima_compra"]   = pd.to_datetime(df["ultima_compra"], errors="coerce")
    df["dias_sem_compra"] = (hoje - df["ultima_compra"]).dt.days.astype("Int64")

    def _status(row):
        if row["tipo_cliente"] == "disponivel":
            return "disponivel"
        if pd.isna(row.get("ultima_compra")):
            return "nunca_comprou"
        if row["dias_sem_compra"] <= DIAS_INATIVO:
            return "ativo"
        return "inativo"

    df["status_compra"] = df.apply(_status, axis=1)
    return df


# ── Step 5: Upsert clientes no Supabase ───────────────────────────────────────

def upsert_clientes(df: pd.DataFrame, supabase: Client):
    logger.info("Fazendo upsert de clientes no Supabase...")

    registros = []
    for _, row in df.iterrows():
        def sv(val):
            if val is None: return None
            try:
                if pd.isna(val): return None
            except (TypeError, ValueError):
                pass
            return val

        ultima = sv(row.get("ultima_compra"))
        if ultima is not None and hasattr(ultima, 'date'):
            ultima = ultima.date().isoformat()
        elif ultima is not None:
            ultima = str(ultima)[:10]

        registros.append({
            "cod_cliente":     str(row["cod_cliente"]),
            "nome_cliente":    sv(row.get("nome_cliente")),
            "cnpj":            sv(row.get("cnpj")),
            "endereco":        sv(row.get("endereco")),
            "bairro":          sv(row.get("bairro")),
            "cep":             sv(row.get("cep")),
            "telefone":        sv(row.get("telefone")),
            "cod_ibge":        int(row["cod_ibge"]) if pd.notna(row.get("cod_ibge")) else None,
            "cidade":          sv(row.get("cidade")),
            "lat_final":       float(row["lat_final"]) if pd.notna(row.get("lat_final")) else None,
            "lng_final":       float(row["lng_final"]) if pd.notna(row.get("lng_final")) else None,
            "limite_disp":     float(row["limite_disp"]) if pd.notna(row.get("limite_disp")) else None,
            "tipo_cliente":    sv(row.get("tipo_cliente")),
            "status_compra":   sv(row.get("status_compra")),
            "ultima_compra":   ultima,
            "dias_sem_compra": int(row["dias_sem_compra"]) if pd.notna(row.get("dias_sem_compra")) else None,
            "total_faturado":  float(row["total_faturado"]) if pd.notna(row.get("total_faturado")) else None,
            "fonte":           sv(row.get("fonte")),
            "updated_at":      datetime.utcnow().isoformat(),
        })

    BATCH = 500
    total = 0
    for i in range(0, len(registros), BATCH):
        lote = registros[i:i+BATCH]
        supabase.table("clientes").upsert(lote, on_conflict="cod_cliente").execute()
        total += len(lote)
        logger.info(f"  Upsert: {total}/{len(registros)}")

    logger.info(f"  Clientes sincronizados: {len(registros)}")


# ── Step 6: Sincroniza carteira do Johnny ─────────────────────────────────────

def sincronizar_carteira(df: pd.DataFrame, supabase: Client):
    logger.info(f"Sincronizando carteira do Johnny ({COD_VENDEDOR_JOHNNY})...")

    df_disp = df[df["tipo_cliente"] == "disponivel"].copy()
    cods_johnny = set(df_disp["cod_cliente"].astype(str))

    res = supabase.table("carteira").select("cod_cliente").eq("cod_vendedor", COD_VENDEDOR_JOHNNY).execute()
    cods_existentes = {r["cod_cliente"] for r in res.data}

    novos = cods_johnny - cods_existentes
    if novos:
        registros = [
            {"cod_cliente": c, "cod_vendedor": COD_VENDEDOR_JOHNNY, "ativo": True}
            for c in novos
        ]
        supabase.table("carteira").insert(registros).execute()
        logger.info(f"  {len(novos)} novos clientes adicionados à carteira do Johnny.")

    saiu = cods_existentes - cods_johnny
    if saiu:
        for c in saiu:
            supabase.table("carteira").update({"ativo": False}).eq("cod_cliente", c).eq("cod_vendedor", COD_VENDEDOR_JOHNNY).execute()
        logger.info(f"  {len(saiu)} clientes marcados como inativos na carteira.")

    if not novos and not saiu:
        logger.info("  Carteira já está atualizada.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("SYNC SUPABASE — São Carlos")
    logger.info("=" * 60)

    if not SUPABASE_KEY:
        logger.error("SUPABASE_SERVICE_ROLE_KEY não encontrada no .env")
        sys.exit(1)

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. TOTVS
    df = carregar_totvs()

    # 2. Coordenadas
    df_coords = carregar_coordenadas()
    df = df.merge(df_coords, on="cod_cliente", how="left")

    import numpy as np
    df["lat_totvs"] = pd.to_numeric(df.get("lat_totvs"), errors="coerce")
    df["lng_totvs"] = pd.to_numeric(df.get("lng_totvs"), errors="coerce")
    df["lat_final"] = df["lat_final"].combine_first(df["lat_totvs"])
    df["lng_final"] = df["lng_final"].combine_first(df["lng_totvs"])

    # 3. Histórico
    df_hist = carregar_historico()
    df["cod_cliente_int"] = pd.to_numeric(df["cod_cliente"], errors="coerce")
    df_hist["cod_cliente_int"] = pd.to_numeric(df_hist["cod_cliente"], errors="coerce")
    df = df.merge(df_hist[["cod_cliente_int", "ultima_compra", "total_faturado"]],
                  on="cod_cliente_int", how="left")
    df = df.drop(columns=["cod_cliente_int"])

    # 4. Status
    df = calcular_status(df)

    # 5. Upsert clientes
    upsert_clientes(df, supabase)

    # 6. Carteira Johnny
    sincronizar_carteira(df, supabase)

    logger.info("\n✅ Sync concluído.")


if __name__ == "__main__":
    main()