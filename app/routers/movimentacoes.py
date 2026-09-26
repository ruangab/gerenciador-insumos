"""Roteador para gerenciamento e auditoria de Movimentações de Estoque com isolamento por usuário."""

from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from app.models.movimentacao import (
    TipoMovimentacao,
    MovimentacaoCreate,
    MovimentacaoResponse,
)
from app.models.usuario import UsuarioResponse
from app.services.estoque_service import EstoqueService
from app.dependencies import get_usuario_atual

router = APIRouter(prefix="/api/movimentacoes", tags=["Movimentações"])


@router.post(
    "",
    response_model=MovimentacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar movimentação de estoque",
    description=(
        "Registra uma Entrada ou Saída com atualização atômica do saldo para o usuário autenticado. "
        "Impede preventivamente que saídas resultem em estoque negativo."
    ),
)
async def registrar_movimentacao(
    dados: MovimentacaoCreate,
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
) -> MovimentacaoResponse:
    """Registra movimentação no estoque do usuário."""
    return await EstoqueService.registrar_movimentacao(dados, usuario_id=usuario_atual.id)


@router.get(
    "",
    response_model=list[MovimentacaoResponse],
    summary="Listar histórico de movimentações",
    description="Retorna o histórico auditável de entradas e saídas do usuário com suporte a filtros.",
)
async def listar_movimentacoes(
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
    recurso_id: str | None = Query(None, description="Filtrar movimentações de um recurso específico"),
    tipo: TipoMovimentacao | None = Query(None, description="Filtrar por tipo (ENTRADA ou SAIDA)"),
    data_inicio: datetime | None = Query(None, description="Data inicial do período (ISO format)"),
    data_fim: datetime | None = Query(None, description="Data final do período (ISO format)"),
    skip: int = Query(0, ge=0, description="Pular registros"),
    limit: int = Query(100, ge=1, le=500, description="Limite por página"),
) -> list[MovimentacaoResponse]:
    """Lista movimentações auditáveis de estoque do usuário."""
    return await EstoqueService.listar_movimentacoes(
        usuario_id=usuario_atual.id,
        recurso_id=recurso_id,
        tipo=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        skip=skip,
        limit=limit,
    )
