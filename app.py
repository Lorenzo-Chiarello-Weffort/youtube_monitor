import plotly.graph_objects as go
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.cloud import firestore
from flask import Flask, redirect, url_for
import os
import time
import io
import logging
from threading import Thread
import isodate
import pytz

# Configurações
CLIENT_SECRET_FILE_LOCAL = "client_secret.json"

TOKEN_FILE = "/etc/secrets/token.json"
TOKEN_FILE_LOCAL = "token.json"

FIREBASE_CREDENTIALS_PATH = "/etc/secrets/firebase.json"
FIREBASE_CREDENTIALS_PATH_LOCAL = "firebase.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

PLAYLIST_ID = "PLEFWxoBc4reTSR7_7lEXQKKjDFZc6xmH8"

TIMEZONE = pytz.timezone("America/Sao_Paulo")

scheduler = False

wait_time = 0

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
    if os.path.exists(FIREBASE_CREDENTIALS_PATH):
        logger.info(f'Credenciais encontradas em {FIREBASE_CREDENTIALS_PATH}.')
        load_db = firestore.Client.from_service_account_json(FIREBASE_CREDENTIALS_PATH)
    elif os.path.exists(FIREBASE_CREDENTIALS_PATH_LOCAL):
        logger.info(f'Credenciais encontradas em {FIREBASE_CREDENTIALS_PATH_LOCAL}.')
        load_db = firestore.Client.from_service_account_json(FIREBASE_CREDENTIALS_PATH_LOCAL)
    else:
        logger.info("Não foi possível obter credenciais de autenticação do firebase")
        return
    
    logger.info("Conexão ao Firestore estabelecida.")
    time.sleep(wait_time)
    return load_db

db = init_firestore()

def save_data(date, video_count, total_minutes):
    logger.info(f"Salvando dados: {date} - {video_count} vídeos - {total_minutes} minutos...")
    doc_ref = db.collection("playlist_data").document(date)
    doc_ref.set({
        "video_count": video_count,
        "total_minutes": total_minutes
    }, merge=True)
    logger.info("Dados salvos com sucesso.")
    time.sleep(wait_time)

def check_and_save(youtube):
    logger.info("Verificando dados...")
    today = datetime.now(TIMEZONE).date().isoformat()
    doc_ref = db.collection("playlist_data").document(today)
    doc = doc_ref.get()
    if not doc.exists:  # Não há dados hoje
        logger.info("Salvando dados...")
        video_count, total_minutes = get_playlist_video_count_and_duration(youtube)
        save_data(today, video_count, total_minutes)
        logger.info(f"Dados salvos para {today}: {video_count} vídeos, {total_minutes} minutos.")
    else:
        logger.info(f"Dados para {today} já existem no Firestore.")
    time.sleep(wait_time)

def authenticate_youtube():
    logger.info("Autenticando conta no YouTube API...")
    credentials = None
    if os.path.exists(TOKEN_FILE):
        logger.info(f'Credenciais encontradas em {TOKEN_FILE}.')
        credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    elif os.path.exists(TOKEN_FILE_LOCAL):
        logger.info(f'Credenciais encontradas em {TOKEN_FILE_LOCAL}.')
        credentials = Credentials.from_authorized_user_file(TOKEN_FILE_LOCAL, SCOPES)
    elif os.path.exists(CLIENT_SECRET_FILE_LOCAL):
        logger.info("Credenciais não encontradas. Executando fluxo de autenticação...")
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE_LOCAL, SCOPES)
        credentials = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token_json:
            token_json.write(credentials.to_json())
        time.sleep(wait_time)
    else:
        logger.info("Não foi possível obter credenciais de autenticação do Youtube API")
        return

    logger.info("Autenticação concluída.")
    time.sleep(wait_time)
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
    time.sleep(wait_time)
    return video_count, total_minutes

def parse_duration_to_minutes(duration):
    parsed_duration = isodate.parse_duration(duration)
    return int(parsed_duration.total_seconds() // 60)

def fetch_data():
    logger.info("Buscando dados...")
    time.sleep(wait_time)

    youtube = authenticate_youtube()
    time.sleep(wait_time)

    check_and_save(youtube)
    time.sleep(wait_time)

    logger.info("Dados carregados")

    if scheduler == True:
        time.sleep(wait_time)
        logger.info("Executando o agendador de tarefas em uma thread separada...")
        scheduler_thread = Thread(target=lambda: run_scheduler(youtube))
        scheduler_thread.start()

def run_scheduler(youtube):
    last_run_date = None

    while True:
        current_date = datetime.now(TIMEZONE).date()

        if last_run_date != current_date:
            check_and_save(youtube)
            last_run_date = current_date

        # Calcula o tempo até a meia-noite do próximo dia
        now = datetime.now(TIMEZONE)
        next_day = datetime.combine(current_date + timedelta(days=1), datetime.min.time(), tzinfo=TIMEZONE)
        seconds_until_next_day = (next_day - now).total_seconds()

        logger.info(f'Segundos para salvar novamente: {seconds_until_next_day}')
        time.sleep(seconds_until_next_day)

@app.route("/")
def init():
    fetch_data()
    return redirect(url_for('show_graph'))

@app.route("/graph")
def show_graph():
    try:
        logger.info("Buscando dados no Firestore...")
        # Acessa a coleção
        collection_ref = db.collection("playlist_data")
        docs = collection_ref.stream()

        # Processa os documentos
        dates = []
        video_counts = []
        total_minutes = []

        for doc in docs:
            doc_data = doc.to_dict()
            dates.append(doc.id)  # ID do documento como data
            video_counts.append(doc_data.get("video_count", 0))
            total_minutes.append(doc_data.get("total_minutes", 0))

        if not dates:
            return "Nenhum dado encontrado na coleção 'playlist_data'."

        # Criação do gráfico interativo
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=video_counts, mode="lines+markers", name="Video Count"))
        fig.add_trace(go.Scatter(x=dates, y=total_minutes, mode="lines+markers", name="Total Minutes"))

        # Configuração do layout
        fig.update_layout(
            title="Playlist Data - Video Count vs Total Minutes",
            xaxis_title="Date",
            yaxis_title="Values",
            legend_title="Metrics",
            template="plotly_white"
        )

        # Renderiza o gráfico interativo como HTML
        graph_html = fig.to_html(full_html=False)

        return f"""
        <html>
            <head><title>Youtube Playlist Monitor</title></head>
            <body>
                {graph_html}
            </body>
        </html>
        """
    except Exception as e:
        logger.error(f"Erro ao acessar dados do Firestore: {e}")
        return "Erro ao acessar dados do Firestore.", 500

@app.route("/logs")
def logs():
    data_buffer.seek(0)
    logs = data_buffer.read()
    return f"<pre>{logs}</pre>"

if __name__ == "__main__":
    app.run(debug=False)