// Dashboard local do Facial Analytics: busca os dados nas rotas /api/* do
// Flask, desenha os graficos com Plotly.js, monta os tiles de KPI e
// preenche as tabelas.

const EMOJI_EXPRESSAO = {
  happy: "😄",
  neutral: "😐",
  sad: "😢",
  surprise: "😮",
  angry: "😠",
  fear: "😨",
  disgust: "🤢",
};

const LABEL_EXPRESSAO_PT = {
  happy: "Feliz",
  neutral: "Neutro",
  sad: "Triste",
  surprise: "Surpreso",
  angry: "Bravo",
  fear: "Medo",
  disgust: "Nojo",
};

function token(nome) {
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
}

function hexParaRgba(hex, alpha) {
  const limpo = hex.replace("#", "");
  const bigint = parseInt(limpo, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
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
    hoverlabel: {
      bgcolor: cores.tintaPrimaria === "#ffffff" ? "#1a1a19" : "#ffffff",
      bordercolor: "transparent",
      font: { family: "system-ui, -apple-system, Segoe UI, sans-serif" },
    },
    bargap: 0.35,
  }, extra);
}

const opcoesPlotly = { displayModeBar: false, responsive: true };

function anotacaoSemDados(cores) {
  return {
    text: "Nenhum dado ainda",
    xref: "paper", yref: "paper", x: 0.5, y: 0.5,
    showarrow: false,
    font: { size: 13, color: cores.tintaMuted, family: "system-ui, -apple-system, Segoe UI, sans-serif" },
  };
}

// --------------------------- Tiles de KPI ---------------------------

function tileKpi(rotulo, valorHtml, detalhe, classeExtra) {
  const div = document.createElement("div");
  div.className = "kpi" + (classeExtra ? ` ${classeExtra}` : "");
  div.innerHTML = `
    <span class="kpi-rotulo">${rotulo}</span>
    <span class="kpi-valor">${valorHtml}</span>
    ${detalhe ? `<span class="kpi-detalhe">${detalhe}</span>` : ""}
  `;
  return div;
}

function tendenciaHumor(media) {
  if (media >= 1) return "tendencia positiva";
  if (media <= -1) return "tendencia negativa";
  return "tendencia neutra";
}

function tileVazio(mensagem) {
  const div = document.createElement("div");
  div.className = "kpi kpi-vazio";
  div.innerHTML = `<span class="kpi-detalhe">${mensagem}</span>`;
  return div;
}

function renderizarKpisHumor(dados) {
  const container = document.getElementById("kpis-humor");
  container.innerHTML = "";
  if (!dados.length) {
    container.append(tileVazio('Nenhuma leitura ainda. Va em "Testar Webcam" e inicie a captura do Humor do Dia.'));
    return;
  }

  const media = dados.reduce((soma, d) => soma + d.valor_bem_estar, 0) / dados.length;
  const maisPositivo = dados.reduce((a, b) => (b.valor_bem_estar > a.valor_bem_estar ? b : a));
  const maisNegativo = dados.reduce((a, b) => (b.valor_bem_estar < a.valor_bem_estar ? b : a));
  const classeMedia = media >= 0.5 ? "kpi-acento" : media <= -0.5 ? "kpi-critico" : "";

  container.append(
    tileKpi("Leituras", String(dados.length)),
    tileKpi("Humor medio", `${media > 0 ? "+" : ""}${media.toFixed(1)}`, tendenciaHumor(media), classeMedia),
    tileKpi("Pico positivo", EMOJI_EXPRESSAO[maisPositivo.expressao] || "—", `${maisPositivo.expressao} · ${maisPositivo.timestamp.slice(11, 16)}`),
    tileKpi("Pico negativo", EMOJI_EXPRESSAO[maisNegativo.expressao] || "—", `${maisNegativo.expressao} · ${maisNegativo.timestamp.slice(11, 16)}`),
  );
}

function indiceDoPicoDeBocejos(dados) {
  // Acha o pico pelo maior valor de bocejos (posicao real na lista), nao
  // pelo "minuto" - esse numero recomeca em 1 a cada sessao/reuniao e
  // pode se repetir se houver mais de uma no mesmo CSV.
  if (!dados.length) return null;
  return dados.reduce((melhor, d, i) => (d.bocejos > dados[melhor].bocejos ? i : melhor), 0);
}

