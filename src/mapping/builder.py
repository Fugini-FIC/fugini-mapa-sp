# ============================================================
# src/mapping/builder.py
# Gera os mapas Folium para São Paulo e Região.
# 4 vendedores (SP01-SP04) + 1 master, cada um com sua carteira.
#
# Cores por status de compra:
#   verde   (#27ae60) — ativo (comprou nos últimos 60 dias)
#   laranja (#e67e22) — inativo (comprou há mais de 60 dias)
#   vermelho (#e74c3c) — nunca comprou
# ============================================================

import json
import logging
import pandas as pd
import folium
import folium.plugins
from pathlib import Path

from config.settings import USUARIOS_MAPA, USUARIO_PARA_COD_VENDEDOR, COR_AREA, NOME_REGIAO, CRM_BASE_URL
from src.mapping.crypto      import criptografar_html
from src.mapping.roteamento  import gerar_roteamento_html

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Cores por status
COR_STATUS = {
    "ativo":         {"border": "#27ae60", "fill": "#2ecc71"},
    "inativo":       {"border": "#e67e22", "fill": "#f39c12"},
    "nunca_comprou": {"border": "#c0392b", "fill": "#e74c3c"},
    "disponivel":    {"border": "#2980b9", "fill": "#3498db"},
}

LABEL_STATUS = {
    "ativo":         "Ativos (≤ 60 dias)",
    "inativo":       "Inativos (> 60 dias)",
    "nunca_comprou": "Nunca compraram",
    "disponivel":    "Disponíveis (sem representante)",
}

CASO_STATUS = {
    "ativo":         "Com Representante - Ativo",
    "inativo":       "Com Representante - Inativo",
    "nunca_comprou": "Com Representante - Nunca Comprou",
    "disponivel":    "Disponível",
}


def _safe_str(val, default="-") -> str:
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return default if s.lower() in ("nan", "none", "nat", "") else s


def _safe_float(val, default=0.0) -> float:
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_date(val, default="-") -> str:
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
        return pd.Timestamp(val).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return default


def _build_export_data(df: pd.DataFrame, df_prospects: pd.DataFrame | None) -> str:
    registros = []

    for status, caso in [("ativo", "ativo"), ("inativo", "inativo"), ("nunca_comprou", "nunca_comprou")]:
        if "status_compra" not in df.columns:
            continue
        df_s = df[df["status_compra"] == status]
        for _, row in df_s.iterrows():
            if not pd.notna(row.get("lat_final")) or not pd.notna(row.get("lng_final")):
                continue
            dias = row.get("dias_sem_compra")
            registros.append({
                "caso":           caso,
                "cod":            _safe_str(row.get("cod_cliente"), "-"),
                "nome":           _safe_str(row.get("nome_cliente"), "-"),
                "cidade":         _safe_str(row.get("cidade"), "-"),
                "endereco":       _safe_str(row.get("endereco"), "-"),
                "bairro":         _safe_str(row.get("bairro"), "-"),
                "cep":            _safe_str(row.get("cep"), "-"),
                "telefone":       _safe_str(row.get("telefone"), "-"),
                "cnpj":           _safe_str(row.get("cnpj"), "-"),
                "representante":  _safe_str(row.get("representante"), "-"),
                "credito":        _safe_float(row.get("limite_disp")),
                "ultima_compra":  _safe_date(row.get("ultima_compra")),
                "dias_sem_compra": int(dias) if pd.notna(dias) else None,
                "total_faturado": _safe_float(row.get("total_faturado")),
            })

    if "tipo_cliente" in df.columns:
        df_disp = df[df["tipo_cliente"] == "disponivel"]
        for _, row in df_disp.iterrows():
            if not pd.notna(row.get("lat_final")) or not pd.notna(row.get("lng_final")):
                continue
            registros.append({
                "caso":           "disponivel",
                "cod":            _safe_str(row.get("cod_cliente"), "-"),
                "nome":           _safe_str(row.get("nome_cliente"), "-"),
                "cidade":         _safe_str(row.get("cidade"), "-"),
                "endereco":       _safe_str(row.get("endereco"), "-"),
                "bairro":         _safe_str(row.get("bairro"), "-"),
                "cep":            _safe_str(row.get("cep"), "-"),
                "telefone":       _safe_str(row.get("telefone"), "-"),
                "cnpj":           _safe_str(row.get("cnpj"), "-"),
                "representante":  "-",
                "credito":        _safe_float(row.get("limite_disp")),
                "ultima_compra":  "-",
                "dias_sem_compra": None,
                "total_faturado": 0.0,
            })

    if df_prospects is not None and not df_prospects.empty:
        for _, row in df_prospects.iterrows():
            if not pd.notna(row.get("lat_final")) or not pd.notna(row.get("lng_final")):
                continue
            nome = _safe_str(row.get("razao_social") or row.get("nome_fantasia"), "-")
            ende = f"{_safe_str(row.get('logradouro'))} {_safe_str(row.get('numero'))}".strip()
            registros.append({
                "caso":           "prospeccao",
                "cnae":           _safe_str(row.get("cnae"), "-"),
                "descricao_cnae": _safe_str(row.get("descricao_cnae"), "-"),
                "cod":            "-",
                "nome":           nome,
                "cidade":         _safe_str(row.get("municipio"), "-"),
                "endereco":       ende,
                "bairro":         _safe_str(row.get("bairro"), "-"),
                "cep":            _safe_str(row.get("cep"), "-"),
                "telefone":       "-",
                "cnpj":           _safe_str(row.get("cnpj"), "-"),
                "representante":  "-",
                "credito":        0.0,
                "ultima_compra":  "-",
                "dias_sem_compra": None,
                "total_faturado": 0.0,
            })

    return json.dumps(registros, ensure_ascii=False)


