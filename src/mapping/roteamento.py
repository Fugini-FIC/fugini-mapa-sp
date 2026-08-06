# ============================================================
# src/mapping/roteamento.py
# Gera os painéis de roteamento TSP (área individual e master).
# ============================================================

import json
import pandas as pd



def _safe_str(val, default="-") -> str:
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    if s.lower() in ("nan", "none", "nat", ""):
        return default
    return s


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


def _build_cliente_dict(row) -> dict:
    return {
        "lat":            float(row["lat_final"]),
        "lng":            float(row["lng_final"]),
        "nome":           _safe_str(row.get("nome_cliente"),   "N/D"),
        "cod":            _safe_str(row.get("cod_cliente"),    "N/D"),
        "cidade":         _safe_str(row.get("cidade"),         "N/D"),
        "endereco":       _safe_str(row.get("endereco"),       "-"),
        "bairro":         _safe_str(row.get("bairro"),         "-"),
        "cep":            _safe_str(row.get("cep"),            "-"),
        "telefone":       _safe_str(row.get("telefone"),       "-"),
        "cnpj":           _safe_str(row.get("cnpj"),           "-"),
        "credito":        _safe_float(row.get("limite_disp")),
        "ultima_compra":  _safe_date(row.get("ultima_compra")),
        "ultimo_produto": _safe_str(row.get("ultimo_produto"), "-"),
        "ultima_qt":      _safe_float(row.get("ultima_qt_pedida")),
        "total_faturado": _safe_float(row.get("total_faturado")),
        "tipo":           "cliente",
    }


def _build_prospect_dict(row) -> dict:
    nome = _safe_str(row.get("razao_social") or row.get("nome_fantasia"), "N/D")
    return {
        "lat":            float(row["lat_final"]),
        "lng":            float(row["lng_final"]),
        "nome":           nome,
        "cod":            _safe_str(row.get("cnpj"), "-"),
        "cidade":         _safe_str(row.get("municipio"), "N/D"),
        "endereco":       f"{_safe_str(row.get('logradouro'))} {_safe_str(row.get('numero'))}".strip(),
        "bairro":         _safe_str(row.get("bairro"), "-"),
        "cep":            _safe_str(row.get("cep"), "-"),
        "telefone":       "-",
        "cnpj":           _safe_str(row.get("cnpj"), "-"),
        "cnae":           _safe_str(row.get("cnae"), "-"),
        "descricao_cnae": _safe_str(row.get("descricao_cnae"), "-"),
        "credito":        0.0,
        "ultima_compra":  "-",
        "ultimo_produto": "-",
        "ultima_qt":      0.0,
        "total_faturado": 0.0,
        "tipo":           "prospect",
    }


