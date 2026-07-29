# Facial Analytics — Humor & Fadiga

Projeto em Python que usa a webcam para captar dados faciais (expressao e
landmarks) e transforma isso em CSV, graficos e um dashboard local. Feito
como base de conteudo tecnico de analise de dados para postar no LinkedIn
— cada escolha de metodo (deteccao de rosto, calculo de EAR/MAR, forma do
grafico) tem um racional documentado abaixo.

O projeto tem **dois modos independentes**, cada um com um script de
captura e uma forma de visualizar o resultado (grafico estatico ou o
dashboard):

| Modo | Captura | Grafico estatico |
|---|---|---|
| 1. Humor do Dia | `humor_do_dia.py` | `gerar_grafico_humor.py` |
| 2. Reuniao (fadiga) | `reuniao_fadiga.py` | `gerar_grafico_fadiga.py` |

## Estrutura do projeto

```
Facial-Analytics/
├── humor_do_dia.py          # Modo 1 - captura periodica de humor
├── gerar_grafico_humor.py   # Modo 1 - grafico estatico de tendencia de humor
├── reuniao_fadiga.py        # Modo 2 - deteccao de fadiga em tempo real
├── gerar_grafico_fadiga.py  # Modo 2 - grafico estatico de piscadas/bocejos
├── dashboard_app.py         # Dashboard local (Flask) - le os CSVs e controla as capturas
├── humor_servico.py         # Servico auxiliar do dashboard (classificacao ao vivo, roda no venv 3.11)
├── templates/, static/      # Frontend do dashboard (HTML/CSS/JS + Plotly)
├── requirements.txt
├── data/                    # CSVs gerados pelos scripts de captura (git-ignored)
├── graficos/                # PNGs gerados pelos scripts de grafico (git-ignored)
└── modelos/                 # Modelo do MediaPipe baixado em tempo de execucao (git-ignored)
```

## Instalacao

Requer uma webcam e **dois ambientes Python**, por causa de uma
particularidade de compatibilidade:

- **Python principal** (3.10+): roda `reuniao_fadiga.py`, `dashboard_app.py`
  e os scripts de grafico. Usa `mediapipe`, que funciona normalmente em
  versoes recentes do Python.
- **Python 3.11 num venv separado** (`.venv-py311`): roda `humor_do_dia.py`
  e `humor_servico.py`. Esses dois dependem da lib `fer`, que por sua vez
  depende de **TensorFlow** — e o TensorFlow ainda nao tem build para
  versoes muito novas do Python (ex: 3.13+). Se voce ja estiver numa
  versao do Python que o TensorFlow suporta, pode usar o mesmo ambiente
  para tudo; o projeto so faz essa separacao pra nao travar em maquinas
  com Python mais novo.

```bash
# ambiente principal
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt

# ambiente extra, so se o TensorFlow nao instalar no principal
py -3.11 -m venv .venv-py311
.venv-py311\Scripts\pip install -r requirements.txt
```

`fer` depende de TensorFlow por baixo dos panos — a primeira instalacao
(e a primeira execucao, que baixa os pesos do modelo) pode demorar alguns
minutos. O `reuniao_fadiga.py` baixa o modelo do MediaPipe (`modelos/`) na
primeira execucao tambem.

---

## Dashboard local

```bash
python dashboard_app.py
# abre em http://127.0.0.1:5000
```

Tres abas:

- **Humor do Dia** e **Reuniao (Fadiga)**: leem os CSVs em `data/` e
  mostram graficos interativos (Plotly), KPIs e uma tabela com botao de
  excluir linha. Sem dado capturado ainda, mostram um estado vazio (o
  dashboard nunca usa dado ficticio de exemplo).
- **Testar Webcam**: pre-visualizacao ao vivo da camera direto no
  navegador, com classificacao de expressao em tempo real (a cada ~2s,
  via `humor_servico.py`) e botoes pra iniciar/parar as capturas reais
  sem precisar abrir terminal.

**A pre-visualizacao do navegador e os scripts de captura disputam a
mesma webcam** — desligue uma antes de iniciar a outra.

---

## Modo 1 — Humor do Dia

Roda em background e, a cada intervalo configuravel (padrao: **15
minutos**), tira um snapshot da webcam e classifica a expressao facial.

```bash
python humor_do_dia.py                # snapshot a cada 15 min
python humor_do_dia.py --intervalo 5  # snapshot a cada 5 min
```

Cada leitura vira uma linha em `data/humor_do_dia.csv`:

| timestamp | expressao | confianca |
|---|---|---|
| 2026-07-21T09:15:00 | happy | 0.8821 |

Pra visualizar como grafico estatico:

```bash
python gerar_grafico_humor.py
```

Isso gera `graficos/humor_do_dia.png`. (O dashboard mostra a mesma coisa,
interativa, na aba "Humor do Dia".)

### Racional tecnico

