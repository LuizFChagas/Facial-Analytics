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
import signal
import subprocess
import sys
import threading

import pandas as pd
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# humor_do_dia.py depende do "fer" (que por sua vez depende de TensorFlow).
# TensorFlow ainda nao tem build pro Python usado por este projeto, entao
# esse modo roda num venv Python 3.11 separado (veja o README). Se esse
# venv nao existir, cai pro mesmo Python do dashboard - o processo so vai
# falhar avisando que falta o "fer", o que e mais claro que travar aqui.
CAMINHO_PYTHON_HUMOR = os.path.join(".venv-py311", "Scripts", "python.exe")
if not os.path.isfile(CAMINHO_PYTHON_HUMOR):
    CAMINHO_PYTHON_HUMOR = sys.executable

# reuniao_fadiga.py usa mediapipe, que roda de boa no mesmo Python do dashboard.
CAMINHO_PYTHON_FADIGA = sys.executable

# Processos de captura disparados pelo dashboard (um por modo). So faz
# sentido ter uma instancia de cada rodando por vez.
processos_captura = {"humor": None, "fadiga": None}
trava_processos = threading.Lock()

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


def excluir_registro(caminho_real, corpo):
    """Remove uma linha (por indice) do CSV real e reescreve o arquivo.

    So opera no CSV real (nunca no de exemplo) - excluir dados ficticios
    nao faz sentido e sujaria um arquivo versionado no git.
    """
    if not os.path.isfile(caminho_real):
        return jsonify({"erro": "nao ha dados reais pra excluir (a tela esta mostrando dados de exemplo)"}), 400

    indice = corpo.get("indice")
    if not isinstance(indice, int):
        return jsonify({"erro": "indice invalido"}), 400

    df = pd.read_csv(caminho_real)
    if indice < 0 or indice >= len(df):
        return jsonify({"erro": "indice fora do intervalo"}), 400

    df = df.drop(df.index[indice])
    df.to_csv(caminho_real, index=False)

    return jsonify({"status": "excluido", "linhas_restantes": len(df)})


@app.route("/api/humor/excluir", methods=["POST"])
def api_humor_excluir():
    return excluir_registro(CAMINHO_HUMOR_REAL, request.get_json(silent=True) or {})


@app.route("/api/fadiga/excluir", methods=["POST"])
def api_fadiga_excluir():
    return excluir_registro(CAMINHO_FADIGA_REAL, request.get_json(silent=True) or {})


def processo_esta_rodando(modo):
    processo = processos_captura.get(modo)
    return processo is not None and processo.poll() is None


@app.route("/api/captura/status")
def api_captura_status():
    return jsonify({modo: ("rodando" if processo_esta_rodando(modo) else "parado") for modo in processos_captura})


@app.route("/api/captura/iniciar", methods=["POST"])
def api_captura_iniciar():
    corpo = request.get_json(silent=True) or {}
    modo = corpo.get("modo")
    if modo not in processos_captura:
        return jsonify({"erro": "modo invalido"}), 400

    with trava_processos:
        if processo_esta_rodando(modo):
            return jsonify({"status": "rodando", "aviso": "essa captura ja estava rodando"})

        if modo == "humor":
            intervalo = str(corpo.get("intervalo", 15))
            comando = [CAMINHO_PYTHON_HUMOR, "humor_do_dia.py", "--intervalo", intervalo]
        else:
            comando = [CAMINHO_PYTHON_FADIGA, "reuniao_fadiga.py"]

        # No Windows, colocar o processo num novo grupo permite mandar um
        # Ctrl+Break nele depois (api_captura_parar), o que interrompe o
        # script de forma limpa (libera a webcam) em vez de um kill bruto.
        opcoes = {}
        if os.name == "nt":
            opcoes["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            processos_captura[modo] = subprocess.Popen(comando, **opcoes)
        except OSError as erro:
            return jsonify({"erro": f"nao foi possivel iniciar: {erro}"}), 500

    return jsonify({"status": "rodando"})


@app.route("/api/captura/parar", methods=["POST"])
def api_captura_parar():
    corpo = request.get_json(silent=True) or {}
    modo = corpo.get("modo")
    if modo not in processos_captura:
        return jsonify({"erro": "modo invalido"}), 400

    with trava_processos:
        processo = processos_captura.get(modo)
        if processo is not None and processo.poll() is None:
            try:
                if os.name == "nt":
                    processo.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    processo.terminate()
            except (OSError, ValueError):
                processo.terminate()
        processos_captura[modo] = None

    return jsonify({"status": "parado"})


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
