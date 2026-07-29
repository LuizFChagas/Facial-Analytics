"""
Dashboard local (Flask) para o Facial Analytics.

Serve uma pagina unica com dois modos (Humor do Dia / Reuniao) e expoe os
dados dos CSVs via API JSON pra pagina montar os graficos (Plotly) e a
tabela no navegador.

So mostra dados reais (gerados por humor_do_dia.py / reuniao_fadiga.py).
Se o CSV ainda nao existir ou estiver vazio, a API responde com uma lista
vazia e a pagina mostra um estado de "nenhuma leitura ainda" - sem dado
ficticio de exemplo.

Uso:
    python dashboard_app.py
    (abre em http://127.0.0.1:5000)
"""

import base64
import json
import os
import signal
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import cv2
import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options as mp_base_options
import mediapipe as mp

from reuniao_fadiga import CAMINHO_MODELO, garantir_modelo

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

# Servico auxiliar (humor_servico.py) que roda o classificador FER no
# Python 3.11, pra pre-visualizacao da webcam poder mostrar a expressao
# detectada ao vivo. Sobe sob demanda (na primeira vez que a aba de
# pre-visualizacao pede uma classificacao) porque carregar o modelo
# demora alguns segundos.
URL_SERVICO_HUMOR = "http://127.0.0.1:5051"
processo_servico_humor = None
trava_servico_humor = threading.Lock()


def servico_humor_esta_de_pe():
    try:
        with urllib.request.urlopen(f"{URL_SERVICO_HUMOR}/saude", timeout=0.5) as resposta:
            return json.loads(resposta.read()).get("modelo_carregado", False)
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def garantir_servico_humor_iniciado():
    global processo_servico_humor
    with trava_servico_humor:
        if processo_servico_humor is not None and processo_servico_humor.poll() is None:
            return
        opcoes = {}
        if os.name == "nt":
            opcoes["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        processo_servico_humor = subprocess.Popen(
            [CAMINHO_PYTHON_HUMOR, "humor_servico.py"], **opcoes
        )

CAMINHO_HUMOR_REAL = os.path.join("data", "humor_do_dia.csv")
CAMINHO_FADIGA_REAL = os.path.join("data", "reuniao_fadiga.csv")

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


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/humor")
def api_humor():
    if not os.path.isfile(CAMINHO_HUMOR_REAL):
        return jsonify({"fonte": "vazio", "registros": []})

    df = pd.read_csv(CAMINHO_HUMOR_REAL, parse_dates=["timestamp"])
    df["valor_bem_estar"] = df["expressao"].map(ESCALA_BEM_ESTAR)
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")

    return jsonify({
        "fonte": "vazio" if df.empty else "real",
        "registros": df.to_dict(orient="records"),
    })


@app.route("/api/fadiga")
def api_fadiga():
    if not os.path.isfile(CAMINHO_FADIGA_REAL):
        return jsonify({"fonte": "vazio", "minuto_pico": None, "registros": []})

    df = pd.read_csv(CAMINHO_FADIGA_REAL)
    minuto_pico = int(df.loc[df["bocejos"].idxmax(), "minuto"]) if not df.empty else None

    return jsonify({
        "fonte": "vazio" if df.empty else "real",
        "minuto_pico": minuto_pico,
        "registros": df.to_dict(orient="records"),
    })


def excluir_registro(caminho_real, corpo):
    """Remove uma linha (por indice) do CSV real e reescreve o arquivo."""
    if not os.path.isfile(caminho_real):
        return jsonify({"erro": "ainda nao ha dados capturados pra excluir"}), 400

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


@app.route("/api/webcam/classificar", methods=["POST"])
def api_webcam_classificar():
    if not servico_humor_esta_de_pe():
        garantir_servico_humor_iniciado()
        return jsonify({"status": "carregando"})

    corpo = request.get_data()
    requisicao = urllib.request.Request(
        f"{URL_SERVICO_HUMOR}/classificar",
        data=corpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=10) as resposta:
            payload = json.loads(resposta.read())
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return jsonify({"status": "carregando"})

    payload["status"] = "ok"
    return jsonify(payload)


# Landmarker (Tasks API) usado so pra desenhar a malha facial na
# pre-visualizacao da webcam. Diferente do FER, o mediapipe roda de boa
# no mesmo Python do dashboard - nao precisa do venv 3.11.
landmarker_malha = None


def obter_landmarker_malha():
    global landmarker_malha
    if landmarker_malha is None:
        garantir_modelo()
        opcoes = vision.FaceLandmarkerOptions(
            base_options=mp_base_options.BaseOptions(model_asset_path=CAMINHO_MODELO),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
        )
        landmarker_malha = vision.FaceLandmarker.create_from_options(opcoes)
    return landmarker_malha


@app.route("/api/webcam/malha", methods=["POST"])
def api_webcam_malha():
    corpo = request.get_json(silent=True) or {}
    imagem_base64 = corpo.get("imagem", "")
    if "," in imagem_base64:
        imagem_base64 = imagem_base64.split(",", 1)[1]

    try:
        bytes_imagem = base64.b64decode(imagem_base64)
    except (ValueError, TypeError):
        return jsonify({"erro": "imagem invalida"}), 400

    array_bytes = np.frombuffer(bytes_imagem, dtype=np.uint8)
    frame = cv2.imdecode(array_bytes, cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"erro": "nao foi possivel decodificar a imagem"}), 400

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    imagem_mp = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
    resultado = obter_landmarker_malha().detect(imagem_mp)

    if not resultado.face_landmarks:
        return jsonify({"rosto_detectado": False, "imagem": None})

    # Mesmo desenho usado na janela do reuniao_fadiga.py: contorno do
    # rosto, olhos, sobrancelhas e boca.
    vision.drawing_utils.draw_landmarks(
        image=frame,
        landmark_list=resultado.face_landmarks[0],
        connections=vision.FaceLandmarksConnections.FACE_LANDMARKS_CONTOURS,
        landmark_drawing_spec=None,
        connection_drawing_spec=vision.drawing_styles.get_default_face_mesh_contours_style(),
    )

    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return jsonify({"erro": "falha ao codificar a imagem"}), 500

    imagem_anotada = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("ascii")
    return jsonify({"rosto_detectado": True, "imagem": imagem_anotada})


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
