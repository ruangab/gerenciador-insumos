"""Serviço de autenticação, hashing de senhas via bcrypt direto e geração/validação de tokens JWT."""

from datetime import datetime, timezone, timedelta
from typing import Any
import bcrypt
from bson import ObjectId
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config import settings
from app.database import get_usuarios_collection
from app.models.usuario import UsuarioCreate, UsuarioResponse, TokenResponse


def gerar_hash_senha(senha: str) -> str:
    """Gera o hash seguro bcrypt para a senha (truncada com segurança em 72 bytes)."""
    senha_bytes = senha.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha_bytes, salt).decode("utf-8")


def verificar_senha(senha_pura: str, senha_hash: str) -> bool:
    """Valida a senha pura contra o hash armazenado."""
    try:
        senha_bytes = senha_pura.encode("utf-8")[:72]
        hash_bytes = senha_hash.encode("utf-8")
        return bcrypt.checkpw(senha_bytes, hash_bytes)
    except Exception:
        return False


def criar_access_token(dados: dict[str, Any], expira_em: timedelta | None = None) -> str:
    """Gera um token JWT com tempo de expiração definido."""
    payload = dados.copy()
    agora = datetime.now(timezone.utc)
    if expira_em:
        expiracao = agora + expira_em
    else:
        expiracao = agora + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    payload.update({"exp": expiracao, "iat": agora})
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decodificar_token(token: str) -> dict[str, Any]:
    """Valida e decodifica um token JWT, retornando o payload."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthService:
    """Regras de negócio para cadastro, login e consulta de usuários."""

    @classmethod
    async def registrar(cls, dados: UsuarioCreate) -> TokenResponse:
        """Cadastra um novo usuário no banco com senha criptografada e retorna o token de acesso."""
        col = get_usuarios_collection()
        email_normalizado = dados.email.lower().strip()

        # Verifica se já existe um usuário cadastrado com este e-mail
        existente = await col.find_one({"email": email_normalizado})
        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe uma conta cadastrada com o e-mail '{dados.email}'.",
            )

        agora = datetime.now(timezone.utc)
        doc = {
            "nome": dados.nome.strip(),
            "email": email_normalizado,
            "senha_hash": gerar_hash_senha(dados.senha),
            "criado_em": agora,
        }

        resultado = await col.insert_one(doc)
        usuario_id = str(resultado.inserted_id)

        token = criar_access_token({"sub": usuario_id, "email": email_normalizado})

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            nome=doc["nome"],
            email=doc["email"],
            usuario_id=usuario_id,
        )

    @classmethod
    async def autenticar(cls, email: str, senha: str) -> TokenResponse:
        """Autentica o usuário com e-mail e senha e retorna um token JWT."""
        col = get_usuarios_collection()
        email_normalizado = email.lower().strip()

        usuario = await col.find_one({"email": email_normalizado})
        if not usuario or not verificar_senha(senha, usuario.get("senha_hash", "")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="E-mail ou senha incorretos.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        usuario_id = str(usuario["_id"])
        token = criar_access_token({"sub": usuario_id, "email": email_normalizado})

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            nome=usuario.get("nome", "Usuário"),
            email=usuario.get("email", email_normalizado),
            usuario_id=usuario_id,
        )

    @classmethod
    async def obter_usuario_por_id(cls, usuario_id: str) -> UsuarioResponse:
        """Busca os dados do perfil do usuário a partir do seu ID."""
        if not ObjectId.is_valid(usuario_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Identificador de usuário inválido.",
            )

        col = get_usuarios_collection()
        doc = await col.find_one({"_id": ObjectId(usuario_id)})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado.",
            )

        return UsuarioResponse.model_validate(doc)
