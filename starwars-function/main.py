import functions_framework
import requests
from flask import jsonify

# URL base da API do Star Wars
SWAPI_BASE_URL = "https://swapi.dev/api"

def fetch_from_swapi(resource, params=None):
    """
    Função auxiliar para consultar a SWAPI.
    """
    url = f"{SWAPI_BASE_URL}/{resource}/"
    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # Levanta erro para status 4xx/5xx
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar com SWAPI: {e}")
        return None

@functions_framework.http
def starwars_handler(request):
    """
    HTTP Cloud Function.
    Args:
        request (flask.Request): O objeto de requisição.
    Returns:
        O objeto de resposta contendo os dados filtrados ou erro.
    """
    
    # CORS Headers (Boa prática para permitir acesso via browser/front-end)
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    headers = {'Access-Control-Allow-Origin': '*'}

    # 1. Captura e Validação de Parâmetros
    # O endpoint esperado será algo como: /consultar?tipo=people&nome=Luke
    args = request.args
    resource_type = args.get('tipo') # Ex: people, planets, starships, films
    search_query = args.get('termo') # Ex: Luke, Tatooine, Falcon
    
    # Validação simples (Regra de Negócio)
    valid_resources = ['people', 'planets', 'starships', 'films']
    
    if not resource_type or resource_type not in valid_resources:
        return jsonify({
            "erro": "Parâmetro 'tipo' inválido ou ausente.",
            "tipos_disponiveis": valid_resources
        }), 400, headers

    # 2. Construção da busca na SWAPI
    # A SWAPI usa o parâmetro '?search=' para filtrar
    swapi_params = {}
    if search_query:
        swapi_params['search'] = search_query

    # 3. Execução
    data = fetch_from_swapi(resource_type, swapi_params)

    if data is None:
        return jsonify({"erro": "Falha ao obter dados da fonte externa."}), 502, headers

    # 4. Refinamento da Resposta (Agregando Valor)
    # Em vez de devolver o JSON bruto, podemos simplificar para o usuário
    results = data.get('results', [])
    
    if not results:
        return jsonify({"mensagem": "Nenhum registro encontrado para os critérios."}), 404, headers

    # Retorna os dados encontrados com metadados básicos
    response_payload = {
        "categoria": resource_type,
        "total_encontrado": data.get('count'),
        "resultados": results
    }

    return jsonify(response_payload), 200, headers