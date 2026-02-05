# Star Wars API Explorer

![Interface do Star Wars API Explorer](docs/frontend.png)

Aplicação para explorar dados de Star Wars usando a SWAPI, com backend em Cloud Functions (GCP) e um frontend em HTML/JS.

**Principais funcionalidades:**
- **Buscar recursos**: personagens, planetas, naves espaciais e filmes.
- **Filtrar por termo**: pesquisar por nome ou título.
- **Ordenar resultados**: por campos como altura, peso, população, data de lançamento etc.
- **Paginar resultados**: controlar página e quantidade de itens.
- **Consultas correlacionadas**: personagens por filme, naves por personagem, planetas por filme.

---

## 1. Como testar (instância já publicada)

Você não precisa subir nada para testar. Já existe uma instância publicada.

- **URL base do API Gateway (minha instância):**

  `https://starwars-gateway-7mwhqkjo.uc.gateway.dev/`

### 1.1. Testar direto no navegador

Abra no navegador, por exemplo:

- **Lista de personagens** (página 1, 10 itens):

  `https://starwars-gateway-7mwhqkjo.uc.gateway.dev/explorar?tipo=people&pagina=1&limite=10`

- **Buscar por “Luke”**:

  `https://starwars-gateway-7mwhqkjo.uc.gateway.dev/explorar?tipo=people&termo=Luke`

- **Planetas com “Tat” no nome**:

  `https://starwars-gateway-7mwhqkjo.uc.gateway.dev/explorar?tipo=planets&termo=Tat`

### 1.2. Testar com o frontend deste projeto

1. Abra o arquivo `frontend/index.html` em um editor.
2. Confira a linha onde está a `API_BASE_URL`:

   ```js
   const API_BASE_URL = 'https://starwars-gateway-7mwhqkjo.uc.gateway.dev/';
   ```

3. Abra o arquivo `frontend/index.html` no navegador.
4. Na interface:
   - Escolha o tipo (Personagens, Planetas, Naves, Filmes).
   - (Opcional) Informe termo de busca, campo de ordenação, ordem e limite por página.
   - Clique em **Buscar** e use os botões de paginação.

### 1.3. Testar via linha de comando (curl)

```bash
# Lista pessoas (paginadas)
curl "https://starwars-gateway-7mwhqkjo.uc.gateway.dev/explorar?tipo=people&pagina=1&limite=10"

# Busca por Luke
curl "https://starwars-gateway-7mwhqkjo.uc.gateway.dev/explorar?tipo=people&termo=Luke"

# Ordenar pessoas por altura (desc)
curl "https://starwars-gateway-7mwhqkjo.uc.gateway.dev/explorar?tipo=people&ordenar_por=height&ordem=desc&pagina=1&limite=5"
```

---

## 2. Referência rápida da API

### 2.1. Endpoint principal: `/explorar`

- **Base (minha instância):**  
  `https://starwars-gateway-7mwhqkjo.uc.gateway.dev/explorar`

- **Parâmetros principais:**
  - **tipo** (obrigatório): `people`, `planets`, `starships`, `films`
  - **termo** (opcional): texto de busca (nome, título etc.)
  - **ordenar_por** (opcional):
    - people: `name`, `height`, `mass`, `birth_year`
    - planets: `name`, `diameter`, `population`, `rotation_period`, `orbital_period`
    - starships: `name`, `length`, `crew`, `passengers`, `cargo_capacity`, `cost_in_credits`
    - films: `title`, `episode_id`, `release_date`
  - **ordem** (opcional): `asc` (padrão) ou `desc`
  - **pagina** (opcional): número ≥ 1 (padrão 1)
  - **limite** (opcional): 1 a 100 (padrão 10)

**Exemplo de resposta simplificada:**

```json
{
  "categoria": "people",
  "total_encontrado": 82,
  "total_na_pagina": 10,
  "pagina_atual": 1,
  "total_paginas": 9,
  "limite_por_pagina": 10,
  "resultados": [
    {
      "name": "Luke Skywalker",
      "height": "172",
      "mass": "77",
      "birth_year": "19BBY",
      "gender": "male",
      "url": "https://swapi.dev/api/people/1/"
    }
  ]
}
```

### 2.2. Endpoints auxiliares

Todos usando a mesma base: `https://starwars-gateway-7mwhqkjo.uc.gateway.dev/`

- **Personagens de um filme**

  `/personagens-filme?filme_id=1`

- **Naves de um personagem**

  `/naves-personagem?personagem_id=1`

- **Planetas de um filme**

  `/planetas-filme?filme_id=1`

---

## 3. Como fazer seu próprio deploy (opcional)

Se quiser subir sua própria instância no GCP, o fluxo é:

### 3.1. Cloud Function

Pré-requisitos:
- Ter um projeto no GCP.
- Ter o `gcloud` instalado e autenticado.

Comandos:

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

### 3.2. API Gateway

No arquivo `starwars-function/openapi2-functions.yaml`, ajuste o campo
`x-google-backend.address` para a URL da função deployada (a URL que o comando
de deploy da Cloud Function retorna).

Depois:

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

Para descobrir a URL do gateway:

```bash
gcloud api-gateway gateways describe starwars-gateway \
  --location=us-central1 \
  --project=SEU_PROJECT_ID
```

Depois é só usar essa URL como `API_BASE_URL` no `frontend/index.html`.

---

## 4. Visão geral da aplicação

- **Backend**: `starwars-function/main.py`
  - Endpoint principal `/explorar` com:
    - Busca por termo.
    - Ordenação por campo.
    - Paginação em memória, após agregar todas as páginas da SWAPI.
  - Endpoints auxiliares:
    - `/personagens-filme`
    - `/naves-personagem`
    - `/planetas-filme`

- **Frontend**: `frontend/index.html`
  - Página única que consome a URL do API Gateway.
  - Permite escolher tipo, termo, ordenação, limite por página e navegar pelos resultados.

---

## 5. Testes (backend)

Opcional, para quem quiser rodar os testes localmente:

```bash
cd starwars-function
pip install -r requirements.txt
pytest -v
```

---

## 6. Cuidados de segurança

- **Não** commitar:
  - Arquivos de credencial do GCP (`*.json` de service account).
  - Tokens, senhas, chaves de API, arquivos `.env`.
- A URL do API Gateway pode ficar no código (ela é pública por natureza).

---

## 7. Estrutura do projeto

```text
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

# Star Wars API Explorer

![Interface do Star Wars API Explorer](docs/frontend.png)

---

## 1. Como testar (instância já publicada)

Você não precisa subir nada para testar. Já existe uma instância publicada.

- **URL base do API Gateway:**

  `https://starwars-gateway-7mwhqkjo.uc.gateway.dev/`

### 1.1. Testar direto no navegador

Abra no navegador, por exemplo:

- Lista de personagens (página 1, 10 itens):

  `https://starwars-gateway-7mwhqkjo.uc.gateway.dev/explorar?tipo=people&pagina=1&limite=10`
- Buscar por “Luke”:

  `https://starwars-gateway-7mwhqkjo.uc.gateway.dev/explorar?tipo=people&termo=Luke`

Você verá o JSON retornado pela API.

### 1.2. Testar com o frontend deste projeto

1. Abra o arquivo `frontend/index.html` em um editor.
2. Confira a linha onde está a `API_BASE_URL`:

   const API_BASE_URL = 'https://starwars-gateway-7mwhqkjo.uc.gateway.dev/';