function renderizarKpisFadiga(dados) {
  const container = document.getElementById("kpis-fadiga");
  container.innerHTML = "";
  if (!dados.length) {
    container.append(tileVazio('Nenhuma leitura ainda. Va em "Testar Webcam" e inicie a captura da Reuniao.'));
    return;
  }

  const totalPiscadas = dados.reduce((soma, d) => soma + d.piscadas, 0);
  const totalBocejos = dados.reduce((soma, d) => soma + d.bocejos, 0);
  const mediaPiscadas = totalPiscadas / dados.length;
  const indicePico = indiceDoPicoDeBocejos(dados);
  const registroPico = indicePico != null ? dados[indicePico] : null;

  container.append(
    tileKpi("Total piscadas", String(totalPiscadas)),
    tileKpi("Total bocejos", String(totalBocejos), null, totalBocejos > 0 ? "kpi-critico" : ""),
    tileKpi("Piscadas / min", mediaPiscadas.toFixed(1)),
    tileKpi(
      "Pico de fadiga",
      registroPico ? `min ${registroPico.minuto}` : "—",
      registroPico ? `${registroPico.bocejos} bocejos nesse minuto (${registroPico.timestamp.slice(11, 16)})` : "",
      "kpi-critico",
    ),
  );
}

// --------------------------- Modo 1: Humor do Dia ---------------------------

let dadosHumorCache = null;

function construirSerieComQuebras(dados, limiteGapMinutos) {
  // Insere um ponto nulo entre leituras separadas por um gap grande (ex:
  // virada do dia sem captura), pra Plotly quebrar a linha em vez de
  // desenhar uma diagonal atravessando um periodo sem dado nenhum.
  const x = [];
  const y = [];
  const customdata = [];
  const yEmoji = [];
  const textoEmoji = [];

  dados.forEach((d, i) => {
    if (i > 0) {
      const gapMinutos = (new Date(d.timestamp) - new Date(dados[i - 1].timestamp)) / 60000;
      if (gapMinutos > limiteGapMinutos) {
        x.push(null);
        y.push(null);
        customdata.push([null, null]);
        yEmoji.push(null);
        textoEmoji.push("");
      }
    }
    x.push(d.timestamp);
    y.push(d.valor_bem_estar);
    customdata.push([d.expressao, d.confianca]);
    yEmoji.push(d.valor_bem_estar + 0.55);
    textoEmoji.push(EMOJI_EXPRESSAO[d.expressao] || "");
  });

  return { x, y, customdata, yEmoji, textoEmoji };
}

function desenharGraficoHumor(dados) {
  const cores = temasDoGrafico();
  const serie = construirSerieComQuebras(dados, 90);

  const traceArea = {
    type: "scatter",
    mode: "lines+markers",
    x: serie.x,
    y: serie.y,
    line: { color: cores.piscadas, width: 2.5, shape: "spline", smoothing: 0.4 },
    marker: { size: 7, color: cores.piscadas, line: { color: cores.tintaPrimaria === "#ffffff" ? "#1a1a19" : "#fcfcfb", width: 1.5 } },
    fill: "tozeroy",
    fillcolor: hexParaRgba(cores.piscadas, 0.14),
    fillgradient: {
      type: "vertical",
      colorscale: [[0, hexParaRgba(cores.piscadas, 0.02)], [1, hexParaRgba(cores.piscadas, 0.30)]],
    },
    customdata: serie.customdata,
    hovertemplate:
      "%{x|%H:%M}<br>" +
      "expressao: <b>%{customdata[0]}</b><br>" +
      "confianca: %{customdata[1]:.0%}<br>" +
      "bem-estar: %{y}<extra></extra>",
    showlegend: false,
  };

  // Segunda camada: emoji da expressao flutuando acima de cada leitura -
  // a leitura fica "com cara" em vez de so um numero na escala.
  const traceEmoji = {
    type: "scatter",
    mode: "text",
    x: serie.x,
    y: serie.yEmoji,
    text: serie.textoEmoji,
    textfont: { size: 18 },
    hoverinfo: "skip",
    showlegend: false,
  };

  const layout = layoutBase(cores, {
    yaxis: {
      gridcolor: cores.grade, zeroline: false, tickfont: { color: cores.tintaMuted },
      range: [-2.7, 2.9], tickvals: [-2, -1, 0, 1, 2], title: { text: "Bem-estar" },
    },
    shapes: [{
      type: "line", x0: 0, x1: 1, xref: "paper", y0: 0, y1: 0,
      line: { color: cores.tintaMuted, width: 1, dash: "dash" },
    }],
    annotations: dados.length ? [] : [anotacaoSemDados(cores)],
  });

  Plotly.newPlot("grafico-humor", [traceArea, traceEmoji], layout, opcoesPlotly);
}

