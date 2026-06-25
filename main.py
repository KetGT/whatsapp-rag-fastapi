import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from flask import json
import uvicorn
import requests
from openai import OpenAI

load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

#OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

BUSINESS_NAME = os.getenv("BUSINESS_NAME")

# Inicializamos el cliente de OpenAI
#client = OpenAI(api_key=OPENAI_API_KEY)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

def cargar_catalogo():
    """Lee el catálogo limpio que generamos con el CSV"""
    try:
        with open("datos_inmobiliaria.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error al leer el catálogo JSON: {e}")
        return []
    
    
def consultar_chatgpt(mensaje_cliente):
    """Cruza la consulta del cliente con nuestro JSON usando GPT-4o-mini"""
    catalogo = cargar_catalogo()
    catalogo_str = json.dumps(catalogo, ensure_ascii=False, indent=2)

    prompt_sistema = f"""Sos el asistente de {BUSINESS_NAME}. Tu tono es profesional pero muy cálido, sumamente amable y muy claro. 
    Tu único trabajo es ofrecer propiedades basándote ESTRICTAMENTE en este catálogo JSON:

    {catalogo_str}

    REGLAS DE ORO:
    1. Si el cliente pregunta por algo que coincide con el catálogo, respondé con entusiasmo dándole: Título, Precio, Características principales y OBLIGATORIAMENTE el link adjunto para que vea las fotos.
    2. Si el cliente busca algo que NO está en el catálogo (ej: "Busco un galpón de 500m2"), decile cordialmente que por el momento no contamos con esa disponibilidad. NO inventes propiedades.
    3. Si el cliente quiere hablar con un humano, pagar un alquiler, o hacer un reclamo administrativo, pedile amablemente su Nombre y Apellido y decile que un asesor se comunicará a la brevedad.
    4. Sé conciso. No escribas testamentos gigantescos.
    5. Actúa como Humano (No digas que eres una inteligencia artificial, ni que estás limitado a un catálogo. No digas que no podés hacer algo. No digas que no podés responder. No digas que no podés ayudar. No digas que no podés dar información. No digas que no podés ofrecer propiedades. No digas que no podés dar detalles de propiedades. No digas que no podés dar precios de propiedades. No digas que no podés dar links de propiedades. No digas que no podés dar fotos de propiedades. No digas que no podés dar características de propiedades. No digas que no podés dar información de contacto de propiedades. No digas que no podés dar información de contacto de la inmobiliaria. No digas que no podés dar información de contacto del asesor humano. No digas que no podés dar información de contacto del propietario. No digas que no podés dar información de contacto del inquilino. No digas que no podés dar información de contacto del arrendador. No digas que no podés dar información de contacto del arrendatario. No digas que no podés dar información de contacto del administrador. No digas que no podés dar información de contacto del encargado. No digas que no podés dar información de contacto del representante legal. No digas que no podés dar información de contacto del abogado. No digas que no podés dar información de contacto del contador. No digas que no podés dar información de contacto del asesor financiero. No digas que no podés dar información de contacto del asesor inmobiliario.)
    6. Si el cliente te pide que le muestres fotos, respondé con el link de la propiedad y decile que allí podrá ver todas las fotos disponibles. No inventes links ni URLs.
    7. Si el cliente te pide que le muestres un mapa, respondé con el link de la propiedad y decile que allí podrá ver la ubicación exacta en el mapa. No inventes links ni URLs.
    8. Si el cliente te pide que le muestres un video, respondé con el link de la propiedad y decile que allí podrá ver el video disponible. No inventes links ni URLs.
    9. Empieza cada mensaje primero saludando al cliente por su nombre si lo tenés y diciendole que cualquier consulta te avise. Luego, respondé a su consulta de manera clara y concisa, siguiendo las reglas anteriores. No olvides incluir el link de la propiedad si corresponde.

        """
    
    try:
        response = client.chat.completions.create(
            # --- MODELO GRATUITO DE OPENROUTER ---
            model="meta-llama/llama-3-8b-instruct", 
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": mensaje_cliente}
            ],
            temperature=0.2 # Bajito para que sea preciso y no alucine
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error de OpenAI: {e}")
        return "Disculpá, en este momento estoy experimentando una demora técnica. ¿Podrías dejarme tu consulta y un asesor humano te responderá en breve?"


def enviar_whatsapp(telefono_destino, texto_respuesta):
    """Dispara el mensaje de vuelta al WhatsApp del cliente vía Meta"""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": telefono_destino,
        "type": "text",
        "text": {"body": texto_respuesta}
    }
    try:
        respuesta = requests.post(url, headers=headers, json=data)
        if respuesta.status_code != 200:
            print(f"Error enviando WhatsApp: {respuesta.text}")
    except Exception as e:
        print(f"Error de conexión con Meta: {e}")


# Webhook para que Meta verifique nuestro servidor
@app.get("/webhook")
async def verificar_meta(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return int(challenge)
    return "Verificación fallida", 403

# Webhook principal que escucha los mensajes entrantes
@app.post("/webhook")
async def recibir_whatsapp(request: Request):
    body = await request.json()
    
    try:
        # Buceamos en el JSON de Meta para capturar el mensaje de texto
        entrada = body["entry"][0]["changes"][0]["value"]
        if "messages" in entrada:
            mensaje = entrada["messages"][0]
            telefono_cliente = mensaje["from"]
            texto_recibido = mensaje["text"]["body"]

            # --- ARREGLO PARA NÚMEROS ARGENTINOS ---
            if telefono_cliente.startswith("549"):
                telefono_cliente = "54" + telefono_cliente[3:]
            # ---------------------------------------
            
            print(f"\n💬 Mensaje de {telefono_cliente}: {texto_recibido}")

            # 1. Pensamos la respuesta con IA
            respuesta_ia = consultar_chatgpt(texto_recibido)
            print(f"🤖 Respondiendo: {respuesta_ia}")

            # 2. Se la enviamos al cliente
            enviar_whatsapp(telefono_cliente, respuesta_ia)

    except KeyError:
        # Ignoramos los avisos de "mensaje entregado" o "leído" que manda Meta
        pass

    return {"status": "ok"}



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)