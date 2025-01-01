import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
import os
import sqlite3
import time
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from flask import Flask, send_file, redirect, url_for
import io
import logging

# Caminho para o arquivo de autenticação OAuth2
CLIENT_SECRET_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

# Arquivo do token
TOKEN_FILE_HOST = "/etc/secrets/token.json"
TOKEN_FILE_LOCAL = "token.json"

# Banco de dados SQLite
DB_FILE = "playlist_data.db"

# Configurações iniciais
PLAYLIST_ID = "PLEFWxoBc4reTSR7_7lEXQKKjDFZc6xmH8"

# Tempo de espera
time_low = 0
time_high = 3

# Inicializar Flask
INITIALIZED = False
app = Flask(__name__)

# Configurar o logger
data_buffer = io.StringIO()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', handlers=[
    logging.StreamHandler(data_buffer),
    logging.StreamHandler()
])
logger = logging.getLogger()

# Checar se tem o arquivo client_secret
def check_secret():
    logger.info("Checando Token...")
    time.sleep(time_low)
    if os.path.exists(TOKEN_FILE_HOST):
        logger.info("Token encontrado")
        return "token_file_host_found"
    
    logger.info("Checando Token localmente...")
    if os.path.exists(TOKEN_FILE_LOCAL):
        logger.info("Token local encontrado")
        return "token_file_local_found"
    
    logger.info("Token não encontrado, checando Client Secret...")
    if os.path.exists(CLIENT_SECRET_FILE):
        logger.info("Client Secret encontrado")
        return "client_file_found"
    
    logger.info("Client Secret não encontrado")
    return "no_file_found"

# Inicializar banco de dados
def init_db():
    logger.info("Inicializando banco de dados SQLite...")
    time.sleep(time_low)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlist_data (
            date TEXT PRIMARY KEY,
            video_count INTEGER
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Banco de dados inicializado.")

# Salvar dados no banco
def save_data(date, video_count):
    logger.info(f"Salvando dados: {date} - {video_count} vídeos...")
    time.sleep(time_low)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO playlist_data (date, video_count) VALUES (?, ?)", (date, video_count))
    conn.commit()
    conn.close()
    logger.info("Dados salvos com sucesso.")

# Checar e salvar dados
def check_and_save(youtube):
    logger.info("Executando tarefa agendada para verificar e salvar dados...")
    time.sleep(time_low)
    today = datetime.now().date().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM playlist_data WHERE date = ?", (today,))
    if not cursor.fetchone():  # Se não há dados hoje
        video_count = get_playlist_video_count(youtube)
        save_data(today, video_count)
        logger.info(f"Dados salvos para {today}: {video_count} vídeos.")
    else:
        logger.info(f"Dados para {today} já existem no banco.")
    conn.close()

# Autenticação e inicialização da API
def authenticate_youtube(TOKEN_FILE):
    logger.info("Autenticando conta no YouTube API...")
    time.sleep(time_low)
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
        time.sleep(time_high)
    logger.info("Autenticação concluída.")
    return build("youtube", "v3", credentials=credentials)

# Obter a quantidade de vídeos da playlist
def get_playlist_video_count(youtube):
    logger.info(f"Obtendo quantidade de vídeos da playlist '{PLAYLIST_ID}'...")
    request = youtube.playlists().list(part="contentDetails", id=PLAYLIST_ID)
    response = request.execute()
    if response["items"]:
        video_count = response["items"][0]["contentDetails"]["itemCount"]
        logger.info(f"Playlist contém {video_count} vídeos.")
        return video_count
    logger.info("Nenhuma playlist encontrada.")
    return 0

def main():
    logger.info("Iniciando aplicativo...")

    global INITIALIZED
    INITIALIZED = True

    time.sleep(time_low)
    client_secret = check_secret()
    if client_secret == "token_file_host_found":
        TOKEN_FILE = TOKEN_FILE_HOST
    elif client_secret == "token_file_local_found":
        TOKEN_FILE = TOKEN_FILE_LOCAL
    elif client_secret == "no_file_found":
        return redirect(url_for("no_file_found"))
    
    time.sleep(time_low)
    init_db()

    time.sleep(time_high)
    youtube = authenticate_youtube(TOKEN_FILE)

    time.sleep(time_high)
    logger.info("Executando o agendador de tarefas em uma thread separada...")
    time.sleep(time_low)
    from threading import Thread
    scheduler_thread = Thread(target=lambda: run_scheduler(youtube))
    scheduler_thread.start()

def run_scheduler(youtube):
    last_run_date = None

    while True:
        current_date = datetime.now().date()

        if last_run_date != current_date:
            check_and_save(youtube)
            last_run_date = current_date

        # Calcula o tempo até a meia-noite do próximo dia
        now = datetime.now()
        next_day = datetime.combine(current_date + timedelta(days=1), datetime.min.time())
        seconds_until_next_day = (next_day - now).total_seconds()

        logger.warning("Segundos para executar novamente:")
        logger.warning(seconds_until_next_day)
        time.sleep(seconds_until_next_day)

# Rotas
@app.route("/")
def initialize():
    global INITIALIZED
    if not INITIALIZED:
        main()
    return redirect(url_for("graph"))

@app.route("/graph")
def graph():
    logger.info("Gerando gráfico para exibição...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT date, video_count FROM playlist_data ORDER BY date")
    data = cursor.fetchall()
    conn.close()
    
    if data:
        dates, counts = zip(*data)

        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(1, 1, 1)
        ax.plot(dates, counts, marker='o')
        ax.set_title("YouTube Playlist Video Count Over Time")
        ax.set_xlabel("Date")
        ax.set_ylabel("Video Count")
        ax.tick_params(axis='x', rotation=45)
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

@app.route("/no_file_found")
def no_file_found():
    return "<h1>Arquivo de autenticação não encontrado</h1>"
    
if __name__ == "__main__":
    app.run()