function botaoExcluirHtml(modo, indice, fonte) {
  if (fonte !== "real") return "<td></td>";
  return `<td class="col-acao"><button class="btn-excluir" data-modo="${modo}" data-indice="${indice}" title="Excluir esta leitura">🗑</button></td>`;
}

function preencherTabelaHumor(dados, fonte) {
  const corpo = document.querySelector("#tabela-humor tbody");
  corpo.innerHTML = "";
  if (!dados.length) {
    corpo.innerHTML = '<tr><td colspan="5" class="linha-vazia">Nenhuma leitura ainda.</td></tr>';
    document.getElementById("humor-contagem").textContent = "0 leituras";
    return;
  }
  dados.forEach((linha, indice) => {
    const tr = document.createElement("tr");
    const hora = linha.timestamp.slice(11, 16);
    tr.innerHTML = `
      <td>${hora}</td>
      <td><span class="emoji-pill">${EMOJI_EXPRESSAO[linha.expressao] || ""} ${linha.expressao}</span></td>
      <td class="num">${(linha.confianca * 100).toFixed(0)}%</td>
      <td class="num">${linha.valor_bem_estar > 0 ? "+" : ""}${linha.valor_bem_estar}</td>
      ${botaoExcluirHtml("humor", indice, fonte)}
    `;
    corpo.appendChild(tr);
  });
  document.getElementById("humor-contagem").textContent = `${dados.length} leituras`;
}

async function excluirLinha(modo, indice) {
  if (!confirm("Excluir essa leitura? Isso remove a linha do CSV e nao da pra desfazer.")) return;
  const resposta = await fetch(`/api/${modo}/excluir`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ indice }),
  });
  if (!resposta.ok) {
    const erro = await resposta.json().catch(() => ({}));
    alert(erro.erro || "Nao foi possivel excluir essa leitura.");
    return;
  }
  if (modo === "humor") carregarHumor();
  else carregarFadiga();
}

document.addEventListener("click", (evento) => {
  const botao = evento.target.closest(".btn-excluir");
  if (!botao) return;
  excluirLinha(botao.dataset.modo, Number(botao.dataset.indice));
});

async function carregarHumor() {
  const resposta = await fetch("/api/humor");
  const payload = await resposta.json();
  dadosHumorCache = payload.registros;

  const tagFonte = document.getElementById("humor-fonte");
  tagFonte.textContent = payload.fonte === "real" ? "dados reais" : "sem dados ainda";

  renderizarKpisHumor(payload.registros);
  desenharGraficoHumor(payload.registros);
  preencherTabelaHumor(payload.registros, payload.fonte);
}

// --------------------------- Modo 2: Reuniao (Fadiga) ---------------------------

let dadosFadigaCache = null;

function faixaDestaquePico(minutoPico, cores) {
  return {
    type: "rect",
    xref: "x", x0: minutoPico - 0.45, x1: minutoPico + 0.45,
    yref: "paper", y0: 0, y1: 1,
    fillcolor: hexParaRgba(cores.critico, 0.10),
    line: { width: 0 },
    layer: "below",
  };
}

function linhaPico(minutoPico, cores) {
  return {
    type: "line", x0: minutoPico, x1: minutoPico, xref: "x", y0: 0, y1: 1, yref: "paper",
    line: { color: cores.critico, width: 1.5, dash: "dash" },
  };
}

