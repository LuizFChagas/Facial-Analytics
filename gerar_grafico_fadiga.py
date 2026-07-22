"""
Gera o grafico de fadiga da reuniao a partir do CSV produzido por
reuniao_fadiga.py (colunas: minuto, timestamp, piscadas, bocejos).

Decisao de design: piscadas e bocejos sao duas grandezas de escalas
diferentes (piscadas/min costuma ser bem maior que bocejos/min). A
tentacao classica e usar um grafico de "dois eixos Y" (twin axis) num
unico plot - mas esse formato e enganoso: a escolha da escala de cada
eixo e arbitraria e pode fazer duas series parecerem correlacionadas (ou
nao) so por causa de como os eixos foram esticados. Aqui usamos
"small multiples": dois paineis empilhados, um por metrica, compartilhando
o eixo X (o minuto da reuniao) - da pra comparar as tendencias lado a lado
sem esse efeito de otica.

Uso:
    python gerar_grafico_fadiga.py
"""

import os

import matplotlib.pyplot as plt
import pandas as pd

CAMINHO_CSV = os.path.join("data", "reuniao_fadiga.csv")
CAMINHO_SAIDA = os.path.join("graficos", "reuniao_fadiga.png")

COR_SUPERFICIE = "#fcfcfb"
COR_PISCADAS = "#2a78d6"     # azul - slot categorico 1
COR_BOCEJOS = "#eb6834"      # laranja - slot categorico 2
COR_PICO = "#d03b3b"         # vermelho - status "critical", reservado pro destaque
COR_GRADE = "#e1e0d9"
COR_EIXO = "#c3c2b7"
COR_TEXTO_PRIMARIO = "#0b0b0b"
COR_TEXTO_SECUNDARIO = "#52514e"
COR_TEXTO_MUTED = "#898781"


def carregar_dados():
    return pd.read_csv(CAMINHO_CSV)


def gerar_grafico(df):
    minuto_pico = df.loc[df["bocejos"].idxmax(), "minuto"]

    fig, (eixo_piscadas, eixo_bocejos) = plt.subplots(
        2, 1, figsize=(10, 7), sharex=True, facecolor=COR_SUPERFICIE
    )

    for eixo, coluna, cor, rotulo in [
        (eixo_piscadas, "piscadas", COR_PISCADAS, "Piscadas por minuto"),
        (eixo_bocejos, "bocejos", COR_BOCEJOS, "Bocejos por minuto"),
    ]:
        eixo.set_facecolor(COR_SUPERFICIE)
        eixo.bar(df["minuto"], df[coluna], color=cor, width=0.6, zorder=2)
        eixo.set_title(rotulo, fontsize=12, color=COR_TEXTO_PRIMARIO, loc="left")
        eixo.grid(axis="y", color=COR_GRADE, linewidth=1, zorder=0)
        eixo.set_axisbelow(True)
        for spine in ("top", "right", "left"):
            eixo.spines[spine].set_visible(False)
        eixo.spines["bottom"].set_color(COR_EIXO)
        eixo.tick_params(axis="both", colors=COR_TEXTO_MUTED)

        # Destaca o minuto de pico de bocejos nos dois paineis, pra
        # facilitar comparar o que aconteceu com as piscadas no mesmo
        # instante. Cor "critical" sempre acompanhada de rotulo (nunca
        # so a cor) para nao depender de percepcao de cor do leitor.
        eixo.axvline(minuto_pico, color=COR_PICO, linewidth=1.5, linestyle="--", zorder=1)

    eixo_bocejos.annotate(
        "⚠ pico de fadiga",
        xy=(minuto_pico, df["bocejos"].max()),
        xytext=(8, 8),
        textcoords="offset points",
        color=COR_PICO,
        fontsize=10,
        fontweight="bold",
    )

    eixo_bocejos.set_xlabel("Minuto da reuniao", color=COR_TEXTO_SECUNDARIO, fontsize=10)
    eixo_bocejos.set_xticks(df["minuto"])

    fig.suptitle("Fadiga durante a reuniao", fontsize=16, color=COR_TEXTO_PRIMARIO, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    os.makedirs(os.path.dirname(CAMINHO_SAIDA), exist_ok=True)
    fig.savefig(CAMINHO_SAIDA, dpi=150, facecolor=COR_SUPERFICIE)
    print(f"Grafico salvo em: {CAMINHO_SAIDA}")
    print(f"Minuto de pico de bocejos (fadiga): {minuto_pico}")

    plt.show()


if __name__ == "__main__":
    dados = carregar_dados()
    gerar_grafico(dados)
