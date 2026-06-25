import os
import json # <-- Cambiado a json estándar de Python
import asyncio # <-- NUEVO: Para manejar pausas
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
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BUSINESS_NAME = os.getenv("BUSINESS_NAME")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# --- MEMORIA DEL BOT ---
# Acá guardamos la conversación de cada número. 
# Formato: {"549351XXXXXX": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
historiales = {}
# -----------------------

def cargar_catalogo():
    try:
        with open("datos_inmobiliaria.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error al leer el catálogo JSON: {e}")
        return []
    
    
def consultar_chatgpt(telefono_cliente, mensaje_cliente):
    """Cruza la consulta considerando el historial completo de ese número"""
    catalogo = cargar_catalogo()
    catalogo_str = json.dumps(catalogo, ensure_ascii=False, indent=2)

    prompt_sistema = f"""Sos el asistente de {BUSINESS_NAME}. Tu tono es profesional pero muy cálido, sumamente amable pero divertido y muy claro. 
    Tu único trabajo es ofrecer propiedades basándote ESTRICTAMENTE en este catálogo JSON:

    {catalogo_str}

    REGLAS DE ORO:
    1. Si el cliente pregunta por algo que coincide con el catálogo, respondé con entusiasmo dándole: Título, Precio, Características principales y OBLIGATORIAMENTE el link adjunto para que vea las fotos.
    2. Si el cliente busca algo que NO está en el catálogo (ej: "Busco un galpón de 500m2"), decile cordialmente que por el momento no contamos con esa disponibilidad. NO inventes propiedades.
    3. Si el cliente quiere hablar con un humano, pagar un alquiler, o hacer un reclamo administrativo, pedile amablemente su Nombre y Apellido y decile que un asesor se comunicará a la brevedad.
    4. Sé conciso. No escribas testamentos gigantescos.
    5. Actúa como Humano (No digas que eres una inteligencia artificial, ni que estás limitado a un catálogo...)
    6. Si el cliente te pide que le muestres fotos, respondé con el link de la propiedad y decile que allí podrá ver todas las fotos disponibles. No inventes links ni URLs.
    7. Si el cliente te pide que le muestres un mapa, respondé con el link de la propiedad y decile que allí podrá ver la ubicación exacta en el mapa. No inventes links ni URLs.
    8. Si el cliente te pide que le muestres un video, respondé con el link de la propiedad y decile que allí podrá ver el video disponible. No inventes links ni URLs.
    10. Siempre que ofrezcas una propiedad, envía su link correspondiente para que el cliente pueda ver fotos, ubicación y detalles. No inventes links ni URLs.
    """
    
    # 1. Si no existe el historial para este número, lo creamos vacío
    if telefono_cliente not in historiales:
        historiales[telefono_cliente] = []

    # 2. Agregamos el mensaje nuevo del usuario
    historiales[telefono_cliente].append({"role": "user", "content": mensaje_cliente})

    # 3. Mantenemos el límite de memoria (últimos 10 mensajes) para no exceder la cuota
    if len(historiales[telefono_cliente]) > 10:
        historiales[telefono_cliente] = historiales[telefono_cliente][-10:]

    # 4. Juntamos el system prompt con todo el historial de mensajes
    mensajes_completos = [{"role": "system", "content": prompt_sistema}] + historiales[telefono_cliente]

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3-8b-instruct", 
            messages=mensajes_completos,
            temperature=0.2 
        )
        respuesta_texto = response.choices[0].message.content
        
        # 5. Guardamos lo que respondió la IA en el historial para que lo recuerde después
        historiales[telefono_cliente].append({"role": "assistant", "content": respuesta_texto})
        
        return respuesta_texto
    except Exception as e:
        print(f"Error de OpenRouter/OpenAI: {e}")
        return "Disculpá, en este momento estoy experimentando una demora técnica. ¿Podrías dejarme tu consulta y un asesor humano te responderá en breve?"


def enviar_whatsapp(telefono_destino, texto_respuesta):
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


@app.get("/webhook")
async def verificar_meta(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return int(challenge)
    return "Verificación fallida", 403


@app.post("/webhook")
async def recibir_whatsapp(request: Request):
    body = await request.json()
    
    try:
        entrada = body["entry"][0]["changes"][0]["value"]
        if "messages" in entrada:
            mensaje = entrada["messages"][0]
            telefono_cliente = mensaje["from"]
            texto_recibido = mensaje["text"]["body"]

            if telefono_cliente.startswith("549"):
                telefono_cliente = "54" + telefono_cliente[3:]
            
            print(f"\n💬 Mensaje de {telefono_cliente}: {texto_recibido}")

            # --- LÓGICA DEL SALUDO INICIAL ---
            # Si el número no está en historiales, significa que es una conversación nueva
            es_nuevo = telefono_cliente not in historiales
            
            if es_nuevo:
                print("🚀 Nueva conversación: Enviando saludo inicial...")
                enviar_whatsapp(telefono_cliente, "¡Hola! ¿Cómo estás? Dame un segundito que ya te atiendo...")
                # Pausa para dar tiempo a la IA a procesar y que los mensajes lleguen en orden
                await asyncio.sleep(2)
            # ---------------------------------

            # 1. Pensamos la respuesta con IA (pasándole el teléfono para la memoria)
            respuesta_ia = consultar_chatgpt(telefono_cliente, texto_recibido)
            print(f"🤖 Respondiendo: {respuesta_ia}")

            # 2. Se la enviamos al cliente
            enviar_whatsapp(telefono_cliente, respuesta_ia)

    except KeyError:
        pass

    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)