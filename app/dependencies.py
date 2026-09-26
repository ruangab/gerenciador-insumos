"""Dependências de injeção do FastAPI para autenticação e controle de acesso."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.models.usuario import UsuarioResponse
from app.services.auth_service import AuthService, decodificar_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)


async def get_usuario_atual(token: str = Depends(oauth2_scheme)) -> UsuarioResponse:
    """Extrai e valida o token JWT do header Authorization e retorna o usuário logado."""
    payload = decodificar_token(token)
    usuario_id = payload.get("sub")
    if not usuario_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais de autenticação inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    usuario = await AuthService.obter_usuario_por_id(usuario_id)
    return usuario
