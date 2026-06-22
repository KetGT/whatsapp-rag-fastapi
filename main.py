import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
import uvicorn
import requests

# Cargar las variables de entorno del archivo .env
load_dotenv()

app = FastAPI()

# Ahora las traemos de forma segura usando os.getenv
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

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
        
        # Verificamos si es un mensaje de WhatsApp entrante
        if "object" in body and body["object"] == "whatsapp_business_account":
            entry = body["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            
            # Si hay mensajes nuevos
            if "messages" in value:
                mensaje_info = value["messages"][0]
                numero_remitente = mensaje_info["from"]
                texto_recibido = mensaje_info["text"]["body"]
                
                print(f"Mensaje recibido de {numero_remitente}: {texto_recibido}")
                
                # --- SOLUCIÓN PARA EL FORMATO DE ARGENTINA ---
                # Si empieza con 549 (Argentina móvil), le removemos el 9 para que coincida con la lista de Meta
                if numero_remitente.startswith("549"):
                    numero_remitente = "54" + numero_remitente[3:]
                # ---------------------------------------------
                
                # Le respondemos al usuario
                enviar_mensaje(numero_remitente, "¡Hola! Gracias por comunicarte con la inmobiliaria. Soy un bot en desarrollo.")
                
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
    print(f"Estado del envío: {response.status_code}")
    print(response.text)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)