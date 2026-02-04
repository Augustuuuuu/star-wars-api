"""
Testes unitários para a Cloud Function Star Wars API Explorer.
"""
import pytest
from unittest.mock import Mock, patch
import requests
from main import fetch_from_swapi, starwars_handler, MAX_RETRIES, RETRY_DELAY, RETRY_BACKOFF


class TestFetchFromSwapi:
    """Testes para a função fetch_from_swapi."""
    
    @patch('main.requests.get')
    def test_success_first_attempt(self, mock_get):
        """Testa sucesso na primeira tentativa."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": [{"name": "Luke Skywalker"}]}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = fetch_from_swapi("people")
        
        assert result == {"results": [{"name": "Luke Skywalker"}]}
        assert mock_get.call_count == 1
    
    @patch('main.time.sleep')
    @patch('main.requests.get')
    def test_retry_on_timeout(self, mock_get, mock_sleep):
        """Testa retry em caso de timeout."""
        # Primeira tentativa: timeout
        # Segunda tentativa: sucesso
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            Mock(json=Mock(return_value={"results": []}), raise_for_status=Mock())
        ]
        
        result = fetch_from_swapi("people")
        
        assert result == {"results": []}
        assert mock_get.call_count == 2
        assert mock_sleep.call_count == 1
        # Verifica que o tempo de espera é calculado corretamente
        assert mock_sleep.call_args[0][0] == RETRY_DELAY * (RETRY_BACKOFF ** 0)
    
    @patch('main.time.sleep')
    @patch('main.requests.get')
    def test_retry_on_connection_error(self, mock_get, mock_sleep):
        """Testa retry em caso de erro de conexão."""
        mock_get.side_effect = [
            requests.exceptions.ConnectionError(),
            Mock(json=Mock(return_value={"results": []}), raise_for_status=Mock())
        ]
        
        result = fetch_from_swapi("people")
        
        assert result == {"results": []}
        assert mock_get.call_count == 2
        assert mock_sleep.call_count == 1
    
    @patch('main.time.sleep')
    @patch('main.requests.get')
    def test_retry_on_http_5xx(self, mock_get, mock_sleep):
        """Testa retry em caso de erro HTTP 5xx."""
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        http_error_500 = requests.exceptions.HTTPError(response=mock_response_500)
        
        mock_get.side_effect = [
            http_error_500,
            Mock(json=Mock(return_value={"results": []}), raise_for_status=Mock())
        ]
        
        result = fetch_from_swapi("people")
        
        assert result == {"results": []}
        assert mock_get.call_count == 2
        assert mock_sleep.call_count == 1
    
    @patch('main.requests.get')
    def test_no_retry_on_http_4xx(self, mock_get):
        """Testa que não há retry em caso de erro HTTP 4xx."""
        mock_response_404 = Mock()
        mock_response_404.status_code = 404
        http_error_404 = requests.exceptions.HTTPError(response=mock_response_404)
        mock_get.side_effect = http_error_404
        
        result = fetch_from_swapi("people")
        
        assert result is None
        assert mock_get.call_count == 1
    
    @patch('main.time.sleep')
    @patch('main.requests.get')
    def test_failure_after_all_retries(self, mock_get, mock_sleep):
        """Testa falha após todas as tentativas."""
        mock_get.side_effect = requests.exceptions.Timeout()
        
        result = fetch_from_swapi("people")
        
        assert result is None
        assert mock_get.call_count == MAX_RETRIES
        assert mock_sleep.call_count == MAX_RETRIES - 1
    
    @patch('main.requests.get')
    def test_with_search_params(self, mock_get):
        """Testa busca com parâmetros de pesquisa."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": [{"name": "Luke"}]}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = fetch_from_swapi("people", {"search": "Luke"})
        
        assert result == {"results": [{"name": "Luke"}]}
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[1]['params'] == {"search": "Luke"}


