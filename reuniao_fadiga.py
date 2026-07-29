"""
Modo 2 - Reuniao (deteccao de fadiga em tempo real)
=====================================================
Roda continuamente durante uma call, usando o MediaPipe Face Landmarker
(Tasks API) para extrair 478 pontos (landmarks) do rosto a cada frame. A
partir desses pontos calculamos duas metricas classicas de visao
computacional:

- EAR (Eye Aspect Ratio): mede o quanto o olho esta aberto. Cai bruscamente
  durante uma piscada. Contando quedas rapidas do EAR, contamos piscadas.
- MAR (Mouth Aspect Ratio): mede o quanto a boca esta aberta. Usada aqui
  pra detectar bocejos: MAR alto sustentado por varios frames seguidos
  (diferente de uma piscada, um bocejo demora - por isso exigimos uma
  quantidade minima de frames consecutivos antes de contar).

A cada minuto fechado (contado a partir do inicio da execucao, nao do
relogio), a contagem de piscadas e bocejos daquele minuto e salva no CSV.

Nota tecnica: usamos a Tasks API (mp.tasks.vision.FaceLandmarker) em vez
da API classica "mp.solutions.face_mesh" porque essa ultima ainda nao tem
build do MediaPipe pra versoes recentes do Python (ex: 3.14) - o Google
descontinuou os builds pre-compilados de "solutions" nesses casos, so a
Tasks API (mais nova) esta disponivel. A logica de EAR/MAR e identica; so
a forma de obter os landmarks do frame muda.

Controles:
    q - encerra a captura (salva o minuto parcial em andamento antes de sair)

Uso:
    python reuniao_fadiga.py
"""

import csv
import os
import time
import urllib.request
from datetime import datetime

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options as mp_base_options

CAMINHO_CSV = os.path.join("data", "reuniao_fadiga.csv")
CABECALHO_CSV = ["minuto", "timestamp", "piscadas", "bocejos"]

CAMINHO_MODELO = os.path.join("modelos", "face_landmarker.task")
URL_MODELO = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"

# --- Indices dos landmarks do MediaPipe Face Mesh usados no calculo ---
# Cada olho e descrito por 6 pontos (p1..p6), na mesma convencao classica
# de Soukupova & Cech (2016): p1/p4 = cantos (horizontal), p2/p6 e p3/p5 =
# pares verticais (superior/inferior).
OLHO_DIREITO = [33, 160, 158, 133, 153, 144]
OLHO_ESQUERDO = [362, 385, 387, 263, 373, 380]

# A boca usa a mesma logica de razao vertical/horizontal do EAR, so que
# aplicada aos landmarks dos labios (por isso o nome "MAR" e a formula
# ficam simetricos ao EAR).
BOCA = [61, 39, 269, 291, 405, 181]

# --- Limiares empiricos (ajustaveis conforme webcam/iluminacao) ---
LIMIAR_EAR = 0.21          # abaixo disso, consideramos o olho "fechado"
FRAMES_MIN_PISCADA = 2      # frames minimos fechado para validar como piscada
LIMIAR_MAR = 0.60           # acima disso, consideramos a boca "aberta"
FRAMES_MIN_BOCEJO = 15      # frames minimos aberto seguidos para validar como bocejo


def calcular_distancia(ponto_a, ponto_b):
    return float(np.linalg.norm(np.array(ponto_a) - np.array(ponto_b)))


def pontos_em_pixels(landmarks, indices, largura, altura):
    """Converte landmarks normalizados (0-1) do MediaPipe em coordenadas de pixel."""
    return [
        (landmarks[i].x * largura, landmarks[i].y * altura)
        for i in indices
    ]


def calcular_razao_abertura(pontos):
    """
    Formula generica de razao vertical/horizontal usada tanto para EAR
    quanto para MAR:

        razao = (dist(p2,p6) + dist(p3,p5)) / (2 * dist(p1,p4))

    p1/p4 = extremidades horizontais; p2/p6 e p3/p5 = pares verticais.
    """
    p1, p2, p3, p4, p5, p6 = pontos
    vertical_1 = calcular_distancia(p2, p6)
    vertical_2 = calcular_distancia(p3, p5)
    horizontal = calcular_distancia(p1, p4)
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def garantir_csv():
    os.makedirs(os.path.dirname(CAMINHO_CSV), exist_ok=True)
    if not os.path.isfile(CAMINHO_CSV):
        with open(CAMINHO_CSV, mode="w", newline="", encoding="utf-8") as arquivo:
            csv.writer(arquivo).writerow(CABECALHO_CSV)


def garantir_modelo():
    """Baixa o modelo do Face Landmarker (uma vez) se ele ainda nao existir localmente."""
    if os.path.isfile(CAMINHO_MODELO):
        return
    os.makedirs(os.path.dirname(CAMINHO_MODELO), exist_ok=True)
    print(f"Baixando modelo do Face Landmarker em {CAMINHO_MODELO}...")
    urllib.request.urlretrieve(URL_MODELO, CAMINHO_MODELO)
    print("Modelo baixado.")


def salvar_minuto(minuto, piscadas_no_minuto, bocejos_no_minuto):
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(CAMINHO_CSV, mode="a", newline="", encoding="utf-8") as arquivo:
        csv.writer(arquivo).writerow([minuto, timestamp, piscadas_no_minuto, bocejos_no_minuto])
    print(f"[minuto {minuto}] piscadas={piscadas_no_minuto} bocejos={bocejos_no_minuto} -> salvo em {CAMINHO_CSV}")


def criar_landmarker():
    """Monta o FaceLandmarker (Tasks API) em modo VIDEO, pra rodar frame a frame."""
    opcoes = vision.FaceLandmarkerOptions(
        base_options=mp_base_options.BaseOptions(model_asset_path=CAMINHO_MODELO),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return vision.FaceLandmarker.create_from_options(opcoes)


def executar():
    garantir_csv()
    garantir_modelo()

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Nao foi possivel acessar a webcam (indice 0).")

    landmarker = criar_landmarker()

    # Estado dos contadores "por evento" (piscada/bocejo)
    frames_olho_fechado = 0
    frames_boca_aberta = 0
    bocejo_ja_contado_neste_ciclo = False

    # Contadores do minuto corrente e acumulados da sessao
    piscadas_no_minuto = 0
    bocejos_no_minuto = 0
    piscadas_totais = 0
    bocejos_totais = 0

    tempo_inicio = time.time()
    minuto_atual = 1

    print("Reuniao (deteccao de fadiga) iniciada. Pressione 'q' para encerrar.\n")

    try:
        while camera.isOpened():
            ok, frame = camera.read()
            if not ok:
                break

            altura, largura = frame.shape[:2]
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            imagem_mp = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            timestamp_ms = int((time.time() - tempo_inicio) * 1000)
            resultado = landmarker.detect_for_video(imagem_mp, timestamp_ms)

            ear_medio, mar = None, None

            if resultado.face_landmarks:
                landmarks = resultado.face_landmarks[0]

                # EAR de cada olho, calculado separadamente e depois combinado.
                # Usar a media dos dois olhos deixa a deteccao mais estavel do
                # que olhar so pra um lado (compensa leve assimetria facial e
                # ruido de deteccao de um dos lados).
                ear_direito = calcular_razao_abertura(pontos_em_pixels(landmarks, OLHO_DIREITO, largura, altura))
                ear_esquerdo = calcular_razao_abertura(pontos_em_pixels(landmarks, OLHO_ESQUERDO, largura, altura))
                ear_medio = (ear_direito + ear_esquerdo) / 2.0

                mar = calcular_razao_abertura(pontos_em_pixels(landmarks, BOCA, largura, altura))

                # --- Deteccao de piscada: conta na transicao "fechado -> aberto" ---
                if ear_medio < LIMIAR_EAR:
                    frames_olho_fechado += 1
                else:
                    if frames_olho_fechado >= FRAMES_MIN_PISCADA:
                        piscadas_no_minuto += 1
                        piscadas_totais += 1
                    frames_olho_fechado = 0

                # --- Deteccao de bocejo: exige abertura sustentada por varios frames ---
                if mar > LIMIAR_MAR:
                    frames_boca_aberta += 1
                    if frames_boca_aberta >= FRAMES_MIN_BOCEJO and not bocejo_ja_contado_neste_ciclo:
                        bocejos_no_minuto += 1
                        bocejos_totais += 1
                        bocejo_ja_contado_neste_ciclo = True
                else:
                    frames_boca_aberta = 0
                    bocejo_ja_contado_neste_ciclo = False

                # Desenha a malha facial (referencia visual) e destaca os
                # pontos usados no calculo de EAR/MAR
                vision.drawing_utils.draw_landmarks(
                    image=frame,
                    landmark_list=landmarks,
                    connections=vision.FaceLandmarksConnections.FACE_LANDMARKS_CONTOURS,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=vision.drawing_styles.get_default_face_mesh_contours_style(),
                )
                for x, y in pontos_em_pixels(landmarks, OLHO_DIREITO + OLHO_ESQUERDO, largura, altura):
                    cv2.circle(frame, (int(x), int(y)), 2, (214, 120, 42), -1)  # azul (BGR) - olhos
                for x, y in pontos_em_pixels(landmarks, BOCA, largura, altura):
                    cv2.circle(frame, (int(x), int(y)), 2, (52, 104, 235), -1)  # laranja (BGR) - boca

            # --- Fecha o minuto corrente quando o tempo decorrido virar a pagina ---
            minuto_decorrido = int((time.time() - tempo_inicio) // 60) + 1
            if minuto_decorrido != minuto_atual:
                salvar_minuto(minuto_atual, piscadas_no_minuto, bocejos_no_minuto)
                piscadas_no_minuto = 0
                bocejos_no_minuto = 0
                minuto_atual = minuto_decorrido

            # --- Overlay com os contadores em tempo real ---
            linhas_overlay = [
                f"EAR: {ear_medio:.2f}" if ear_medio is not None else "EAR: --",
                f"MAR: {mar:.2f}" if mar is not None else "MAR: --",
                f"Piscadas (min {minuto_atual}): {piscadas_no_minuto}",
                f"Bocejos (min {minuto_atual}): {bocejos_no_minuto}",
                f"Total: {piscadas_totais} piscadas / {bocejos_totais} bocejos",
            ]
            for indice, texto in enumerate(linhas_overlay):
                cv2.putText(
                    frame, texto, (10, 25 + indice * 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA,
                )

            cv2.imshow("Reuniao - Deteccao de Fadiga (q para sair)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        landmarker.close()
        camera.release()
        cv2.destroyAllWindows()

    # Salva o minuto parcial em andamento ao encerrar, pra nao perder dados
    # de uma reuniao que nao termina exatamente num minuto fechado.
    if piscadas_no_minuto or bocejos_no_minuto:
        salvar_minuto(minuto_atual, piscadas_no_minuto, bocejos_no_minuto)

    print(f"\nSessao encerrada. Total: {piscadas_totais} piscadas, {bocejos_totais} bocejos.")


if __name__ == "__main__":
    executar()
