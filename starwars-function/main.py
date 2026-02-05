import functions_framework
import requests
from flask import jsonify, Request
import time
import re
import logging
from typing import Optional, Dict, Any, Tuple

# Configuração do logger estruturado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# URL base da API do Star Wars
SWAPI_BASE_URL = "https://swapi.dev/api"

# Configurações de retry
MAX_RETRIES = 3
RETRY_DELAY = 1  # segundos
RETRY_BACKOFF = 2  # multiplicador exponencial

def fetch_from_swapi(resource: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
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
            logger.info(f"Consultando SWAPI: {resource} (tentativa {attempt + 1}/{MAX_RETRIES})")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()  # Levanta erro para status 4xx/5xx
            logger.info(f"Sucesso ao consultar SWAPI: {resource}")
            return response.json()
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                logger.warning(
                    f"Timeout na tentativa {attempt + 1}/{MAX_RETRIES} para {resource}. "
                    f"Aguardando {wait_time}s antes de tentar novamente."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Timeout após {MAX_RETRIES} tentativas para {resource}")
                return None
        except requests.exceptions.ConnectionError:
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                logger.warning(
                    f"Erro de conexão na tentativa {attempt + 1}/{MAX_RETRIES} para {resource}. "
                    f"Aguardando {wait_time}s antes de tentar novamente."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Falha de conexão após {MAX_RETRIES} tentativas para {resource}")
                return None
        except requests.exceptions.HTTPError as e:
            # Erros 4xx não devem ser retentados (erro do cliente)
            if 400 <= e.response.status_code < 500:
                logger.error(f"Erro HTTP do cliente ({e.response.status_code}) para {resource}: {e}")
                return None
            # Erros 5xx podem ser retentados
            elif attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                logger.warning(
                    f"Erro HTTP do servidor ({e.response.status_code}) na tentativa {attempt + 1}/{MAX_RETRIES} "
                    f"para {resource}. Aguardando {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Falha HTTP após {MAX_RETRIES} tentativas para {resource}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao conectar com SWAPI para {resource}: {e}")
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                time.sleep(wait_time)
            else:
                return None
    
    return None


def fetch_swapi_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Consulta a SWAPI por URL completa (usado para seguir paginação 'next').
    Usa a mesma política de retry que fetch_from_swapi.
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if 400 <= e.response.status_code < 500:
                logger.error(f"Erro HTTP do cliente ao buscar {url}: {e}")
                return None
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (RETRY_BACKOFF ** attempt))
            else:
                logger.error(f"Erro ao buscar URL SWAPI {url}: {e}")
                return None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.RequestException) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (RETRY_BACKOFF ** attempt))
            else:
                logger.error(f"Erro ao buscar URL SWAPI {url}: {e}")
                return None
    return None


def fetch_all_pages_swapi(resource: str, params: Optional[Dict[str, str]] = None) -> Optional[Tuple[list, int]]:
    """
    Busca todos os resultados do recurso na SWAPI, percorrendo todas as páginas.
    A SWAPI retorna no máximo 10 itens por página e um campo 'next' com a URL da próxima página.

    Returns:
        Tupla (lista_completa_de_resultados, total_count) ou None em caso de falha.
    """
    data = fetch_from_swapi(resource, params)
    if data is None:
        return None

    all_results = list(data.get('results', []))
    total_count = data.get('count', len(all_results))
    next_url = data.get('next')

    while next_url:
        data = fetch_swapi_url(next_url)
        if data is None:
            logger.warning("Falha ao obter próxima página da SWAPI; retornando resultados obtidos até aqui.")
            break
        page_results = data.get('results', [])
        all_results.extend(page_results)
        next_url = data.get('next')

    logger.info(f"SWAPI: total de {len(all_results)} resultado(s) para {resource} (count={total_count})")
    return (all_results, total_count)


