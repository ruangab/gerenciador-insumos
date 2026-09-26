"""Módulo de rotas da API REST."""

from app.routers.auth import router as auth_router
from app.routers.recursos import router as recursos_router
from app.routers.movimentacoes import router as movimentacoes_router
from app.routers.relatorios import router as relatorios_router

__all__ = [
    "auth_router",
    "recursos_router",
    "movimentacoes_router",
    "relatorios_router",
]
