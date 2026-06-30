# ============================================================
# src/mapping/builder.py
# Gera o mapa Folium para São Carlos e Região.
# Área única — sem K-Means, sem múltiplas áreas.
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

from config.settings import USUARIOS_MAPA, COR_AREA, NOME_REGIAO
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
    """
    Monta JSON com todos os clientes + campo 'caso' para exportação Excel.
    Usado pelo botão 'Exportar Selecionados' no painel lateral.
    """
    registros = []

    # Clientes com dono
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

    # Disponíveis
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

    # Prospects
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
    """Botão + lógica JS de exportação Excel por caso (abas separadas)."""
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
    // Mapa de caso → label legível
    var CASO_LABELS = {
      "ativo":         "Com Representante - Ativo",
      "inativo":       "Com Representante - Inativo",
      "nunca_comprou": "Com Representante - Nunca Comprou",
      "disponivel":    "Disponível",
      "prospeccao":    "Prospecção"
    };

    // Quais casos cada checkbox controla
    var CHECKBOX_CASO = {
      "Ativos (≤ 60 dias)":              ["ativo"],
      "Inativos (> 60 dias)":            ["inativo"],
      "Nunca compraram":                 ["nunca_comprou"],
      "Disponíveis (sem representante)": ["disponivel"],
      "Sem representante":               ["disponivel"],
    };

    function getCasosSelecionados() {
      var casos = new Set();
      var cnaesSelecionados = new Set();

      document.querySelectorAll('#painel-resumo input[type=checkbox]').forEach(function(cb) {
        if (!cb.checked) return;
        var label = cb.closest('label');
        if (!label) return;
        var txt = label.textContent.trim().replace(/\s+/g, ' ');
        // Remove contagem no final ex: "Ativos (≤ 60 dias) (36)"
        var nome = txt.replace(/\s*\(\d+\)\s*$/, '').trim();

        if (CHECKBOX_CASO[nome]) {
          CHECKBOX_CASO[nome].forEach(function(c) { casos.add(c); });
          return;
        }

        // Prospects — captura o CNAE específico marcado
        // Label format: "Restaurantes e similares (305)" → remove contagem
        var nomeBase = nome.replace(/\s*\(\d+\)\s*$/, '').trim();
        // Verifica se este label corresponde a algum prospect no CLIENTES_EXPORT
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
        if (casosSel.size === 0) {
          status.textContent = '⚠️ Nenhuma categoria selecionada.';
          return;
        }

        // Agrupa por caso
        var porCaso = {};
        (window.CLIENTES_EXPORT || []).forEach(function(c) {
          if (!casosSel.has(c.caso)) return;
          // Prospects: filtra pelo CNAE específico marcado
          if (c.caso === 'prospeccao' && cnaesSel.size > 0 && !cnaesSel.has(c.descricao_cnae)) return;
          var label = CASO_LABELS[c.caso] || c.caso;
          if (!porCaso[label]) porCaso[label] = [];
          porCaso[label].push(c);
        });

        if (Object.keys(porCaso).length === 0) {
          status.textContent = '⚠️ Nenhum cliente encontrado.';
          return;
        }

        var wb = XLSX.utils.book_new();
        var ordemAbas = [
          "Com Representante - Ativo",
          "Com Representante - Inativo",
          "Com Representante - Nunca Comprou",
          "Disponível",
          "Prospecção"
        ];

        ordemAbas.forEach(function(label) {
          if (!porCaso[label]) return;
          var linhas = porCaso[label].map(function(c) {
            var linha = {
              'Caso':               label,
              'Código':             c.cod,
              'Cliente':            c.nome,
              'Cidade':             c.cidade,
              'Endereço':           c.endereco,
              'Bairro':             c.bairro,
              'CEP':                c.cep,
              'Telefone':           c.telefone,
              'CNPJ':               c.cnpj,
              'Representante':      c.representante,
              'Crédito Disponível': c.credito,
              'Última Compra':      c.ultima_compra,
              'Dias Sem Compra':    c.dias_sem_compra !== null ? c.dias_sem_compra : '-',
              'Faturamento Total':  c.total_faturado,
            };
            if (c.caso === 'prospeccao') {
              linha['CNAE']          = c.cnae || '-';
              linha['Descrição CNAE'] = c.descricao_cnae || '-';
            }
            return linha;
          });
          var ws = XLSX.utils.json_to_sheet(linhas);
          ws['!cols'] = [
            {wch:32},{wch:10},{wch:35},{wch:18},{wch:35},
            {wch:20},{wch:12},{wch:15},{wch:18},{wch:28},
            {wch:18},{wch:14},{wch:16},{wch:18}
          ];
          // Trunca nome da aba para 31 chars (limite do Excel)
          var nomeAba = label.length > 31 ? label.substring(0, 31) : label;
          XLSX.utils.book_append_sheet(wb, ws, nomeAba);
        });

        var total = Object.values(porCaso).reduce(function(s, arr) { return s + arr.length; }, 0);
        XLSX.writeFile(wb, 'clientes_sao_carlos.xlsx');
        status.textContent = '✅ ' + total + ' clientes exportados.';
      }

      if (typeof XLSX === 'undefined') {
        var s = document.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
        s.onload = function() { _doExport(); };
        document.head.appendChild(s);
      } else {
        _doExport();
      }
    }
    </script>
    """


def montar_mapa(df: pd.DataFrame, df_prospects: pd.DataFrame | None = None) -> folium.Map:
    """Monta mapa Folium com marcadores de clientes por status de compra e prospects."""

    mapa = folium.Map(
        location=[-21.994, -47.890],
        zoom_start=10,
        tiles="CartoDB positron",
    )

    # CSS global
    mapa.get_root().html.add_child(folium.Element(
        """<style>
        .leaflet-overlay-pane { pointer-events: none !important; }
        .leaflet-control-layers { display: none !important; }
        .leaflet-top.leaflet-left { right: 10px !important; left: auto !important; }
        </style>"""
    ))

    # ── Marcadores de clientes com dono (por status de compra) ─────────────
    contagens = {}

    for status in ["ativo", "inativo", "nunca_comprou"]:
        label = LABEL_STATUS[status]
        fg = folium.FeatureGroup(name=label, show=True)
        df_status = df[df["status_compra"] == status] if "status_compra" in df.columns else pd.DataFrame()

        count = 0
        for _, row in df_status.iterrows():
            if not pd.notna(row.get("lat_final")) or not pd.notna(row.get("lng_final")):
                continue

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

            popup_html = f"""
            <div style="font-family:Arial;font-size:12px;min-width:180px">
                <b>{nome}</b><br>
                <span style="color:#666">Cód: {cod}</span><br>
                <span style="color:#666">{cidade}</span><br>
                <span style="color:#666">Representante: {rep}</span><br>
                <span style="color:#666">Crédito disp.: R$ {credito:,.2f}</span><br>
                <span style="color:#666">Última NF: {ult_nf}</span><br>
                <span style="color:#666">Sem comprar: {dias_str}</span><br>
                <span style="color:#666">Faturamento total: {fat_fmt}</span>
            </div>
            """
            folium.CircleMarker(
                location=[float(row["lat_final"]), float(row["lng_final"])],
                radius=6,
                color=cor["border"],
                fill=True,
                fill_color=cor["fill"],
                fill_opacity=0.85,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=folium.Tooltip(f"{nome} — {dias_str}"),
            ).add_to(fg)
            count += 1

        fg.add_to(mapa)
        contagens[status] = count

    # ── Marcadores de disponíveis (azul) ────────────────────────────────────
    df_disp = df[df["tipo_cliente"] == "disponivel"] if "tipo_cliente" in df.columns else pd.DataFrame()
    fg_disp = folium.FeatureGroup(name=LABEL_STATUS["disponivel"], show=True)
    count_disp = 0

    for _, row in df_disp.iterrows():
        if not pd.notna(row.get("lat_final")) or not pd.notna(row.get("lng_final")):
            continue

        nome    = _safe_str(row.get("nome_cliente"), "N/D")
        cod     = _safe_str(row.get("cod_cliente"),  "N/D")
        cidade  = _safe_str(row.get("cidade"), "N/D")
        credito = _safe_float(row.get("limite_disp"))
        cor     = COR_STATUS["disponivel"]

        popup_html = f"""
        <div style="font-family:Arial;font-size:12px;min-width:180px">
            <b>{nome}</b><br>
            <span style="color:#3498db;font-weight:700;font-size:10px">DISPONÍVEL</span><br>
            <span style="color:#666">Cód: {cod}</span><br>
            <span style="color:#666">{cidade}</span><br>
            <span style="color:#666">Crédito disp.: R$ {credito:,.2f}</span>
        </div>
        """
        folium.CircleMarker(
            location=[float(row["lat_final"]), float(row["lng_final"])],
            radius=6,
            color=cor["border"],
            fill=True,
            fill_color=cor["fill"],
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=folium.Tooltip(f"{nome} — Disponível"),
        ).add_to(fg_disp)
        count_disp += 1

    fg_disp.add_to(mapa)
    contagens["disponivel"] = count_disp

    # ── Heatmap de crédito ──────────────────────────────────────────────────
    fg_heat = folium.FeatureGroup(name="Heatmap Crédito", show=False)
    heat_data = [
        [float(row["lat_final"]), float(row["lng_final"]), float(row["limite_disp"])]
        for _, row in df.iterrows()
        if pd.notna(row.get("lat_final")) and pd.notna(row.get("lng_final"))
        and pd.notna(row.get("limite_disp")) and float(row.get("limite_disp", 0)) > 0
        and row.get("geo_valida_final", True)
    ]
    if heat_data:
        folium.plugins.HeatMap(heat_data, min_opacity=0.3, radius=20, blur=15).add_to(fg_heat)
    fg_heat.add_to(mapa)

    # ── Prospects por CNAE ──────────────────────────────────────────────────
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
                </div>
                """
                folium.CircleMarker(
                    location=[float(row["lat_final"]), float(row["lng_final"])],
                    radius=4,
                    color="#888888",
                    fill=True,
                    fill_color="#aaaaaa",
                    fill_opacity=0.5,
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=folium.Tooltip(f"{nome} — {descricao}"),
                ).add_to(fg_p)

            fg_p.add_to(mapa)

    # ── JSON de exportação ──────────────────────────────────────────────────
    export_data_js = _build_export_data(df, df_prospects)

    # ── Painel lateral ──────────────────────────────────────────────────────
    soma_cred = df["limite_disp"].fillna(0).sum()
    cred_fmt  = f"R$ {soma_cred/1_000:.0f}K" if soma_cred >= 1_000 else f"R$ {soma_cred:,.0f}"
    total_com_dono = contagens.get("ativo", 0) + contagens.get("inativo", 0) + contagens.get("nunca_comprou", 0)

    # Checkboxes — clientes com dono por status de compra
    com_dono_html = ""
    for status in ["ativo", "inativo", "nunca_comprou"]:
        cor   = COR_STATUS[status]
        label = LABEL_STATUS[status]
        n     = contagens.get(status, 0)
        com_dono_html += f"""
      <label style="display:flex;align-items:center;cursor:pointer;gap:6px;margin-bottom:5px;">
        <input type="checkbox" checked
               onchange="toggleLayer('{label}', this.checked)"
               style="width:13px;height:13px;cursor:pointer;accent-color:{cor['border']};">
        <span style="display:inline-block;width:10px;height:10px;border-radius:50%;
                     background:{cor['fill']};border:1.5px solid {cor['border']};flex-shrink:0;"></span>
        <span style="font-size:11px;color:#333;">{label} <b>({n})</b></span>
      </label>"""

    # Checkbox — disponíveis
    cor_disp   = COR_STATUS["disponivel"]
    label_disp = LABEL_STATUS["disponivel"]
    n_disp     = contagens.get("disponivel", 0)
    disp_html  = f"""
    <div style="border-top:1px solid #eee;margin-top:8px;padding-top:8px;">
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
      </label>
    </div>"""

    # Checkboxes de prospects
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
          <div style="font-size:11px;font-weight:700;color:#888;margin-bottom:6px;">
            🎯 PROSPECÇÃO ({len(df_prospects):,})
          </div>
          {linhas_cnae}
        </div>"""

    botao_exportar = _botao_exportar_html()

    painel_html = f"""
    <div id="painel-resumo" style="
        position: fixed; top: 10px; left: 10px; z-index: 1000;
        background: rgba(255,255,255,0.97); border-radius: 10px;
        padding: 14px 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.15);
        min-width: 210px; max-width: 250px;
        font-family: 'Segoe UI', Arial, sans-serif;
        border-left: 4px solid #e74c3c;
        max-height: 90vh; overflow-y: auto;
    ">
      <div style="font-size:12px;font-weight:700;color:#e74c3c;margin-bottom:10px;">
        📊 {NOME_REGIAO.upper()}
      </div>

      <div style="font-size:11px;font-weight:700;color:#444;margin-bottom:6px;">
        👥 COM REPRESENTANTE ({total_com_dono})
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
    </script>"""

    mapa.get_root().html.add_child(folium.Element(painel_html))
    folium.LayerControl(collapsed=False).add_to(mapa)

    # Painel de roteamento
    mapa.get_root().html.add_child(
        folium.Element(gerar_roteamento_html(df))
    )

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
    """Gera e salva os HTMLs em data/output/."""
    arquivos = {}

    for usuario, dados in USUARIOS_MAPA.items():
        arquivo = dados["arquivo"]
        senha   = dados["senha"]
        slug    = arquivo.replace(".html", "")

        logger.info(f"Gerando {arquivo}...")
        mapa = montar_mapa(df, df_prospects=df_prospects)
        _salvar_html(
            mapa,
            OUTPUT_DIR / f"_{slug}_raw.html",
            OUTPUT_DIR / arquivo,
            senha,
            criptografar,
        )
        arquivos[usuario] = OUTPUT_DIR / arquivo
        logger.info(f"✅ {arquivo}")

    logger.info(f"\n📁 HTMLs em: {OUTPUT_DIR.resolve()}")
    return arquivos