function construirPosicoesSequenciais(dados, limiteGapMinutos) {
  // O "minuto" de cada reuniao recomeca em 1 - se houver mais de uma
  // sessao no mesmo CSV, os minutos colidem (duas reunioes teriam ambas
  // um minuto 1, 2, 3...). Por isso o eixo X usa uma posicao sequencial
  // propria, nao o minuto cru; um gap grande de horario abre um espaco
  // visual pra marcar "comecou uma sessao nova".
  const posicoes = [];
  let pos = 0;
  dados.forEach((d, i) => {
    if (i > 0) {
      const gapMinutos = (new Date(d.timestamp) - new Date(dados[i - 1].timestamp)) / 60000;
      if (gapMinutos > limiteGapMinutos) pos += 2;
    }
    pos += 1;
    posicoes.push(pos);
  });
  return posicoes;
}

function divisoresDeSessao(dados, posicoes, cores) {
  const divisores = [];
  for (let i = 1; i < dados.length; i++) {
    if (posicoes[i] - posicoes[i - 1] > 1) {
      divisores.push({
        type: "line", xref: "x", x0: (posicoes[i - 1] + posicoes[i]) / 2, x1: (posicoes[i - 1] + posicoes[i]) / 2,
        yref: "paper", y0: 0, y1: 1,
        line: { color: cores.grade, width: 1, dash: "dot" },
      });
    }
  }
  return divisores;
}

function desenharGraficosFadiga(dados) {
  const cores = temasDoGrafico();
  const posicoes = construirPosicoesSequenciais(dados, 90);
  const customdata = dados.map((d) => [d.minuto]);

  const indicePico = indiceDoPicoDeBocejos(dados);
  const posicaoPico = indicePico != null ? posicoes[indicePico] : null;

  const formas = [
    ...divisoresDeSessao(dados, posicoes, cores),
    ...(posicaoPico != null ? [faixaDestaquePico(posicaoPico, cores), linhaPico(posicaoPico, cores)] : []),
  ];

  Plotly.newPlot("grafico-piscadas", [{
    type: "bar",
    x: posicoes,
    y: dados.map((d) => d.piscadas),
    customdata,
    marker: {
      color: dados.map((d) => d.piscadas),
      colorscale: [[0, hexParaRgba(cores.piscadas, 0.35)], [1, cores.piscadas]],
      cornerradius: 6,
      line: { width: 0 },
    },
    hovertemplate: "minuto %{customdata[0]}<br>%{y} piscadas<extra></extra>",
  }], layoutBase(cores, {
    xaxis: { gridcolor: cores.grade, tickfont: { color: cores.tintaMuted }, showticklabels: false },
    shapes: formas,
    annotations: dados.length ? [] : [anotacaoSemDados(cores)],
  }), opcoesPlotly);

  const anotacoesBocejos = [];
  if (posicaoPico != null) {
    anotacoesBocejos.push({
      x: posicaoPico, y: 1, yref: "paper", yshift: 14,
      text: "⚠ pico de fadiga", showarrow: false,
      font: { color: cores.critico, size: 12, family: "system-ui, -apple-system, Segoe UI, sans-serif" },
      bgcolor: hexParaRgba(cores.critico, 0.12),
      borderpad: 4,
    });
  }
  if (!dados.length) anotacoesBocejos.push(anotacaoSemDados(cores));

  Plotly.newPlot("grafico-bocejos", [{
    type: "bar",
    x: posicoes,
    y: dados.map((d) => d.bocejos),
    customdata,
    marker: {
      color: dados.map((d) => d.bocejos),
      colorscale: [[0, hexParaRgba(cores.bocejos, 0.35)], [1, cores.bocejos]],
      cornerradius: 6,
      line: { width: 0 },
    },
    hovertemplate: "minuto %{customdata[0]}<br>%{y} bocejos<extra></extra>",
  }], layoutBase(cores, {
    xaxis: { gridcolor: cores.grade, tickfont: { color: cores.tintaMuted }, showticklabels: false, title: { text: "Minuto da reuniao (passe o mouse pra ver o valor exato)" } },
    shapes: formas,
    annotations: anotacoesBocejos,
  }), opcoesPlotly);
}

