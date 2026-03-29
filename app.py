from flask import Flask, request
import requests
import datetime
import os
import json
from huggingface_hub import InferenceClient
import re


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
    token=HF_TOKEN
)


def mensagem_valida(texto):
    texto = texto.lower()

    # precisa ter número
    tem_numero = bool(re.search(r"\d", texto))

    # precisa ter pelo menos uma palavra com letra
    tem_texto = bool(re.search(r"[a-zA-Z]", texto))

    # return tem_numero and tem_texto
    return True

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
Você é um assistente que extrai informações financeiras de mensagens.

Regras obrigatórias:
- Extraia os campos: Nome, Valor, Pagamento, Categoria
- A mensagem só é válida se tiver Nome e Valor
- Se não tiver Nome ou Valor → retorne: {"erro": "dados_insuficientes"}

- Se não informar pagamento → use "PIX"
- Valores devem ser números (ex: 35.90)
- Não invente valores

Categorias possíveis:
Moradia, Doacao, Alimentacao, C. Pessoais, Transporte, Educacao, Compras, Taxas, Divida, Lazer, Saude, Outros, Empreendimento

- Escolha a categoria mais apropriada
- Se não souber → use "Outros"

Responda SOMENTE em JSON válido, sem texto extra.

Formato de saída:
{
  "Nome": "...",
  "Valor": 0.0,
  "Pagamento": "...",
  "Categoria": "..."
}
"""
            },
            {
                "role": "user",
                "content": texto
            }
        ],
        temperature=0.2,
        max_tokens=200
    )

        return resposta.choices[0].message.content



    except Exception as e:
        print("Erro IA:", e)
        return None

def interpretar_gasto2(texto):

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
    print(texto)

    if not mensagem_valida(texto):
        resposta = "Envie algo como: nome + valor (ex: 'uber 35')"

    else:
        resposta_texto = interpretar_gasto(texto)
        print(resposta_texto)

        if resposta_texto:

            if "erro" in resposta_texto:
                resposta = "Não entendi. Envie pelo menos nome e valor."

            else:

                dados = json.loads(resposta_texto)

                data_hoje = datetime.datetime.now().strftime("%Y-%m-%d")

                print(dados)

                registro = {
                    "Data": data_hoje,
                    "Tipo": "Saída",
                    "Nome": dados["Nome"],
                    "Valor": float(dados["Valor"]),
                    "Pagamento": dados["Pagamento"],
                    "Categoria": dados["Categoria"]
                }

                status, resposta_excel = adicionar_no_excel(registro)

                if status == 201:

                    resposta = (
                        f"✅ Dados registrados\n\n"
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
