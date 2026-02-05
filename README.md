# Star Wars API Explorer

Aplicação para explorar dados de Star Wars usando a SWAPI, com backend em Cloud Functions (GCP) e um frontend simples em HTML/JS.

Objetivo: buscar personagens, planetas, naves e filmes com filtro, ordenação e paginação.

---

## 1. Visão geral rápida

- **Backend**: `starwars-function/main.py`  
  - Endpoint principal: `/explorar`
  - Outros endpoints: `/personagens-filme`, `/naves-personagem`, `/planetas-filme`
- **Frontend**: `frontend/index.html`  
  - Página única que consome o API Gateway.

---

## 2. Como fazer deploy (resumo)

### 2.1. Cloud Function

```bash
gcloud config set project SEU_PROJECT_ID

cd starwars-function
gcloud functions deploy starwars-backend \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=starwars_handler \
  --trigger=http \
  --allow-unauthenticated
```

### 2.2. API Gateway

No arquivo `openapi2-functions.yaml`, aponte `x-google-backend.address` para a URL da função deployada.

```bash
gcloud api-gateway api-configs create starwars-config \
  --api=starwars-api \
  --openapi-spec=openapi2-functions.yaml \
  --project=SEU_PROJECT_ID

gcloud api-gateway gateways create starwars-gateway \
  --api=starwars-api \
  --api-config=starwars-config \
  --location=us-central1 \
  --project=SEU_PROJECT_ID
```

Descobrir a URL do gateway (BASE_URL):

```bash
gcloud api-gateway gateways describe starwars-gateway \
  --location=us-central1 \
  --project=SEU_PROJECT_ID
```

Depois, no `frontend/index.html`:

```js
const API_BASE_URL = "https://SEU_GATEWAY_URL";
```

---

## 3. Uso da API

### 3.1. Endpoint principal: `/explorar`

Base: `https://SEU_GATEWAY_URL/explorar`

Parâmetros principais:

- **tipo** (obrigatório): `people`, `planets`, `starships`, `films`
- **termo** (opcional): texto para filtro (nome, título etc.)
- **ordenar_por** (opcional):
  - people: `name`, `height`, `mass`, `birth_year`
  - planets: `name`, `diameter`, `population`, `rotation_period`, `orbital_period`
  - starships: `name`, `length`, `crew`, `passengers`, `cargo_capacity`, `cost_in_credits`
  - films: `title`, `episode_id`, `release_date`
- **ordem** (opcional): `asc` (padrão) ou `desc`
- **pagina** (opcional): número ≥ 1 (padrão 1)
- **limite** (opcional): 1 a 100 (padrão 10)

Exemplos:

```bash
# Lista pessoas (paginadas)
curl "https://SEU_GATEWAY_URL/explorar?tipo=people&pagina=1&limite=10"

# Busca por termo
curl "https://SEU_GATEWAY_URL/explorar?tipo=people&termo=Luke"

# Ordenação
curl "https://SEU_GATEWAY_URL/explorar?tipo=people&ordenar_por=height&ordem=desc"
```

### 3.2. Endpoints auxiliares

- `/personagens-filme?filme_id=1`
- `/naves-personagem?personagem_id=1`
- `/planetas-filme?filme_id=1`

---

## 4. Frontend (uso)

1. Ajuste `API_BASE_URL` em `frontend/index.html` para o seu gateway.
2. Abra `frontend/index.html` no navegador **ou** sirva com `python -m http.server`.
3. Na tela:
   - Escolha o tipo (Personagens, Planetas, Naves, Filmes).
   - Opcional: termo de busca, ordenação, limite por página.
   - Clique em **Buscar** e use a paginação.

---

## 5. Testes

```bash
cd starwars-function
pip install -r requirements.txt
pytest -v
```

---

## 6. Cuidados de segurança

- **Não** commitar:
  - Arquivos de credencial do GCP (`*.json` de service account).
  - Tokens, senhas, chaves de API, `.env`.
- A URL do API Gateway pode ficar no código (ela é pública por natureza).

---

## 7. Estrutura do projeto

```
star-wars-api/
  frontend/
    index.html
  starwars-function/
    main.py
    test_main.py
    requirements.txt
    openapi2-functions.yaml
  README.md
  ARCHITECTURE.md
```

