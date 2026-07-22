"""
Dashboard local (Flask) para o Facial Analytics.

Serve uma pagina unica com dois modos (Humor do Dia / Reuniao) e expoe os
dados dos CSVs via API JSON pra pagina montar os graficos (Plotly) e a
tabela no navegador.

Se o CSV "de verdade" (gerado por humor_do_dia.py / reuniao_fadiga.py)
ainda nao existir, cai pro CSV de exemplo em exemplos/ so pra a tela nao
ficar vazia - a resposta da API sinaliza isso no campo "fonte".

Uso:
    python dashboard_app.py
    (abre em http://127.0.0.1:5000)
"""

import os

import pandas as pd
from flask import Flask, jsonify, render_template

app = Flask(__name__)

CAMINHO_HUMOR_REAL = os.path.join("data", "humor_do_dia.csv")
CAMINHO_HUMOR_EXEMPLO = os.path.join("exemplos", "humor_do_dia_exemplo.csv")

CAMINHO_FADIGA_REAL = os.path.join("data", "reuniao_fadiga.csv")
CAMINHO_FADIGA_EXEMPLO = os.path.join("exemplos", "reuniao_fadiga_exemplo.csv")

# Mesma escala de bem-estar usada em gerar_grafico_humor.py - mantida aqui
# tambem porque o dashboard e um consumidor independente do mesmo CSV.
ESCALA_BEM_ESTAR = {
    "happy": 2,
    "surprise": 1,
    "neutral": 0,
    "fear": -1,
    "disgust": -1,
    "sad": -2,
    "angry": -2,
}


def escolher_fonte(caminho_real, caminho_exemplo):
    """Usa o CSV real se ele ja existir; caso contrario, cai pro exemplo."""
    if os.path.isfile(caminho_real):
        return caminho_real, "real"
    return caminho_exemplo, "exemplo"


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/humor")
def api_humor():
    caminho, fonte = escolher_fonte(CAMINHO_HUMOR_REAL, CAMINHO_HUMOR_EXEMPLO)
    df = pd.read_csv(caminho, parse_dates=["timestamp"])
    df["valor_bem_estar"] = df["expressao"].map(ESCALA_BEM_ESTAR)
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")

    return jsonify({
        "fonte": fonte,
        "registros": df.to_dict(orient="records"),
    })


@app.route("/api/fadiga")
def api_fadiga():
    caminho, fonte = escolher_fonte(CAMINHO_FADIGA_REAL, CAMINHO_FADIGA_EXEMPLO)
    df = pd.read_csv(caminho)

    minuto_pico = int(df.loc[df["bocejos"].idxmax(), "minuto"]) if not df.empty else None

    return jsonify({
        "fonte": fonte,
        "minuto_pico": minuto_pico,
        "registros": df.to_dict(orient="records"),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
