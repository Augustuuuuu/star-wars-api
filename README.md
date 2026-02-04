# Star Wars API Explorer

Plataforma desenvolvida no Google Cloud Platform (GCP) que oferece uma experiência envolvente para explorar informações detalhadas sobre personagens, planetas, naves e filmes da saga Star Wars.

## 🚀 Tecnologias

- **Cloud Functions**: Função HTTP serverless no GCP
- **API Gateway**: Gerenciamento e exposição da API
- **Python 3**: Linguagem principal do projeto
- **SWAPI**: Fonte de dados (https://swapi.dev/)

## 📋 Pré-requisitos

- Conta no Google Cloud Platform
- Google Cloud SDK instalado e configurado
- Python 3.7 ou superior
- Permissões para criar Cloud Functions e API Gateway

## 🛠️ Instalação e Deploy

### 1. Configurar o projeto GCP

```bash
# Definir o projeto GCP
gcloud config set project SEU_PROJECT_ID

# Habilitar APIs necessárias
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable apigateway.googleapis.com
gcloud services enable servicemanagement.googleapis.com
gcloud services enable servicecontrol.googleapis.com
```

### 2. Deploy da Cloud Function

```bash
# Navegar para o diretório da função
cd starwars-function

# Fazer deploy da função
gcloud functions deploy starwars-backend \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=starwars_handler \
  --trigger=http \
  --allow-unauthenticated
```

### 3. Configurar o API Gateway

```bash
# Criar o API Gateway
gcloud api-gateway api-configs create starwars-config \
  --api=starwars-api \
  --openapi-spec=openapi2-functions.yaml \
  --project=SEU_PROJECT_ID \
  --backend-auth-service-account=SERVICE_ACCOUNT_EMAIL

# Criar o gateway (se ainda não existir)
gcloud api-gateway gateways create starwars-gateway \
  --api=starwars-api \
  --api-config=starwars-config \
  --location=us-central1 \
  --project=SEU_PROJECT_ID
```

### 4. Obter a URL do API Gateway

```bash
# Listar gateways
gcloud api-gateway gateways describe starwars-gateway \
  --location=us-central1 \
  --project=SEU_PROJECT_ID
```

## 📖 Uso da API

### Endpoint Base

```
https://SEU_GATEWAY_URL/explorar
```

### Parâmetros

| Parâmetro | Tipo | Obrigatório | Descrição | Valores Aceitos |
|-----------|------|-------------|-----------|-----------------|
| `tipo` | string | Sim | Tipo de recurso a consultar | `people`, `planets`, `starships`, `films` |
| `termo` | string | Não | Termo de busca (nome, título, etc.) | Qualquer string (máx. 100 caracteres) |

### Exemplos de Requisições

#### Buscar todos os personagens
```bash
curl "https://SEU_GATEWAY_URL/explorar?tipo=people"
```

#### Buscar personagem específico
```bash
curl "https://SEU_GATEWAY_URL/explorar?tipo=people&termo=Luke"
```

#### Buscar planetas
```bash
curl "https://SEU_GATEWAY_URL/explorar?tipo=planets&termo=Tatooine"
```

#### Buscar naves espaciais
```bash
curl "https://SEU_GATEWAY_URL/explorar?tipo=starships&termo=Falcon"
```

#### Buscar filmes
```bash
curl "https://SEU_GATEWAY_URL/explorar?tipo=films&termo=Empire"
```

### Exemplo de Resposta de Sucesso

```json
{
  "categoria": "people",
  "total_encontrado": 1,
  "resultados": [
    {
      "name": "Luke Skywalker",
      "height": "172",
      "mass": "77",
      "hair_color": "blond",
      "skin_color": "fair",
      "eye_color": "blue",
      "birth_year": "19BBY",
      "gender": "male",
      "homeworld": "https://swapi.dev/api/planets/1/",
      "films": [
        "https://swapi.dev/api/films/1/",
        "https://swapi.dev/api/films/2/",
        ...
      ],
      "species": [],
      "vehicles": [
        "https://swapi.dev/api/vehicles/14/",
        "https://swapi.dev/api/vehicles/30/"
      ],
      "starships": [
        "https://swapi.dev/api/starships/12/",
        "https://swapi.dev/api/starships/22/"
      ],
      "created": "2014-12-09T13:50:51.644000Z",
      "edited": "2014-12-20T21:17:56.891000Z",
      "url": "https://swapi.dev/api/people/1/"
    }
  ]
}
```

### Códigos de Status HTTP

| Código | Descrição |
|--------|-----------|
| 200 | Sucesso - Dados retornados |
| 400 | Requisição inválida - Parâmetros incorretos ou ausentes |
| 404 | Nenhum resultado encontrado |
| 502 | Erro ao conectar com a API externa (SWAPI) |
| 500 | Erro interno do servidor |

### Exemplos de Respostas de Erro

#### Parâmetro 'tipo' inválido
```json
{
  "erro": "Parâmetro 'tipo' inválido ou ausente.",
  "tipos_disponiveis": ["people", "planets", "starships", "films"]
}
```

#### Nenhum resultado encontrado
```json
{
  "mensagem": "Nenhum registro encontrado para os critérios."
}
```

#### Erro de conexão com SWAPI
```json
{
  "erro": "Falha ao obter dados da fonte externa."
}
```

## 🧪 Testes

### Executar Testes Unitários

O projeto inclui testes unitários abrangentes usando pytest:

```bash
# Instalar dependências (incluindo dependências de teste)
cd starwars-function
pip install -r requirements.txt

# Executar todos os testes
pytest

# Executar testes com output detalhado
pytest -v

# Executar testes com cobertura de código
pytest --cov=main --cov-report=html

# Executar um teste específico
pytest test_main.py::TestFetchFromSwapi::test_success_first_attempt
```

### Estrutura de Testes

Os testes estão organizados em duas classes principais:

- **TestFetchFromSwapi**: Testa a função auxiliar `fetch_from_swapi()`
  - Sucesso na primeira tentativa
  - Retry em caso de timeout
  - Retry em caso de erro de conexão
  - Retry em caso de HTTP 5xx
  - Não retry em caso de HTTP 4xx
  - Falha após todas as tentativas
  - Busca com parâmetros de pesquisa

- **TestStarwarsHandler**: Testa o handler principal `starwars_handler()`
  - Requisição OPTIONS (CORS)
  - Validação de parâmetros (tipo ausente, inválido, etc.)
  - Validação de termo (caracteres inválidos, muito longo, vazio)
  - Sucesso com e sem filtro
  - Tratamento de erros da SWAPI
  - Todos os tipos de recursos

### Testes Locais da API

Para testar a API localmente antes do deploy:

```bash
# Instalar dependências
cd starwars-function
pip install -r requirements.txt

# Executar localmente com Functions Framework
functions-framework --target=starwars_handler --port=8080

# Testar em outro terminal
curl "http://localhost:8080?tipo=people&termo=Luke"
```

## 📁 Estrutura do Projeto

```
star-wars-api/
├── README.md                          # Documentação do projeto
├── LICENSE                            # Licença do projeto
├── starwars-function/
│   ├── main.py                        # Código principal da Cloud Function
│   ├── test_main.py                   # Testes unitários
│   ├── pytest.ini                     # Configuração do pytest
│   ├── requirements.txt               # Dependências Python
│   └── openapi2-functions.yaml       # Especificação OpenAPI para API Gateway
```

## 🔧 Desenvolvimento

### Dependências

**Produção:**
- `functions-framework==3.*`: Framework para desenvolvimento de Cloud Functions
- `requests`: Biblioteca para requisições HTTP

**Desenvolvimento/Testes:**
- `pytest==7.4.3`: Framework de testes
- `pytest-mock==3.12.0`: Mocking para testes
- `pytest-cov==4.1.0`: Cobertura de código

### Funcionalidades Implementadas

- ✅ Consulta de personagens, planetas, naves e filmes
- ✅ Busca por termo específico
- ✅ Validação de parâmetros
- ✅ Tratamento de erros com retry automático
- ✅ Suporte a CORS
- ✅ Respostas estruturadas com metadados

## 📝 Notas Técnicas

- A API utiliza a SWAPI (https://swapi.dev/) como fonte de dados
- Implementa retry automático para falhas temporárias de rede
- Validação de parâmetros com limites de tamanho
- Headers CORS configurados para permitir acesso via browser
- Logging estruturado para melhor observabilidade
- Type hints para melhor suporte de IDE e detecção de erros
- Testes unitários com cobertura abrangente usando pytest

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests.

## 📄 Licença

Este projeto está sob a licença especificada no arquivo LICENSE.