function preencherTabelaFadiga(dados, fonte) {
  const corpo = document.querySelector("#tabela-fadiga tbody");
  corpo.innerHTML = "";
  if (!dados.length) {
    corpo.innerHTML = '<tr><td colspan="5" class="linha-vazia">Nenhuma leitura ainda.</td></tr>';
    document.getElementById("fadiga-contagem").textContent = "0 minutos";
    return;
  }
  const indicePico = indiceDoPicoDeBocejos(dados);
  dados.forEach((linha, indice) => {
    const tr = document.createElement("tr");
    if (indice === indicePico) tr.classList.add("linha-pico");
    const hora = String(linha.timestamp).slice(11, 16);
    tr.innerHTML = `
      <td class="num">${linha.minuto}</td>
      <td>${hora}</td>
      <td class="num">${linha.piscadas}</td>
      <td class="num">${linha.bocejos}</td>
      ${botaoExcluirHtml("fadiga", indice, fonte)}
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
  tagFonte.textContent = payload.fonte === "real" ? "dados reais" : "sem dados ainda";

  const indicePico = indiceDoPicoDeBocejos(payload.registros);
  const tagPico = document.getElementById("fadiga-pico");
  tagPico.textContent = indicePico != null ? `pico no minuto ${payload.registros[indicePico].minuto}` : "sem dados";

  renderizarKpisFadiga(payload.registros);
  desenharGraficosFadiga(payload.registros);
  preencherTabelaFadiga(payload.registros, payload.fonte);
}

// --------------------------- Testar Webcam ---------------------------

let streamCamera = null;
let cicloClassificacao = null;
let classificandoAgora = false;

async function ligarPreviewCamera() {
  const aviso = document.getElementById("webcam-aviso");
  aviso.classList.add("is-hidden");
  aviso.textContent = "";

  try {
    streamCamera = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    document.getElementById("video-preview").srcObject = streamCamera;
    document.getElementById("webcam-status").textContent = "ligada";
    document.getElementById("btn-ligar-camera").disabled = true;
    document.getElementById("btn-desligar-camera").disabled = false;
    iniciarClassificacaoAoVivo();
  } catch (erro) {
    aviso.textContent = `Nao foi possivel acessar a camera: ${erro.message}. Verifique se ela nao esta em uso por outro programa (ou pela captura Python abaixo) e se o navegador tem permissao.`;
    aviso.classList.remove("is-hidden");
  }
}

function desligarPreviewCamera() {
  if (streamCamera) {
    streamCamera.getTracks().forEach((faixa) => faixa.stop());
    streamCamera = null;
  }
  document.getElementById("video-preview").srcObject = null;
  document.getElementById("webcam-status").textContent = "desligada";
  document.getElementById("btn-ligar-camera").disabled = false;
  document.getElementById("btn-desligar-camera").disabled = true;
  pararClassificacaoAoVivo();
}

document.getElementById("btn-ligar-camera").addEventListener("click", ligarPreviewCamera);
document.getElementById("btn-desligar-camera").addEventListener("click", desligarPreviewCamera);
window.addEventListener("beforeunload", desligarPreviewCamera);

// --- Classificacao de expressao ao vivo na pre-visualizacao ---
//
// O navegador captura um frame do <video> a cada poucos segundos, manda
// pro dashboard, que repassa pro servico Python (humor_servico.py, que
// roda o mesmo FER do Modo 1) e mostra o resultado como texto. Nao e
// video continuo (o classificador e pesado demais pra 30fps) - e uma
// foto periodica, no mesmo espirito do humor_do_dia.py.

function capturarFrameComoJpegBase64() {
  const video = document.getElementById("video-preview");
  const canvas = document.getElementById("canvas-captura");
  if (!video.videoWidth) return null;

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  return canvas.toDataURL("image/jpeg", 0.8);
}

function mostrarExpressao(texto) {
  const elemento = document.getElementById("webcam-expressao");
  elemento.textContent = texto;
  elemento.classList.remove("is-hidden");
}

async function classificarFrameAtual() {
  if (classificandoAgora) return; // nao empilha requisicoes se uma anterior ainda nao voltou
  const imagem = capturarFrameComoJpegBase64();
  if (!imagem) return;

  classificandoAgora = true;
  try {
    const resposta = await fetch("/api/webcam/classificar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ imagem }),
    });
    const payload = await resposta.json();

    if (payload.status === "carregando") {
      mostrarExpressao("Carregando modelo de classificacao... (so na primeira vez, leva uns 10-20s)");
    } else if (payload.expressao) {
      const emoji = EMOJI_EXPRESSAO[payload.expressao] || "";
      const rotulo = LABEL_EXPRESSAO_PT[payload.expressao] || payload.expressao;
      const confianca = payload.confianca != null ? ` (${(payload.confianca * 100).toFixed(0)}%)` : "";
      mostrarExpressao(`${emoji} ${rotulo}${confianca}`);
    } else {
      mostrarExpressao("Nenhum rosto detectado");
    }
  } catch (erro) {
    mostrarExpressao("Nao foi possivel classificar agora.");
  } finally {
    classificandoAgora = false;
  }
}

function iniciarClassificacaoAoVivo() {
  mostrarExpressao("Analisando...");
  classificarFrameAtual();
  cicloClassificacao = setInterval(classificarFrameAtual, 2000);
}

function pararClassificacaoAoVivo() {
  if (cicloClassificacao) {
    clearInterval(cicloClassificacao);
    cicloClassificacao = null;
  }
  document.getElementById("webcam-expressao").classList.add("is-hidden");
}

// --- Controle dos processos de captura (humor_do_dia.py / reuniao_fadiga.py) ---

const BOTOES_CAPTURA = {
  humor: { iniciar: "btn-iniciar-humor", parar: "btn-parar-humor", status: "status-humor-captura" },
  fadiga: { iniciar: "btn-iniciar-fadiga", parar: "btn-parar-fadiga", status: "status-fadiga-captura" },
};

function aplicarStatusCaptura(modo, rodando) {
  const refs = BOTOES_CAPTURA[modo];
  const tagStatus = document.getElementById(refs.status);
  tagStatus.textContent = rodando ? "rodando" : "parado";
  tagStatus.classList.toggle("tag-rodando", rodando);
  document.getElementById(refs.iniciar).disabled = rodando;
  document.getElementById(refs.parar).disabled = !rodando;
}

async function atualizarStatusCaptura() {
  try {
    const resposta = await fetch("/api/captura/status");
    const status = await resposta.json();
    aplicarStatusCaptura("humor", status.humor === "rodando");
    aplicarStatusCaptura("fadiga", status.fadiga === "rodando");
  } catch (erro) {
    // dashboard offline momentaneamente - tenta de novo no proximo ciclo
  }
}

async function iniciarCaptura(modo, corpoExtra) {
  await fetch("/api/captura/iniciar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modo, ...corpoExtra }),
  });
  atualizarStatusCaptura();
}

async function pararCaptura(modo) {
  await fetch("/api/captura/parar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modo }),
  });
  atualizarStatusCaptura();
}

document.getElementById("btn-iniciar-humor").addEventListener("click", () => {
  const intervalo = Number(document.getElementById("input-intervalo-humor").value) || 15;
  iniciarCaptura("humor", { intervalo });
});
document.getElementById("btn-parar-humor").addEventListener("click", () => pararCaptura("humor"));
document.getElementById("btn-iniciar-fadiga").addEventListener("click", () => iniciarCaptura("fadiga"));
document.getElementById("btn-parar-fadiga").addEventListener("click", () => pararCaptura("fadiga"));

atualizarStatusCaptura();
setInterval(atualizarStatusCaptura, 4000);

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

// Permite abrir direto numa aba especifica via #humor / #fadiga / #webcam (link compartilhavel)
const abaInicial = window.location.hash.replace("#", "");
if (abaInicial === "fadiga" || abaInicial === "webcam") ativarAba(abaInicial);

// Redesenha os graficos quando o tema do SO muda (light/dark), ja que as
// cores do Plotly sao fixadas no momento do desenho, nao acompanham CSS sozinhas.
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (dadosHumorCache) desenharGraficoHumor(dadosHumorCache);
  if (dadosFadigaCache) desenharGraficosFadiga(dadosFadigaCache.registros);
});

carregarHumor();
carregarFadiga();