def sort_results(results: list, sort_by: str, sort_order: str, resource_type: str) -> list:
    """
    Ordena os resultados baseado no campo especificado.
    
    Args:
        results: Lista de resultados para ordenar
        sort_by: Campo para ordenação (nome, altura, etc.)
        sort_order: Ordem de classificação ('asc' ou 'desc')
        resource_type: Tipo de recurso para determinar campos válidos
    
    Returns:
        Lista ordenada de resultados
    """
    # Mapeamento de campos válidos por tipo de recurso
    valid_sort_fields = {
        'people': ['name', 'height', 'mass', 'birth_year'],
        'planets': ['name', 'diameter', 'population', 'rotation_period', 'orbital_period'],
        'starships': ['name', 'length', 'crew', 'passengers', 'cargo_capacity', 'cost_in_credits'],
        'films': ['title', 'episode_id', 'release_date']
    }
    
    # Normalizar campo de ordenação
    sort_by = sort_by.strip().lower()
    sort_order = sort_order.strip().lower()
    
    # Validar campo de ordenação
    if resource_type not in valid_sort_fields:
        logger.warning(f"Tipo de recurso inválido para ordenação: {resource_type}")
        return results
    
    if sort_by not in valid_sort_fields[resource_type]:
        logger.warning(f"Campo de ordenação inválido '{sort_by}' para {resource_type}")
        return results
    
    if sort_order not in ['asc', 'desc']:
        logger.warning(f"Ordem de classificação inválida: {sort_order}. Usando 'asc'")
        sort_order = 'asc'
    
    # Função auxiliar para converter valores para comparação.
    # Retorna sempre (tipo, valor): (0, num) ou (1, str), para evitar TypeError ao comparar int/float com str.
    def get_sort_key(item: dict, field: str) -> Tuple[int, Any]:
        value = item.get(field, '')
        if value is None or value == 'unknown' or value == 'n/a' or value == '':
            sentinel = float('inf') if sort_order == 'asc' else float('-inf')
            return (0, sentinel)
        try:
            cleaned = str(value).replace(',', '').replace('km', '').strip()
            if not cleaned:
                sentinel = float('inf') if sort_order == 'asc' else float('-inf')
                return (0, sentinel)
            if '.' in cleaned:
                return (0, float(cleaned))
            return (0, int(cleaned))
        except (ValueError, AttributeError, TypeError):
            return (1, str(value).lower())
    
    # Ordenar resultados
    try:
        sorted_results = sorted(
            results,
            key=lambda x: get_sort_key(x, sort_by),
            reverse=(sort_order == 'desc')
        )
        logger.info(f"Resultados ordenados por '{sort_by}' em ordem '{sort_order}'")
        return sorted_results
    except Exception as e:
        logger.error(f"Erro ao ordenar resultados: {e}")
        return results

def apply_pagination(results: list, page: str, limit: str) -> Tuple[int, int, list]:
    """
    Aplica paginação aos resultados.
    
    Args:
        results: Lista completa de resultados
        page: Número da página (string)
        limit: Limite de itens por página (string)
    
    Returns:
        Tupla contendo (número_da_página, limite, resultados_paginados)
    """
    try:
        page_num = max(1, int(page))
        limit_num = max(1, min(100, int(limit)))  # Limite máximo de 100 itens
    except (ValueError, TypeError):
        logger.warning(f"Valores de paginação inválidos: pagina={page}, limite={limit}. Usando valores padrão.")
        page_num = 1
        limit_num = 10
    
    # Calcular índices
    start_index = (page_num - 1) * limit_num
    end_index = start_index + limit_num
    
    # Aplicar paginação
    paginated_results = results[start_index:end_index]
    
    logger.info(f"Paginação aplicada: página {page_num}, limite {limit_num}, {len(paginated_results)} resultados")
    return page_num, limit_num, paginated_results