A classificacao usa a biblioteca [`fer`](https://github.com/JustinShenk/fer),
que combina dois modelos:

1. **Deteccao de rosto — MTCNN** (Multi-task Cascaded Convolutional
   Networks): localiza a caixa delimitadora do rosto no frame, numa
   cascata de 3 redes (P-Net → R-Net → O-Net) que vai refinando a regiao
   candidata. Optamos por `mtcnn=True` em vez do Haar Cascade padrao do
   OpenCV porque o MTCNN e sensivelmente mais robusto a variacoes de
   angulo, iluminacao e distancia da camera — cenario tipico de uma
   webcam de notebook num ambiente real (nao um estudio com luz
   controlada).
2. **Classificacao de emocao**: uma CNN treinada no dataset **FER2013**
   (~35 mil fotos de rosto rotuladas), que retorna um score de confianca
   (0 a 1) para cada uma de 7 categorias: `angry`, `disgust`, `fear`,
   `happy`, `sad`, `surprise`, `neutral`. A expressao registrada e a de
   maior score.

Para visualizar a tendencia ao longo do dia como uma linha continua (em
vez de 7 categorias soltas), cada emocao e mapeada para um valor numerico
numa **escala de bem-estar** de -2 a +2:

| Emocao | Valor |
|---|---|
| happy | +2 |
| surprise | +1 |
| neutral | 0 |
| fear / disgust | -1 |
| sad / angry | -2 |

E uma escala subjetiva (nao existe "unidade cientifica" de bem-estar) —
serve para dar uma leitura rapida de tendencia, nao um diagnostico. E
importante frisar: essas 7 categorias sao fixas (vem do FER2013, baseado
nas emocoes basicas de Ekman) — nao existe categoria "concentrado", por
exemplo, porque concentracao nao e uma expressao facial universal do
mesmo jeito que um sorriso.

---

## Modo 2 — Reuniao (deteccao de fadiga)

Roda continuamente durante uma call, usando o **MediaPipe Face Landmarker**
(Tasks API) para extrair 478 landmarks faciais em tempo real. Mostra uma
janela com o video, a malha facial desenhada e os contadores ao vivo.
Encerra ao pressionar **`q`**.

```bash
python reuniao_fadiga.py
```

> Usamos a Tasks API (`mp.tasks.vision.FaceLandmarker`) em vez da API
> classica `mp.solutions.face_mesh` porque essa ultima nao tem build do
> MediaPipe pra versoes recentes do Python — o Google descontinuou os
> builds pre-compilados de "solutions" nesses casos. A logica de EAR/MAR
> e identica; so a forma de obter os landmarks do frame muda.

A cada minuto fechado (contado a partir do inicio da execucao), salva uma
linha em `data/reuniao_fadiga.csv`:

| minuto | timestamp | piscadas | bocejos |
|---|---|---|---|
| 1 | 2026-07-21T14:01:00 | 16 | 0 |

Pra visualizar como grafico estatico:

```bash
python gerar_grafico_fadiga.py
```

Isso gera `graficos/reuniao_fadiga.png`, com piscadas e bocejos por
minuto, destacando automaticamente o minuto de pico de bocejos como
**pico de fadiga**. (O dashboard mostra a mesma coisa, interativa, na
aba "Reuniao (Fadiga)" — e lida com mais de uma reuniao no mesmo CSV sem
misturar os minutos de sessoes diferentes.)

### Racional tecnico

**EAR (Eye Aspect Ratio)** e **MAR (Mouth Aspect Ratio)** usam a mesma
formula geometrica, aplicada a seis pontos ao redor do olho ou da boca
(convencao de Soukupova & Cech, 2016):

```
razao = (dist(p2,p6) + dist(p3,p5)) / (2 * dist(p1,p4))
```

`p1`/`p4` sao os cantos (distancia horizontal, o "tamanho" da abertura).
`p2`/`p6` e `p3`/`p5` sao pares de pontos opostos, um em cima e um
embaixo (a distancia vertical, o "quao aberto"). Duas medidas verticais
em vez de uma so deixam o numero mais estavel.

- **EAR**: com o olho aberto fica estavel em torno de 0.25–0.35; numa
  piscada, despenca por 2–4 frames e volta a subir. Conta-se uma piscada
  quando o EAR fica abaixo do limiar (`LIMIAR_EAR = 0.21`) por pelo menos
  `FRAMES_MIN_PISCADA` frames e depois volta a subir.
- **MAR**: mesma formula, aplicada aos labios. A diferenca esta no
  criterio de contagem — uma piscada e rapida, mas um bocejo e uma
  abertura **sustentada**, entao so conta quando o MAR fica acima do
  limiar (`LIMIAR_MAR = 0.60`) por varios frames consecutivos
  (`FRAMES_MIN_BOCEJO`), nao a cada frame com a boca aberta (o que
  inflaria a contagem e capturaria falar/rir como bocejo).

**Por que dois graficos empilhados em vez de um grafico de eixo duplo?**
Piscadas/minuto e bocejos/minuto tem escalas bem diferentes. A solucao
classica seria um grafico com dois eixos Y (`twin axis`) — mas esse
formato costuma **enganar**: a escala de cada eixo e escolhida de forma
arbitraria, o que pode fazer duas series parecerem correlacionadas (ou
descorrelacionadas) so por causa de como os eixos foram esticados
visualmente. Em vez disso, usamos **small multiples**: paineis
empilhados compartilhando o eixo X, com o minuto de pico de bocejos
marcado em todos — da pra comparar as tendencias sem esse efeito de
otica.

### Limitacoes conhecidas

- Detecta um rosto por vez (`num_faces=1`).
- Limiares de EAR/MAR sao empiricos — podem precisar de ajuste conforme a
  webcam, distancia e iluminacao do seu setup.
- `reuniao_fadiga.py` precisa de uma janela de video ativa (nao roda
  100% headless).
- A pre-visualizacao da webcam no dashboard e os scripts de captura via
  OpenCV nao conseguem usar a camera ao mesmo tempo (limitacao do
  sistema operacional, nao do codigo).
