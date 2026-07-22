# Facial Analytics — Humor & Fadiga

Projeto em Python que usa a webcam para captar dados faciais (expressao e
landmarks) e transforma isso em dashboards/graficos com Pandas e
Matplotlib. Feito como base de conteudo tecnico de analise de dados para
postar no LinkedIn — cada escolha de metodo (deteccao de rosto, calculo de
EAR/MAR, forma do grafico) e comentada no codigo para servir de material
de estudo/explicacao.

O projeto tem **dois modos independentes**, cada um com um script de
captura e um script de visualizacao:

| Modo | Captura | Grafico |
|---|---|---|
| 1. Humor do Dia | `humor_do_dia.py` | `gerar_grafico_humor.py` |
| 2. Reuniao (fadiga) | `reuniao_fadiga.py` | `gerar_grafico_fadiga.py` |

## Estrutura do projeto

```
Facial-Analytics/
├── humor_do_dia.py          # Modo 1 - captura periodica de humor
├── gerar_grafico_humor.py   # Modo 1 - grafico de tendencia de humor
├── reuniao_fadiga.py        # Modo 2 - deteccao de fadiga em tempo real
├── gerar_grafico_fadiga.py  # Modo 2 - grafico de piscadas/bocejos
├── requirements.txt
├── data/                    # CSVs gerados pelos scripts de captura (git-ignored)
└── graficos/                # PNGs gerados pelos scripts de grafico (git-ignored)
```

## Instalacao

Requer Python 3.10+ e uma webcam.

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

`fer` depende de TensorFlow por baixo dos panos — a primeira instalacao
(e a primeira execucao, que baixa os pesos do modelo) pode demorar alguns
minutos.

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

Ao final do expediente (ou a qualquer momento, com os dados que ja foram
coletados):

```bash
python gerar_grafico_humor.py
```

Isso gera `graficos/humor_do_dia.png`: um grafico de linha do humor ao
longo do tempo.

### Racional tecnico

A classificacao usa a biblioteca [`fer`](https://github.com/JustinShenk/fer),
que combina dois modelos:

1. **Deteccao de rosto — MTCNN** (Multi-task Cascaded Convolutional
   Networks): localiza a caixa delimitadora do rosto no frame. Optamos por
   `mtcnn=True` em vez do Haar Cascade padrao do OpenCV porque o MTCNN e
   sensivelmente mais robusto a variacoes de angulo, iluminacao e distancia
   da camera — cenario tipico de uma webcam de notebook num ambiente real
   (nao um estudio com luz controlada).
2. **Classificacao de emocao**: uma CNN treinada no dataset **FER2013**,
   que retorna um score de confianca (0 a 1) para cada uma de 7 categorias:
   `angry`, `disgust`, `fear`, `happy`, `sad`, `surprise`, `neutral`. A
   expressao registrada e a de maior score.

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
serve para dar uma leitura rapida de tendencia, nao um diagnostico.

---

## Modo 2 — Reuniao (deteccao de fadiga)

Roda continuamente durante uma call, usando o **MediaPipe Face Mesh** para
extrair 468 landmarks faciais em tempo real. Mostra uma janela com o video,
a malha facial desenhada e os contadores ao vivo. Encerra ao pressionar
**`q`**.

```bash
python reuniao_fadiga.py
```

A cada minuto fechado (contado a partir do inicio da execucao), salva uma
linha em `data/reuniao_fadiga.csv`:

| minuto | timestamp | piscadas | bocejos |
|---|---|---|---|
| 1 | 2026-07-21T14:01:00 | 16 | 0 |

Ao final da reuniao:

```bash
python gerar_grafico_fadiga.py
```

Isso gera `graficos/reuniao_fadiga.png`, com piscadas e bocejos por minuto,
destacando automaticamente o minuto de pico de bocejos como **pico de
fadiga**.

### Racional tecnico

**EAR (Eye Aspect Ratio)** mede o quanto o olho esta aberto, a partir de 6
pontos ao redor dele (convencao de Soukupova & Cech, 2016):

```
EAR = (dist(p2,p6) + dist(p3,p5)) / (2 * dist(p1,p4))
```

`p1`/`p4` sao os cantos do olho (distancia horizontal); `p2`/`p6` e
`p3`/`p5` sao pares de pontos superior/inferior (distancia vertical). Com
o olho aberto, o EAR fica estavel em torno de 0.25–0.35; numa piscada, ele
despenca por 2–4 frames e volta a subir. O script conta uma piscada
quando o EAR fica abaixo do limiar (`0.21`) por pelo menos
`FRAMES_MIN_PISCADA` frames e depois volta a subir (transicao
fechado → aberto).

**MAR (Mouth Aspect Ratio)** usa exatamente a mesma formula, aplicada aos
landmarks dos labios. A diferenca esta no criterio de contagem: uma
piscada e rapida, mas um bocejo e uma abertura de boca **sustentada** — por
isso um bocejo so e contado quando o MAR fica acima do limiar (`0.60`) por
varios frames consecutivos seguidos (`FRAMES_MIN_BOCEJO`), e nao a cada
frame em que a boca esta aberta (o que inflaria a contagem e capturaria
falar/rir como bocejo).

**Por que dois graficos empilhados em vez de um grafico de eixo duplo?**
Piscadas/minuto e bocejos/minuto tem escalas bem diferentes. A solucao
classica seria um grafico com dois eixos Y (`twin axis`) — mas esse
formato costuma **enganar**: a escala de cada eixo e escolhida de forma
arbitraria, o que pode fazer duas series parecerem correlacionadas (ou
descorrelacionadas) so por causa de como os eixos foram esticados
visualmente. Em vez disso, `gerar_grafico_fadiga.py` usa **small
multiples**: dois paineis empilhados compartilhando o eixo X (minuto da
reuniao), com o minuto de pico de bocejos marcado nos dois — da pra
comparar as tendencias sem esse efeito de otica.

### Limitacoes conhecidas

- Detecta um rosto por vez (`max_num_faces=1`).
- Limiares de EAR/MAR sao empiricos — podem precisar de ajuste conforme a
  webcam, distancia e iluminacao do seu setup.
- `reuniao_fadiga.py` precisa de uma janela de video ativa (nao roda
  100% headless).
