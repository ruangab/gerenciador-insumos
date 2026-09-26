"""Modelos de dados para usuários e respostas de autenticação."""

from datetime import datetime, timezone
from typing import Annotated, Any
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field, BeforeValidator


def _normalizar_object_id(valor: Any) -> str:
    """Garante que o ObjectId do MongoDB seja lido e representado como string."""
    if isinstance(valor, ObjectId):
        return str(valor)
    if isinstance(valor, str) and ObjectId.is_valid(valor):
        return valor
    raise ValueError("Identificador informado não é um ObjectId válido do MongoDB.")


PyObjectIdStr = Annotated[str, BeforeValidator(_normalizar_object_id)]


class UsuarioCreate(BaseModel):
    """Dados enviados pelo cliente para criar uma conta nova."""

    nome: str = Field(..., min_length=2, max_length=100, description="Nome completo do usuário")
    email: EmailStr = Field(..., description="E-mail único — usado como login")
    senha: str = Field(..., min_length=6, max_length=128, description="Senha (mínimo 6 caracteres)")


class UsuarioResponse(BaseModel):
    """Representação pública de um usuário (nunca expõe a senha)."""

    id: PyObjectIdStr = Field(validation_alias="_id", description="Identificador único no MongoDB")
    nome: str
    email: str
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )


class TokenResponse(BaseModel):
    """Resposta retornada após login ou cadastro bem-sucedido."""

    access_token: str = Field(..., description="JWT Bearer token para autenticação")
    token_type: str = Field(default="bearer")
    nome: str = Field(..., description="Nome do usuário autenticado")
    email: str = Field(..., description="E-mail do usuário autenticado")
    usuario_id: str = Field(..., description="ID do usuário no MongoDB")
