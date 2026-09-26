"""Ponto de entrada da aplicação FastAPI e montagem das rotas e front-end."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import conectar_banco, fechar_banco, DatabaseManager
from app.routers import (
    auth_router,
    recursos_router,
    movimentacoes_router,
    relatorios_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia a inicialização e o encerramento gracioso de recursos assíncronos."""
    logger.info("Iniciando Sistema de Estoque (Parnamirim/RN)...")
    try:
        await conectar_banco()
    except Exception as erro:
        logger.error("Aviso: Falha ao conectar ao MongoDB na inicialização: %s", erro)
    yield
    logger.info("Fechando conexões com o banco de dados...")
    await fechar_banco()


app = FastAPI(
    title="Sistema de Gerenciamento de Estoques — Pequenos Negócios e ONGs",
    description=(
        "API REST para controle centralizado de recursos, fluxo de entradas/saídas, "
        "alertas de validade e prestação de contas. Desenvolvido com foco em impacto social "
        "para pequenos comerciantes e organizações comunitárias em Parnamirim/RN (ODS 9 e ODS 12)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Permite chamadas de clientes locais e ferramentas de teste
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Roteadores REST
app.include_router(auth_router)
app.include_router(recursos_router)
app.include_router(movimentacoes_router)
app.include_router(relatorios_router)

# Arquivos estáticos do front-end Vanilla
PASTA_RAIZ = Path(__file__).resolve().parent.parent
PASTA_ESTATICA = PASTA_RAIZ / "static"

if PASTA_ESTATICA.exists():
    app.mount("/static", StaticFiles(directory=str(PASTA_ESTATICA)), name="static")


@app.get("/api/health", tags=["Sistema"], summary="Status de saúde da aplicação")
async def checar_saude() -> dict[str, Any]:
    """Informa se a API e o banco de dados estão operacionais."""
    conectado = False
    try:
        if DatabaseManager.client:
            await DatabaseManager.client.admin.command("ping")
            conectado = True
    except Exception:
        conectado = False

    return {
        "status": "online" if conectado else "database_unavailable",
        "database_connected": conectado,
        "database_name": settings.DATABASE_NAME,
    }


@app.get("/", include_in_schema=False)
async def pagina_inicial():
    """Entrega a aplicação web Vanilla de página única na raiz."""
    index = PASTA_ESTATICA / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"mensagem": "Interface web não encontrada. Acesse /docs para explorar a API."}
