from flask import Flask, request
import requests
import datetime
import os

app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
refresh_token = os.getenv("REFRESH_TOKEN")
file_id = os.getenv("FILE_ID")
tenant = "common"


def adicionar_no_excel(registro):

    # 1. Gerar novo access_token
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "offline_access Files.ReadWrite User.Read"
    }

    token_response = requests.post(token_url, data=token_data)
    access_token = token_response.json()["access_token"]

    # 2. Escrever no Excel
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/tables/TabelaCustos/rows/add"

    data = {
        "values": [[
            registro["Data"],
            registro["Nome"],
            registro["Valor"],
            registro["Pagamento"],
            registro["Categoria"]
        ]]
    }

    response = requests.post(url, headers=headers, json=data)

    return response.status_code, response.text


def processar_mensagem(texto):
    partes = [p.strip() for p in texto.split(",")]

    if len(partes) != 4:
        return None, f'Formato inválido "{texto}". Use: Nome, Valor, Pagamento, Categoria'

    nome = partes[0]

    try:
        valor = float(partes[1].replace(",", "."))
    except:
        return None, f'Valor inválido "{partes[1]}".'

    pagamento = partes[2]
    categoria = partes[3]

    data_hoje = datetime.datetime.now().strftime("%Y-%m-%d")

    return {
        "Data": data_hoje,
        "Nome": nome,
        "Valor": valor,
        "Pagamento": pagamento,
        "Categoria": categoria
    }, None

@app.route("/", methods=["GET"])
def home():
    return "online"

@app.route("/", methods=["POST"])
def receber_mensagem():
    dados = request.json

    if "message" in dados:

        texto = dados["message"]["text"]

        registro, erro = processar_mensagem(texto)

        if erro:
            resposta = erro
        else:
            resposta = f"Registrado: {registro}"
            a, b = adicionar_no_excel(registro)

        print(resposta)

        chat_id = dados["message"]["chat"]["id"]

        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": f"Recebi: {resposta}"
            }
        )

    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