def _botao_exportar_html() -> str:
    return """
    <div style="border-top:1px solid #eee;margin-top:10px;padding-top:10px;">
      <button onclick="exportarSelecionados()"
              style="width:100%;padding:8px;background:#27ae60;color:white;border:none;
                     border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;
                     display:flex;align-items:center;justify-content:center;gap:6px;">
        📥 Exportar Selecionados
      </button>
      <div id="export-status" style="font-size:10px;color:#888;margin-top:4px;text-align:center;"></div>
    </div>

    <script>
    var CASO_LABELS = {
      "ativo":         "Com Representante - Ativo",
      "inativo":       "Com Representante - Inativo",
      "nunca_comprou": "Com Representante - Nunca Comprou",
      "disponivel":    "Disponível",
      "prospeccao":    "Prospecção"
    };

    var CHECKBOX_CASO = {
      "Ativos (≤ 60 dias)":              ["ativo"],
      "Inativos (> 60 dias)":            ["inativo"],
      "Nunca compraram":                 ["nunca_comprou"],
      "Disponíveis (sem representante)": ["disponivel"],
      "Sem representante":               ["disponivel"],
      "Clientes da carteira":            ["ativo", "inativo", "nunca_comprou"],
    };

    function getCasosSelecionados() {
      var casos = new Set();
      var cnaesSelecionados = new Set();
      document.querySelectorAll('#painel-resumo input[type=checkbox]').forEach(function(cb) {
        if (!cb.checked) return;
        var label = cb.closest('label');
        if (!label) return;
        var txt = label.textContent.trim().replace(/\s+/g, ' ');
        var nome = txt.replace(/\s*\(\d+\)\s*$/, '').trim();
        if (CHECKBOX_CASO[nome]) {
          CHECKBOX_CASO[nome].forEach(function(c) { casos.add(c); });
          return;
        }
        var nomeBase = nome.replace(/\s*\(\d+\)\s*$/, '').trim();
        var temProspect = (window.CLIENTES_EXPORT || []).some(function(c) {
          return c.caso === 'prospeccao' && c.descricao_cnae === nomeBase;
        });
        if (temProspect) {
          casos.add('prospeccao');
          cnaesSelecionados.add(nomeBase);
        }
      });
      return { casos: casos, cnaes: cnaesSelecionados };
    }

    function exportarSelecionados() {
      var status = document.getElementById('export-status');
      status.textContent = 'Carregando...';
      function _doExport() {
        var sel = getCasosSelecionados();
        var casosSel = sel.casos;
        var cnaesSel = sel.cnaes;
        if (casosSel.size === 0) { status.textContent = '⚠️ Nenhuma categoria selecionada.'; return; }
        var porCaso = {};
        (window.CLIENTES_EXPORT || []).forEach(function(c) {
          if (!casosSel.has(c.caso)) return;
          if (c.caso === 'prospeccao' && cnaesSel.size > 0 && !cnaesSel.has(c.descricao_cnae)) return;
          var label = CASO_LABELS[c.caso] || c.caso;
          if (!porCaso[label]) porCaso[label] = [];
          porCaso[label].push(c);
        });
        if (Object.keys(porCaso).length === 0) { status.textContent = '⚠️ Nenhum cliente encontrado.'; return; }
        var wb = XLSX.utils.book_new();
        var ordemAbas = ["Com Representante - Ativo","Com Representante - Inativo",
                         "Com Representante - Nunca Comprou","Disponível","Prospecção"];
        ordemAbas.forEach(function(label) {
          if (!porCaso[label]) return;
          var linhas = porCaso[label].map(function(c) {
            var linha = {
              'Caso': label, 'Código': c.cod, 'Cliente': c.nome, 'Cidade': c.cidade,
              'Endereço': c.endereco, 'Bairro': c.bairro, 'CEP': c.cep,
              'Telefone': c.telefone, 'CNPJ': c.cnpj, 'Representante': c.representante,
              'Crédito Disponível': c.credito, 'Última Compra': c.ultima_compra,
              'Dias Sem Compra': c.dias_sem_compra !== null ? c.dias_sem_compra : '-',
              'Faturamento Total': c.total_faturado,
            };
            if (c.caso === 'prospeccao') {
              linha['CNAE'] = c.cnae || '-';
              linha['Descrição CNAE'] = c.descricao_cnae || '-';
            }
            return linha;
          });
          var ws = XLSX.utils.json_to_sheet(linhas);
          ws['!cols'] = [{wch:32},{wch:10},{wch:35},{wch:18},{wch:35},{wch:20},{wch:12},
                         {wch:15},{wch:18},{wch:28},{wch:18},{wch:14},{wch:16},{wch:18}];
          var nomeAba = label.length > 31 ? label.substring(0, 31) : label;
          XLSX.utils.book_append_sheet(wb, ws, nomeAba);
        });
        var total = Object.values(porCaso).reduce(function(s, arr) { return s + arr.length; }, 0);
        XLSX.writeFile(wb, 'clientes_sao_paulo.xlsx');
        status.textContent = '✅ ' + total + ' clientes exportados.';
      }
      if (typeof XLSX === 'undefined') {
        var s = document.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
        s.onload = function() { _doExport(); };
        document.head.appendChild(s);
      } else { _doExport(); }
    }
    </script>
    """