@functions_framework.http
def starwars_handler(request: Request) -> Tuple[Any, int, Dict[str, str]]:
    """
    HTTP Cloud Function - Handler principal que roteia para diferentes endpoints.
    Args:
        request: O objeto de requisição Flask.
    Returns:
        Tupla contendo (resposta, código_status, headers).
    """
    
    # CORS Headers (Boa prática para permitir acesso via browser/front-end)
    if request.method == 'OPTIONS':
        logger.info("Requisição OPTIONS (CORS preflight)")
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    headers = {'Access-Control-Allow-Origin': '*'}
    path = request.path
    
    logger.info(f"Requisição recebida: {request.method} {path}")
    
    # Roteamento baseado no path
    if path == '/personagens-filme' or path.endswith('/personagens-filme'):
        return personagens_filme_handler(request)
    elif path == '/naves-personagem' or path.endswith('/naves-personagem'):
        return naves_personagem_handler(request)
    elif path == '/planetas-filme' or path.endswith('/planetas-filme'):
        return planetas_filme_handler(request)
    elif path == '/explorar' or path.endswith('/explorar') or path == '/' or not path or path == '':
        # Endpoint principal de exploração
        return explorar_handler(request)
    else:
        return jsonify({
            "erro": f"Endpoint não encontrado: {path}",
            "endpoints_disponiveis": ["/explorar", "/personagens-filme", "/naves-personagem", "/planetas-filme"]
        }), 404, headers

