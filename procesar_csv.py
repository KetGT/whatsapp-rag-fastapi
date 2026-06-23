import csv
import json
import re
import html  

def limpiar_html(texto):
    """Limpia las entidades HTML y etiquetas web de la descripción."""
    if not texto:
        return "Sin descripción detallada."
    
    # 1. Traduce las entidades HTML (&oacute;, &#127969;) a texto y emojis reales
    texto_decodificado = html.unescape(texto)
    
    # 2. Reemplaza los saltos de línea HTML por saltos reales
    texto_limpio = re.sub(r'<br\s*/?>|</p>', '\n', texto_decodificado)
    texto_limpio = texto_limpio.replace('<li>', '\n- ')
    
    # 3. Elimina cualquier otra etiqueta <lo_que_sea> residual
    texto_limpio = re.sub(r'<[^>]+>', '', texto_limpio)
    
    return texto_limpio.strip()

def generar_catalogo_ia():
    nombre_archivo = 'avisos.csv' 
    avisos_publicados = []

    print("Leyendo el archivo CSV y decodificando texto...")
    
    try:
        with open(nombre_archivo, mode='r', encoding='utf-8') as archivo:
            lector_csv = csv.DictReader(archivo, delimiter=';')
            
            for fila in lector_csv:
                if fila.get('Estado') == 'Publicado':
                    
                    # Usamos html.unescape también en el título por si las dudas
                    titulo_limpio = html.unescape(fila.get('Titulo', 'Sin título'))
                    
                    moneda = fila.get('Moneda', '$')
                    precio = fila.get('Precio', 'Consultar')
                    precio_final = f"{moneda} {precio}"
                    
                    caracteristicas = []
                    dormitorios = fila.get('Dormitorios', '').strip()
                    banios = fila.get('Banios', '').strip()
                    superficie = fila.get('Superficie', '').strip()
                    
                    if dormitorios: caracteristicas.append(f"{dormitorios} Dorm.")
                    if banios: caracteristicas.append(f"{banios} Baños")
                    if superficie: caracteristicas.append(f"{superficie} m²")
                    
                    descripcion_cruda = fila.get('Descripcion', '')
                    descripcion_limpia = limpiar_html(descripcion_cruda)
                    
                    avisos_publicados.append({
                        "titulo": titulo_limpio,
                        "precio": precio_final,
                        "caracteristicas": " | ".join(caracteristicas) if caracteristicas else "Detalles a consultar",
                        "link": fila.get('URL', ''),
                        "descripcion_interna": descripcion_limpia
                    })

        with open('datos_inmobiliaria.json', mode='w', encoding='utf-8') as f_json:
            json.dump(avisos_publicados, f_json, indent=2, ensure_ascii=False)
            
        print(f"¡Éxito total! Se procesaron {len(avisos_publicados)} propiedades de forma limpia.")

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {nombre_archivo}")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")

if __name__ == "__main__":
    generar_catalogo_ia()