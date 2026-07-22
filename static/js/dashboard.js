// Dashboard local do Facial Analytics: busca os dados nas rotas /api/* do
// Flask, desenha os graficos com Plotly.js e preenche as tabelas.

function token(nome) {
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
}

function temasDoGrafico() {
  // Le as cores atuais direto do CSS (que ja resolve dark/light sozinho
  // via prefers-color-scheme), pra o grafico acompanhar o tema do SO.
  return {
    tintaPrimaria: token("--ink-primary"),
    tintaSecundaria: token("--ink-secondary"),
    tintaMuted: token("--ink-muted"),
    grade: token("--grid-line"),
    piscadas: token("--accent-piscadas"),
    bocejos: token("--accent-bocejos"),
    critico: token("--accent-critical"),
  };
}

function layoutBase(cores, extra) {
  return Object.assign({
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    margin: { l: 44, r: 16, t: 8, b: 36 },
    font: { family: "system-ui, -apple-system, Segoe UI, sans-serif", color: cores.tintaSecundaria, size: 12 },
    xaxis: { gridcolor: cores.grade, zeroline: false, linecolor: cores.grade, tickfont: { color: cores.tintaMuted } },
    yaxis: { gridcolor: cores.grade, zeroline: false, tickfont: { color: cores.tintaMuted } },
    hoverlabel: { bgcolor: cores.tintaPrimaria === "#ffffff" ? "#1a1a19" : "#ffffff" },
  }, extra);
}

const opcoesPlotly = { displayModeBar: false, responsive: true };

// --------------------------- Modo 1: Humor do Dia ---------------------------

let dadosHumorCache = null;

function desenharGraficoHumor(dados) {
  const cores = temasDoGrafico();

  const trace = {
    type: "scatter",
    mode: "lines+markers",
    x: dados.map((d) => d.timestamp),
    y: dados.map((d) => d.valor_bem_estar),
    line: { color: cores.piscadas, width: 2, shape: "linear" },
    marker: { size: 7, color: cores.piscadas },
    customdata: dados.map((d) => [d.expressao, d.confianca]),
    hovertemplate:
      "%{x|%H:%M}<br>" +
      "expressao: <b>%{customdata[0]}</b><br>" +
      "confianca: %{customdata[1]:.0%}<br>" +
      "bem-estar: %{y}<extra></extra>",
  };

  const layout = layoutBase(cores, {
    yaxis: {
      gridcolor: cores.grade, zeroline: false, tickfont: { color: cores.tintaMuted },
      range: [-2.4, 2.4], tickvals: [-2, -1, 0, 1, 2], title: { text: "Bem-estar" },
    },
    shapes: [{
      type: "line", x0: 0, x1: 1, xref: "paper", y0: 0, y1: 0,
      line: { color: cores.tintaMuted, width: 1, dash: "dash" },
    }],
  });

  Plotly.newPlot("grafico-humor", [trace], layout, opcoesPlotly);
}

function preencherTabelaHumor(dados) {
  const corpo = document.querySelector("#tabela-humor tbody");
  corpo.innerHTML = "";
  dados.forEach((linha) => {
    const tr = document.createElement("tr");
    const hora = linha.timestamp.slice(11, 16);
    tr.innerHTML = `
      <td>${hora}</td>
      <td><span class="emoji-pill">${linha.expressao}</span></td>
      <td class="num">${(linha.confianca * 100).toFixed(0)}%</td>
      <td class="num">${linha.valor_bem_estar > 0 ? "+" : ""}${linha.valor_bem_estar}</td>
    `;
    corpo.appendChild(tr);
  });
  document.getElementById("humor-contagem").textContent = `${dados.length} leituras`;
}

async function carregarHumor() {
  const resposta = await fetch("/api/humor");
  const payload = await resposta.json();
  dadosHumorCache = payload.registros;

  const tagFonte = document.getElementById("humor-fonte");
  tagFonte.textContent = payload.fonte === "real" ? "dados reais" : "dados de exemplo";

  desenharGraficoHumor(payload.registros);
  preencherTabelaHumor(payload.registros);
}

// --------------------------- Modo 2: Reuniao (Fadiga) ---------------------------

let dadosFadigaCache = null;

