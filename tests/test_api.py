"""Testes automatizados cobrindo Autenticação JWT, Isolamento de Usuários e RF01 a RF04."""

import pytest
import pytest_asyncio
import httpx
from datetime import datetime, timezone, timedelta
from app.main import app
from app.database import (
    DatabaseManager,
    get_recursos_collection,
    get_movimentacoes_collection,
    get_usuarios_collection,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Garante conexão com banco antes de cada teste e limpa dados de teste após."""
    await DatabaseManager.connect()
    yield
    try:
        recursos_col = get_recursos_collection()
        movimentacoes_col = get_movimentacoes_collection()
        usuarios_col = get_usuarios_collection()
        await recursos_col.delete_many({"nome": {"$regex": "^TEST_"}})
        await movimentacoes_col.delete_many({"motivo": {"$regex": "^TEST_"}})
        await usuarios_col.delete_many({"email": {"$regex": "^test_.*@exemplo.com$"}})
    except Exception:
        pass


@pytest_asyncio.fixture
async def client():
    """Cliente HTTP assíncrono para testes da API."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    """Cria um usuário de teste e retorna o cabeçalho Authorization com JWT Bearer."""
    email = f"test_user_{datetime.now().timestamp()}@exemplo.com"
    payload = {
        "nome": "Usuário Teste",
        "email": email,
        "senha": "senha_segura_123"
    }
    res = await client.post("/api/auth/registrar", json=payload)
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# TESTES DE SAÚDE E AUTENTICAÇÃO
# =============================================================================

@pytest.mark.asyncio
async def test_health_check(client: httpx.AsyncClient):
    """Verifica saúde do sistema e conectividade com o MongoDB."""
    res = await client.get("/api/health")
    assert res.status_code == 200
    dados = res.json()
    assert dados["status"] == "online"
    assert dados["database_connected"] is True


@pytest.mark.asyncio
async def test_autenticacao_fluxo_completo(client: httpx.AsyncClient):
    """Testa cadastro, login e verificação de rota protegida /api/auth/perfil."""
    email = f"test_fluxo_{datetime.now().timestamp()}@exemplo.com"
    senha = "senha_teste_456"

    # 1. Cadastro
    res_reg = await client.post("/api/auth/registrar", json={
        "nome": "João Silva",
        "email": email,
        "senha": senha,
    })
    assert res_reg.status_code == 201
    dados_reg = res_reg.json()
    assert "access_token" in dados_reg
    assert dados_reg["nome"] == "João Silva"
    assert dados_reg["email"] == email

    # 2. Rejeição de e-mail duplicado (409 Conflict)
    res_dup = await client.post("/api/auth/registrar", json={
        "nome": "Outro João",
        "email": email,
        "senha": "outra_senha_123",
    })
    assert res_dup.status_code == 409

    # 3. Login com credenciais corretas
    res_login = await client.post("/api/auth/login", json={
        "email": email,
        "senha": senha,
    })
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]

    # 4. Login com senha errada (401 Unauthorized)
    res_err = await client.post("/api/auth/login", json={
        "email": email,
        "senha": "senha_incorreta",
    })
    assert res_err.status_code == 401

    # 5. Acesso ao perfil com token válido
    headers = {"Authorization": f"Bearer {token}"}
    res_perfil = await client.get("/api/auth/perfil", headers=headers)
    assert res_perfil.status_code == 200
    assert res_perfil.json()["email"] == email


@pytest.mark.asyncio
async def test_bloqueio_rotas_sem_autenticacao(client: httpx.AsyncClient):
    """Garante que rotas protegidas retornem 401 quando chamadas sem token."""
    res_rec = await client.get("/api/recursos")
    assert res_rec.status_code == 401

    res_mov = await client.get("/api/movimentacoes")
    assert res_mov.status_code == 401

    res_dash = await client.get("/api/relatorios/dashboard")
    assert res_dash.status_code == 401


@pytest.mark.asyncio
async def test_isolamento_de_estoque_entre_usuarios(client: httpx.AsyncClient):
    """Garante que o Usuário A NÃO enxergue os recursos cadastrados pelo Usuário B."""
    hoje = datetime.now(timezone.utc)
    validade = (hoje + timedelta(days=60)).isoformat()

    # Cria Usuário A
    res_a = await client.post("/api/auth/registrar", json={
        "nome": "Usuário A",
        "email": f"test_a_{datetime.now().timestamp()}@exemplo.com",
        "senha": "senha_usuario_a",
    })
    headers_a = {"Authorization": f"Bearer {res_a.json()['access_token']}"}

    # Cria Usuário B
    res_b = await client.post("/api/auth/registrar", json={
        "nome": "Usuário B",
        "email": f"test_b_{datetime.now().timestamp()}@exemplo.com",
        "senha": "senha_usuario_b",
    })
    headers_b = {"Authorization": f"Bearer {res_b.json()['access_token']}"}

    # Usuário A cria um recurso exclusivo
    payload = {
        "nome": "TEST_Item Exclusivo Usuario A",
        "categoria": "Alimentos",
        "unidade_medida": "KG",
        "quantidade_atual": 50.0,
        "estoque_minimo": 10.0,
        "lote": "LOTE-A",
        "data_validade": validade,
    }
    res_post_a = await client.post("/api/recursos", json=payload, headers=headers_a)
    assert res_post_a.status_code == 201
    item_id_a = res_post_a.json()["id"]

    # Usuário A lista e enxerga seu item
    lista_a = (await client.get("/api/recursos", headers=headers_a)).json()
    assert any(i["id"] == item_id_a for i in lista_a)

    # Usuário B lista e NÃO deve enxergar o item do Usuário A
    lista_b = (await client.get("/api/recursos", headers=headers_b)).json()
    assert not any(i["id"] == item_id_a for i in lista_b)

    # Usuário B tenta acessar o item de A diretamente por ID -> deve retornar 404
    res_b_acesso_direto = await client.get(f"/api/recursos/{item_id_a}", headers=headers_b)
    assert res_b_acesso_direto.status_code == 404


# =============================================================================
# TESTES DE REQUISITOS RF01 - RF04 (AUTENTICADOS)
# =============================================================================

@pytest.mark.asyncio
async def test_rf01_crud_recurso(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    """RF01: Testa cadastro, consulta, atualização e exclusão de um recurso autenticado."""
    hoje = datetime.now(timezone.utc)
    validade_futura = (hoje + timedelta(days=120)).isoformat()

    # 1. Criação
    payload_criar = {
        "nome": "TEST_Feijao Carioca 1kg",
        "descricao": "Insumo teste para cestas básicas",
        "categoria": "Alimentos",
        "unidade_medida": "KG",
        "quantidade_atual": 100.0,
        "estoque_minimo": 25.0,
        "lote": "LOTE-TEST-001",
        "data_validade": validade_futura,
    }

    res_post = await client.post("/api/recursos", json=payload_criar, headers=auth_headers)
    assert res_post.status_code == 201, res_post.text
    recurso_criado = res_post.json()
    recurso_id = recurso_criado["id"]

    assert recurso_criado["nome"] == payload_criar["nome"]
    assert recurso_criado["status_estoque"] == "NORMAL"
    assert recurso_criado["status_validade"] == "NORMAL"

    # 2. Consulta por ID
    res_get = await client.get(f"/api/recursos/{recurso_id}", headers=auth_headers)
    assert res_get.status_code == 200
    assert res_get.json()["id"] == recurso_id

    # 3. Atualização
    payload_update = {
        "estoque_minimo": 30.0,
        "descricao": "Descrição atualizada no teste",
    }
    res_put = await client.put(f"/api/recursos/{recurso_id}", json=payload_update, headers=auth_headers)
    assert res_put.status_code == 200
    assert res_put.json()["estoque_minimo"] == 30.0
    assert res_put.json()["descricao"] == "Descrição atualizada no teste"

    # 4. Listagem com busca
    res_lista = await client.get("/api/recursos?busca=TEST_Feijao", headers=auth_headers)
    assert res_lista.status_code == 200
    itens = res_lista.json()
    assert any(item["id"] == recurso_id for item in itens)

    # 5. Exclusão
    res_del = await client.delete(f"/api/recursos/{recurso_id}", headers=auth_headers)
    assert res_del.status_code == 200

    # Confirma que foi excluído
    res_get_pos = await client.get(f"/api/recursos/{recurso_id}", headers=auth_headers)
    assert res_get_pos.status_code == 404


@pytest.mark.asyncio
async def test_rf02_fluxo_movimentacoes_e_validacao_saldo_negativo(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
):
    """RF02: Valida entradas, saídas auditáveis e rejeição preventiva de saldo negativo."""
    hoje = datetime.now(timezone.utc)
    validade_futura = (hoje + timedelta(days=90)).isoformat()

    # Cria recurso base com saldo inicial de 50
    payload_rec = {
        "nome": "TEST_Leite Integral 1L",
        "categoria": "Alimentos",
        "unidade_medida": "LITRO",
        "quantidade_atual": 50.0,
        "estoque_minimo": 15.0,
        "lote": "LOTE-TEST-LEITE",
        "data_validade": validade_futura,
    }
    rec_res = await client.post("/api/recursos", json=payload_rec, headers=auth_headers)
    assert rec_res.status_code == 201
    rec = rec_res.json()
    recurso_id = rec["id"]

    try:
        # 1. ENTRADA: adiciona 30 unidades (saldo esperado: 80)
        mov_entrada = {
            "recurso_id": recurso_id,
            "tipo": "ENTRADA",
            "quantidade": 30.0,
            "origem_destino": "Doação Fornecedor Local",
            "motivo": "TEST_Campanha Solidária",
            "responsavel": "Operador Teste",
        }
        res_ent = await client.post("/api/movimentacoes", json=mov_entrada, headers=auth_headers)
        assert res_ent.status_code == 201
        dados_ent = res_ent.json()
        assert dados_ent["saldo_anterior"] == 50.0
        assert dados_ent["saldo_posterior"] == 80.0

        # Verifica saldo atualizado no recurso
        rec_check1 = (await client.get(f"/api/recursos/{recurso_id}", headers=auth_headers)).json()
        assert rec_check1["quantidade_atual"] == 80.0

        # 2. SAÍDA válida: retira 25 unidades (saldo esperado: 55)
        mov_saida = {
            "recurso_id": recurso_id,
            "tipo": "SAIDA",
            "quantidade": 25.0,
            "origem_destino": "Comunidade Passagem de Areia",
            "motivo": "TEST_Distribuição Familiar",
            "responsavel": "Operador Teste",
        }
        res_sai = await client.post("/api/movimentacoes", json=mov_saida, headers=auth_headers)
        assert res_sai.status_code == 201
        dados_sai = res_sai.json()
        assert dados_sai["saldo_anterior"] == 80.0
        assert dados_sai["saldo_posterior"] == 55.0

        rec_check2 = (await client.get(f"/api/recursos/{recurso_id}", headers=auth_headers)).json()
        assert rec_check2["quantidade_atual"] == 55.0

        # 3. SAÍDA INVÁLIDA: tentativa de retirar 60 unidades tendo apenas 55 em estoque
        mov_invalida = {
            "recurso_id": recurso_id,
            "tipo": "SAIDA",
            "quantidade": 60.0,
            "origem_destino": "Comunidade Centro",
            "motivo": "TEST_Entrega Excedente",
            "responsavel": "Operador Teste",
        }
        res_inv = await client.post("/api/movimentacoes", json=mov_invalida, headers=auth_headers)
        # Deve retornar 400 Bad Request
        assert res_inv.status_code == 400
        assert "Saldo insuficiente" in res_inv.json()["detail"]

        # Garante que o saldo permaneceu inalterado (55.0)
        rec_check3 = (await client.get(f"/api/recursos/{recurso_id}", headers=auth_headers)).json()
        assert rec_check3["quantidade_atual"] == 55.0

    finally:
        # Cleanup
        await client.delete(f"/api/recursos/{recurso_id}", headers=auth_headers)


@pytest.mark.asyncio
async def test_rf03_alertas_automaticos(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    """RF03: Testa classificação de estoque baixo/zerado e alertas de vencimento."""
    hoje = datetime.now(timezone.utc)

    # 1. Recurso com estoque baixo (quantidade <= estoque_minimo)
    rec_baixo = {
        "nome": "TEST_Sabonete Barra",
        "categoria": "Higiene",
        "unidade_medida": "UN",
        "quantidade_atual": 5.0,
        "estoque_minimo": 10.0,
        "lote": "LOTE-SAB",
        "data_validade": (hoje + timedelta(days=90)).isoformat(),
    }
    res_b = await client.post("/api/recursos", json=rec_baixo, headers=auth_headers)
    assert res_b.status_code == 201
    dados_b = res_b.json()
    assert dados_b["status_estoque"] == "BAIXO"

    # 2. Recurso vencendo em breve (em até 30 dias)
    rec_vencendo = {
        "nome": "TEST_Iogurte 200ml",
        "categoria": "Alimentos",
        "unidade_medida": "UN",
        "quantidade_atual": 20.0,
        "estoque_minimo": 5.0,
        "lote": "LOTE-IOG",
        "data_validade": (hoje + timedelta(days=10)).isoformat(),
    }
    res_v = await client.post("/api/recursos", json=rec_vencendo, headers=auth_headers)
    assert res_v.status_code == 201
    dados_v = res_v.json()
    assert dados_v["status_validade"] == "PROXIMO_VENCIMENTO"

    # 3. Recurso já vencido
    rec_vencido = {
        "nome": "TEST_Medicamento Vencido",
        "categoria": "Medicamentos",
        "unidade_medida": "CAIXA",
        "quantidade_atual": 2.0,
        "estoque_minimo": 5.0,
        "lote": "LOTE-MED-V",
        "data_validade": (hoje - timedelta(days=5)).isoformat(),
    }
    res_vcd = await client.post("/api/recursos", json=rec_vencido, headers=auth_headers)
    assert res_vcd.status_code == 201
    dados_vcd = res_vcd.json()
    assert dados_vcd["status_validade"] == "VENCIDO"

    # Limpeza
    await client.delete(f"/api/recursos/{dados_b['id']}", headers=auth_headers)
    await client.delete(f"/api/recursos/{dados_v['id']}", headers=auth_headers)
    await client.delete(f"/api/recursos/{dados_vcd['id']}", headers=auth_headers)


@pytest.mark.asyncio
async def test_rf04_relatorios_e_exportacao_csv(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    """RF04: Testa relatórios digitais, indicadores do dashboard e download de CSV."""
    # 1. Dashboard
    res_dash = await client.get("/api/relatorios/dashboard", headers=auth_headers)
    assert res_dash.status_code == 200
    dados_dash = res_dash.json()
    assert "total_recursos" in dados_dash
    assert "total_unidades_estoque" in dados_dash
    assert "total_alertas_ativos" in dados_dash

    # 2. Itens críticos
    res_crit = await client.get("/api/relatorios/itens-criticos", headers=auth_headers)
    assert res_crit.status_code == 200
    assert isinstance(res_crit.json(), list)

    # 3. Balanço
    res_balanco = await client.get("/api/relatorios/balanco", headers=auth_headers)
    assert res_balanco.status_code == 200
    dados_balanco = res_balanco.json()
    assert "entradas" in dados_balanco
    assert "saidas" in dados_balanco
    assert "saldo_liquido" in dados_balanco

    # 4. Exportação de CSV de Recursos
    res_csv_rec = await client.get("/api/relatorios/exportar/recursos-csv", headers=auth_headers)
    assert res_csv_rec.status_code == 200
    assert "text/csv" in res_csv_rec.headers["content-type"]
    assert "Nome" in res_csv_rec.text
    assert "Quantidade Atual" in res_csv_rec.text

    # 5. Exportação de CSV de Movimentações
    res_csv_mov = await client.get("/api/relatorios/exportar/movimentacoes-csv", headers=auth_headers)
    assert res_csv_mov.status_code == 200
    assert "text/csv" in res_csv_mov.headers["content-type"]