def explorar_handler(request: Request) -> Tuple[Any, int, Dict[str, str]]:
    """
    Handler para o endpoint principal /explorar
    """
    headers = {'Access-Control-Allow-Origin': '*'}

    # 1. Captura e Validação de Parâmetros
    # O endpoint esperado será algo como: /explorar?tipo=people&termo=Luke&ordenar_por=nome&ordem=asc&pagina=1&limite=10
    args = request.args
    resource_type = args.get('tipo')  # Ex: people, planets, starships, films
    search_query = args.get('termo')  # Ex: Luke, Tatooine, Falcon
    sort_by = args.get('ordenar_por')  # Campo para ordenação
    sort_order = args.get('ordem', 'asc')  # asc ou desc
    page = args.get('pagina', '1')  # Número da página
    limit = args.get('limite', '10')  # Itens por página
    
    # Validação do parâmetro 'tipo'
    valid_resources = ['people', 'planets', 'starships', 'films']
    
    # Validar se o tipo foi fornecido
    if not resource_type:
        logger.warning("Requisição sem parâmetro 'tipo'")
        return jsonify({
            "erro": "Parâmetro 'tipo' é obrigatório.",
            "tipos_disponiveis": valid_resources
        }), 400, headers
    
    # Validar se o tipo é uma string
    if not isinstance(resource_type, str):
        logger.warning(f"Parâmetro 'tipo' não é string: {type(resource_type)}")
        return jsonify({
            "erro": "Parâmetro 'tipo' deve ser uma string.",
            "tipos_disponiveis": valid_resources
        }), 400, headers
    
    # Validar se o tipo está na lista de recursos válidos
    resource_type = resource_type.strip().lower()
    if resource_type not in valid_resources:
        logger.warning(f"Parâmetro 'tipo' inválido recebido: '{resource_type}'")
        return jsonify({
            "erro": f"Parâmetro 'tipo' inválido: '{resource_type}'.",
            "tipos_disponiveis": valid_resources
        }), 400, headers
    
    # Validação do parâmetro 'termo' (opcional)
    if search_query is not None:
        # Validar se o termo é uma string
        if not isinstance(search_query, str):
            logger.warning(f"Parâmetro 'termo' não é string: {type(search_query)}")
            return jsonify({
                "erro": "Parâmetro 'termo' deve ser uma string."
            }), 400, headers
        
        # Remover espaços em branco no início e fim
        search_query = search_query.strip()
        
        # Validar se o termo não está vazio após remover espaços
        if not search_query:
            logger.warning("Parâmetro 'termo' vazio ou contém apenas espaços")
            return jsonify({
                "erro": "Parâmetro 'termo' não pode estar vazio ou conter apenas espaços."
            }), 400, headers
        
        # Validar comprimento máximo do termo (limite de 100 caracteres)
        MAX_SEARCH_LENGTH = 100
        if len(search_query) > MAX_SEARCH_LENGTH:
            logger.warning(f"Parâmetro 'termo' excede limite: {len(search_query)} caracteres")
            return jsonify({
                "erro": f"Parâmetro 'termo' excede o limite de {MAX_SEARCH_LENGTH} caracteres.",
                "tamanho_atual": len(search_query)
            }), 400, headers
        
        # Validar caracteres especiais perigosos (proteção básica contra injection)
        # Permitir apenas letras, números, espaços e alguns caracteres especiais comuns
        if not re.match(r'^[a-zA-Z0-9\s\-_\.]+$', search_query):
            logger.warning(f"Parâmetro 'termo' contém caracteres inválidos: '{search_query}'")
            return jsonify({
                "erro": "Parâmetro 'termo' contém caracteres inválidos. Use apenas letras, números, espaços e os caracteres: - _ ."
            }), 400, headers

    # 2. Construção da busca na SWAPI
    # A SWAPI usa o parâmetro '?search=' para filtrar
    swapi_params = {}
    if search_query:
        swapi_params['search'] = search_query

    # 3. Execução — buscar todas as páginas da SWAPI para ter a lista completa
    logger.info(f"Buscando dados: tipo={resource_type}, termo={search_query or 'nenhum'}")
    fetch_result = fetch_all_pages_swapi(resource_type, swapi_params)

    if fetch_result is None:
        logger.error(f"Falha ao obter dados da SWAPI para {resource_type}")
        return jsonify({"erro": "Falha ao obter dados da fonte externa."}), 502, headers

    results, total_count = fetch_result

    if not results:
        logger.info(f"Nenhum resultado encontrado para {resource_type} com termo '{search_query or 'nenhum'}'")
        return jsonify({"mensagem": "Nenhum registro encontrado para os critérios."}), 404, headers

    # 4. Aplicar ordenação se solicitada
    if sort_by:
        results = sort_results(results, sort_by, sort_order, resource_type)

    # 5. Aplicar paginação sobre a lista completa
    total_results = len(results)
    page_num, limit_num, paginated_results = apply_pagination(results, page, limit)

    # Retorna os dados encontrados com metadados básicos
    response_payload = {
        "categoria": resource_type,
        "total_encontrado": total_count,
        "total_na_pagina": len(paginated_results),
        "pagina_atual": page_num,
        "total_paginas": (total_results + limit_num - 1) // limit_num if limit_num > 0 else 1,
        "limite_por_pagina": limit_num,
        "resultados": paginated_results
    }

    logger.info(f"Sucesso: {len(paginated_results)} resultado(s) encontrado(s) para {resource_type} (página {page_num})")
    return jsonify(response_payload), 200, headers

def fetch_resource_by_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Busca um recurso específico da SWAPI pela URL.
    
    Args:
        url: URL completa do recurso na SWAPI
    
    Returns:
        Dados do recurso ou None em caso de falha
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Erro ao buscar recurso por URL {url}: {e}")
        return None

@functions_framework.http
def personagens_filme_handler(request: Request) -> Tuple[Any, int, Dict[str, str]]:
    """
    Endpoint para buscar personagens de um filme específico.
    Exemplo: /personagens-filme?filme_id=1
    """
    headers = {'Access-Control-Allow-Origin': '*'}
    
    if request.method == 'OPTIONS':
        return ('', 204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        })
    
    filme_id = request.args.get('filme_id')
    
    if not filme_id:
        return jsonify({
            "erro": "Parâmetro 'filme_id' é obrigatório."
        }), 400, headers
    
    # Buscar filme na SWAPI
    filme_url = f"{SWAPI_BASE_URL}/films/{filme_id}/"
    filme_data = fetch_resource_by_url(filme_url)
    
    if not filme_data:
        return jsonify({
            "erro": f"Filme com ID {filme_id} não encontrado."
        }), 404, headers
    
    # Extrair URLs dos personagens
    characters_urls = filme_data.get('characters', [])
    
    # Buscar dados de cada personagem
    personagens = []
    for char_url in characters_urls:
        char_data = fetch_resource_by_url(char_url)
        if char_data:
            personagens.append(char_data)
    
    response_payload = {
        "filme": {
            "titulo": filme_data.get('title'),
            "episodio": filme_data.get('episode_id'),
            "data_lancamento": filme_data.get('release_date')
        },
        "total_personagens": len(personagens),
        "personagens": personagens
    }
    
    logger.info(f"Retornados {len(personagens)} personagens para o filme {filme_id}")
    return jsonify(response_payload), 200, headers