def _df_credito_sem_duplicata_matriz(df: pd.DataFrame) -> pd.DataFrame:
    """
    O ERP replica o limite_disp da matriz em cada filial (mesmo CNPJ raiz,
    mesmo valor de crédito) — característica geral da tabela de clientes,
    NÃO específica de SP: medido em 06/08/2026, São Carlos inflava 2,76x e
    as carteiras SP entre 1,00x e 3,06x. Somar direto infla o total do
    Heatmap de Crédito. Esta função deduplica por CNPJ raiz SOMENTE quando
    o limite_disp é idêntico entre as filiais — preserva casos onde cada
    filial tem limite genuinamente diferente.

    Usada apenas para os cálculos de soma_cred/heat_data — não afeta
    os marcadores individuais no mapa (cada cliente continua sendo
    plotado normalmente). Mesma função existe no Projeto_19 (SC).
    """
    if "cnpj" not in df.columns:
        return df

    df = df.copy()
    df["_cnpj_raiz"] = df["cnpj"].astype(str).str.zfill(14).str[:8]

    # Para cada raiz, mantém só 1 linha SE todas as filiais tiverem o
    # mesmo limite_disp (sintoma de duplicação). Se os valores variarem
    # de verdade entre filiais, mantém todas as linhas.
    valores_por_raiz = df.groupby("_cnpj_raiz")["limite_disp"].nunique()
    raizes_duplicadas = valores_por_raiz[valores_por_raiz == 1].index

    mask_duplicada = df["_cnpj_raiz"].isin(raizes_duplicadas) & (df["_cnpj_raiz"] != "00000000")
    df_dedup = pd.concat([
        df[~mask_duplicada],
        df[mask_duplicada].drop_duplicates(subset="_cnpj_raiz", keep="first"),
    ])

    return df_dedup.drop(columns=["_cnpj_raiz"])


