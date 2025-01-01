import os
import sqlite3
import datetime
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import matplotlib.pyplot as plt
from flask import Flask, send_file, jsonify, redirect, url_for
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

# Inicializar Flask
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
    time.sleep(2)
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
    time.sleep(2)
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
    time.sleep(2)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO playlist_data (date, video_count) VALUES (?, ?)", (date, video_count))
    conn.commit()
    conn.close()
    logger.info("Dados salvos com sucesso.")

# Checar e salvar dados
def check_and_save(youtube):
    logger.info("Executando tarefa agendada para verificar e salvar dados...")
    time.sleep(2)
    today = datetime.date.today().isoformat()
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
    time.sleep(2)
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
        time.sleep(5)
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

# Rota para gerar o gráfico
@app.route("/")
def generate_graph():
    logger.info("Gerando gráfico para exibição...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT date, video_count FROM playlist_data ORDER BY date")
    data = cursor.fetchall()
    conn.close()
    
    if data:
        dates, counts = zip(*data)
        plt.figure(figsize=(10, 6))
        plt.plot(dates, counts, marker='o')
        plt.title("YouTube Playlist Video Count Over Time")
        plt.xlabel("Date")
        plt.ylabel("Video Count")
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Salvar gráfico em um buffer e enviar como resposta
        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        plt.close()
        logger.info("Gráfico gerado com sucesso.")
        return send_file(buf, mimetype="image/png")
    else:
        logger.info("Nenhum dado disponível para gerar gráfico.")
        return jsonify({"message": "No data to display."})

@app.route("/log")
def show_logs():
    logger.info("Exibindo logs...")
    data_buffer.seek(0)
    logs = data_buffer.read()
    return f"<pre>{logs}</pre>"

@app.route("/no_file_found")
def no_file_found():
    return "<h1>Arquivo de autenticação não encontrado</h1>"
    
def main():

    logger.info("Iniciando aplicativo...")

    time.sleep(2)
    client_secret = check_secret()
    if client_secret == "token_file_host_found":
        TOKEN_FILE = TOKEN_FILE_HOST
    elif client_secret == "token_file_local_found":
        TOKEN_FILE = TOKEN_FILE_LOCAL
    elif client_secret == "no_file_found":
        return redirect(url_for("no_file_found"))
    
    time.sleep(2)
    init_db()

    time.sleep(5)
    youtube = authenticate_youtube(TOKEN_FILE)

    time.sleep(5)
    logger.info("Iniciando servidor Flask em uma thread separada...")
    time.sleep(2)
    from threading import Thread
    flask_thread = Thread(target=lambda: app.run(port=5000, debug=False, use_reloader=False))
    flask_thread.start()

    time.sleep(5)
    logger.info("Executando o agendador de tarefas...")
    time.sleep(2)
    while True:
        check_and_save(youtube)
        time.sleep(3600)

if __name__ == "__main__":
    app.run()