def gerar_roteamento_html(df_area: pd.DataFrame, df_prospects: pd.DataFrame | None = None,
                           cod_vendedor: str = "") -> tuple[str, str]:
    """
    Retorna (navbar_html, conteudo_roteiro_html).
    - navbar_html: barra superior fixa com logo e links
    - conteudo_roteiro_html: HTML interno do painel de roteiro (sem container externo),
      para ser injetado pelo builder.py como aba do painel unificado
    - cod_vendedor: identificador do dono deste mapa específico (ex: "SP01",
      "SC01", ou "MASTER_SP"/"MASTER_SC" para os mapas master). Definido em
      tempo de geração pelo builder.py — NÃO é editável pelo usuário no
      navegador. Antes desse parâmetro existia um campo de texto livre
      ("Seu cód. vendedor") que qualquer pessoa podia preencher com
      qualquer código, inclusive de OUTRO vendedor/região, permitindo
      criar e agendar roteiros na carteira alheia. Isso foi removido:
      o valor agora vem embutido no HTML gerado, um por vendedor.
    """
    clientes_js = json.dumps([
        _build_cliente_dict(row)
        for _, row in df_area.iterrows()
        if pd.notna(row["lat_final"]) and pd.notna(row["lng_final"])
    ], ensure_ascii=False)

    if df_prospects is not None and not df_prospects.empty:
        prospects_js = json.dumps([
            _build_prospect_dict(row)
            for _, row in df_prospects.iterrows()
            if pd.notna(row.get("lat_final")) and pd.notna(row.get("lng_final"))
        ], ensure_ascii=False)
    else:
        prospects_js = "[]"

    cod_vendedor_js = json.dumps(cod_vendedor or "")

    navbar_html = """
    <!-- NAV SUPERIOR -->
    <div style="
        position: fixed; top: 0; left: 0; right: 0; z-index: 2000;
        background: #1a1a2e; color: white;
        display: flex; align-items: center; justify-content: space-between;
        padding: 0 16px; height: 44px;
        font-family: 'Segoe UI', Arial, sans-serif;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    ">
      <a href="https://fugini-checkin-api.vercel.app/painel"
         style="text-decoration:none;color:white;">
        <div style="font-size:14px;font-weight:700;letter-spacing:1px;">
          FUGINI<span style="color:#D2001B;">.</span>CRM
        </div>
      </a>
      <div style="display:flex;gap:8px;">
        <a href="https://fugini-checkin-api.vercel.app/painel"
           style="font-size:12px;color:#aaa;text-decoration:none;padding:6px 10px;
                  border-radius:6px;transition:background 0.15s;"
           onmouseover="this.style.background='rgba(255,255,255,0.1)'"
           onmouseout="this.style.background='transparent'">
          🏠 Painel
        </a>
        <a href="https://fugini-checkin-api.vercel.app/agenda"
           style="font-size:12px;color:#aaa;text-decoration:none;padding:6px 10px;
                  border-radius:6px;transition:background 0.15s;"
           onmouseover="this.style.background='rgba(255,255,255,0.1)'"
           onmouseout="this.style.background='transparent'">
          📅 Agenda
        </a>
      </div>
    </div>

    """

    conteudo_roteiro_html = """
      <div style="font-size:12px;font-weight:700;color:#2980b9;margin-bottom:8px;">
        🗺️ ROTEIRO
      </div>

      <div style="width:100%;padding:6px 8px;border:1.5px solid #eee;border-radius:6px;
                  font-size:11px;margin-bottom:6px;box-sizing:border-box;background:#f9f9f9;
                  color:#555;display:flex;justify-content:space-between;align-items:center;">
        <span>Vendedor</span>
        <span id="rota-cod-vendedor-display" style="font-weight:700;color:#1a1a2e;"></span>
      </div>

      <input id="endereco-partida" type="text" placeholder="Seu endereço de partida"
             style="width:100%;padding:6px 8px;border:1.5px solid #ddd;border-radius:6px;
                    font-size:11px;margin-bottom:6px;box-sizing:border-box;outline:none;">

      <input id="rota-data-inicio" type="date"
             style="width:100%;padding:6px 8px;border:1.5px solid #ddd;border-radius:6px;
                    font-size:11px;margin-bottom:6px;box-sizing:border-box;outline:none;">

      <div style="display:flex;gap:6px;margin-bottom:4px;">
        <div style="flex:1;">
          <label style="font-size:9px;color:#888;display:block;margin-bottom:2px;">Clientes/dia</label>
          <input id="rota-n-clientes" type="number" min="0" value="4"
                 oninput="atualizarSomaDia()"
                 style="width:100%;padding:6px 8px;border:1.5px solid #ddd;border-radius:6px;
                        font-size:11px;box-sizing:border-box;outline:none;">
        </div>
        <div style="flex:1;">
          <label style="font-size:9px;color:#888;display:block;margin-bottom:2px;">Prospects/dia</label>
          <input id="rota-n-prospects" type="number" min="0" value="2"
                 oninput="atualizarSomaDia()"
                 style="width:100%;padding:6px 8px;border:1.5px solid #ddd;border-radius:6px;
                        font-size:11px;box-sizing:border-box;outline:none;">
        </div>
      </div>
      <div id="rota-soma-dia" style="font-size:10px;color:#888;margin-bottom:6px;text-align:center;">
        6 clientes por dia
      </div>

      <!-- Seleção de CNAEs para prospecção -->
      <div style="border:1.5px solid #eee;border-radius:6px;margin-bottom:6px;">
        <div onclick="toggleCnaes()" style="
            padding:6px 8px;font-size:10px;font-weight:700;color:#888;
            cursor:pointer;display:flex;justify-content:space-between;align-items:center;
            user-select:none;">
          <span>🎯 CNAEs para prospecção</span>
          <span id="cnae-arrow">▶</span>
        </div>
        <div id="lista-cnaes-roteiro" style="display:none;padding:0 8px 8px;">
          <div style="font-size:9px;color:#aaa;margin-bottom:4px;">
            Nenhum selecionado = todos os CNAEs
          </div>
          <label style="display:flex;align-items:center;gap:4px;margin-bottom:4px;cursor:pointer;">
            <input type="checkbox" id="cb-todos-cnaes" onchange="toggleTodosCnaes(this.checked)"
                   style="width:11px;height:11px;">
            <span style="font-size:10px;font-weight:700;color:#444;">Selecionar todos</span>
          </label>
          <div id="cnaes-checkboxes"></div>
        </div>
      </div>

      <button onclick="calcularRota()"
              style="width:100%;padding:7px;background:#2980b9;color:white;border:none;
                     border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;">
        Calcular Rota
      </button>
      <button id="btn-exportar" onclick="exportarExcel()"
              style="width:100%;padding:7px;background:#27ae60;color:white;border:none;
                     border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;
                     margin-top:4px;display:none;">
        📥 Exportar Excel
      </button>
      <button id="btn-incluir-todos" onclick="incluirTodosNaAgenda()"
              style="width:100%;padding:7px;background:#8e44ad;color:white;border:none;
                     border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;
                     margin-top:4px;display:none;">
        📅 Incluir Todos na Agenda
      </button>

      <div id="rota-status" style="font-size:10px;color:#888;margin-top:6px;"></div>
      <div id="rota-resultado" style="margin-top:8px;font-size:11px;
                                       max-height:300px;overflow-y:auto;"></div>
    </div>

    <script>
    var CLIENTES = """ + clientes_js + """;
    var PROSPECTS = """ + prospects_js + """;
    // Cód. do vendedor dono deste mapa — definido em tempo de geração do
    // HTML (builder.py), não editável pelo usuário. Ver docstring de
    // gerar_roteamento_html() para o histórico de por que isso mudou.
    var COD_VENDEDOR_FIXO = """ + cod_vendedor_js + """;
    var CORES_DIAS = ['#e74c3c','#2980b9','#27ae60','#8e44ad','#f39c12','#16a085','#c0392b'];
    var rotaLayers = [];
    var layersPorDia = {};
    var API_AGENDAMENTOS = 'https://fugini-checkin-api.vercel.app/api/agendamentos';

    (function() {
      var display = document.getElementById('rota-cod-vendedor-display');
      if (display) display.textContent = COD_VENDEDOR_FIXO || '—';
      var hoje = new Date().toISOString().split('T')[0];
      document.getElementById('rota-data-inicio').value = hoje;
      atualizarSomaDia();

      // Popular lista de CNAEs únicos dos prospects
      var cnaesMap = {};
      PROSPECTS.forEach(function(p) {
        if (p.cnpj && p.cod) {
          // usa descricao_cnae se disponível
        }
      });
      // Extrai CNAEs únicos do array PROSPECTS via campo cnae/descricao
      var cnaesUnicos = {};
      PROSPECTS.forEach(function(p) {
        var cnae = p.cnae || p.cod_cnae;
        var desc = p.descricao_cnae || p.descricao || cnae;
        if (cnae && cnae !== '-') cnaesUnicos[cnae] = desc;
      });
      var container = document.getElementById('cnaes-checkboxes');
      if (container) {
        Object.keys(cnaesUnicos).sort().forEach(function(cnae) {
          var desc = cnaesUnicos[cnae];
          var label = document.createElement('label');
          label.style.cssText = 'display:flex;align-items:center;gap:4px;margin-bottom:3px;cursor:pointer;';
          label.innerHTML = '<input type="checkbox" class="cb-cnae" value="' + cnae + '" style="width:11px;height:11px;">' +
                            '<span style="font-size:9px;color:#555;">' + desc + '</span>';
          container.appendChild(label);
        });
      }
    })();

    function toggleCnaes() {
      var lista = document.getElementById('lista-cnaes-roteiro');
      var arrow = document.getElementById('cnae-arrow');
      if (lista.style.display === 'none') {
        lista.style.display = 'block';
        arrow.textContent = '▼';
      } else {
        lista.style.display = 'none';
        arrow.textContent = '▶';
      }
    }

    function toggleTodosCnaes(checked) {
      document.querySelectorAll('.cb-cnae').forEach(function(cb) { cb.checked = checked; });
    }

    function getCnaesSelecionados() {
      var selecionados = [];
      document.querySelectorAll('.cb-cnae:checked').forEach(function(cb) {
        selecionados.push(cb.value);
      });
      return selecionados;
    }

    function atualizarSomaDia() {
      var nc = parseInt(document.getElementById('rota-n-clientes').value) || 0;
      var np = parseInt(document.getElementById('rota-n-prospects').value) || 0;
      document.getElementById('rota-soma-dia').textContent = (nc + np) + ' clientes por dia';
    }

    function haversineKm(lat1, lng1, lat2, lng2) {
      var R = 6371;
      var dLat = (lat2-lat1)*Math.PI/180;
      var dLng = (lng2-lng1)*Math.PI/180;
      var a = Math.sin(dLat/2)*Math.sin(dLat/2) +
              Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*
              Math.sin(dLng/2)*Math.sin(dLng/2);
      return R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a));
    }

    function nearestNeighbor(clientes, latP, lngP) {
      var nv = clientes.slice(), rota = [], latA = latP, lngA = lngP;
      while (nv.length > 0) {
        var melhor = null, melhorD = Infinity;
        nv.forEach(function(c) {
          var d = haversineKm(latA, lngA, c.lat, c.lng);
          if (d < melhorD) { melhorD = d; melhor = c; }
        });
        rota.push(melhor);
        latA = melhor.lat; lngA = melhor.lng;
        nv.splice(nv.indexOf(melhor), 1);
      }
      return rota;
    }

    // Pega os N elementos mais próximos de (lat, lng), removendo-os da lista original
    function pegarMaisProximos(lista, n, lat, lng) {
      if (n <= 0 || lista.length === 0) return [];
      var comDist = lista.map(function(c) {
        return { item: c, dist: haversineKm(lat, lng, c.lat, c.lng) };
      });
      comDist.sort(function(a, b) { return a.dist - b.dist; });
      var selecionados = comDist.slice(0, n).map(function(c) { return c.item; });
      selecionados.forEach(function(sel) {
        var idx = lista.indexOf(sel);
        if (idx !== -1) lista.splice(idx, 1);
      });
      return selecionados;
    }

    // Monta o roteiro dia a dia: todo dia parte de casa (latP, lngP) e volta
    // para casa no fim do dia (ciclo fechado). A cada dia, pega N clientes +
    // M prospects mais próximos de casa ainda não utilizados, e otimiza o
    // deslocamento dentro do dia com nearest-neighbor a partir de casa.
    // Como pegarMaisProximos remove os itens usados, dias sucessivos avançam
    // radialmente para pontos cada vez mais distantes de casa.
    function montarRoteiroDiario(clientes, prospects, nCli, nPro, latP, lngP) {
      var clientesRestantes  = clientes.slice();
      var prospectsRestantes = prospects.slice();
      var dias = [];
      var MAX_DIAS = 60; // proteção contra loop infinito

      while ((clientesRestantes.length > 0 || prospectsRestantes.length > 0) && dias.length < MAX_DIAS) {
        var poolClientes  = pegarMaisProximos(clientesRestantes,  nCli, latP, lngP);
        var poolProspects = pegarMaisProximos(prospectsRestantes, nPro, latP, lngP);
        var pool = poolClientes.concat(poolProspects);

        if (pool.length === 0) break; // nada mais para agendar (ex: nCli=0 e nPro=0)

        var rotaDia = nearestNeighbor(pool, latP, lngP);
        dias.push(rotaDia);
      }

      return dias;
    }

    async function geocodificarNominatim(endereco) {
      var url = 'https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=br&q=' +
                encodeURIComponent(endereco);
      var resp = await fetch(url, {headers: {'Accept-Language': 'pt-BR'}});
      var data = await resp.json();
      if (data.length === 0) return null;
      return {lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon)};
    }

    function getMap() {
      for (var key in window) {
        try { if (key.startsWith('map_') && window[key] && window[key].eachLayer) return window[key]; }
        catch(e) {}
      }
      return null;
    }

    function limparRotas() {
      var m = getMap(); if (!m) return;
      rotaLayers.forEach(function(l) { m.removeLayer(l); });
      rotaLayers = [];
      layersPorDia = {};
    }

    function toggleDia(idx, visible) {
      var m = getMap(); if (!m) return;
      (layersPorDia[idx] || []).forEach(function(l) {
        if (visible) { m.addLayer(l); } else { m.removeLayer(l); }
      });
    }

    function selecionarTodosDias(checked) {
      var cbs = document.querySelectorAll('.cb-dia');
      cbs.forEach(function(cb, idx) {
        if (cb.checked !== checked) {
          cb.checked = checked;
          toggleDia(idx, checked);
        }
      });
    }

    function desenharRota(dias, latP, lngP) {
      var m = getMap(); if (!m) return;
      limparRotas();

      dias.forEach(function(dia, idx) {
        var cor = CORES_DIAS[idx % CORES_DIAS.length];
        layersPorDia[idx] = [];

        // Ciclo fechado: casa -> pontos do dia -> casa
        var pts = [[latP, lngP]];
        dia.forEach(function(c) { pts.push([c.lat, c.lng]); });
        pts.push([latP, lngP]);

        var linha = L.polyline(pts, {color: cor, weight: 3, opacity: 0.8, dashArray: '6,4'});
        rotaLayers.push(linha);
        layersPorDia[idx].push(linha);

        dia.forEach(function(c, i) {
          var ehProspect = c.tipo === 'prospect';
          var corMarker = ehProspect ? '#888888' : cor;
          var icon = L.divIcon({
            html: '<div style="background:' + corMarker + ';color:white;border-radius:50%;' +
                  'width:20px;height:20px;display:flex;align-items:center;justify-content:center;' +
                  'font-size:10px;font-weight:700;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3);">' +
                  (i+1) + '</div>',
            iconSize: [20,20], iconAnchor: [10,10], className: ''
          });
          var tag = ehProspect ? ' (Prospect)' : '';
          var mk = L.marker([c.lat, c.lng], {icon: icon})
            .bindPopup('<b>Dia ' + (idx+1) + ' - Visita ' + (i+1) + tag + '</b><br>' + c.nome + '<br>' + c.cidade);
          rotaLayers.push(mk);
          layersPorDia[idx].push(mk);
        });
      });

      var iconP = L.divIcon({
        html: '<div style="background:#1a1a2e;color:white;border-radius:50%;' +
              'width:24px;height:24px;display:flex;align-items:center;justify-content:center;' +
              'font-size:14px;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3);">🏠</div>',
        iconSize: [24,24], iconAnchor: [12,12], className: ''
      });
      var iconPartida = L.marker([latP, lngP], {icon: iconP}).bindPopup('<b>Ponto de partida (casa)</b>');
      iconPartida.addTo(getMap());
      rotaLayers.push(iconPartida);
    }

    function somarDiasUteis(dataStr, n) {
      var d = new Date(dataStr + 'T12:00:00');
      var adicionados = 0;
      while (adicionados < n) {
        d.setDate(d.getDate() + 1);
        var dow = d.getDay();
        if (dow !== 0 && dow !== 6) adicionados++;
      }
      return d.toISOString().split('T')[0];
    }

    function getDataDia(idxDia) {
      var dataInicio = document.getElementById('rota-data-inicio').value;
      if (!dataInicio) return null;
      if (idxDia === 0) return dataInicio;
      return somarDiasUteis(dataInicio, idxDia);
    }

    async function agendarCliente(c, dataVisita, codVendedor, ordem) {
      try {
        var obs = c.tipo === 'prospect'
          ? 'Prospecção — Roteiro gerado pelo mapa'
          : 'Roteiro gerado pelo mapa';
        var endereco = c.endereco && c.endereco !== '-'
          ? (c.endereco + (c.bairro && c.bairro !== '-' ? ', ' + c.bairro : '') +
             (c.cidade && c.cidade !== '-' ? ' — ' + c.cidade : ''))
          : null;
        var res = await fetch(API_AGENDAMENTOS, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            cod_cliente:   c.cod,
            nome_cliente:  c.nome,
            cod_vendedor:  codVendedor,
            data_visita:   dataVisita,
            observacao:    obs,
            endereco:      endereco,
            ordem_roteiro: ordem
          })
        });
        if (res.status === 200) return 'skipped';
        if (res.ok)             return 'ok';
        return 'erro';
      } catch(e) {
        return 'erro';
      }
    }

    async function incluirDiaNaAgenda(idxDia) {
      if (!COD_VENDEDOR_FIXO) { alert('Este mapa não tem um vendedor definido. Contate o suporte.'); return; }
      var dataVisita = getDataDia(idxDia);
      if (!dataVisita) { alert('Selecione a data de início do roteiro.'); return; }

      var dia = window._diasRotaAtual[idxDia];
      var status = document.getElementById('rota-status');
      status.innerHTML = '⏳ Agendando dia ' + (idxDia+1) + '...';

      var ok = 0, skipped = 0, erro = 0;
      for (var i = 0; i < dia.length; i++) {
        var resultado = await agendarCliente(dia[i], dataVisita, COD_VENDEDOR_FIXO, i + 1);
        if (resultado === 'ok')           ok++;
        else if (resultado === 'skipped') skipped++;
        else                              erro++;
      }

      var msg = ok > 0 ? '✅ Dia ' + (idxDia+1) + ': ' + ok + ' agendados' : '⚠️ Dia ' + (idxDia+1) + ':';
      if (skipped > 0) msg += ' · ' + skipped + ' já registrados';
      if (erro > 0)    msg += ' · ' + erro + ' erros';
      status.innerHTML = msg;
    }

    async function incluirTodosNaAgenda() {
      if (!COD_VENDEDOR_FIXO) { alert('Este mapa não tem um vendedor definido. Contate o suporte.'); return; }
      var dataInicio = document.getElementById('rota-data-inicio').value;
      if (!dataInicio) { alert('Selecione a data de início do roteiro.'); return; }

      var dias = window._diasRotaAtual;
      var status = document.getElementById('rota-status');
      var totalOk = 0, totalSkipped = 0, totalErro = 0;

      for (var idx = 0; idx < dias.length; idx++) {
        var dataVisita = getDataDia(idx);
        status.innerHTML = '⏳ Agendando dia ' + (idx+1) + '/' + dias.length + '...';
        for (var i = 0; i < dias[idx].length; i++) {
          var resultado = await agendarCliente(dias[idx][i], dataVisita, COD_VENDEDOR_FIXO, i + 1);
          if (resultado === 'ok')           totalOk++;
          else if (resultado === 'skipped') totalSkipped++;
          else                              totalErro++;
        }
      }

      var msg = totalOk > 0 ? '✅ ' + totalOk + ' agendados em ' + dias.length + ' dias' : '⚠️ Nenhum novo agendamento';
      if (totalSkipped > 0) msg += ' · ' + totalSkipped + ' já registrados';
      if (totalErro > 0)    msg += ' · ' + totalErro + ' erros';
      status.innerHTML = msg;
    }

    function exibirRoteiro(dias, distTotal) {
      var html = '<div style="font-size:10px;color:#888;margin-bottom:6px;">' +
                 '📏 Distância estimada: ' + distTotal.toFixed(1) + ' km</div>';

      html += '<div style="margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #eee;">' +
              '<label style="display:flex;align-items:center;cursor:pointer;gap:6px;">' +
              '<input type="checkbox" id="cb-selecionar-todos-dias" ' +
              'onchange="selecionarTodosDias(this.checked)" ' +
              'style="width:13px;height:13px;cursor:pointer;">' +
              '<span style="font-size:11px;font-weight:700;color:#444;">Selecionar todos</span>' +
              '</label></div>';

      dias.forEach(function(dia, idx) {
        var cor = CORES_DIAS[idx % CORES_DIAS.length];
        var dataVisita = getDataDia(idx);
        var dataFmt = '';
        if (dataVisita) {
          var partes = dataVisita.split('-');
          dataFmt = ' · ' + partes[2] + '/' + partes[1];
        }

        html += '<div style="margin-bottom:8px;">';
        html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;">';
        html += '<label style="display:flex;align-items:center;cursor:pointer;gap:6px;">' +
                '<input type="checkbox" class="cb-dia" ' +
                'onchange="toggleDia(' + idx + ', this.checked)" ' +
                'style="width:13px;height:13px;cursor:pointer;accent-color:' + cor + ';">' +
                '<span style="display:inline-block;width:9px;height:9px;border-radius:50%;' +
                'background:' + cor + ';flex-shrink:0;"></span>' +
                '<span style="font-weight:700;font-size:11px;color:#1a1a2e;">Dia ' + (idx+1) + dataFmt + '</span>' +
                '</label>';
        html += '<button onclick="incluirDiaNaAgenda(' + idx + ')" ' +
                'style="font-size:9px;padding:2px 6px;background:#8e44ad;color:white;' +
                'border:none;border-radius:4px;cursor:pointer;white-space:nowrap;">📅 Agendar</button>';
        html += '</div>';

        dia.forEach(function(c, i) {
          var tagProspect = c.tipo === 'prospect'
            ? ' <span style="color:#888;font-size:9px;">(prospect)</span>'
            : '';
          var tagAgendado = c.tipo === 'agendado'
            ? ' <span style="color:#8e44ad;font-size:9px;">📅 agendado</span>'
            : '';
          var corNome = c.tipo === 'agendado' ? '#8e44ad' : '#444';
          html += '<div style="padding-left:26px;font-size:10px;color:' + corNome + ';line-height:1.6;">' +
                  (i+1) + '. ' + c.nome + tagProspect + tagAgendado + '</div>';
        });
        html += '</div>';
      });

      document.getElementById('rota-resultado').innerHTML = html;
    }

    async function calcularRota() {
      var endereco  = document.getElementById('endereco-partida').value.trim();
      var status    = document.getElementById('rota-status');
      var resultado = document.getElementById('rota-resultado');
      var nCli = parseInt(document.getElementById('rota-n-clientes').value) || 0;
      var nPro = parseInt(document.getElementById('rota-n-prospects').value) || 0;
      var codVendedor = COD_VENDEDOR_FIXO;

      if (!endereco) { status.innerHTML = '⚠️ Digite um endereço.'; return; }
      if (nCli === 0 && nPro === 0) { status.innerHTML = '⚠️ Defina ao menos 1 cliente ou prospect por dia.'; return; }

      status.innerHTML = '🔍 Geocodificando...';
      resultado.innerHTML = '';

      var partida = await geocodificarNominatim(endereco);
      if (!partida) { status.innerHTML = '❌ Endereço não encontrado.'; return; }

      // Busca clientes já visitados ou reagendados para excluir do roteiro
      var visitados = new Set();
      if (codVendedor) {
        try {
          status.innerHTML = '🔍 Verificando histórico de visitas...';
          var resHist = await fetch(API_AGENDAMENTOS + '?cod_vendedor=' + codVendedor);
          if (resHist.ok) {
            var agendamentos = await resHist.json();
            agendamentos.forEach(function(a) {
              if (a.status === 'realizada' || a.status === 'reagendada' || a.status === 'inexistente') {
                visitados.add(String(a.cod_cliente));
              }
            });
          }
        } catch(e) {
          // Falha silenciosa: se a API não responder, roteiriza sem filtro
          // em vez de bloquear o vendedor
        }
      }

      var clientesFiltrados = CLIENTES.filter(function(c) {
        return !visitados.has(String(c.cod));
      });

      var prospectsFiltrados = PROSPECTS.filter(function(c) {
        return !visitados.has(String(c.cod));
      });

      // Filtro de CNAE — se algum selecionado, usa só esses; senão usa todos
      var cnaesSel = getCnaesSelecionados();
      if (cnaesSel.length > 0) {
        prospectsFiltrados = prospectsFiltrados.filter(function(c) {
          return cnaesSel.indexOf(String(c.cnae || c.cod_cnae || '')) !== -1;
        });
      }

      // Contagem correta: só conta visitados, não prospects filtrados por CNAE
      var nVisitadosClientes = CLIENTES.length - clientesFiltrados.length;
      var nVisitadosProspects = PROSPECTS.filter(function(c) { return visitados.has(String(c.cod)); }).length;
      var nVisitados = nVisitadosClientes + nVisitadosProspects;

      // Busca agendamentos pendentes/reagendados por data para injetar no roteiro
      // Monta mapa: data -> [clientes agendados]
      var agendadosPorData = {};
      var codsAgendados = new Set();
      if (codVendedor) {
        try {
          status.innerHTML = '🔍 Verificando agenda...';
          var resAg = await fetch(API_AGENDAMENTOS + '?cod_vendedor=' + codVendedor);
          if (resAg.ok) {
            var todosAg = await resAg.json();
            var dataInicio = document.getElementById('rota-data-inicio').value;
            todosAg.forEach(function(a) {
              if ((a.status === 'pendente' || a.status === 'reagendada') && a.data_visita >= dataInicio) {
                var data = a.data_visita; // YYYY-MM-DD
                if (!agendadosPorData[data]) agendadosPorData[data] = [];
                // Tenta encontrar coordenadas do cliente na base local
                var clienteBase = CLIENTES.find(function(c) { return String(c.cod) === String(a.cod_cliente); })
                               || PROSPECTS.find(function(c) { return String(c.cod) === String(a.cod_cliente); });
                agendadosPorData[data].push({
                  lat:            clienteBase ? clienteBase.lat : null,
                  lng:            clienteBase ? clienteBase.lng : null,
                  nome:           a.nome_cliente,
                  cod:            a.cod_cliente,
                  cidade:         clienteBase ? clienteBase.cidade : '-',
                  endereco:       a.endereco || (clienteBase ? clienteBase.endereco : '-'),
                  bairro:         clienteBase ? clienteBase.bairro : '-',
                  cep:            clienteBase ? clienteBase.cep : '-',
                  telefone:       clienteBase ? clienteBase.telefone : '-',
                  cnpj:           clienteBase ? clienteBase.cnpj : a.cod_cliente,
                  credito:        clienteBase ? clienteBase.credito : 0,
                  ultima_compra:  clienteBase ? clienteBase.ultima_compra : '-',
                  ultimo_produto: clienteBase ? clienteBase.ultimo_produto : '-',
                  ultima_qt:      clienteBase ? clienteBase.ultima_qt : 0,
                  total_faturado: clienteBase ? clienteBase.total_faturado : 0,
                  tipo:           'agendado',
                  ordem_roteiro:  a.ordem_roteiro || null,
                });
                codsAgendados.add(String(a.cod_cliente));
              }
            });
          }
        } catch(e) {}
      }

      // Remove da carteira livre clientes que já estão agendados em alguma data
      clientesFiltrados = clientesFiltrados.filter(function(c) {
        return !codsAgendados.has(String(c.cod));
      });
      prospectsFiltrados = prospectsFiltrados.filter(function(c) {
        return !codsAgendados.has(String(c.cod));
      });

      status.innerHTML = '⚙️ Calculando rota...';
      var dias = montarRoteiroDiario(clientesFiltrados, prospectsFiltrados, nCli, nPro, partida.lat, partida.lng);

      // Injeta agendamentos fixos nos dias correspondentes
      // Para cada dia do roteiro, verifica se existe agendamento na data daquele dia
      dias.forEach(function(dia, idx) {
        var dataDodia = getDataDia(idx);
        if (dataDodia && agendadosPorData[dataDodia]) {
          var fixos = agendadosPorData[dataDodia].filter(function(a) { return a.lat && a.lng; });
          // Adiciona fixos no início do dia, ordenados por ordem_roteiro se houver
          fixos.sort(function(a, b) { return (a.ordem_roteiro || 99) - (b.ordem_roteiro || 99); });
          fixos.forEach(function(f) { dia.unshift(f); });
          // Remove do agendadosPorData para não duplicar
          delete agendadosPorData[dataDodia];
        }
      });

      // Datas agendadas que não têm dia correspondente no roteiro gerado:
      // cria dias extras só com os agendamentos fixos
      Object.keys(agendadosPorData).forEach(function(data) {
        var fixos = agendadosPorData[data].filter(function(a) { return a.lat && a.lng; });
        if (fixos.length > 0) {
          fixos.sort(function(a, b) { return (a.ordem_roteiro || 99) - (b.ordem_roteiro || 99); });
          dias.push(fixos);
        }
      });

      if (dias.length === 0) {
        status.innerHTML = '⚠️ Nenhum cliente ou prospect disponível para roteirizar.';
        return;
      }

      // Distância total: cada dia é um ciclo fechado casa -> pontos -> casa
      var dist = 0;
      dias.forEach(function(dia) {
        if (dia.length === 0) return;
        dist += haversineKm(partida.lat, partida.lng, dia[0].lat, dia[0].lng);
        for (var i = 0; i < dia.length-1; i++)
          dist += haversineKm(dia[i].lat, dia[i].lng, dia[i+1].lat, dia[i+1].lng);
        var ult = dia[dia.length-1];
        dist += haversineKm(ult.lat, ult.lng, partida.lat, partida.lng);
      });

      var totalParadas = dias.reduce(function(s, d) { return s + d.length; }, 0);

      desenharRota(dias, partida.lat, partida.lng);
      exibirRoteiro(dias, dist);

      var msgVisitados = nVisitados > 0 ? ' · ' + nVisitados + ' já visitados ignorados' : '';
      status.innerHTML = '✅ ' + dias.length + ' dias | ' + totalParadas + ' paradas' + msgVisitados;
      window._diasRotaAtual = dias;

      document.getElementById('btn-exportar').style.display      = 'block';
      document.getElementById('btn-incluir-todos').style.display = 'block';
    }

    document.getElementById('endereco-partida').addEventListener('keydown', function(e) {
      if (e.key === 'Enter') calcularRota();
    });

    function exportarExcel() {
      if (!window._diasRotaAtual || window._diasRotaAtual.length === 0) return;
      if (typeof XLSX === 'undefined') {
        var script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
        script.onload = function() { _gerarExcel(); };
        document.head.appendChild(script);
      } else {
        _gerarExcel();
      }
    }

    function _gerarExcel() {
      var wb = XLSX.utils.book_new();
      (window._diasRotaAtual || []).forEach(function(dia, idx) {
        var linhas = dia.map(function(c, i) {
          return {
            'Ordem':              i + 1,
            'Código':             c.cod,
            'Cliente':            c.nome,
            'Cidade':             c.cidade,
            'Endereço':           c.endereco,
            'Bairro':             c.bairro,
            'CEP':                c.cep,
            'Telefone':           c.telefone,
            'CNPJ':               c.cnpj,
            'Crédito Disponível': c.credito,
            'Última Compra':      c.ultima_compra,
            'Faturamento Total':  c.total_faturado,
            'Último Produto':     c.ultimo_produto,
            'Qtd Última Compra':  c.ultima_qt,
          };
        });
        var ws = XLSX.utils.json_to_sheet(linhas);
        ws['!cols'] = [
          {wch:6},{wch:10},{wch:35},{wch:20},
          {wch:35},{wch:20},{wch:12},{wch:15},{wch:18},{wch:18},{wch:14},{wch:18},{wch:20},{wch:10}
        ];
        XLSX.utils.book_append_sheet(wb, ws, 'Dia ' + (idx + 1));
      });
      XLSX.writeFile(wb, 'roteiro.xlsx');
    }
    </script>"""

    return navbar_html, conteudo_roteiro_html