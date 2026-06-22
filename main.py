import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
import uvicorn
import requests
from openai import OpenAI

load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BUSINESS_NAME = os.getenv("BUSINESS_NAME")
# Inicializamos el cliente de OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# --- NUEVA FUNCIÓN: EL CEREBRO DEL BOT ---
def generar_respuesta_ia(texto_usuario):
    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o-mini", # Usamos el modelo más rápido y económico
            messages=[
                # El "System Prompt": Acá le damos la personalidad y las reglas
                {"role": "system", "content": f"Sos el asistente virtual de {BUSINESS_NAME}. Tu tono es profesional, amable y conciso. Tu objetivo es responder consultas sobre alquileres. Si te preguntan algo fuera del rubro o no sabés la respuesta, pedí cordialmente que dejen su nombre y domicilio para que un humano los contacte."},
                # El mensaje real del cliente
                {"role": "user", "content": texto_usuario}
            ],
            max_tokens=150,
            temperature=0.5 # Qué tan creativo queremos que sea (0 es robótico, 1 es muy creativo)
        )
        return respuesta.choices[0].message.content
    except Exception as e:
        print(f"Error con OpenAI: {e}")
        return "Disculpá, en este momento estoy teniendo un problema técnico. ¿Podrías dejarme tu nombre y un humano te contactará a la brevedad?"
# -----------------------------------------

@app.get("/webhook")
async def verificar_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, status_code=200)
    return Response(status_code=403)

@app.post("/webhook")
async def recibir_mensajes(request: Request):
    try:
        body = await request.json()
        
        if "object" in body and body["object"] == "whatsapp_business_account":
            entry = body["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            
            if "messages" in value:
                mensaje_info = value["messages"][0]
                numero_remitente = mensaje_info["from"]
                texto_recibido = mensaje_info["text"]["body"]
                
                print(f"Mensaje recibido de {numero_remitente}: {texto_recibido}")
                
                if numero_remitente.startswith("549"):
                    numero_remitente = "54" + numero_remitente[3:]
                
                # --- ACÁ CONECTAMOS LA IA ---
                # 1. Le mandamos el texto del cliente a OpenAI
                respuesta_inteligente = generar_respuesta_ia(texto_recibido)
                
                # 2. Le mandamos la respuesta generada por OpenAI a WhatsApp
                enviar_mensaje(numero_remitente, respuesta_inteligente)
                
        return Response(content="EVENT_RECEIVED", status_code=200)
    except Exception as e:
        print(f"Error: {e}")
        return Response(status_code=500)

def enviar_mensaje(numero_destino, texto):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "to": numero_destino,
        "type": "text",
        "text": {"body": texto}
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Error de Meta: {response.text}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)