function desenharGraficosFadiga(dados, minutoPico) {
  const cores = temasDoGrafico();
  const minutos = dados.map((d) => d.minuto);

  const linhaPico = (eixoY) => ({
    type: "line", x0: minutoPico, x1: minutoPico, xref: "x", y0: 0, y1: 1, yref: "paper",
    line: { color: cores.critico, width: 1.5, dash: "dash" },
  });

  Plotly.newPlot("grafico-piscadas", [{
    type: "bar",
    x: minutos,
    y: dados.map((d) => d.piscadas),
    marker: { color: cores.piscadas },
    hovertemplate: "minuto %{x}<br>%{y} piscadas<extra></extra>",
  }], layoutBase(cores, {
    xaxis: { gridcolor: cores.grade, tickfont: { color: cores.tintaMuted }, dtick: 1 },
    shapes: minutoPico != null ? [linhaPico()] : [],
  }), opcoesPlotly);

  Plotly.newPlot("grafico-bocejos", [{
    type: "bar",
    x: minutos,
    y: dados.map((d) => d.bocejos),
    marker: { color: cores.bocejos },
    hovertemplate: "minuto %{x}<br>%{y} bocejos<extra></extra>",
  }], layoutBase(cores, {
    xaxis: { gridcolor: cores.grade, tickfont: { color: cores.tintaMuted }, dtick: 1, title: { text: "Minuto da reuniao" } },
    shapes: minutoPico != null ? [linhaPico()] : [],
    annotations: minutoPico != null ? [{
      x: minutoPico, y: 1, yref: "paper", yshift: 10,
      text: "⚠ pico de fadiga", showarrow: false,
      font: { color: cores.critico, size: 12, family: "system-ui, -apple-system, Segoe UI, sans-serif" },
    }] : [],
  }), opcoesPlotly);
}

function preencherTabelaFadiga(dados, minutoPico) {
  const corpo = document.querySelector("#tabela-fadiga tbody");
  corpo.innerHTML = "";
  dados.forEach((linha) => {
    const tr = document.createElement("tr");
    if (linha.minuto === minutoPico) tr.classList.add("linha-pico");
    const hora = String(linha.timestamp).slice(11, 16);
    tr.innerHTML = `
      <td class="num">${linha.minuto}</td>
      <td>${hora}</td>
      <td class="num">${linha.piscadas}</td>
      <td class="num">${linha.bocejos}</td>
    `;
    corpo.appendChild(tr);
  });
  document.getElementById("fadiga-contagem").textContent = `${dados.length} minutos`;
}

async function carregarFadiga() {
  const resposta = await fetch("/api/fadiga");
  const payload = await resposta.json();
  dadosFadigaCache = payload;

  const tagFonte = document.getElementById("fadiga-fonte");
  tagFonte.textContent = payload.fonte === "real" ? "dados reais" : "dados de exemplo";

  const tagPico = document.getElementById("fadiga-pico");
  tagPico.textContent = payload.minuto_pico != null ? `pico no minuto ${payload.minuto_pico}` : "sem dados";

  desenharGraficosFadiga(payload.registros, payload.minuto_pico);
  preencherTabelaFadiga(payload.registros, payload.minuto_pico);
}

// --------------------------- Abas e tema ---------------------------

function ativarAba(nome) {
  document.querySelectorAll(".tab-btn").forEach((botao) => {
    const ativo = botao.dataset.tab === nome;
    botao.classList.toggle("is-active", ativo);
    botao.setAttribute("aria-selected", String(ativo));
  });
  document.querySelectorAll(".painel").forEach((painel) => {
    painel.classList.toggle("is-hidden", painel.dataset.panel !== nome);
  });
  // Plotly precisa de um resize apos sair de display:none pra medir o container certo
  if (nome === "humor" && dadosHumorCache) Plotly.Plots.resize("grafico-humor");
  if (nome === "fadiga" && dadosFadigaCache) {
    Plotly.Plots.resize("grafico-piscadas");
    Plotly.Plots.resize("grafico-bocejos");
  }
}

document.querySelectorAll(".tab-btn").forEach((botao) => {
  botao.addEventListener("click", () => {
    ativarAba(botao.dataset.tab);
    history.replaceState(null, "", `#${botao.dataset.tab}`);
  });
});

// Permite abrir direto numa aba especifica via #humor / #fadiga (link compartilhavel)
const abaInicial = window.location.hash.replace("#", "");
if (abaInicial === "fadiga") ativarAba("fadiga");

// Redesenha os graficos quando o tema do SO muda (light/dark), ja que as
// cores do Plotly sao fixadas no momento do desenho, nao acompanham CSS sozinhas.
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (dadosHumorCache) desenharGraficoHumor(dadosHumorCache);
  if (dadosFadigaCache) desenharGraficosFadiga(dadosFadigaCache.registros, dadosFadigaCache.minuto_pico);
});

carregarHumor();
carregarFadiga();
