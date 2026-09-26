"""Conexão e ciclo de vida assíncrono do MongoDB via Motor."""

import logging
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from pymongo import ASCENDING, DESCENDING

from app.config import settings

logger = logging.getLogger(__name__)

# Instâncias globais gerenciadas pelo ciclo de vida da aplicação
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def conectar_banco() -> None:
    """Inicializa o cliente do MongoDB, verifica conectividade e garante os índices."""
    global _client, _db
    try:
        logger.info("Conectando ao MongoDB em %s...", settings.MONGODB_URL)
        _client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000,
        )
        # O comando ping força uma checagem ativa com o servidor
        await _client.admin.command("ping")
        _db = _client[settings.DATABASE_NAME]
        logger.info("Conexão estabelecida com sucesso no banco '%s'.", settings.DATABASE_NAME)
        await criar_indices()
    except Exception as erro:
        logger.error("Falha ao inicializar banco de dados: %s", erro)
        raise


async def fechar_banco() -> None:
    """Fecha a conexão com o MongoDB de forma graciosa."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("Conexão com MongoDB finalizada.")


async def criar_indices() -> None:
    """Cria os índices mais frequentes para acelerar filtros, ordenações e relatórios."""
    if _db is None:
        return

    try:
        # Otimiza buscas por nome, categoria, data de validade e alertas de estoque
        await _db["recursos"].create_index([("nome", ASCENDING)])
        await _db["recursos"].create_index([("categoria", ASCENDING)])
        await _db["recursos"].create_index([("data_validade", ASCENDING)])
        await _db["recursos"].create_index([("quantidade_atual", ASCENDING)])
        await _db["recursos"].create_index([("usuario_id", ASCENDING)])

        # Otimiza auditoria de movimentações por recurso, data decrescente e tipo
        await _db["movimentacoes"].create_index([("recurso_id", ASCENDING)])
        await _db["movimentacoes"].create_index([("data_movimentacao", DESCENDING)])
        await _db["movimentacoes"].create_index([("tipo", ASCENDING)])
        await _db["movimentacoes"].create_index([("usuario_id", ASCENDING)])

        # Garante que cada e-mail seja único no sistema de usuários
        await _db["usuarios"].create_index([("email", ASCENDING)], unique=True)
        logger.info("Índices do banco de dados prontos.")
    except Exception as aviso:
        logger.warning("Não foi possível criar índices automáticos: %s", aviso)


def get_database() -> AsyncIOMotorDatabase:
    """Retorna a instância ativa do banco de dados para injeção ou uso direto."""
    if _db is None:
        raise RuntimeError("Banco de dados ainda não foi conectado. Verifique o ciclo de vida do app.")
    return _db


def get_recursos_collection() -> AsyncIOMotorCollection:
    """Atalho para acessar a coleção 'recursos'."""
    return get_database()["recursos"]


def get_movimentacoes_collection() -> AsyncIOMotorCollection:
    """Atalho para acessar a coleção 'movimentacoes'."""
    return get_database()["movimentacoes"]


def get_usuarios_collection() -> AsyncIOMotorCollection:
    """Atalho para acessar a coleção 'usuarios'."""
    return get_database()["usuarios"]


class DatabaseManager:
    """Fachada para compatibilidade de chamadas legadas de ciclo de vida."""

    @classmethod
    async def connect(cls) -> None:
        await conectar_banco()

    @classmethod
    async def close(cls) -> None:
        await fechar_banco()

    @classmethod
    async def init_indexes(cls) -> None:
        await criar_indices()

    @classmethod
    @property
    def client(cls) -> AsyncIOMotorClient | None:
        return _client

    @classmethod
    @property
    def db(cls) -> AsyncIOMotorDatabase | None:
        return _db
