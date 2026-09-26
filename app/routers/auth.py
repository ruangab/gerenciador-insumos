"""Roteador para cadastro, login e verificação de perfil de usuários."""

from typing import Annotated
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.models.usuario import UsuarioCreate, UsuarioResponse, TokenResponse
from app.services.auth_service import AuthService
from app.dependencies import get_usuario_atual

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])


class LoginPayload(BaseModel):
    """Corpo de requisição para login via JSON."""
    email: EmailStr
    senha: str


@router.post(
    "/registrar",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar novo usuário",
    description="Cria uma nova conta de usuário no sistema e retorna o token de acesso.",
)
async def registrar_usuario(dados: UsuarioCreate) -> TokenResponse:
    """Registra uma nova conta com e-mail único e senha criptografada."""
    return await AuthService.registrar(dados)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Autenticar usuário (JSON)",
    description="Realiza login com e-mail e senha, retornando o token JWT.",
)
async def login_usuario(dados: LoginPayload) -> TokenResponse:
    """Valida credenciais e gera token JWT."""
    return await AuthService.autenticar(email=dados.email, senha=dados.senha)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Obter token OAuth2 (Swagger UI)",
    description="Endpoint compatível com OAuth2PasswordRequestForm para autenticação direta no Swagger (/docs).",
    include_in_schema=False,
)
async def login_oauth2(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
    """Permite autorização no botão 'Authorize' da documentação Swagger."""
    return await AuthService.autenticar(email=form_data.username, senha=form_data.password)


@router.get(
    "/perfil",
    response_model=UsuarioResponse,
    summary="Consultar perfil do usuário autenticado",
    description="Retorna os dados cadastrais do usuário associado ao token JWT enviado no cabeçalho.",
)
async def obter_perfil(
    usuario_atual: Annotated[UsuarioResponse, Depends(get_usuario_atual)],
) -> UsuarioResponse:
    """Retorna os dados do usuário autenticado."""
    return usuario_atual
