"""Regras de negócio, operações de estoque e geração de relatórios operacionais com isolamento por usuário."""

import csv
import io
import re
from datetime import datetime, timezone, timedelta
from typing import Any
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ReturnDocument, DESCENDING, ASCENDING

from app.config import settings
from app.database import get_recursos_collection, get_movimentacoes_collection
from app.models.recurso import (
    RecursoCreate,
    RecursoUpdate,
    RecursoResponse,
    StatusEstoque,
    StatusValidade,
)
from app.models.movimentacao import (
    TipoMovimentacao,
    MovimentacaoCreate,
    MovimentacaoResponse,
)


def _validar_object_id(id_str: str) -> ObjectId:
    """Converte uma string para ObjectId do MongoDB, lançando 400 amigável em caso de erro."""
    if not ObjectId.is_valid(id_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O identificador '{id_str}' não possui o formato esperado de 24 caracteres hexadecimais.",
        )
    return ObjectId(id_str)


class EstoqueService:
    """Serviço que orquestra as regras de negócio de recursos, estoque e auditoria com isolamento por usuário."""

    # -------------------------------------------------------------------------
    # RF01 - Gerenciamento de Recursos (CRUD) com isolamento por usuario_id
    # -------------------------------------------------------------------------

    @classmethod
    async def criar_recurso(cls, dados: RecursoCreate, usuario_id: str) -> RecursoResponse:
        """Cadastra um novo produto ou insumo associado ao usuário logado."""
        col = get_recursos_collection()
        agora = datetime.now(timezone.utc)

        doc = dados.model_dump()
        doc["usuario_id"] = usuario_id
        doc["criado_em"] = agora
        doc["atualizado_em"] = agora

        resultado = await col.insert_one(doc)
        doc["_id"] = resultado.inserted_id

        return RecursoResponse.model_validate(doc)

    @classmethod
    async def listar_recursos(
        cls,
        usuario_id: str,
        busca: str | None = None,
        categoria: str | None = None,
        alerta_estoque: str | None = None,
        alerta_validade: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[RecursoResponse]:
        """Lista os recursos do catálogo do usuário aplicando busca textual e filtros de alerta."""
        col = get_recursos_collection()
        filtro: dict[str, Any] = {"usuario_id": usuario_id}

        if busca and busca.strip():
            termo = re.escape(busca.strip())
            filtro["$and"] = [
                {"usuario_id": usuario_id},
                {
                    "$or": [
                        {"nome": {"$regex": termo, "$options": "i"}},
                        {"descricao": {"$regex": termo, "$options": "i"}},
                        {"lote": {"$regex": termo, "$options": "i"}},
                    ]
                }
            ]
            del filtro["usuario_id"]

        if categoria and categoria.strip():
            filtro["categoria"] = categoria.strip()

        cursor = col.find(filtro).sort("nome", ASCENDING).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        itens = [RecursoResponse.model_validate(d) for d in docs]

        # Filtros baseados nas propriedades computadas pelo modelo Pydantic
        if alerta_estoque:
            alvo_estoque = alerta_estoque.upper()
            itens = [item for item in itens if item.status_estoque.value == alvo_estoque]

        if alerta_validade:
            alvo_validade = alerta_validade.upper()
            itens = [item for item in itens if item.status_validade.value == alvo_validade]

        return itens

    @classmethod
    async def obter_recurso_por_id(cls, recurso_id: str, usuario_id: str) -> RecursoResponse:
        """Busca um recurso por ID pertencente ao usuário no MongoDB."""
        obj_id = _validar_object_id(recurso_id)
        col = get_recursos_collection()
        doc = await col.find_one({"_id": obj_id, "usuario_id": usuario_id})

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recurso com ID '{recurso_id}' não foi encontrado no seu estoque.",
            )
        return RecursoResponse.model_validate(doc)

    @classmethod
    async def atualizar_recurso(
        cls,
        recurso_id: str,
        dados: RecursoUpdate,
        usuario_id: str,
    ) -> RecursoResponse:
        """Atualiza metadados do recurso pertencente ao usuário."""
        obj_id = _validar_object_id(recurso_id)
        col = get_recursos_collection()

        campos_atualizar = dados.model_dump(exclude_unset=True)
        if not campos_atualizar:
            return await cls.obter_recurso_por_id(recurso_id, usuario_id=usuario_id)

        campos_atualizar["atualizado_em"] = datetime.now(timezone.utc)

        doc_atualizado = await col.find_one_and_update(
            {"_id": obj_id, "usuario_id": usuario_id},
            {"$set": campos_atualizar},
            return_document=ReturnDocument.AFTER,
        )

        if not doc_atualizado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recurso '{recurso_id}' não encontrado para atualização no seu perfil.",
            )

        return RecursoResponse.model_validate(doc_atualizado)

    @classmethod
    async def remover_recurso(cls, recurso_id: str, usuario_id: str) -> bool:
        """Remove o cadastro de um recurso pertencente ao usuário."""
        obj_id = _validar_object_id(recurso_id)
        col = get_recursos_collection()
        resultado = await col.delete_one({"_id": obj_id, "usuario_id": usuario_id})

        if resultado.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recurso '{recurso_id}' não foi localizado no seu estoque para exclusão.",
            )
        return True

    # -------------------------------------------------------------------------
    # RF02 - Registro de Fluxo e Movimentações com usuario_id
    # -------------------------------------------------------------------------

    @classmethod
    async def registrar_movimentacao(
        cls,
        dados: MovimentacaoCreate,
        usuario_id: str,
    ) -> MovimentacaoResponse:
        """
        Registra uma movimentação (entrada ou saída) de forma atômica e auditada para o usuário logado.
        Garante preventivamente que uma saída nunca resulte em saldo negativo.
        """
        obj_id = _validar_object_id(dados.recurso_id)
        recursos_col = get_recursos_collection()
        movimentacoes_col = get_movimentacoes_collection()

        # 1. Localizar o recurso do usuário e verificar o saldo atual
        recurso = await recursos_col.find_one({"_id": obj_id, "usuario_id": usuario_id})
        if not recurso:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Não é possível movimentar: recurso '{dados.recurso_id}' não existe no seu estoque.",
            )

        saldo_anterior = float(recurso.get("quantidade_atual", 0.0))
        unidade = recurso.get("unidade_medida", "UN")
        agora = datetime.now(timezone.utc)
        data_mov = dados.data_movimentacao or agora

        # 2. Processar a alteração de saldo
        if dados.tipo == TipoMovimentacao.SAIDA:
            # Validação preventiva contra saldo negativo
            if dados.quantidade > saldo_anterior:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Saldo insuficiente para saída de '{recurso.get('nome')}'. "
                        f"Disponível: {saldo_anterior:.2f} {unidade}, "
                        f"Solicitado: {dados.quantidade:.2f} {unidade}."
                    ),
                )

            # Atualização atômica condicional: só deduz se quantidade_atual >= saída
            doc_atualizado = await recursos_col.find_one_and_update(
                {
                    "_id": obj_id,
                    "usuario_id": usuario_id,
                    "quantidade_atual": {"$gte": dados.quantidade},
                },
                {
                    "$inc": {"quantidade_atual": -dados.quantidade},
                    "$set": {"atualizado_em": agora},
                },
                return_document=ReturnDocument.AFTER,
            )

            if not doc_atualizado:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Concorrência detectada: o saldo foi alterado por outra operação antes da conclusão.",
                )

            saldo_posterior = float(doc_atualizado["quantidade_atual"])

        else:  # ENTRADA
            doc_atualizado = await recursos_col.find_one_and_update(
                {"_id": obj_id, "usuario_id": usuario_id},
                {
                    "$inc": {"quantidade_atual": dados.quantidade},
                    "$set": {"atualizado_em": agora},
                },
                return_document=ReturnDocument.AFTER,
            )

            if not doc_atualizado:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Erro inesperado ao creditar saldo no banco de dados.",
                )

            saldo_posterior = float(doc_atualizado["quantidade_atual"])

        # 3. Gravar histórico auditável vinculado ao usuário
        registro_auditoria = {
            "recurso_id": str(obj_id),
            "recurso_nome": recurso.get("nome"),
            "tipo": dados.tipo.value,
            "quantidade": dados.quantidade,
            "origem_destino": dados.origem_destino,
            "motivo": dados.motivo,
            "data_movimentacao": data_mov,
            "responsavel": dados.responsavel,
            "saldo_anterior": saldo_anterior,
            "saldo_posterior": saldo_posterior,
            "usuario_id": usuario_id,
        }

        resultado = await movimentacoes_col.insert_one(registro_auditoria)
        registro_auditoria["_id"] = resultado.inserted_id

        return MovimentacaoResponse.model_validate(registro_auditoria)

    @classmethod
    async def listar_movimentacoes(
        cls,
        usuario_id: str,
        recurso_id: str | None = None,
        tipo: TipoMovimentacao | None = None,
        data_inicio: datetime | None = None,
        data_fim: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[MovimentacaoResponse]:
        """Consulta o extrato histórico de entradas e saídas do usuário."""
        col = get_movimentacoes_collection()
        filtro: dict[str, Any] = {"usuario_id": usuario_id}

        if recurso_id and recurso_id.strip():
            filtro["recurso_id"] = recurso_id.strip()

        if tipo:
            filtro["tipo"] = tipo.value

        if data_inicio or data_fim:
            data_filtro: dict[str, Any] = {}
            if data_inicio:
                data_filtro["$gte"] = data_inicio
            if data_fim:
                data_filtro["$lte"] = data_fim
            filtro["data_movimentacao"] = data_filtro

        cursor = col.find(filtro).sort("data_movimentacao", DESCENDING).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        return [MovimentacaoResponse.model_validate(d) for d in docs]

    # -------------------------------------------------------------------------
    # RF03 & RF04 - Alertas Automáticos, Dashboard e Relatórios por usuário
    # -------------------------------------------------------------------------

    @classmethod
    async def obter_resumo_dashboard(cls, usuario_id: str) -> dict[str, Any]:
        """Consolida as métricas principais e alertas prioritários para o usuário logado."""
        recursos_col = get_recursos_collection()
        movimentacoes_col = get_movimentacoes_collection()

        hoje = datetime.now(timezone.utc)
        limite_proximo_vencimento = hoje + timedelta(days=settings.ALERTA_DIAS_VALIDADE)

        # 1. Carregar inventário do usuário para consolidação de status
        recursos_docs = await recursos_col.find({"usuario_id": usuario_id}).to_list(length=None)

        total_recursos = len(recursos_docs)
        total_unidades = sum(float(r.get("quantidade_atual", 0.0)) for r in recursos_docs)
        categorias = sorted({r["categoria"] for r in recursos_docs if r.get("categoria")})

        itens_estoque_baixo = 0
        itens_vencidos = 0
        itens_proximo_vencimento = 0

        for r in recursos_docs:
            qtd = float(r.get("quantidade_atual", 0.0))
            minimo = float(r.get("estoque_minimo", 0.0))
            if qtd <= minimo:
                itens_estoque_baixo += 1

            val = r.get("data_validade")
            if val:
                val_dt = val if (isinstance(val, datetime) and val.tzinfo) else (
                    val.replace(tzinfo=timezone.utc) if isinstance(val, datetime)
                    else datetime.combine(val, datetime.min.time(), tzinfo=timezone.utc)
                )

                if val_dt < hoje:
                    itens_vencidos += 1
                elif val_dt <= limite_proximo_vencimento:
                    itens_proximo_vencimento += 1

        # 2. Fluxo dos últimos 30 dias do usuário
        trinta_dias_atras = hoje - timedelta(days=30)
        pipeline_fluxo = [
            {"$match": {"usuario_id": usuario_id, "data_movimentacao": {"$gte": trinta_dias_atras}}},
            {"$group": {
                "_id": "$tipo",
                "total_qtd": {"$sum": "$quantidade"},
            }}
        ]
        fluxo_docs = await movimentacoes_col.aggregate(pipeline_fluxo).to_list(length=None)

        entradas_30d = next((f["total_qtd"] for f in fluxo_docs if f["_id"] == "ENTRADA"), 0.0)
        saidas_30d = next((f["total_qtd"] for f in fluxo_docs if f["_id"] == "SAIDA"), 0.0)
        total_movimentacoes = await movimentacoes_col.count_documents({"usuario_id": usuario_id})

        # 3. Amostra recente de movimentações do usuário
        ultimas_cursor = movimentacoes_col.find({"usuario_id": usuario_id}).sort("data_movimentacao", DESCENDING).limit(6)
        ultimas_docs = await ultimas_cursor.to_list(length=6)
        ultimas_movimentacoes = [
            MovimentacaoResponse.model_validate(d).model_dump() for d in ultimas_docs
        ]

        return {
            "total_recursos": total_recursos,
            "total_unidades_estoque": round(total_unidades, 2),
            "itens_estoque_baixo": itens_estoque_baixo,
            "itens_vencidos": itens_vencidos,
            "itens_proximo_vencimento": itens_proximo_vencimento,
            "total_alertas_ativos": itens_estoque_baixo + itens_vencidos + itens_proximo_vencimento,
            "total_movimentacoes": total_movimentacoes,
            "total_entradas_30d": round(entradas_30d, 2),
            "total_saidas_30d": round(saidas_30d, 2),
            "categorias_disponiveis": categorias,
            "ultimas_movimentacoes": ultimas_movimentacoes,
            "timestamp": hoje.isoformat(),
        }

    @classmethod
    async def obter_itens_criticos(cls, usuario_id: str) -> list[RecursoResponse]:
        """Filtra itens do usuário que necessitam de intervenção urgente."""
        recursos = await cls.listar_recursos(usuario_id=usuario_id, limit=1000)

        criticos = [
            r for r in recursos
            if r.status_estoque != StatusEstoque.NORMAL or r.status_validade != StatusValidade.NORMAL
        ]

        # Ordenação humana: prioriza vencidos, depois vencendo, depois estoque crítico
        def ordem_urgencia(item: RecursoResponse):
            peso_validade = {
                StatusValidade.VENCIDO: 0,
                StatusValidade.PROXIMO_VENCIMENTO: 1,
                StatusValidade.NORMAL: 2,
            }.get(item.status_validade, 2)

            peso_estoque = {
                StatusEstoque.ZERADO: 0,
                StatusEstoque.BAIXO: 1,
                StatusEstoque.NORMAL: 2,
            }.get(item.status_estoque, 2)

            return (peso_validade, peso_estoque, item.quantidade_atual)

        criticos.sort(key=ordem_urgencia)
        return criticos

    @classmethod
    async def obter_balanco_movimentacoes(
        cls,
        usuario_id: str,
        data_inicio: datetime | None = None,
        data_fim: datetime | None = None,
    ) -> dict[str, Any]:
        """Gera o balanço consolidado de entradas e saídas do usuário logado."""
        movimentacoes_col = get_movimentacoes_collection()
        filtro: dict[str, Any] = {"usuario_id": usuario_id}

        if data_inicio or data_fim:
            data_filtro: dict[str, Any] = {}
            if data_inicio:
                data_filtro["$gte"] = data_inicio
            if data_fim:
                data_filtro["$lte"] = data_fim
            filtro["data_movimentacao"] = data_filtro

        pipeline = [
            {"$match": filtro},
            {"$group": {
                "_id": "$tipo",
                "quantidade_total": {"$sum": "$quantidade"},
                "total_registros": {"$sum": 1},
            }}
        ]
        totais = await movimentacoes_col.aggregate(pipeline).to_list(length=None)

        entradas = {"quantidade": 0.0, "registros": 0}
        saidas = {"quantidade": 0.0, "registros": 0}

        for item in totais:
            dados_grupo = {
                "quantidade": round(float(item["quantidade_total"]), 2),
                "registros": int(item["total_registros"]),
            }
            if item["_id"] == "ENTRADA":
                entradas = dados_grupo
            elif item["_id"] == "SAIDA":
                saidas = dados_grupo

        saldo_liquido = entradas["quantidade"] - saidas["quantidade"]

        cursor_detalhe = movimentacoes_col.find(filtro).sort("data_movimentacao", DESCENDING).limit(500)
        docs_detalhe = await cursor_detalhe.to_list(length=500)
        movimentacoes = [MovimentacaoResponse.model_validate(d).model_dump() for d in docs_detalhe]

        return {
            "periodo": {
                "data_inicio": data_inicio.isoformat() if data_inicio else None,
                "data_fim": data_fim.isoformat() if data_fim else None,
            },
            "entradas": entradas,
            "saidas": saidas,
            "saldo_liquido": round(saldo_liquido, 2),
            "total_operacoes": entradas["registros"] + saidas["registros"],
            "movimentacoes": movimentacoes,
        }

    # -------------------------------------------------------------------------
    # Exportação CSV amigável para Excel (ponto e vírgula e UTF-8 com BOM)
    # -------------------------------------------------------------------------

    @classmethod
    async def exportar_csv_recursos(cls, usuario_id: str) -> str:
        """Gera arquivo CSV do estoque do usuário formatado para Excel em português."""
        recursos = await cls.listar_recursos(usuario_id=usuario_id, limit=5000)
        saida = io.StringIO()
        saida.write("\ufeff")
        writer = csv.writer(saida, delimiter=";")

        writer.writerow([
            "ID",
            "Nome",
            "Descrição",
            "Categoria",
            "Unidade",
            "Quantidade Atual",
            "Estoque Mínimo",
            "Status Estoque",
            "Lote",
            "Data de Validade",
            "Dias para Vencer",
            "Status Validade",
        ])

        for r in recursos:
            writer.writerow([
                r.id,
                r.nome,
                r.descricao or "",
                r.categoria,
                r.unidade_medida.value,
                f"{r.quantidade_atual:.2f}".replace(".", ","),
                f"{r.estoque_minimo:.2f}".replace(".", ","),
                r.status_estoque.value,
                r.lote,
                r.data_validade.strftime("%d/%m/%Y"),
                r.dias_para_vencer,
                r.status_validade.value,
            ])

        return saida.getvalue()

    @classmethod
    async def exportar_csv_movimentacoes(
        cls,
        usuario_id: str,
        data_inicio: datetime | None = None,
        data_fim: datetime | None = None,
    ) -> str:
        """Gera arquivo CSV com o extrato de entradas e saídas do usuário."""
        movimentacoes = await cls.listar_movimentacoes(
            usuario_id=usuario_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
            limit=10000,
        )
        saida = io.StringIO()
        saida.write("\ufeff")
        writer = csv.writer(saida, delimiter=";")

        writer.writerow([
            "ID Movimentação",
            "Data/Hora",
            "Tipo",
            "Recurso",
            "Quantidade",
            "Saldo Anterior",
            "Saldo Posterior",
            "Origem/Destino",
            "Motivo",
            "Responsável",
        ])

        for m in movimentacoes:
            saldo_ant = f"{m.saldo_anterior:.2f}".replace(".", ",") if m.saldo_anterior is not None else ""
            saldo_pos = f"{m.saldo_posterior:.2f}".replace(".", ",") if m.saldo_posterior is not None else ""

            writer.writerow([
                m.id,
                m.data_movimentacao.strftime("%d/%m/%Y %H:%M:%S"),
                m.tipo.value,
                m.recurso_nome or m.recurso_id,
                f"{m.quantidade:.2f}".replace(".", ","),
                saldo_ant,
                saldo_pos,
                m.origem_destino,
                m.motivo,
                m.responsavel,
            ])

        return saida.getvalue()