def montar_mapa(df: pd.DataFrame, df_prospects: pd.DataFrame | None = None,
                df_roteamento: pd.DataFrame | None = None, perfil: str = "master",
                cod_vendedor: str | None = None, mapa_senha: str | None = None) -> folium.Map:
    """
    perfil='vendedor' → painel mostra carteira completa (todos os status visíveis)
    perfil='master'   → painel mostra tudo separado por status
    df_roteamento     → DataFrame filtrado para roteamento
    """

    if df_roteamento is None:
        df_roteamento = df[df["tipo_cliente"] == "disponivel"] if "tipo_cliente" in df.columns else df

    mapa = folium.Map(location=[-23.55, -46.63], zoom_start=10, tiles="CartoDB positron")

    mapa.get_root().html.add_child(folium.Element(
        """<style>
        .leaflet-overlay-pane { pointer-events: none !important; }
        .leaflet-control-layers { display: none !important; }
        .leaflet-top.leaflet-left { right: 10px !important; left: auto !important; }
        </style>"""
    ))

    contagens = {}

    # ── Clientes com representante ──────────────────────────────────────────
    for status in ["ativo", "inativo", "nunca_comprou"]:
        label = LABEL_STATUS[status]
        show_default = (perfil == "vendedor") or (perfil == "master" and False)
        if perfil == "master":
            show_default = False
        fg = folium.FeatureGroup(name=label, show=show_default)
        df_status = df[df["status_compra"] == status] if "status_compra" in df.columns else pd.DataFrame()
        count = 0
        for _, row in df_status.iterrows():
            if not pd.notna(row.get("lat_final")) or not pd.notna(row.get("lng_final")):
                continue
            import urllib.parse
            nome     = _safe_str(row.get("nome_cliente"), "N/D")
            cod      = _safe_str(row.get("cod_cliente"),  "N/D")
            cidade   = _safe_str(row.get("cidade"), "N/D")
            credito  = _safe_float(row.get("limite_disp"))
            ult_nf   = _safe_date(row.get("ultima_compra"))
            fat      = _safe_float(row.get("total_faturado"))
            fat_fmt  = f"R$ {fat:,.2f}" if fat > 0 else "-"
            dias     = row.get("dias_sem_compra")
            dias_str = f"{int(dias)} dias" if pd.notna(dias) else "nunca comprou"
            rep      = _safe_str(row.get("representante"), "-")
            cor      = COR_STATUS[status]
            nome_encoded = urllib.parse.quote(nome)
            cod_vendedor_encoded = urllib.parse.quote(cod_vendedor or "")
            mapa_senha_encoded   = urllib.parse.quote(mapa_senha or "")
            popup_html = f"""
            <div style="font-family:Arial;font-size:12px;min-width:180px">
                <b>{nome}</b><br>
                <span style="color:#666">Cód: {cod}</span><br>
                <span style="color:#666">{cidade}</span><br>
                <span style="color:#666">Representante: {rep}</span><br>
                <span style="color:#666">Crédito disp.: R$ {credito:,.2f}</span><br>
                <span style="color:#666">Última NF: {ult_nf}</span><br>
                <span style="color:#666">Sem comprar: {dias_str}</span><br>
                <span style="color:#666">Faturamento total: {fat_fmt}</span><br>
                <a href="checkin.html?cod_cliente={cod}&nome_cliente={nome_encoded}&cod_vendedor={cod_vendedor_encoded}&mapa_senha={mapa_senha_encoded}"
                   style="display:inline-block;margin-top:8px;padding:5px 10px;
                          background:#D2001B;color:white;border-radius:5px;
                          font-size:11px;font-weight:700;text-decoration:none;">
                  📍 Check-in
                </a>
                <a href="{CRM_BASE_URL}/agenda?cod_cliente={cod}&nome_cliente={nome_encoded}"
                   target="_blank" rel="noopener"
                   style="display:inline-block;margin-top:8px;margin-left:4px;padding:5px 10px;
                          background:#fff;color:#1a1a2e;border:1px solid #ccc;border-radius:5px;
                          font-size:11px;font-weight:700;text-decoration:none;">
                  📅 Agendar
                </a>
            </div>"""
            folium.CircleMarker(
                location=[float(row["lat_final"]), float(row["lng_final"])],
                radius=6, color=cor["border"], fill=True,
                fill_color=cor["fill"], fill_opacity=0.85,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=folium.Tooltip(f"{nome} — {dias_str}"),
            ).add_to(fg)
            count += 1
        fg.add_to(mapa)
        contagens[status] = count

    # ── Disponíveis ─────────────────────────────────────────────────────────
    df_disp = df[df["tipo_cliente"] == "disponivel"] if "tipo_cliente" in df.columns else pd.DataFrame()
    fg_disp = folium.FeatureGroup(name=LABEL_STATUS["disponivel"], show=True)
    count_disp = 0
    for _, row in df_disp.iterrows():
        if not pd.notna(row.get("lat_final")) or not pd.notna(row.get("lng_final")):
            continue
        import urllib.parse
        nome    = _safe_str(row.get("nome_cliente"), "N/D")
        cod     = _safe_str(row.get("cod_cliente"),  "N/D")
        cidade  = _safe_str(row.get("cidade"), "N/D")
        credito = _safe_float(row.get("limite_disp"))
        cor     = COR_STATUS["disponivel"]
        nome_encoded = urllib.parse.quote(nome)
        cod_vendedor_encoded = urllib.parse.quote(cod_vendedor or "")
        mapa_senha_encoded   = urllib.parse.quote(mapa_senha or "")
        popup_html = f"""
        <div style="font-family:Arial;font-size:12px;min-width:180px">
            <b>{nome}</b><br>
            <span style="color:#3498db;font-weight:700;font-size:10px">DISPONÍVEL</span><br>
            <span style="color:#666">Cód: {cod}</span><br>
            <span style="color:#666">{cidade}</span><br>
            <span style="color:#666">Crédito disp.: R$ {credito:,.2f}</span><br>
            <a href="checkin.html?cod_cliente={cod}&nome_cliente={nome_encoded}&cod_vendedor={cod_vendedor_encoded}&mapa_senha={mapa_senha_encoded}"
               style="display:inline-block;margin-top:8px;padding:5px 10px;
                      background:#D2001B;color:white;border-radius:5px;
                      font-size:11px;font-weight:700;text-decoration:none;">
              📍 Check-in
            </a>
            <a href="{CRM_BASE_URL}/agenda?cod_cliente={cod}&nome_cliente={nome_encoded}"
               target="_blank" rel="noopener"
               style="display:inline-block;margin-top:8px;margin-left:4px;padding:5px 10px;
                      background:#fff;color:#1a1a2e;border:1px solid #ccc;border-radius:5px;
                      font-size:11px;font-weight:700;text-decoration:none;">
              📅 Agendar
            </a>
        </div>"""
        folium.CircleMarker(
            location=[float(row["lat_final"]), float(row["lng_final"])],
            radius=6, color=cor["border"], fill=True,
            fill_color=cor["fill"], fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=folium.Tooltip(f"{nome} — Disponível"),
        ).add_to(fg_disp)
        count_disp += 1
    fg_disp.add_to(mapa)
    contagens["disponivel"] = count_disp

    # ── Heatmap ─────────────────────────────────────────────────────────────
    # Usa df deduplicado por CNPJ raiz para não inflar o crédito agregado
    # quando o mesmo limite está replicado entre filiais da mesma matriz.
    df_credito = _df_credito_sem_duplicata_matriz(df)
    fg_heat = folium.FeatureGroup(name="Heatmap Crédito", show=False)
    heat_data = [
        [float(row["lat_final"]), float(row["lng_final"]), float(row["limite_disp"])]
        for _, row in df_credito.iterrows()
        if pd.notna(row.get("lat_final")) and pd.notna(row.get("lng_final"))
        and pd.notna(row.get("limite_disp")) and float(row.get("limite_disp", 0)) > 0
        and row.get("geo_valida_final", True)
    ]
    if heat_data:
        folium.plugins.HeatMap(heat_data, min_opacity=0.3, radius=20, blur=15).add_to(fg_heat)
    fg_heat.add_to(mapa)

    # ── Prospects ────────────────────────────────────────────────────────────
    if df_prospects is not None and not df_prospects.empty:
        for cnae in sorted(df_prospects["cnae"].dropna().unique()):
            df_cnae   = df_prospects[df_prospects["cnae"] == cnae]
            descricao = df_cnae["descricao_cnae"].iloc[0] if not df_cnae.empty else cnae
            fg_p      = folium.FeatureGroup(name=f"Prospect: {descricao}", show=False)
            for _, row in df_cnae.iterrows():
                nome   = _safe_str(row.get("razao_social") or row.get("nome_fantasia"), "N/D")
                cnpj   = _safe_str(row.get("cnpj"), "N/D")
                ende   = f"{_safe_str(row.get('logradouro'))} {_safe_str(row.get('numero'))}".strip()
                bairro = _safe_str(row.get("bairro"))
                cidade = _safe_str(row.get("municipio"))
                popup_html = f"""
                <div style="font-family:Arial;font-size:12px;min-width:180px">
                    <b>{nome}</b><br>
                    <span style="color:#888;font-size:10px">PROSPECT</span><br>
                    <span style="color:#666">CNPJ: {cnpj}</span><br>
                    <span style="color:#666">CNAE: {descricao}</span><br>
                    <span style="color:#666">{ende}</span><br>
                    <span style="color:#666">{bairro} — {cidade}</span>
                </div>"""
                folium.CircleMarker(
                    location=[float(row["lat_final"]), float(row["lng_final"])],
                    radius=4, color="#888888", fill=True,
                    fill_color="#aaaaaa", fill_opacity=0.5,
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=folium.Tooltip(f"{nome} — {descricao}"),
                ).add_to(fg_p)
            fg_p.add_to(mapa)

    # ── Painel lateral ───────────────────────────────────────────────────────
    export_data_js = _build_export_data(df, df_prospects)
    soma_cred      = df_credito["limite_disp"].fillna(0).sum()
    cred_fmt       = f"R$ {soma_cred/1_000:.0f}K" if soma_cred >= 1_000 else f"R$ {soma_cred:,.0f}"
    total_com_dono = contagens.get("ativo", 0) + contagens.get("inativo", 0) + contagens.get("nunca_comprou", 0)
    n_disp         = contagens.get("disponivel", 0)
    cor_disp       = COR_STATUS["disponivel"]
    label_disp     = LABEL_STATUS["disponivel"]

    com_dono_html = ""
    if perfil == "vendedor":
        n = total_com_dono
        com_dono_html = f"""
      <div style="font-size:11px;font-weight:700;color:#444;margin-bottom:6px;">
        👥 CARTEIRA ({n})
      </div>
      <label style="display:flex;align-items:center;cursor:pointer;gap:6px;margin-bottom:5px;">
        <input type="checkbox" checked
               onchange="toggleCarteira(this.checked)"
               style="width:13px;height:13px;cursor:pointer;accent-color:#c0392b;">
        <span style="display:inline-block;width:10px;height:10px;border-radius:50%;
                     background:#e74c3c;border:1.5px solid #c0392b;flex-shrink:0;"></span>
        <span style="font-size:11px;color:#333;">Clientes da carteira <b>({n})</b></span>
      </label>
      <div style="border-top:1px solid #eee;margin-top:8px;padding-top:8px;"></div>"""
    elif perfil == "master":
        linhas = ""
        for status in ["ativo", "inativo", "nunca_comprou"]:
            cor   = COR_STATUS[status]
            label = LABEL_STATUS[status]
            n     = contagens.get(status, 0)
            linhas += f"""
      <label style="display:flex;align-items:center;cursor:pointer;gap:6px;margin-bottom:5px;">
        <input type="checkbox"
               onchange="toggleLayer('{label}', this.checked)"
               style="width:13px;height:13px;cursor:pointer;accent-color:{cor['border']};">
        <span style="display:inline-block;width:10px;height:10px;border-radius:50%;
                     background:{cor['fill']};border:1.5px solid {cor['border']};flex-shrink:0;"></span>
        <span style="font-size:11px;color:#333;">{label} <b>({n})</b></span>
      </label>"""
        com_dono_html = f"""
      <div style="font-size:11px;font-weight:700;color:#444;margin-bottom:6px;">
        👥 COM REPRESENTANTE ({total_com_dono})
      </div>
      {linhas}
      <div style="border-top:1px solid #eee;margin-top:8px;padding-top:8px;"></div>"""

    prospects_html = ""
    if df_prospects is not None and not df_prospects.empty:
        cnaes = (
            df_prospects.groupby(["cnae", "descricao_cnae"])
            .size().reset_index(name="n")
            .sort_values("n", ascending=False)
        )
        linhas_cnae = ""
        for _, row in cnaes.iterrows():
            layer_name = f"Prospect: {row['descricao_cnae']}"
            linhas_cnae += f"""
          <label style="display:flex;align-items:center;cursor:pointer;gap:6px;margin-bottom:4px;">
            <input type="checkbox"
                   onchange="toggleLayer('{layer_name}', this.checked)"
                   style="width:13px;height:13px;cursor:pointer;accent-color:#888;">
            <span style="display:inline-block;width:9px;height:9px;border-radius:50%;
                         background:#aaa;flex-shrink:0;"></span>
            <span style="font-size:10px;color:#555;">{row['descricao_cnae']} ({row['n']})</span>
          </label>"""
        prospects_html = f"""
        <div style="border-top:1px solid #eee;margin-top:8px;padding-top:8px;">
          <div onclick="toggleProspects()" style="font-size:11px;font-weight:700;color:#888;
               margin-bottom:6px;cursor:pointer;display:flex;align-items:center;
               justify-content:space-between;user-select:none;">
            <span>🎯 PROSPECÇÃO ({len(df_prospects):,})</span>
            <span id="prospect-arrow" style="font-size:10px;">▶</span>
          </div>
          <div id="lista-cnaes" style="display:none;">
            {linhas_cnae}
          </div>
        </div>
        <script>
        function toggleProspects() {{
          var lista = document.getElementById('lista-cnaes');
          var arrow = document.getElementById('prospect-arrow');
          if (lista.style.display === 'none') {{
            lista.style.display = 'block';
            arrow.textContent = '▼';
          }} else {{
            lista.style.display = 'none';
            arrow.textContent = '▶';
          }}
        }}
        </script>"""

    botao_exportar = _botao_exportar_html()

    navbar_html, conteudo_roteiro_html = gerar_roteamento_html(df_roteamento, df_prospects, cod_vendedor=cod_vendedor)

    if perfil == "master":
        disp_html = f"""
        <div style="font-size:11px;font-weight:700;color:#2980b9;margin-bottom:6px;">
          🔵 DISPONÍVEIS ({n_disp})
        </div>
        <label style="display:flex;align-items:center;cursor:pointer;gap:6px;margin-bottom:5px;">
          <input type="checkbox" checked
                 onchange="toggleLayer('{label_disp}', this.checked)"
                 style="width:13px;height:13px;cursor:pointer;accent-color:{cor_disp['border']};">
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;
                       background:{cor_disp['fill']};border:1.5px solid {cor_disp['border']};flex-shrink:0;"></span>
          <span style="font-size:11px;color:#333;">Sem representante <b>({n_disp})</b></span>
        </label>"""
    else:
        disp_html = ""

    painel_abas_html = f"""
    <div id="painel-unificado" style="
        position: fixed; top: 54px; left: 10px; z-index: 1000;
        background: rgba(255,255,255,0.97); border-radius: 10px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.15);
        width: 245px;
        font-family: 'Segoe UI', Arial, sans-serif;
        max-height: calc(90vh - 64px);
        display: flex; flex-direction: column;
        transition: width 0.2s;
    ">
      <div style="display:flex;border-bottom:1px solid #eee;border-radius:10px 10px 0 0;overflow:hidden;">
        <button id="aba-filtros" onclick="trocarAba('filtros')" style="
            flex:1;padding:9px 0;font-size:11px;font-weight:700;border:none;cursor:pointer;
            background:#D2001B;color:white;border-radius:10px 0 0 0;">
          📊 Filtros
        </button>
        <button id="aba-roteiro" onclick="trocarAba('roteiro')" style="
            flex:1;padding:9px 0;font-size:11px;font-weight:700;border:none;cursor:pointer;
            background:#f5f5f5;color:#888;">
          🗺️ Roteiro
        </button>
        <button onclick="togglePainel()" id="btn-colapsar" style="
            width:28px;padding:0;font-size:13px;font-weight:700;border:none;cursor:pointer;
            background:#eee;color:#555;border-radius:0 10px 0 0;flex-shrink:0;">
          ‹
        </button>
      </div>

      <div id="conteudo-filtros" style="padding:14px 16px;overflow-y:auto;max-height:calc(90vh - 110px);">
        <div style="font-size:12px;font-weight:700;color:#e74c3c;margin-bottom:10px;">
          📊 {NOME_REGIAO.upper()}
        </div>
        {com_dono_html}
        {disp_html}
        <div style="border-top:1px solid #eee;margin-top:8px;padding-top:8px;">
          <label style="display:flex;align-items:center;cursor:pointer;gap:6px;">
            <input type="checkbox"
                   onchange="toggleLayer('Heatmap Crédito', this.checked)"
                   style="width:13px;height:13px;cursor:pointer;">
            <span style="font-size:11px;color:#555;">🔥 Heatmap Crédito</span>
          </label>
          <div style="padding-left:20px;font-size:10px;color:#888;margin-top:2px;">
            {cred_fmt} disponível
          </div>
        </div>
        {prospects_html}
        {botao_exportar}
      </div>

      <div id="conteudo-roteiro" style="padding:14px 16px;overflow-y:auto;max-height:calc(90vh - 110px);display:none;">
        {conteudo_roteiro_html}
      </div>
    </div>

    <script>
    window.CLIENTES_EXPORT = {export_data_js};

    function toggleLayer(layerName, visible) {{
      var labels = document.querySelectorAll('.leaflet-control-layers-overlays label');
      labels.forEach(function(label) {{
        if (label.textContent.trim() === layerName) {{
          var checkbox = label.querySelector('input');
          if (checkbox && checkbox.checked !== visible) checkbox.click();
        }}
      }});
    }}

    function toggleCarteira(visible) {{
      var camadas = ['{LABEL_STATUS["ativo"]}', '{LABEL_STATUS["inativo"]}', '{LABEL_STATUS["nunca_comprou"]}'];
      camadas.forEach(function(nome) {{ toggleLayer(nome, visible); }});
    }}

    function trocarAba(aba) {{
      var filtros = document.getElementById('conteudo-filtros');
      var roteiro = document.getElementById('conteudo-roteiro');
      var btnFiltros = document.getElementById('aba-filtros');
      var btnRoteiro = document.getElementById('aba-roteiro');
      var painel = document.getElementById('painel-unificado');
      if (painel.dataset.colapsado === 'true') togglePainel();
      if (aba === 'filtros') {{
        filtros.style.display = 'block';
        roteiro.style.display = 'none';
        btnFiltros.style.background = '#D2001B';
        btnFiltros.style.color = 'white';
        btnRoteiro.style.background = '#f5f5f5';
        btnRoteiro.style.color = '#888';
      }} else {{
        filtros.style.display = 'none';
        roteiro.style.display = 'block';
        btnRoteiro.style.background = '#2980b9';
        btnRoteiro.style.color = 'white';
        btnFiltros.style.background = '#f5f5f5';
        btnFiltros.style.color = '#888';
      }}
    }}

    function togglePainel() {{
      var painel   = document.getElementById('painel-unificado');
      var conteudoFiltros = document.getElementById('conteudo-filtros');
      var conteudoRoteiro = document.getElementById('conteudo-roteiro');
      var abas     = document.querySelectorAll('#painel-unificado > div:first-child button:not(#btn-colapsar)');
      var btn      = document.getElementById('btn-colapsar');
      var colapsado = painel.dataset.colapsado === 'true';

      if (colapsado) {{
        painel.style.width = '245px';
        abas.forEach(function(b) {{ b.style.display = ''; }});
        var abaAtiva = painel.dataset.abaAtiva || 'filtros';
        if (abaAtiva === 'filtros') {{ conteudoFiltros.style.display = 'block'; conteudoRoteiro.style.display = 'none'; }}
        else {{ conteudoFiltros.style.display = 'none'; conteudoRoteiro.style.display = 'block'; }}
        btn.textContent = '‹';
        painel.dataset.colapsado = 'false';
      }} else {{
        var abaAtiva = conteudoRoteiro.style.display === 'block' ? 'roteiro' : 'filtros';
        painel.dataset.abaAtiva = abaAtiva;
        painel.style.width = '32px';
        abas.forEach(function(b) {{ b.style.display = 'none'; }});
        conteudoFiltros.style.display = 'none';
        conteudoRoteiro.style.display = 'none';
        btn.textContent = '›';
        painel.dataset.colapsado = 'true';
      }}
    }}
    </script>"""

    mapa.get_root().html.add_child(folium.Element(navbar_html))
    mapa.get_root().html.add_child(folium.Element(painel_abas_html))
    folium.LayerControl(collapsed=False).add_to(mapa)

    return mapa


