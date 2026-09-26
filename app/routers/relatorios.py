"""Roteador para geração de relatórios operacionais, KPIs e exportação CSV com isolamento por usuário."""

from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter, Depends, Query, Response
from app.models.recurso import RecursoResponse
from app.models.usuario import UsuarioResponse
from app.services.estoque_service import EstoqueService
from app.dependencies import get_usuario_atual

router = APIRouter(prefix="/api/relatorios", tags=["Relatórios & Dashboard"])


@router.get(
    "/dashboard",
    response_model=dict[str, Any],
    summary="Resumo do Dashboard",
    description="Retorna indicadores-chave (KPIs), contagem de alertas ativos e últimas movimentações do usuário.",
)
async def obter_dashboard(
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
) -> dict[str, Any]:
    """Retorna consolidação estatística para os cartões e gráficos do painel."""
    return await EstoqueService.obter_resumo_dashboard(usuario_id=usuario_atual.id)


@router.get(
    "/itens-criticos",
    response_model=list[RecursoResponse],
    summary="Relatório de Itens Críticos",
    description="Lista insumos com estoque baixo/zerado ou data de validade vencida/próxima do vencimento do usuário.",
)
async def obter_itens_criticos(
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
) -> list[RecursoResponse]:
    """Retorna lista de recursos prioritários para reposição ou descarte."""
    return await EstoqueService.obter_itens_criticos(usuario_id=usuario_atual.id)


@router.get(
    "/balanco",
    response_model=dict[str, Any],
    summary="Balanço de Movimentações por Período",
    description="Retorna o consolidado de entradas, saídas e saldo líquido do usuário em um intervalo de datas.",
)
async def obter_balanco(
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
    data_inicio: datetime | None = Query(None, description="Data inicial do filtro"),
    data_fim: datetime | None = Query(None, description="Data final do filtro"),
) -> dict[str, Any]:
    """Retorna balanço analítico para prestação de contas de ONGs e planejamento financeiro."""
    return await EstoqueService.obter_balanco_movimentacoes(
        usuario_id=usuario_atual.id,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@router.get(
    "/exportar/recursos-csv",
    summary="Exportar Recursos em CSV",
    description="Gera e faz download de um arquivo CSV formatado com todos os recursos e seus status do usuário.",
)
async def exportar_recursos_csv(
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
) -> Response:
    """Download do CSV completo do estoque do usuário formatado para Excel."""
    conteudo_csv = await EstoqueService.exportar_csv_recursos(usuario_id=usuario_atual.id)
    nome_arquivo = f"relatorio_estoque_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=conteudo_csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )


@router.get(
    "/exportar/movimentacoes-csv",
    summary="Exportar Histórico de Movimentações em CSV",
    description="Gera e faz download do histórico auditável de entradas e saídas no formato CSV do usuário.",
)
async def exportar_movimentacoes_csv(
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
    data_inicio: datetime | None = Query(None, description="Data inicial do filtro"),
    data_fim: datetime | None = Query(None, description="Data final do filtro"),
) -> Response:
    """Download do CSV de histórico de movimentações do usuário formatado para Excel."""
    conteudo_csv = await EstoqueService.exportar_csv_movimentacoes(
        usuario_id=usuario_atual.id,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
    nome_arquivo = f"historico_movimentacoes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=conteudo_csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )
