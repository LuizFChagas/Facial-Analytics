"""
Modo 1 - Humor do Dia
======================
Script que roda em background durante o expediente e, a cada N minutos,
tira uma foto pela webcam, classifica a expressao facial predominante e
registra o resultado num CSV.

Como funciona a classificacao:
- A biblioteca `fer` usa o MTCNN (Multi-task Cascaded Convolutional Networks)
  para DETECTAR o rosto no frame (achar a caixa delimitadora do rosto).
- Em cima do rosto detectado, ela roda uma CNN treinada no dataset FER2013
  para CLASSIFICAR a expressao entre 7 categorias: angry, disgust, fear,
  happy, sad, surprise, neutral - cada uma com um score de confianca (0-1).
- Usamos mtcnn=True (em vez do detector Haar Cascade padrao do OpenCV)
  porque o MTCNN e mais robusto a variacoes de angulo/iluminacao, o que
  importa bastante numa webcam de notebook em ambiente domestico/escritorio.

Uso:
    python humor_do_dia.py
    python humor_do_dia.py --intervalo 10   # captura a cada 10 minutos
"""

import argparse
import csv
import os
import time
from datetime import datetime

import cv2
from fer import FER

CAMINHO_CSV = os.path.join("data", "humor_do_dia.csv")
CABECALHO_CSV = ["timestamp", "expressao", "confianca"]


def garantir_csv():
    """Cria o arquivo CSV com cabecalho caso ele ainda nao exista."""
    os.makedirs(os.path.dirname(CAMINHO_CSV), exist_ok=True)
    if not os.path.isfile(CAMINHO_CSV):
        with open(CAMINHO_CSV, mode="w", newline="", encoding="utf-8") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(CABECALHO_CSV)


def capturar_frame():
    """
    Abre a webcam, captura um unico frame e libera o dispositivo em seguida.

    Abrir e fechar a camera a cada snapshot (em vez de deixar o VideoCapture
    aberto o expediente inteiro) evita segurar o dispositivo ocupado/travado
    por horas e economiza recursos entre uma captura e outra.
    """
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Nao foi possivel acessar a webcam (indice 0).")

    # Descarta os primeiros frames: a maioria das webcams demora alguns
    # frames para ajustar exposicao/foco automaticos apos ligar.
    frame = None
    for _ in range(5):
        ok, frame = camera.read()
        if not ok:
            frame = None

    camera.release()
    return frame


def classificar_expressao(detector, frame):
    """
    Roda o detector FER sobre o frame e retorna (expressao, confianca)
    da emocao dominante encontrada no primeiro rosto detectado.

    Retorna (None, None) se nenhum rosto for encontrado no frame.
    """
    resultados = detector.detect_emotions(frame)
    if not resultados:
        return None, None

    # Pega o primeiro rosto detectado (cenario tipico: uma pessoa por vez
    # em frente ao notebook durante o expediente)
    emocoes = resultados[0]["emotions"]
    expressao_dominante = max(emocoes, key=emocoes.get)
    confianca = emocoes[expressao_dominante]
    return expressao_dominante, confianca


def registrar_leitura(expressao, confianca):
    """Acrescenta uma linha (timestamp, expressao, confianca) no CSV."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(CAMINHO_CSV, mode="a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow([timestamp, expressao, f"{confianca:.4f}"])
    print(f"[{timestamp}] expressao={expressao} confianca={confianca:.2%}")


def executar(intervalo_minutos):
    garantir_csv()

    detector = FER(mtcnn=True)

    print(f"Humor do Dia iniciado. Snapshot a cada {intervalo_minutos} min.")
    print(f"Registrando leituras em: {CAMINHO_CSV}")
    print("Pressione Ctrl+C para encerrar.\n")

    try:
        while True:
            frame = capturar_frame()
            if frame is not None:
                expressao, confianca = classificar_expressao(detector, frame)
                if expressao is not None:
                    registrar_leitura(expressao, confianca)
                else:
                    print(f"[{datetime.now().isoformat(timespec='seconds')}] "
                          "nenhum rosto detectado neste snapshot.")
            else:
                print("Falha ao capturar frame da webcam neste ciclo.")

            time.sleep(intervalo_minutos * 60)
    except KeyboardInterrupt:
        print("\nHumor do Dia encerrado pelo usuario.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor de humor via webcam (snapshots periodicos).")
    parser.add_argument(
        "--intervalo",
        type=int,
        default=15,
        help="Intervalo entre snapshots, em minutos (padrao: 15).",
    )
    args = parser.parse_args()

    executar(args.intervalo)