def _salvar_html(mapa: folium.Map, path_raw: Path, path_out: Path, senha: str | None, criptografar: bool):
    mapa.save(str(path_raw))
    if criptografar and senha:
        criptografar_html(path_raw, path_out, senha)
        logger.info(f"  Criptografado: {path_out.name}")
        path_raw.unlink()
    else:
        if path_out.exists():
            path_out.unlink()
        path_raw.rename(path_out)


def exportar_mapas(df: pd.DataFrame, criptografar: bool = True, df_prospects: pd.DataFrame | None = None) -> dict:
    """
    Gera e salva os HTMLs em data/output/.

    Cada chave de USUARIOS_MAPA que aparecer em USUARIO_PARA_COD_VENDEDOR
    recebe perfil='vendedor' e o df FILTRADO pelo cod_vendedor correspondente.
    Qualquer chave que NÃO aparecer em USUARIO_PARA_COD_VENDEDOR (ex: "master_sp")
    recebe perfil='master' e vê a carteira completa, sem filtro.
    """
    arquivos = {}
    df_disponiveis = df[df["tipo_cliente"] == "disponivel"].copy() if "tipo_cliente" in df.columns else df.copy()

    for usuario, dados in USUARIOS_MAPA.items():
        arquivo = dados["arquivo"]
        senha   = dados["senha"]
        slug    = arquivo.replace(".html", "")

        cod_vendedor = USUARIO_PARA_COD_VENDEDOR.get(usuario)
        perfil = "vendedor" if cod_vendedor else "master"

        if perfil == "vendedor":
            df_mapa = df[df["cod_vendedor"] == cod_vendedor].copy()
            if df_mapa.empty:
                logger.warning(
                    f"  ATENÇÃO: {usuario} (cod_vendedor={cod_vendedor}) gerou "
                    f"DataFrame VAZIO. Verifique USUARIO_PARA_COD_VENDEDOR ou a carteira."
                )
            df_rot = df_mapa
        else:
            df_mapa = df
            df_rot  = df_disponiveis if not df_disponiveis.empty else df

        logger.info(
            f"Gerando {arquivo} (perfil={perfil}"
            f"{f', cod_vendedor={cod_vendedor}' if cod_vendedor else ''}"
            f") — {len(df_mapa):,} clientes no mapa..."
        )

        # cod_vendedor para o link de checkin: usa o mapeado, ou "MASTER_SP"
        # como identificador quando o perfil é master (sem entrada em
        # USUARIO_PARA_COD_VENDEDOR). Isso permite ao checkin.ts validar
        # a senha do mapa mesmo para o perfil master.
        cod_vendedor_checkin = cod_vendedor or "MASTER_SP"

        # Prospects: cada vendedor só vê os prospects atribuídos ao seu
        # território (coluna cod_vendedor calculada por
        # prospect_ownership.py, com base no centroide da carteira
        # atual). Master vê todos, sem filtro — visão consolidada.
        if perfil == "vendedor" and df_prospects is not None and "cod_vendedor" in df_prospects.columns:
            df_prospects_mapa = df_prospects[df_prospects["cod_vendedor"] == cod_vendedor].copy()
        else:
            df_prospects_mapa = df_prospects

        mapa = montar_mapa(df_mapa, df_prospects=df_prospects_mapa, df_roteamento=df_rot, perfil=perfil,
                           cod_vendedor=cod_vendedor_checkin, mapa_senha=senha)
        _salvar_html(mapa, OUTPUT_DIR / f"_{slug}_raw.html", OUTPUT_DIR / arquivo, senha, criptografar)
        arquivos[usuario] = OUTPUT_DIR / arquivo
        logger.info(f"✅ {arquivo}")

    logger.info(f"\n📁 HTMLs em: {OUTPUT_DIR.resolve()}")
    return arquivos
