from flask import Flask, request
import requests
import datetime
import os

user_states = {}
app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
refresh_token = os.getenv("REFRESH_TOKEN")
file_id = os.getenv("FILE_ID")
tenant = "common"


def enviar_botoes_categoria(chat_id):

    botoes = {
        "inline_keyboard": [
            [
                {"text": "🏠 Moradia", "callback_data": "Moradia"},
                {"text": "❤️ Doação", "callback_data": "Doacao"}
            ],
            [
                {"text": "🍔 Alimentação", "callback_data": "Alimentacao"},
                {"text": "🧴 C. Pessoais", "callback_data": "C. Pessoais"}
            ],
            [
                {"text": "🚌 Transporte", "callback_data": "Transporte"},
                {"text": "🎓 Educação", "callback_data": "Educacao"}
            ],
            [
                {"text": "🛍 Compras", "callback_data": "Compras"},
                {"text": "📄 Taxas", "callback_data": "Taxas"}
            ],
            [
                {"text": "💳 Dívida", "callback_data": "Divida"},
                {"text": "🎮 Lazer", "callback_data": "Lazer"}
            ],
            [
                {"text": "🏥 Saúde", "callback_data": "Saude"},
                {"text": "📦 Outros", "callback_data": "Outros"}
            ],
            [
                {"text": "🚀 Empreendimento", "callback_data": "Empreendimento"}
            ]
        ]
    }

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "Escolha a categoria:",
            "reply_markup": botoes
        }
    )

def enviar_botoes_pagamento(chat_id):

    botoes = {
        "inline_keyboard": [
            [
                {"text": "💵 Dinheiro", "callback_data": "Dinheiro"},
                {"text": "⚡ PIX", "callback_data": "PIX"}
            ],
            [
                {"text": "💳 Crédito", "callback_data": "Credito"},
                {"text": "🏦 Débito", "callback_data": "Debito"}
            ]
        ]
    }

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "Escolha a forma de pagamento:",
            "reply_markup": botoes
        }
    )


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
    return 200

@app.route("/", methods=["POST"])
def receber_mensagem():
    dados = request.json

    if "callback_query" in dados:

        callback = dados["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        escolha = callback["data"]

        if chat_id in user_states:
            estado = user_states[chat_id]

            if estado["step"] == "pagamento":
                estado["Pagamento"] = escolha
                estado["step"] = "categoria"
                enviar_botoes_categoria(chat_id)

            elif estado["step"] == "categoria":

                estado["Categoria"] = escolha
                estado["Data"] = datetime.datetime.now().strftime("%Y-%m-%d")

                adicionar_no_excel(estado)

                requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": "✅ Gasto registrado com sucesso!\nDigite /add para registrar novo gasto."
                    }
                )

                del user_states[chat_id]

        # necessário para remover o loading do botão
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback["id"]}
        )

        return "ok"

    if "message" not in dados:
        return "ok"

    chat_id = dados["message"]["chat"]["id"]
    texto = dados["message"]["text"].strip()

    # Inicia fluxo assistente
    if texto == "/add":
        user_states[chat_id] = {"step": "nome"}
        resposta = "Qual foi a compra?"

    # Se usuário já está em fluxo
    elif chat_id in user_states:

        estado = user_states[chat_id]

        if estado["step"] == "nome":
            estado["Nome"] = texto
            estado["step"] = "valor"
            resposta = "Qual o valor?"

        elif estado["step"] == "valor":
            try:
                estado["Valor"] = float(texto.replace(",", "."))
                estado["step"] = "pagamento"
                enviar_botoes_pagamento(chat_id)
                return "ok"
            except:
                resposta = "Valor inválido. Digite apenas número."

    else:
        resposta = "Digite /add para registrar um gasto."

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": resposta
        }
    )

    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