class TestStarwarsHandler:
    """Testes para a função starwars_handler."""
    
    def create_mock_request(self, method='GET', args=None):
        """Cria um mock de request Flask."""
        mock_request = Mock()
        mock_request.method = method
        mock_request.path = '/explorar'
        mock_request.args = Mock()
        if args:
            mock_request.args.get = lambda key, default=None: args.get(key, default)
        else:
            mock_request.args.get = lambda key, default=None: default
        return mock_request
    
    def test_options_request(self):
        """Testa requisição OPTIONS (CORS preflight)."""
        mock_request = self.create_mock_request(method='OPTIONS')
        
        response, status_code, headers = starwars_handler(mock_request)
        
        assert status_code == 204
        assert headers['Access-Control-Allow-Origin'] == '*'
        assert headers['Access-Control-Allow-Methods'] == 'GET'
    
    def test_missing_tipo_parameter(self):
        """Testa validação quando parâmetro 'tipo' está ausente."""
        mock_request = self.create_mock_request(args={})
        
        response, status_code, headers = starwars_handler(mock_request)
        
        assert status_code == 400
        data = response.get_json()
        assert 'erro' in data
        assert "obrigatório" in data['erro'].lower()
    
    def test_invalid_tipo_parameter(self):
        """Testa validação quando parâmetro 'tipo' é inválido."""
        mock_request = self.create_mock_request(args={'tipo': 'invalid'})
        
        response, status_code, headers = starwars_handler(mock_request)
        
        assert status_code == 400
        data = response.get_json()
        assert 'erro' in data
        assert 'tipos_disponiveis' in data
    
    def test_tipo_case_insensitive(self):
        """Testa que o parâmetro 'tipo' é case-insensitive."""
        mock_request = self.create_mock_request(args={'tipo': 'PEOPLE'})
        
        with patch('main.fetch_from_swapi') as mock_fetch:
            mock_fetch.return_value = {
                'results': [{'name': 'Luke'}],
                'count': 1
            }
            
            response, status_code, headers = starwars_handler(mock_request)
            
            assert status_code == 200
            mock_fetch.assert_called_once_with('people', {})
    
    def test_invalid_termo_characters(self):
        """Testa validação de caracteres inválidos no parâmetro 'termo'."""
        mock_request = self.create_mock_request(args={
            'tipo': 'people',
            'termo': 'Luke<script>alert("xss")</script>'
        })
        
        response, status_code, headers = starwars_handler(mock_request)
        
        assert status_code == 400
        data = response.get_json()
        assert 'erro' in data
        assert 'caracteres inválidos' in data['erro'].lower()
    
    def test_termo_too_long(self):
        """Testa validação de comprimento máximo do parâmetro 'termo'."""
        long_term = 'a' * 101  # 101 caracteres
        mock_request = self.create_mock_request(args={
            'tipo': 'people',
            'termo': long_term
        })
        
        response, status_code, headers = starwars_handler(mock_request)
        
        assert status_code == 400
        data = response.get_json()
        assert 'erro' in data
        assert 'limite' in data['erro'].lower()
    
    def test_termo_empty_string(self):
        """Testa validação quando 'termo' é string vazia."""
        mock_request = self.create_mock_request(args={
            'tipo': 'people',
            'termo': '   '  # apenas espaços
        })
        
        response, status_code, headers = starwars_handler(mock_request)
        
        assert status_code == 400
        data = response.get_json()
        assert 'erro' in data
    
    @patch('main.fetch_from_swapi')
    def test_success_without_filter(self, mock_fetch):
        """Testa sucesso sem filtro de busca."""
        mock_request = self.create_mock_request(args={'tipo': 'people'})
        mock_fetch.return_value = {
            'results': [{'name': 'Luke Skywalker'}],
            'count': 1
        }
        
        response, status_code, headers = starwars_handler(mock_request)
        
        assert status_code == 200
        data = response.get_json()
        assert data['categoria'] == 'people'
        assert data['total_encontrado'] == 1
        assert len(data['resultados']) == 1
        mock_fetch.assert_called_once_with('people', {})
    
    @patch('main.fetch_from_swapi')
    def test_success_with_filter(self, mock_fetch):
        """Testa sucesso com filtro de busca."""
        mock_request = self.create_mock_request(args={
            'tipo': 'people',
            'termo': 'Luke'
        })
        mock_fetch.return_value = {
            'results': [{'name': 'Luke Skywalker'}],
            'count': 1
        }
        
        response, status_code, headers = starwars_handler(mock_request)
        
        assert status_code == 200
        data = response.get_json()
        assert data['categoria'] == 'people'
        assert len(data['resultados']) == 1
        mock_fetch.assert_called_once_with('people', {'search': 'Luke'})
    
    @patch('main.fetch_from_swapi')
    def test_no_results_found(self, mock_fetch):
        """Testa resposta quando não há resultados."""
        mock_request = self.create_mock_request(args={
            'tipo': 'people',
            'termo': 'NonExistent'
        })
        mock_fetch.return_value = {
            'results': [],
            'count': 0
        }
        
        response, status_code, headers = starwars_handler(mock_request)
        
        assert status_code == 404
        data = response.get_json()
        assert 'mensagem' in data
    
    @patch('main.fetch_from_swapi')
    def test_swapi_error(self, mock_fetch):
        """Testa tratamento de erro da SWAPI."""
        mock_request = self.create_mock_request(args={'tipo': 'people'})
        mock_fetch.return_value = None
        
        response, status_code, headers = starwars_handler(mock_request)
        
        assert status_code == 502
        data = response.get_json()
        assert 'erro' in data
    
    @patch('main.fetch_from_swapi')
    def test_all_resource_types(self, mock_fetch):
        """Testa que todos os tipos de recursos são aceitos."""
        mock_fetch.return_value = {'results': [], 'count': 0}
        
        resource_types = ['people', 'planets', 'starships', 'films']
        
        for resource_type in resource_types:
            mock_request = self.create_mock_request(args={'tipo': resource_type})
            response, status_code, headers = starwars_handler(mock_request)
            
            # Deve retornar 404 (sem resultados) mas não erro de validação
            assert status_code in [200, 404]
            mock_fetch.assert_called_with(resource_type, {})
    
    def test_termo_stripped(self):
        """Testa que espaços em branco são removidos do 'termo'."""
        mock_request = self.create_mock_request(args={
            'tipo': 'people',
            'termo': '  Luke  '
        })
        
        with patch('main.fetch_from_swapi') as mock_fetch:
            mock_fetch.return_value = {'results': [], 'count': 0}
            
            starwars_handler(mock_request)
            
            # Verifica que o termo foi passado sem espaços
            mock_fetch.assert_called_once_with('people', {'search': 'Luke'})