@functions_framework.http
def naves_personagem_handler(request: Request) -> Tuple[Any, int, Dict[str, str]]:
    """
    Endpoint para buscar naves de um personagem específico.
    Exemplo: /naves-personagem?personagem_id=1
    """
    headers = {'Access-Control-Allow-Origin': '*'}
    
    if request.method == 'OPTIONS':
        return ('', 204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        })
    
    personagem_id = request.args.get('personagem_id')
    
    if not personagem_id:
        return jsonify({
            "erro": "Parâmetro 'personagem_id' é obrigatório."
        }), 400, headers
    
    # Buscar personagem na SWAPI
    personagem_url = f"{SWAPI_BASE_URL}/people/{personagem_id}/"
    personagem_data = fetch_resource_by_url(personagem_url)
    
    if not personagem_data:
        return jsonify({
            "erro": f"Personagem com ID {personagem_id} não encontrado."
        }), 404, headers
    
    # Extrair URLs das naves
    starships_urls = personagem_data.get('starships', [])
    
    # Buscar dados de cada nave
    naves = []
    for ship_url in starships_urls:
        ship_data = fetch_resource_by_url(ship_url)
        if ship_data:
            naves.append(ship_data)
    
    response_payload = {
        "personagem": {
            "nome": personagem_data.get('name'),
            "altura": personagem_data.get('height'),
            "peso": personagem_data.get('mass')
        },
        "total_naves": len(naves),
        "naves": naves
    }
    
    logger.info(f"Retornadas {len(naves)} naves para o personagem {personagem_id}")
    return jsonify(response_payload), 200, headers

@functions_framework.http
def planetas_filme_handler(request: Request) -> Tuple[Any, int, Dict[str, str]]:
    """
    Endpoint para buscar planetas de um filme específico.
    Exemplo: /planetas-filme?filme_id=1
    """
    headers = {'Access-Control-Allow-Origin': '*'}
    
    if request.method == 'OPTIONS':
        return ('', 204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        })
    
    filme_id = request.args.get('filme_id')
    
    if not filme_id:
        return jsonify({
            "erro": "Parâmetro 'filme_id' é obrigatório."
        }), 400, headers
    
    # Buscar filme na SWAPI
    filme_url = f"{SWAPI_BASE_URL}/films/{filme_id}/"
    filme_data = fetch_resource_by_url(filme_url)
    
    if not filme_data:
        return jsonify({
            "erro": f"Filme com ID {filme_id} não encontrado."
        }), 404, headers
    
    # Extrair URLs dos planetas
    planets_urls = filme_data.get('planets', [])
    
    # Buscar dados de cada planeta
    planetas = []
    for planet_url in planets_urls:
        planet_data = fetch_resource_by_url(planet_url)
        if planet_data:
            planetas.append(planet_data)
    
    response_payload = {
        "filme": {
            "titulo": filme_data.get('title'),
            "episodio": filme_data.get('episode_id'),
            "data_lancamento": filme_data.get('release_date')
        },
        "total_planetas": len(planetas),
        "planetas": planetas
    }
    
    logger.info(f"Retornados {len(planetas)} planetas para o filme {filme_id}")
    return jsonify(response_payload), 200, headers