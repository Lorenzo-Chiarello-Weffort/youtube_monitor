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
import json

# Caminho para o arquivo de autenticação OAuth2
CLIENT_SECRET_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

app = Flask(__name__)

def check_secret():
    print("Checando Client Secret")
    if os.path.exists(CLIENT_SECRET_FILE):
        print("Client Secret encontrado")
        print(CLIENT_SECRET_FILE)
        return True
    
    print("Client Secret não encontrado")
    return False

def check_secret_stored():
    file_path = '/etc/secrets/token.json'
    if os.path.exists(file_path):
        print(f'Arquivo em {file_path} encontrado')
        with open(file_path, 'r') as file:
            data = json.load(file)
        print(data)
    else:
        print(f'Arquivo em {file_path} não encontrado')

@app.route('/')
def main_page():
    client_secret = check_secret()
    if client_secret:
        return f'Client file: {CLIENT_SECRET_FILE}'
    return 'Sem Client Secret'

if __name__ == '__main__':
    app.run()
