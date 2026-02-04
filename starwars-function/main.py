import functions_framework
import requests
from flask import jsonify
import time
import re

# URL base da API do Star Wars
SWAPI_BASE_URL = "https://swapi.dev/api"

# Configurações de retry
MAX_RETRIES = 3
RETRY_DELAY = 1  # segundos
RETRY_BACKOFF = 2  # multiplicador exponencial

def fetch_from_swapi(resource, params=None):
    """
    Função auxiliar para consultar a SWAPI com retry automático.
    
    Args:
        resource: Tipo de recurso (people, planets, starships, films)
        params: Parâmetros de busca opcionais
    
    Returns:
        dict: Dados JSON da resposta ou None em caso de falha
    """
    url = f"{SWAPI_BASE_URL}/{resource}/"
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()  # Levanta erro para status 4xx/5xx
            return response.json()
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                print(f"Timeout na tentativa {attempt + 1}/{MAX_RETRIES}. Aguardando {wait_time}s antes de tentar novamente...")
                time.sleep(wait_time)
            else:
                print(f"Erro: Timeout após {MAX_RETRIES} tentativas")
                return None
        except requests.exceptions.ConnectionError:
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                print(f"Erro de conexão na tentativa {attempt + 1}/{MAX_RETRIES}. Aguardando {wait_time}s antes de tentar novamente...")
                time.sleep(wait_time)
            else:
                print(f"Erro: Falha de conexão após {MAX_RETRIES} tentativas")
                return None
        except requests.exceptions.HTTPError as e:
            # Erros 4xx não devem ser retentados (erro do cliente)
            if 400 <= e.response.status_code < 500:
                print(f"Erro HTTP do cliente: {e.response.status_code}")
                return None
            # Erros 5xx podem ser retentados
            elif attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                print(f"Erro HTTP do servidor ({e.response.status_code}) na tentativa {attempt + 1}/{MAX_RETRIES}. Aguardando {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Erro: Falha HTTP após {MAX_RETRIES} tentativas")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Erro ao conectar com SWAPI: {e}")
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                time.sleep(wait_time)
            else:
                return None
    
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
    # O endpoint esperado será algo como: /explorar?tipo=people&termo=Luke
    args = request.args
    resource_type = args.get('tipo')  # Ex: people, planets, starships, films
    search_query = args.get('termo')  # Ex: Luke, Tatooine, Falcon
    
    # Validação do parâmetro 'tipo'
    valid_resources = ['people', 'planets', 'starships', 'films']
    
    # Validar se o tipo foi fornecido
    if not resource_type:
        return jsonify({
            "erro": "Parâmetro 'tipo' é obrigatório.",
            "tipos_disponiveis": valid_resources
        }), 400, headers
    
    # Validar se o tipo é uma string
    if not isinstance(resource_type, str):
        return jsonify({
            "erro": "Parâmetro 'tipo' deve ser uma string.",
            "tipos_disponiveis": valid_resources
        }), 400, headers
    
    # Validar se o tipo está na lista de recursos válidos
    resource_type = resource_type.strip().lower()
    if resource_type not in valid_resources:
        return jsonify({
            "erro": f"Parâmetro 'tipo' inválido: '{resource_type}'.",
            "tipos_disponiveis": valid_resources
        }), 400, headers
    
    # Validação do parâmetro 'termo' (opcional)
    if search_query is not None:
        # Validar se o termo é uma string
        if not isinstance(search_query, str):
            return jsonify({
                "erro": "Parâmetro 'termo' deve ser uma string."
            }), 400, headers
        
        # Remover espaços em branco no início e fim
        search_query = search_query.strip()
        
        # Validar se o termo não está vazio após remover espaços
        if not search_query:
            return jsonify({
                "erro": "Parâmetro 'termo' não pode estar vazio ou conter apenas espaços."
            }), 400, headers
        
        # Validar comprimento máximo do termo (limite de 100 caracteres)
        MAX_SEARCH_LENGTH = 100
        if len(search_query) > MAX_SEARCH_LENGTH:
            return jsonify({
                "erro": f"Parâmetro 'termo' excede o limite de {MAX_SEARCH_LENGTH} caracteres.",
                "tamanho_atual": len(search_query)
            }), 400, headers
        
        # Validar caracteres especiais perigosos (proteção básica contra injection)
        # Permitir apenas letras, números, espaços e alguns caracteres especiais comuns
        if not re.match(r'^[a-zA-Z0-9\s\-_\.]+$', search_query):
            return jsonify({
                "erro": "Parâmetro 'termo' contém caracteres inválidos. Use apenas letras, números, espaços e os caracteres: - _ ."
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