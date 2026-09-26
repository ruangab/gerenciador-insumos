"""Modelos de dados para recursos/produtos e cálculo dinâmico de alertas."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, BeforeValidator, computed_field

from app.config import settings


def _normalizar_object_id(valor: Any) -> str:
    """Garante que o ObjectId do MongoDB seja lido e representado como string."""
    if isinstance(valor, ObjectId):
        return str(valor)
    if isinstance(valor, str) and ObjectId.is_valid(valor):
        return valor
    raise ValueError("Identificador informado não é um ObjectId válido do MongoDB.")


PyObjectIdStr = Annotated[str, BeforeValidator(_normalizar_object_id)]


class UnidadeMedida(StrEnum):
    """Unidades de medida padronizadas para alimentos, insumos e medicamentos."""
    UN = "UN"
    KG = "KG"
    LITRO = "LITRO"
    CAIXA = "CAIXA"
    PACOTE = "PACOTE"


class StatusEstoque(StrEnum):
    """Classificação visual do nível de estoque."""
    NORMAL = "NORMAL"
    BAIXO = "BAIXO"
    ZERADO = "ZERADO"


class StatusValidade(StrEnum):
    """Classificação visual da proximidade do vencimento."""
    NORMAL = "NORMAL"
    PROXIMO_VENCIMENTO = "PROXIMO_VENCIMENTO"
    VENCIDO = "VENCIDO"


class RecursoBase(BaseModel):
    """Atributos fundamentais compartilhados por um produto ou insumo de estoque."""

    nome: str = Field(..., min_length=2, max_length=150, description="Nome do produto ou insumo")
    descricao: str | None = Field(default="", max_length=500, description="Observações úteis ou destinação comunitária")
    categoria: str = Field(..., min_length=2, max_length=100, description="Categoria (ex: Alimentos, Higiene, Medicamentos)")
    unidade_medida: UnidadeMedida = Field(default=UnidadeMedida.UN, description="Unidade de medida de estoque")
    quantidade_atual: float = Field(default=0.0, ge=0, description="Saldo atual disponível no inventário")
    estoque_minimo: float = Field(default=10.0, ge=0, description="Ponto de reposição ou alerta de estoque baixo")
    lote: str = Field(default="PADRAO", min_length=1, max_length=80, description="Código identificador do lote")
    data_validade: datetime = Field(..., description="Data de validade do insumo")
    usuario_id: str | None = Field(default=None, description="ID do usuário dono deste recurso")


class RecursoCreate(RecursoBase):
    """Payload enviado pelo usuário ao cadastrar um novo item."""
    pass


class RecursoUpdate(BaseModel):
    """Campos editáveis de um recurso (a quantidade deve ser alterada via movimentações auditadas)."""

    nome: str | None = Field(None, min_length=2, max_length=150)
    descricao: str | None = Field(None, max_length=500)
    categoria: str | None = Field(None, min_length=2, max_length=100)
    unidade_medida: UnidadeMedida | None = None
    quantidade_atual: float | None = Field(None, ge=0)
    estoque_minimo: float | None = Field(None, ge=0)
    lote: str | None = Field(None, min_length=1, max_length=80)
    data_validade: datetime | None = None


class RecursoResponse(RecursoBase):
    """Representação serializada de um recurso entregue para a API e o front-end."""

    # validation_alias="_id" lê o identificador do MongoDB e o expõe como 'id' no JSON da API
    id: PyObjectIdStr = Field(validation_alias="_id", description="Identificador único no MongoDB")
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    atualizado_em: datetime | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    @computed_field
    @property
    def status_estoque(self) -> StatusEstoque:
        """Indica se o item está zerado, baixo (<= mínimo) ou em nível saudável."""
        if self.quantidade_atual <= 0:
            return StatusEstoque.ZERADO
        if self.quantidade_atual <= self.estoque_minimo:
            return StatusEstoque.BAIXO
        return StatusEstoque.NORMAL

    @computed_field
    @property
    def dias_para_vencer(self) -> int:
        """Quantidade de dias restantes até o vencimento (negativo indica vencido)."""
        hoje = datetime.now(timezone.utc).date()
        validade = self.data_validade.date() if isinstance(self.data_validade, datetime) else self.data_validade
        return (validade - hoje).days

    @computed_field
    @property
    def status_validade(self) -> StatusValidade:
        """Alerta de validade: vencido, próximo do vencimento (<= dias configurados) ou normal."""
        dias = self.dias_para_vencer
        if dias < 0:
            return StatusValidade.VENCIDO
        if dias <= settings.ALERTA_DIAS_VALIDADE:
            return StatusValidade.PROXIMO_VENCIMENTO
        return StatusValidade.NORMAL
