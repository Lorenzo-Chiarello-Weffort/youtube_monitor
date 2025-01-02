import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
import os
import time
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from flask import Flask, send_file
import io
import logging
from threading import Thread
import isodate
import pytz
from google.cloud import firestore

# Configurações iniciais
CLIENT_SECRET_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

TOKEN_FILE = "/etc/secrets/token.json"

PLAYLIST_ID = "PLEFWxoBc4reTSR7_7lEXQKKjDFZc6xmH8"

TIMEZONE = pytz.timezone("America/Sao_Paulo")

CREDENTIALS_PATH = "/etc/secrets/firebase.json"

wait_time = 3

app = Flask(__name__)

data_buffer = io.StringIO()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', handlers=[
    logging.StreamHandler(data_buffer),
    logging.StreamHandler()
])
logger = logging.getLogger()

# Inicialização do Firestore
def init_firestore():
    logger.info("Conectando ao Firestore...")
    db = firestore.Client.from_service_account_json(CREDENTIALS_PATH)
    logger.info("Conexão ao Firestore estabelecida.")
    return db

def save_data(db, date, video_count, total_minutes):
    logger.info(f"Salvando dados: {date} - {video_count} vídeos - {total_minutes} minutos...")
    doc_ref = db.collection("playlist_data").document(date)
    doc_ref.set({
        "video_count": video_count,
        "total_minutes": total_minutes
    }, merge=True)
    logger.info("Dados salvos com sucesso.")

def check_and_save(db, youtube):
    logger.info("Executando tarefa agendada para verificar e salvar dados...")
    today = datetime.now(TIMEZONE).date().isoformat()
    doc_ref = db.collection("playlist_data").document(today)
    doc = doc_ref.get()
    if not doc.exists:  # Se não há dados hoje
        video_count, total_minutes = get_playlist_video_count_and_duration(youtube)
        save_data(db, today, video_count, total_minutes)
        logger.info(f"Dados salvos para {today}: {video_count} vídeos, {total_minutes} minutos.")
    else:
        logger.info(f"Dados para {today} já existem no Firestore.")

def authenticate_youtube(TOKEN_FILE):
    logger.info("Autenticando conta no YouTube API...")
    credentials = None
    if os.path.exists(TOKEN_FILE):
        logger.info(f'Credenciais encontradas em {TOKEN_FILE}.')
        credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    else:
        logger.info("Credenciais não encontradas. Executando fluxo de autenticação...")
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        credentials = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token_json:
            token_json.write(credentials.to_json())
        time.sleep(wait_time)

    logger.info("Autenticação concluída.")
    return build("youtube", "v3", credentials=credentials)

def get_playlist_video_count_and_duration(youtube):
    logger.info(f"Obtendo dados da playlist '{PLAYLIST_ID}'...")
    request = youtube.playlistItems().list(
        part="contentDetails", playlistId=PLAYLIST_ID, maxResults=50
    )
    video_ids = []
    while request:
        response = request.execute()
        video_ids.extend(item["contentDetails"]["videoId"] for item in response["items"])
        request = youtube.playlistItems().list_next(request, response)

    video_count = len(video_ids)
    total_minutes = 0

    if video_ids:
        for i in range(0, len(video_ids), 50):
            video_request = youtube.videos().list(
                part="contentDetails", id=','.join(video_ids[i:i + 50])
            )
            video_response = video_request.execute()
            for video in video_response["items"]:
                duration = video["contentDetails"]["duration"]
                total_minutes += parse_duration_to_minutes(duration)

    logger.info(f"Playlist contém {video_count} vídeos e {total_minutes} minutos no total.")
    return video_count, total_minutes

def parse_duration_to_minutes(duration):
    parsed_duration = isodate.parse_duration(duration)
    return int(parsed_duration.total_seconds() // 60)

def configure():
    logger.info("Iniciando configuração do aplicativo...")

    time.sleep(wait_time)
    youtube = authenticate_youtube(TOKEN_FILE)

    time.sleep(wait_time)
    db = init_firestore()

    time.sleep(wait_time)
    check_and_save(db, youtube)

    return db

    # time.sleep(time_high)
    # logger.info("Executando o agendador de tarefas em uma thread separada...")
    # scheduler_thread = Thread(target=lambda: run_scheduler(db, youtube))
    # scheduler_thread.start()

def run_scheduler(db, youtube):
    last_run_date = None

    while True:
        current_date = datetime.now(TIMEZONE).date()

        if last_run_date != current_date:
            check_and_save(db, youtube)
            last_run_date = current_date

        # Calcula o tempo até a meia-noite do próximo dia
        now = datetime.now(TIMEZONE)
        next_day = datetime.combine(current_date + timedelta(days=1), datetime.min.time(), tzinfo=TIMEZONE)
        seconds_until_next_day = (next_day - now).total_seconds()

        logger.info(f'Segundos para salvar novamente: {seconds_until_next_day}')
        time.sleep(seconds_until_next_day)

@app.route("/")
def graph():
    db = configure()
    logger.info("Gerando gráfico para exibição...")

    docs = db.collection("playlist_data").order_by("date").stream()
    data = [(doc.id, doc.to_dict()["video_count"], doc.to_dict()["total_minutes"]) for doc in docs]

    if data:
        dates, counts, durations = zip(*data)

        fig = Figure(figsize=(15, 9))
        ax = fig.add_subplot(1, 1, 1)
        ax.plot(dates, counts, marker='o', label='Video Count')
        ax.plot(dates, durations, marker='o', label='Total Minutes')
        ax.set_title("YouTube Playlist Data Over Time")
        ax.set_xlabel("Date")
        ax.set_ylabel("Count / Minutes")
        ax.tick_params(axis='x', rotation=45)
        ax.legend()

        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)

        logger.info("Gráfico gerado com sucesso.")
        return send_file(buf, mimetype="image/png")
    else:
        logger.info("Nenhum dado disponível para gerar gráfico.")
        return "<h1>Nenhum dado para mostrar</h1>"

@app.route("/logs")
def logs():
    data_buffer.seek(0)
    logs = data_buffer.read()
    return f"<pre>{logs}</pre>"

if __name__ == "__main__":
    app.run()