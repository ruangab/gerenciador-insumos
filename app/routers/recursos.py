"""Roteador para gerenciamento de Recursos e Produtos (CRUD) com isolamento por usuário."""

from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from app.models.recurso import (
    RecursoCreate,
    RecursoUpdate,
    RecursoResponse,
)
from app.models.usuario import UsuarioResponse
from app.services.estoque_service import EstoqueService
from app.dependencies import get_usuario_atual

router = APIRouter(prefix="/api/recursos", tags=["Recursos"])


@router.post(
    "",
    response_model=RecursoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar novo recurso",
    description="Registra um novo item/insumo no estoque com lote e data de validade para o usuário autenticado.",
)
async def criar_recurso(
    dados: RecursoCreate,
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
) -> RecursoResponse:
    """Cadastra um novo produto/recurso no sistema associado ao usuário."""
    return await EstoqueService.criar_recurso(dados, usuario_id=usuario_atual.id)


@router.get(
    "",
    response_model=list[RecursoResponse],
    summary="Listar recursos cadastrados",
    description="Retorna recursos do usuário com filtros opcionais por busca textual, categoria e status de alerta.",
)
async def listar_recursos(
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
    busca: str | None = Query(None, description="Busca por nome, descrição ou lote"),
    categoria: str | None = Query(None, description="Filtrar por categoria"),
    alerta_estoque: str | None = Query(None, description="Filtrar por status de estoque (NORMAL, BAIXO, ZERADO)"),
    alerta_validade: str | None = Query(None, description="Filtrar por validade (NORMAL, PROXIMO_VENCIMENTO, VENCIDO)"),
    skip: int = Query(0, ge=0, description="Registros a pular para paginação"),
    limit: int = Query(100, ge=1, le=500, description="Limite de registros por página"),
) -> list[RecursoResponse]:
    """Lista todos os recursos do usuário respeitando os filtros informados."""
    return await EstoqueService.listar_recursos(
        usuario_id=usuario_atual.id,
        busca=busca,
        categoria=categoria,
        alerta_estoque=alerta_estoque,
        alerta_validade=alerta_validade,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{recurso_id}",
    response_model=RecursoResponse,
    summary="Obter detalhes de um recurso",
    description="Retorna dados completos de um recurso específico pelo seu ID (somente se pertencer ao usuário).",
)
async def obter_recurso(
    recurso_id: str,
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
) -> RecursoResponse:
    """Busca um recurso por ID pertencente ao usuário."""
    return await EstoqueService.obter_recurso_por_id(recurso_id, usuario_id=usuario_atual.id)


@router.put(
    "/{recurso_id}",
    response_model=RecursoResponse,
    summary="Atualizar dados de um recurso",
    description="Atualiza informações cadastrais como nome, categoria, estoque mínimo, etc.",
)
async def atualizar_recurso(
    recurso_id: str,
    dados: RecursoUpdate,
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
) -> RecursoResponse:
    """Atualiza dados cadastrais de um recurso existente do usuário."""
    return await EstoqueService.atualizar_recurso(recurso_id, dados, usuario_id=usuario_atual.id)


@router.delete(
    "/{recurso_id}",
    status_code=status.HTTP_200_OK,
    summary="Excluir recurso",
    description="Remove o recurso especificado do banco de dados do usuário.",
)
async def excluir_recurso(
    recurso_id: str,
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
) -> dict[str, str]:
    """Remove um recurso do estoque do usuário."""
    await EstoqueService.remover_recurso(recurso_id, usuario_id=usuario_atual.id)
    return {"mensagem": f"Recurso '{recurso_id}' removido com sucesso."}
