import os
import sqlite3
import datetime
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import matplotlib.pyplot as plt
from flask import Flask, send_file, jsonify
import io

# Caminho para o arquivo de autenticação OAuth2
CLIENT_SECRET_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

# Arquivo do token
TOKEN_FILE = "token.json"

# Banco de dados SQLite
DB_FILE = "playlist_data.db"

# Configurações iniciais
PLAYLIST_ID = "PLEFWxoBc4reTSR7_7lEXQKKjDFZc6xmH8"

# Inicializar Flask
app = Flask(__name__)

# Checar se tem o arquivo client_secret
def check_secret():
    print("\nChecando Token...")
    time.sleep(2)
    if os.path.exists(TOKEN_FILE):
        print("Token encontrado")
        return True
    
    print("Token não encontrado, checando Client Secret...")
    if os.path.exists(CLIENT_SECRET_FILE):
        print("Client Secret encontrado")
        return True
    
    print("Client Secret não encontrado")
    return False

# Inicializar banco de dados
def init_db():
    print("\nInicializando banco de dados SQLite...")
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
    print("Banco de dados inicializado.")

# Salvar dados no banco
def save_data(date, video_count):
    print(f"\nSalvando dados: {date} - {video_count} vídeos...")
    time.sleep(2)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO playlist_data (date, video_count) VALUES (?, ?)", (date, video_count))
    conn.commit()
    conn.close()
    print("Dados salvos com sucesso.")

# Checar e salvar dados
def check_and_save(youtube):
    print("\nExecutando tarefa agendada para verificar e salvar dados...")
    time.sleep(2)
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM playlist_data WHERE date = ?", (today,))
    if not cursor.fetchone():  # Se não há dados hoje
        video_count = get_playlist_video_count(youtube)
        save_data(today, video_count)
        print(f"Dados salvos para {today}: {video_count} vídeos.")
    else:
        print(f"Dados para {today} já existem no banco.")
    conn.close()

# Autenticação e inicialização da API
def authenticate_youtube():
    print("\nAutenticando conta no YouTube API...")
    time.sleep(2)
    credentials = None
    if os.path.exists(TOKEN_FILE):
        print(f'Credenciais encontradas em {TOKEN_FILE}.')
        credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    else:
        print("Credenciais não encontradas. Executando fluxo de autenticação...")
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        credentials = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token_json:
            token_json.write(credentials.to_json())
        time.sleep(5)
    print("Autenticação concluída.")
    return build("youtube", "v3", credentials=credentials)

# Obter a quantidade de vídeos da playlist
def get_playlist_video_count(youtube):
    print(f"Obtendo quantidade de vídeos da playlist '{PLAYLIST_ID}'...")
    request = youtube.playlists().list(part="contentDetails", id=PLAYLIST_ID)
    response = request.execute()
    if response["items"]:
        video_count = response["items"][0]["contentDetails"]["itemCount"]
        print(f"Playlist contém {video_count} vídeos.")
        return video_count
    print("Nenhuma playlist encontrada.")
    return 0

# Rota para gerar o gráfico
@app.route("/")
def generate_graph():
    print("Gerando gráfico para exibição...")
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
        print("Gráfico gerado com sucesso.")
        return send_file(buf, mimetype="image/png")
    else:
        print("Nenhum dado disponível para gerar gráfico.")
        return jsonify({"message": "No data to display."})

def main():

    print("Iniciando aplicativo...")

    time.sleep(2)
    client_secret = check_secret()
    if not client_secret: return
    
    time.sleep(2)
    init_db()

    time.sleep(5)
    youtube = authenticate_youtube()

    time.sleep(5)
    print("\nIniciando servidor Flask em uma thread separada...")
    time.sleep(2)
    from threading import Thread
    flask_thread = Thread(target=lambda: app.run(port=5000, debug=False, use_reloader=False))
    flask_thread.start()

    time.sleep(5)
    print("\nExecutando o agendador de tarefas...")
    time.sleep(2)
    while True:
        check_and_save(youtube)
        time.sleep(3600)

if __name__ == "__main__":
    main()