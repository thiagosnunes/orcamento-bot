from flask import Flask, request
import requests
import datetime
import os
import json
from huggingface_hub import InferenceClient


user_states = {}
app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
refresh_token = os.getenv("REFRESH_TOKEN")
file_id = os.getenv("FILE_ID")
HF_TOKEN = os.getenv("IA_TOKEN")
tenant_id = os.getenv("TENANT_ID")
tenant = "common"


ia_client = InferenceClient(
    api_key=HF_TOKEN
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
            registro["Tipo"],
            registro["Nome"],
            registro["Valor"],
            registro["Pagamento"],
            registro["Categoria"]
        ]]
    }

    response = requests.post(url, headers=headers, json=data)

    return response.status_code, response.text


def interpretar_gasto(texto):

    try:

        resposta = ia_client.chat_completion(
            model="meta-llama/Meta-Llama-3-8B-Instruct",
            messages=[
                {
                    "role": "system",
                    "content": """
Você recebe frases de gastos financeiros.
Resposta sem forma de pagamento considere como PIX.
Acate apenas as mensagem que tiver no minimo o nome e valor.
Responda SOMENTE em JSON válido.

Formato:

{
 "nome": "...",
 "valor": numero,
 "pagamento": "...",
 "categoria": "..."
}

Pagamentos possíveis:
Dinheiro
PIX
Credito
Debito

Categorias possíveis:
Moradia
Doação
Alimentação
C. Pessoais
Transporte
Educação
Compras
Taxas
Dívida
Lazer
Saúde
Outros
Empreendimento
"""
                },
                {
                    "role": "user",
                    "content": texto
                }
            ],
            max_tokens=200
        )

        resposta_texto = resposta.choices[0].message.content

        dados = json.loads(resposta_texto)

        data_hoje = datetime.datetime.now().strftime("%Y-%m-%d")

        return {
            "Data": data_hoje,
            "Tipo": "Saída",
            "Nome": dados["nome"],
            "Valor": float(dados["valor"]),
            "Pagamento": dados["pagamento"],
            "Categoria": dados["categoria"]
        }

    except Exception as e:
        print("Erro IA:", e)
        return None

@app.route("/", methods=["GET"])
def home():
    return "online"

@app.route("/", methods=["POST"])
def receber_mensagem():

    dados = request.json

    if "message" not in dados:
        return "ok"

    chat_id = dados["message"]["chat"]["id"]
    texto = dados["message"]["text"]

    registro = interpretar_gasto(texto)

    print(registro)

    if registro:

        status, resposta_excel = adicionar_no_excel(registro)

        if status == 201:

            resposta = (
                f"✅ Gasto registrado\n\n"
                f"Nome: {registro['Nome']}\n"
                f"Valor: {registro['Valor']}\n"
                f"Pagamento: {registro['Pagamento']}\n"
                f"Categoria: {registro['Categoria']}"
            )

        else:
            resposta = "Erro ao gravar no Excel."

    else:

        resposta = (
            "❌ Não consegui entender.\n\n"
            "Exemplos:\n"
            "uber 35 credito\n"
            "mercado 120 pix\n"
            "farmacia 40 debito"
        )

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
