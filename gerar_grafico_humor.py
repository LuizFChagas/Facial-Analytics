"""
Gera o grafico de "Humor do Dia" a partir do CSV produzido por humor_do_dia.py.

Cada expressao facial classificada pela FER e mapeada para um valor numerico
numa escala de bem-estar (-2 a +2), permitindo enxergar a variacao de humor
ao longo do expediente como uma linha do tempo continua, em vez de rotulos
categoricos soltos.

Uso:
    python gerar_grafico_humor.py
"""

import os

import matplotlib.pyplot as plt
import pandas as pd

CAMINHO_CSV = os.path.join("data", "humor_do_dia.csv")
CAMINHO_SAIDA = os.path.join("graficos", "humor_do_dia.png")

# Escala de bem-estar: mapeia cada uma das 7 emocoes da FER para um valor
# numerico. E uma escala subjetiva (nao ha "unidade" cientifica aqui) mas
# serve bem para visualizar tendencia geral de humor ao longo do tempo.
ESCALA_BEM_ESTAR = {
    "happy": 2,
    "surprise": 1,
    "neutral": 0,
    "fear": -1,
    "disgust": -1,
    "sad": -2,
    "angry": -2,
}

# Paleta (mesma logica de tokens usada nos demais graficos do projeto)
COR_SUPERFICIE = "#fcfcfb"
COR_LINHA = "#2a78d6"       # azul - serie principal (unica serie, sem legenda)
COR_GRADE = "#e1e0d9"       # gridline hairline
COR_EIXO = "#c3c2b7"        # baseline/eixo
COR_TEXTO_PRIMARIO = "#0b0b0b"
COR_TEXTO_SECUNDARIO = "#52514e"
COR_TEXTO_MUTED = "#898781"
COR_REFERENCIA = "#898781"  # linha tracejada em "neutro" (0)


def carregar_dados():
    df = pd.read_csv(CAMINHO_CSV, parse_dates=["timestamp"])
    df["valor_bem_estar"] = df["expressao"].map(ESCALA_BEM_ESTAR)
    return df


def gerar_grafico(df):
    fig, ax = plt.subplots(figsize=(10, 5), facecolor=COR_SUPERFICIE)
    ax.set_facecolor(COR_SUPERFICIE)

    ax.plot(
        df["timestamp"],
        df["valor_bem_estar"],
        color=COR_LINHA,
        linewidth=2,
        marker="o",
        markersize=6,
        solid_capstyle="round",
    )

    # Linha de referencia no "neutro" (0), pra dar contexto visual imediato
    ax.axhline(0, color=COR_REFERENCIA, linewidth=1, linestyle="--", zorder=0)

    # Rotula diretamente o pico mais positivo e o mais negativo do dia
    # (label direto em vez de legenda, ja que e serie unica)
    linha_maxima = df.loc[df["valor_bem_estar"].idxmax()]
    linha_minima = df.loc[df["valor_bem_estar"].idxmin()]
    for linha, deslocamento in [(linha_maxima, 10), (linha_minima, -14)]:
        ax.annotate(
            linha["expressao"],
            xy=(linha["timestamp"], linha["valor_bem_estar"]),
            xytext=(0, deslocamento),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color=COR_TEXTO_SECUNDARIO,
        )

    ax.set_title("Humor do Dia", fontsize=16, color=COR_TEXTO_PRIMARIO, loc="left", pad=16)
    ax.set_ylabel("Escala de bem-estar", color=COR_TEXTO_SECUNDARIO, fontsize=10)
    ax.set_yticks([-2, -1, 0, 1, 2])

    ax.grid(axis="y", color=COR_GRADE, linewidth=1)
    ax.set_axisbelow(True)

    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(COR_EIXO)

    ax.tick_params(axis="x", colors=COR_TEXTO_MUTED, rotation=30)
    ax.tick_params(axis="y", colors=COR_TEXTO_MUTED)

    fig.tight_layout()

    os.makedirs(os.path.dirname(CAMINHO_SAIDA), exist_ok=True)
    fig.savefig(CAMINHO_SAIDA, dpi=150, facecolor=COR_SUPERFICIE)
    print(f"Grafico salvo em: {CAMINHO_SAIDA}")

    plt.show()


if __name__ == "__main__":
    dados = carregar_dados()
    gerar_grafico(dados)
