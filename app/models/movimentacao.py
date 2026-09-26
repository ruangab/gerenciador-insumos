"""Modelos de dados para movimentações auditáveis de estoque (entradas e saídas)."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, BeforeValidator


def _normalizar_object_id(valor: Any) -> str:
    """Garante que o ObjectId do MongoDB seja lido e representado como string."""
    if isinstance(valor, ObjectId):
        return str(valor)
    if isinstance(valor, str) and ObjectId.is_valid(valor):
        return valor
    raise ValueError("Identificador informado não é um ObjectId válido do MongoDB.")


PyObjectIdStr = Annotated[str, BeforeValidator(_normalizar_object_id)]


class TipoMovimentacao(StrEnum):
    """Tipos permitidos de movimentação no estoque."""
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"


class MovimentacaoBase(BaseModel):
    """Informações essenciais de auditoria de qualquer movimentação de recursos."""

    recurso_id: str = Field(..., description="ID do recurso que foi movimentado")
    tipo: TipoMovimentacao = Field(..., description="Operação: ENTRADA (soma) ou SAIDA (subtrai)")
    quantidade: float = Field(..., gt=0, description="Quantidade movimentada (estritamente maior que zero)")
    origem_destino: str = Field(..., min_length=2, max_length=150, description="Origem da entrada ou destino da saída")
    motivo: str = Field(..., min_length=2, max_length=200, description="Justificativa operacional (ex: Doação, Venda, Avaria)")
    responsavel: str = Field(..., min_length=2, max_length=100, description="Nome do operador que registrou a movimentação")
    usuario_id: str | None = Field(default=None, description="ID do usuário que registrou esta movimentação")


class MovimentacaoCreate(MovimentacaoBase):
    """Dados enviados pelo usuário para registrar uma nova movimentação."""

    data_movimentacao: datetime | None = Field(
        default=None,
        description="Data da ocorrência (se omitida, assume o instante atual)",
    )


class MovimentacaoResponse(MovimentacaoBase):
    """Registro completo de auditoria com saldos calculados antes e após a operação."""

    id: PyObjectIdStr = Field(validation_alias="_id", description="Identificador único da movimentação")
    recurso_nome: str | None = Field(default=None, description="Nome do recurso no instante da operação")
    data_movimentacao: datetime = Field(..., description="Data e hora do registro")
    saldo_anterior: float | None = Field(default=None, description="Saldo em estoque antes da movimentação")
    saldo_posterior: float | None = Field(default=None, description="Saldo em estoque após a movimentação")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )
