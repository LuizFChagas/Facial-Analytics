"""
Servico auxiliar de classificacao de expressao (roda no Python 3.11).

O dashboard (Flask) roda no mesmo Python usado pelo resto do projeto, que
nao tem TensorFlow disponivel (veja a nota em requirements.txt). Pra
classificar frames em tempo real na pre-visualizacao da webcam, o
dashboard sobe este servico como um processo separado, no venv Python
3.11 que ja tem o "fer" instalado - e fala com ele por HTTP local.

Nao acessa a webcam diretamente: recebe um frame (JPEG em base64) que o
navegador capturou da pre-visualizacao, roda a mesma logica de
classificar_expressao() do humor_do_dia.py, e devolve o resultado.

Uso (chamado automaticamente pelo dashboard_app.py, mas pode rodar solto):
    python humor_servico.py
"""

import base64

import cv2
import numpy as np
from fer import FER
from flask import Flask, jsonify, request

from humor_do_dia import classificar_expressao

app = Flask(__name__)
detector = None  # carregado sob demanda, no primeiro request (ver abaixo)


def obter_detector():
    global detector
    if detector is None:
        print("Carregando o modelo do FER (MTCNN + CNN do FER2013)... isso demora alguns segundos.")
        detector = FER(mtcnn=True)
        print("Modelo pronto.")
    return detector


@app.route("/saude")
def saude():
    """Usado pelo dashboard pra saber se o servico ja subiu."""
    return jsonify({"status": "ok", "modelo_carregado": detector is not None})


@app.route("/classificar", methods=["POST"])
def classificar():
    corpo = request.get_json(silent=True) or {}
    imagem_base64 = corpo.get("imagem", "")

    # O navegador manda "data:image/jpeg;base64,....." - descarta o prefixo
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

    expressao, confianca = classificar_expressao(obter_detector(), frame)
    return jsonify({"expressao": expressao, "confianca": confianca})


if __name__ == "__main__":
    # Carrega o modelo logo de cara quando rodado standalone, pra ja
    # avisar no terminal se algo der errado no import/pesos.
    obter_detector()
    app.run(host="127.0.0.1", port=5051, debug=False)
