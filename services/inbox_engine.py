# -*- coding: utf-8 -*-
"""
Inbox Engine — Central de Notificações e Mensagens do Técnico.

Responsabilidades:
- Gerar mensagens dinâmicas baseadas no contexto do save
- Gerenciar inbox (lidas, não lidas, arquivadas, expiradas)
- Processar ações em mensagens (aceitar, recusar, prometer, etc.)
- Aplicar impactos (moral, reputação, satisfação, financeiro)
- Suportar período desempregado
- Integrar com diretoria, jogadores, staff, scouts, imprensa, mercado

Inspirado em: Brasfoot (mensagens da diretoria), EAFC Career Mode (objetivos e inbox)
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, TYPE_CHECKING

from core.enums import (
    TipoRemetente, PrioridadeMensagem, CategoriaMensagem,
    StatusMensagem, TipoAcaoMensagem, CategoriaNoticia,
)
from core.models import (
    MensagemInbox, AcaoMensagem, Noticia,
)
from utils.logger import get_logger

if TYPE_CHECKING:
    from core.models import Time, Jogador, Diretoria

log = get_logger(__name__)


class InboxEngine:
    """Motor de geração e gerenciamento de mensagens do técnico."""

    def __init__(self):
        self._mensagens: List[MensagemInbox] = []
        self._next_id: int = 1
        self._historico_acoes: List[Dict] = []

    @property
    def mensagens(self) -> List[MensagemInbox]:
        return self._mensagens

    @property
    def nao_lidas(self) -> int:
        return sum(1 for m in self._mensagens if m.status == StatusMensagem.NAO_LIDA)

    @property
    def criticas(self) -> int:
        return sum(1 for m in self._mensagens
                   if m.prioridade == PrioridadeMensagem.CRITICA
                   and m.status == StatusMensagem.NAO_LIDA)

    # ══════════════════════════════════════════════════════════
    #  CRIAÇÃO DE MENSAGENS
    # ══════════════════════════════════════════════════════════

    def _criar_mensagem(self, **kwargs) -> MensagemInbox:
        msg = MensagemInbox(id=self._next_id, **kwargs)
        self._next_id += 1
        self._mensagens.append(msg)
        return msg

    # ══════════════════════════════════════════════════════════
    #  GERAÇÃO AUTOMÁTICA POR CONTEXTO — chamada a cada semana
    # ══════════════════════════════════════════════════════════

    def processar_semana(
        self,
        semana: int,
        temporada: int,
        time_jogador: Optional["Time"],
        todos_times: List["Time"],
        resultados: Dict[str, list],
        noticias: List[Noticia],
        desempregado: bool = False,
    ) -> List[MensagemInbox]:
        """Gera mensagens automáticas com base no contexto semanal."""
        novas: List[MensagemInbox] = []

        # Expirar mensagens com prazo vencido
        self._expirar_mensagens(semana)

        if desempregado:
            novas.extend(self._gerar_mensagens_desempregado(semana, temporada, todos_times))
            return novas

        if not time_jogador:
            return novas

        # 1. Mensagens da diretoria
        novas.extend(self._gerar_diretoria(semana, temporada, time_jogador, resultados))

        # 2. Mensagens de jogadores
        novas.extend(self._gerar_jogadores(semana, temporada, time_jogador))

        # 3. Mensagens do staff/departamento médico
        novas.extend(self._gerar_staff_medico(semana, temporada, time_jogador))

        # 4. Mensagens de scouts
        novas.extend(self._gerar_scouts(semana, temporada, time_jogador, todos_times))

        # 5. Mensagens da imprensa/torcida
        novas.extend(self._gerar_imprensa(semana, temporada, time_jogador, resultados))

        # 6. Mensagens financeiras
        novas.extend(self._gerar_financeiro(semana, temporada, time_jogador))

        # 7. Alertas de calendário
        novas.extend(self._gerar_alertas_calendario(semana, temporada, time_jogador))

        # 8. Mensagens pós-jogo
        novas.extend(self._gerar_pos_jogo(semana, temporada, time_jogador, resultados))

        return novas

    # ══════════════════════════════════════════════════════════
    #  GERADORES POR TIPO DE REMETENTE
    # ══════════════════════════════════════════════════════════

    def _gerar_diretoria(
        self, semana: int, temporada: int,
        time: "Time", resultados: Dict[str, list],
    ) -> List[MensagemInbox]:
        msgs = []
        d = time.diretoria

        # Cobrança por satisfação baixa
        if d.satisfacao < 30 and semana % 4 == 0:
            prioridade = PrioridadeMensagem.CRITICA if d.satisfacao < 15 else PrioridadeMensagem.ALTA
            categoria = CategoriaMensagem.RISCO_DEMISSAO if d.satisfacao < 15 else CategoriaMensagem.COBRANCA_DIRETORIA

            if d.satisfacao < 15:
                titulo = "URGENTE: Seu cargo está em risco!"
                texto = (
                    f"A diretoria do {time.nome} está extremamente insatisfeita com os resultados. "
                    f"Satisfação atual: {d.satisfacao}%. Se a situação não melhorar rapidamente, "
                    f"sua demissão será inevitável."
                )
                acoes = [
                    AcaoMensagem(TipoAcaoMensagem.PROMETER, "Prometo melhorar", "melhorar_resultados"),
                    AcaoMensagem(TipoAcaoMensagem.RESPONDER, "Preciso de reforços", "pedir_reforcos"),
                    AcaoMensagem(TipoAcaoMensagem.ARQUIVAR, "Entendido", ""),
                ]
            else:
                titulo = "Diretoria preocupada com resultados"
                texto = (
                    f"Os resultados recentes do {time.nome} não estão agradando. "
                    f"A diretoria espera uma melhora imediata. Satisfação: {d.satisfacao}%."
                )
                acoes = [
                    AcaoMensagem(TipoAcaoMensagem.PROMETER, "Vamos reagir", "promessa_reacao"),
                    AcaoMensagem(TipoAcaoMensagem.ARQUIVAR, "Ok", ""),
                ]
            msgs.append(self._criar_mensagem(
                rodada=semana, temporada=temporada,
                remetente_tipo=TipoRemetente.DIRETORIA,
                remetente_nome="Diretoria", remetente_cargo="Presidente",
                categoria=categoria, prioridade=prioridade,
                titulo=titulo, texto=texto, acoes=acoes,
                prazo_resposta=4 if prioridade == PrioridadeMensagem.CRITICA else -1,
                impacto_satisfacao_diretoria=-5 if prioridade == PrioridadeMensagem.CRITICA else 0,
                time_nome=time.nome,
            ))

        # Ultimato
        if d.satisfacao <= 15 and d.paciencia <= 15 and semana % 2 == 0:
            msgs.append(self._criar_mensagem(
                rodada=semana, temporada=temporada,
                remetente_tipo=TipoRemetente.DIRETORIA,
                remetente_nome="Diretoria", remetente_cargo="Presidente",
                categoria=CategoriaMensagem.ULTIMATO,
                prioridade=PrioridadeMensagem.CRITICA,
                titulo="ULTIMATO: Última chance!",
                texto=(
                    f"Esta é sua última chance. A diretoria decidiu dar mais 2 rodadas "
                    f"para mostrar resultados. Caso contrário, não teremos alternativa."
                ),
                acoes=[
                    AcaoMensagem(TipoAcaoMensagem.ACEITAR, "Vou dar o meu melhor", "aceitar_ultimato"),
                ],
                prazo_resposta=2,
                impacto_reputacao=-3,
                time_nome=time.nome,
            ))

        # Elogio por desempenho bom
        if d.satisfacao > 75 and semana % 8 == 0 and semana > 4:
            msgs.append(self._criar_mensagem(
                rodada=semana, temporada=temporada,
                remetente_tipo=TipoRemetente.DIRETORIA,
                remetente_nome="Diretoria", remetente_cargo="Presidente",
                categoria=CategoriaMensagem.ELOGIO,
                prioridade=PrioridadeMensagem.BAIXA,
                titulo="Parabéns pelo excelente trabalho!",
                texto=(
                    f"A diretoria do {time.nome} reconhece o ótimo trabalho que você "
                    f"vem fazendo. Continue assim! Satisfação: {d.satisfacao}%."
                ),
                acoes=[AcaoMensagem(TipoAcaoMensagem.ARQUIVAR, "Obrigado", "")],
                impacto_moral=3,
                time_nome=time.nome,
            ))

        # Objetivo da temporada (início)
        if semana == 1:
            msgs.append(self._criar_mensagem(
                rodada=semana, temporada=temporada,
                remetente_tipo=TipoRemetente.DIRETORIA,
                remetente_nome="Diretoria", remetente_cargo="Presidente",
                categoria=CategoriaMensagem.OBJETIVO_TEMPORADA,
                prioridade=PrioridadeMensagem.ALTA,
                titulo=f"Objetivos da temporada {temporada}",
                texto=(
                    f"Bem-vindo à temporada {temporada}! "
                    f"Meta principal: {d.meta_principal}. "
                    f"Meta mínima: {d.meta_minima}. "
                    f"Contamos com seu trabalho para levar o {time.nome} ao sucesso."
                ),
                acoes=[
                    AcaoMensagem(TipoAcaoMensagem.ACEITAR, "Vamos em frente!", "aceitar_metas"),
                    AcaoMensagem(TipoAcaoMensagem.NEGOCIAR, "Metas irreais", "negociar_metas"),
                ],
                time_nome=time.nome,
            ))

        return msgs

    def _gerar_jogadores(
        self, semana: int, temporada: int, time: "Time",
    ) -> List[MensagemInbox]:
        msgs = []

        for j in time.jogadores:
            # Jogador insatisfeito por falta de minutos (a cada 8 semanas)
            if (semana % 8 == 0 and semana > 8
                    and j.id not in time.titulares
                    and j.overall >= 65
                    and j.moral < 45
                    and random.random() < 0.4):
                msgs.append(self._criar_mensagem(
                    rodada=semana, temporada=temporada,
                    remetente_tipo=TipoRemetente.JOGADOR,
                    remetente_nome=j.nome, remetente_cargo="Jogador",
                    categoria=CategoriaMensagem.JOGADOR_RECLAMACAO,
                    prioridade=PrioridadeMensagem.MEDIA,
                    titulo=f"{j.nome} reclama de falta de oportunidades",
                    texto=(
                        f"{j.nome} está insatisfeito com a falta de minutos em campo. "
                        f"Overall: {j.overall}, Moral: {j.moral}. "
                        f"\"Preciso jogar, mister. Se não tiver espaço aqui, vou precisar buscar outro clube.\""
                    ),
                    acoes=[
                        AcaoMensagem(TipoAcaoMensagem.PROMETER, "Terá mais chances", "promessa_minutos"),
                        AcaoMensagem(TipoAcaoMensagem.RESPONDER, "Precisa melhorar no treino", "cobrar_treino"),
                        AcaoMensagem(TipoAcaoMensagem.ACEITAR, "Pode procurar outro clube", "liberar_jogador"),
                    ],
                    prazo_resposta=4,
                    impacto_moral=-5,
                    jogador_id=j.id,
                    time_nome=time.nome,
                ))

            # Jogador pedindo renovação (contrato acabando)
            if (j.contrato.meses_restantes <= 6
                    and j.contrato.meses_restantes > 0
                    and semana % 8 == 0
                    and random.random() < 0.5):
                msgs.append(self._criar_mensagem(
                    rodada=semana, temporada=temporada,
                    remetente_tipo=TipoRemetente.JOGADOR,
                    remetente_nome=j.nome, remetente_cargo="Jogador",
                    categoria=CategoriaMensagem.JOGADOR_RENOVACAO,
                    prioridade=PrioridadeMensagem.ALTA,
                    titulo=f"{j.nome} quer discutir renovação",
                    texto=(
                        f"{j.nome} tem apenas {j.contrato.meses_restantes} meses de contrato restantes "
                        f"e gostaria de discutir uma renovação. Salário atual: R$ {j.contrato.salario:,.0f}."
                    ),
                    acoes=[
                        AcaoMensagem(TipoAcaoMensagem.NEGOCIAR, "Vamos negociar", "iniciar_renovacao"),
                        AcaoMensagem(TipoAcaoMensagem.RECUSAR, "Não vou renovar", "recusar_renovacao"),
                        AcaoMensagem(TipoAcaoMensagem.ADIAR, "Veremos mais pra frente", "adiar_renovacao"),
                    ],
                    prazo_resposta=8,
                    jogador_id=j.id,
                    time_nome=time.nome,
                ))

            # Jogador querendo sair
            if (j.quer_sair and semana % 4 == 0 and random.random() < 0.3):
                msgs.append(self._criar_mensagem(
                    rodada=semana, temporada=temporada,
                    remetente_tipo=TipoRemetente.JOGADOR,
                    remetente_nome=j.nome, remetente_cargo="Jogador",
                    categoria=CategoriaMensagem.JOGADOR_TRANSFERENCIA,
                    prioridade=PrioridadeMensagem.ALTA,
                    titulo=f"{j.nome} pede para sair",
                    texto=(
                        f"{j.nome} formalizou o pedido de transferência. "
                        f"\"Preciso de um novo desafio na minha carreira.\""
                    ),
                    acoes=[
                        AcaoMensagem(TipoAcaoMensagem.ACEITAR, "Aceito colocar no mercado", "aceitar_saida"),
                        AcaoMensagem(TipoAcaoMensagem.RECUSAR, "Não vai sair", "recusar_saida"),
                        AcaoMensagem(TipoAcaoMensagem.NEGOCIAR, "Só pelo preço certo", "negociar_saida"),
                    ],
                    prazo_resposta=4,
                    impacto_moral=-8,
                    jogador_id=j.id,
                    time_nome=time.nome,
                ))

        # Conflito entre jogadores (raro)
        if semana % 12 == 0 and len(time.jogadores) >= 11 and random.random() < 0.15:
            j1 = random.choice([j for j in time.jogadores if j.overall >= 60])
            j2 = random.choice([j for j in time.jogadores if j.id != j1.id and j.overall >= 60])
            msgs.append(self._criar_mensagem(
                rodada=semana, temporada=temporada,
                remetente_tipo=TipoRemetente.CAPITAO,
                remetente_nome="Capitão", remetente_cargo="Capitão",
                categoria=CategoriaMensagem.CONFLITO_ELENCO,
                prioridade=PrioridadeMensagem.MEDIA,
                titulo="Problema no vestiário",
                texto=(
                    f"Mister, preciso relatar um atrito entre {j1.nome} e {j2.nome} no vestiário. "
                    f"A situação pode afetar o grupo se não for resolvida."
                ),
                acoes=[
                    AcaoMensagem(TipoAcaoMensagem.RESPONDER, "Conversar com ambos", "mediar_conflito"),
                    AcaoMensagem(TipoAcaoMensagem.RESPONDER, "Punir o agressor", "punir_conflito"),
                    AcaoMensagem(TipoAcaoMensagem.ARQUIVAR, "Deixar o grupo resolver", "ignorar_conflito"),
                ],
                impacto_moral=-3,
                time_nome=time.nome,
            ))

        return msgs

    def _gerar_staff_medico(
        self, semana: int, temporada: int, time: "Time",
    ) -> List[MensagemInbox]:
        msgs = []

        # Avisos do departamento médico sobre jogadores lesionados
        for j in time.jogadores:
            if j.status_lesao.name != "SAUDAVEL" and j.dias_lesao <= 7 and j.dias_lesao > 0:
                msgs.append(self._criar_mensagem(
                    rodada=semana, temporada=temporada,
                    remetente_tipo=TipoRemetente.DEPARTAMENTO_MEDICO,
                    remetente_nome="Departamento Médico", remetente_cargo="Médico",
                    categoria=CategoriaMensagem.RETORNO_LESAO,
                    prioridade=PrioridadeMensagem.MEDIA,
                    titulo=f"{j.nome} próximo de se recuperar",
                    texto=(
                        f"{j.nome} está se recuperando bem e deve voltar em {j.dias_lesao} dias. "
                        f"Status: {j.status_lesao.value}."
                    ),
                    acoes=[AcaoMensagem(TipoAcaoMensagem.ARQUIVAR, "Ok", "")],
                    jogador_id=j.id,
                    time_nome=time.nome,
                ))

        # Aviso de fadiga do elenco (a cada 4 semanas)
        if semana % 4 == 0:
            cansados = [j for j in time.jogadores if j.condicao_fisica < 50 and j.id in time.titulares]
            if len(cansados) >= 3:
                nomes = ", ".join(j.nome for j in cansados[:5])
                msgs.append(self._criar_mensagem(
                    rodada=semana, temporada=temporada,
                    remetente_tipo=TipoRemetente.STAFF,
                    remetente_nome="Preparador Físico", remetente_cargo="Preparador Físico",
                    categoria=CategoriaMensagem.STAFF_RECOMENDACAO,
                    prioridade=PrioridadeMensagem.ALTA,
                    titulo="Alerta de fadiga no elenco",
                    texto=(
                        f"Vários titulares estão com condição física baixa: {nomes}. "
                        f"Recomendo rotação imediata para evitar lesões."
                    ),
                    acoes=[
                        AcaoMensagem(TipoAcaoMensagem.ACEITAR, "Vou rotacionar", "aceitar_rotacao"),
                        AcaoMensagem(TipoAcaoMensagem.RECUSAR, "Vou manter", "ignorar_fadiga"),
                    ],
                    time_nome=time.nome,
                ))

        # Suspensão de jogador
        for j in time.jogadores:
            if j.suspensao_jogos > 0 and semana % 2 == 0:
                msgs.append(self._criar_mensagem(
                    rodada=semana, temporada=temporada,
                    remetente_tipo=TipoRemetente.FEDERACAO,
                    remetente_nome="Federação", remetente_cargo="Comissão Disciplinar",
                    categoria=CategoriaMensagem.SUSPENSAO,
                    prioridade=PrioridadeMensagem.ALTA,
                    titulo=f"{j.nome} suspenso",
                    texto=(
                        f"{j.nome} está suspenso por {j.suspensao_jogos} jogo(s). "
                        f"Acúmulo de cartões amarelos."
                    ),
                    acoes=[AcaoMensagem(TipoAcaoMensagem.ARQUIVAR, "Entendido", "")],
                    jogador_id=j.id,
                    time_nome=time.nome,
                ))

        return msgs

    def _gerar_scouts(
        self, semana: int, temporada: int,
        time: "Time", todos_times: List["Time"],
    ) -> List[MensagemInbox]:
        msgs = []
        if semana % 8 != 0:
            return msgs

        # Scout recomenda jogador
        if random.random() < 0.3 and todos_times:
            # Encontrar jogador de bom nível em outro time
            outros = [t for t in todos_times if t.nome != time.nome and t.jogadores]
            if outros:
                t_alvo = random.choice(outros)
                bons = [j for j in t_alvo.jogadores if j.overall >= 65 and j.idade < 28]
                if bons:
                    j_alvo = random.choice(bons)
                    msgs.append(self._criar_mensagem(
                        rodada=semana, temporada=temporada,
                        remetente_tipo=TipoRemetente.SCOUT,
                        remetente_nome="Olheiro", remetente_cargo="Scout",
                        categoria=CategoriaMensagem.RECOMENDACAO_SCOUT,
                        prioridade=PrioridadeMensagem.MEDIA,
                        titulo=f"Recomendação: {j_alvo.nome} ({t_alvo.nome})",
                        texto=(
                            f"Nosso olheiro identificou {j_alvo.nome}, {j_alvo.idade} anos, "
                            f"{j_alvo.posicao.value}, OVR {j_alvo.overall}, POT {j_alvo.potencial}. "
                            f"Atualmente no {t_alvo.nome}. Valor estimado: R$ {j_alvo.valor_mercado:,.0f}. "
                            f"Pode ser um ótimo reforço para o elenco."
                        ),
                        acoes=[
                            AcaoMensagem(TipoAcaoMensagem.ABRIR_TELA, "Ir ao mercado", "",
                                         tela_destino="mercado"),
                            AcaoMensagem(TipoAcaoMensagem.ARQUIVAR, "Anotar", ""),
                        ],
                        jogador_id=j_alvo.id,
                        time_nome=t_alvo.nome,
                    ))

        return msgs

    def _gerar_imprensa(
        self, semana: int, temporada: int,
        time: "Time", resultados: Dict[str, list],
    ) -> List[MensagemInbox]:
        msgs = []

        # Verificar se o time do jogador jogou nesta rodada
        jogou = False
        for comp, lista in resultados.items():
            for r in lista:
                if time.nome in (r.time_casa, r.time_fora):
                    jogou = True
                    break

        # Cobrança da torcida após sequência ruim (3+ derrotas)
        if time.derrotas >= 3 and semana % 6 == 0 and time.diretoria.pressao_torcida > 60:
            msgs.append(self._criar_mensagem(
                rodada=semana, temporada=temporada,
                remetente_tipo=TipoRemetente.TORCIDA,
                remetente_nome="Torcida Organizada", remetente_cargo="",
                categoria=CategoriaMensagem.COBRANCA_TORCIDA,
                prioridade=PrioridadeMensagem.MEDIA,
                titulo="Torcida insatisfeita cobra resultados",
                texto=(
                    f"A torcida do {time.nome} está revoltada com a fase ruim. "
                    f"Faixas de protesto foram vistas no estádio. "
                    f"Pressão: {time.diretoria.pressao_torcida}%."
                ),
                acoes=[AcaoMensagem(TipoAcaoMensagem.ARQUIVAR, "Entendido", "")],
                impacto_moral=-3,
                time_nome=time.nome,
            ))

        # Entrevista pré-jogo (a cada 4 semanas)
        if semana % 4 == 0 and random.random() < 0.4:
            msgs.append(self._criar_mensagem(
                rodada=semana, temporada=temporada,
                remetente_tipo=TipoRemetente.IMPRENSA,
                remetente_nome="Imprensa Esportiva", remetente_cargo="Repórter",
                categoria=CategoriaMensagem.ENTREVISTA,
                prioridade=PrioridadeMensagem.BAIXA,
                titulo="Convite para entrevista coletiva",
                texto=(
                    f"A imprensa gostaria de ouvir suas palavras antes da próxima rodada. "
                    f"Como avalia o momento do {time.nome}?"
                ),
                acoes=[
                    AcaoMensagem(TipoAcaoMensagem.RESPONDER, "Estamos confiantes", "entrevista_otimista"),
                    AcaoMensagem(TipoAcaoMensagem.RESPONDER, "Jogo a jogo", "entrevista_cauteloso"),
                    AcaoMensagem(TipoAcaoMensagem.RESPONDER, "Precisamos melhorar", "entrevista_autocritico"),
                    AcaoMensagem(TipoAcaoMensagem.RECUSAR, "Não vou falar", "recusar_entrevista"),
                ],
                impacto_reputacao=1,
                time_nome=time.nome,
            ))

        return msgs

    def _gerar_financeiro(
        self, semana: int, temporada: int, time: "Time",
    ) -> List[MensagemInbox]:
        msgs = []

        # Alerta financeiro (a cada 8 semanas)
        if semana % 8 == 0 and time.financas.saldo < 0:
            msgs.append(self._criar_mensagem(
                rodada=semana, temporada=temporada,
                remetente_tipo=TipoRemetente.DIRETORIA,
                remetente_nome="Diretor Financeiro", remetente_cargo="Diretor Financeiro",
                categoria=CategoriaMensagem.RESULTADO_FINANCEIRO,
                prioridade=PrioridadeMensagem.ALTA,
                titulo="Finanças em estado crítico!",
                texto=(
                    f"O {time.nome} está com saldo negativo de R$ {abs(time.financas.saldo):,.0f}. "
                    f"Folha salarial: R$ {time.folha_salarial:,.0f}. "
                    f"A diretoria exige redução de gastos."
                ),
                acoes=[
                    AcaoMensagem(TipoAcaoMensagem.ACEITAR, "Vou vender jogadores", "vender_para_equilibrar"),
                    AcaoMensagem(TipoAcaoMensagem.ABRIR_TELA, "Ir às finanças", "", tela_destino="financas"),
                ],
                impacto_satisfacao_diretoria=-5,
                impacto_financeiro=time.financas.saldo,
                time_nome=time.nome,
            ))

        return msgs

    def _gerar_alertas_calendario(
        self, semana: int, temporada: int, time: "Time",
    ) -> List[MensagemInbox]:
        msgs = []

        # Alertas do calendário (mensagem simples no início da temporada)
        if semana == 2:
            msgs.append(self._criar_mensagem(
                rodada=semana, temporada=temporada,
                remetente_tipo=TipoRemetente.SISTEMA,
                remetente_nome="Sistema", remetente_cargo="",
                categoria=CategoriaMensagem.ALERTA_CALENDARIO,
                prioridade=PrioridadeMensagem.BAIXA,
                titulo="Calendário da temporada disponível",
                texto="O calendário completo da temporada já está disponível na aba Agenda.",
                acoes=[
                    AcaoMensagem(TipoAcaoMensagem.ABRIR_TELA, "Ver agenda", "", tela_destino="agenda"),
                    AcaoMensagem(TipoAcaoMensagem.ARQUIVAR, "Ok", ""),
                ],
                time_nome=time.nome,
            ))

        return msgs

    # ══════════════════════════════════════════════════════════
    #  PÓS-JOGO
    # ══════════════════════════════════════════════════════════

    def _gerar_pos_jogo(
        self, semana: int, temporada: int,
        time: "Time", resultados: Dict[str, list],
    ) -> List[MensagemInbox]:
        msgs = []
        for comp, lista in resultados.items():
            for r in lista:
                eh_casa = time.nome == r.time_casa
                eh_fora = time.nome == r.time_fora
                if not eh_casa and not eh_fora:
                    continue
                gols_pro = r.gols_casa if eh_casa else r.gols_fora
                gols_contra = r.gols_fora if eh_casa else r.gols_casa
                adversario = r.time_fora if eh_casa else r.time_casa
                diff = gols_pro - gols_contra

                # Goleada a favor
                if diff >= 3:
                    msgs.append(self._criar_mensagem(
                        rodada=semana, temporada=temporada,
                        remetente_tipo=TipoRemetente.IMPRENSA,
                        remetente_nome="Imprensa Esportiva", remetente_cargo="",
                        categoria=CategoriaMensagem.ELOGIO,
                        prioridade=PrioridadeMensagem.BAIXA,
                        titulo=f"Goleada! {time.nome} {gols_pro}x{gols_contra} {adversario}",
                        texto=(
                            f"Excelente atuação do {time.nome}! A equipe goleou o {adversario} "
                            f"por {gols_pro} a {gols_contra}. A imprensa elogia o desempenho."
                        ),
                        acoes=[AcaoMensagem(TipoAcaoMensagem.ARQUIVAR, "Obrigado", "")],
                        impacto_moral=3,
                        competicao=comp,
                        time_nome=time.nome,
                    ))
                # Derrota pesada
                elif diff <= -3:
                    msgs.append(self._criar_mensagem(
                        rodada=semana, temporada=temporada,
                        remetente_tipo=TipoRemetente.IMPRENSA,
                        remetente_nome="Imprensa Esportiva", remetente_cargo="",
                        categoria=CategoriaMensagem.COBRANCA_TORCIDA,
                        prioridade=PrioridadeMensagem.ALTA,
                        titulo=f"Derrota humilhante: {adversario} {gols_contra}x{gols_pro} {time.nome}",
                        texto=(
                            f"O {time.nome} sofreu uma derrota acachapante para o {adversario}. "
                            f"A torcida cobra explicações e a diretoria está indignada."
                        ),
                        acoes=[
                            AcaoMensagem(TipoAcaoMensagem.RESPONDER, "Vou corrigir", "autocritica_goleada"),
                            AcaoMensagem(TipoAcaoMensagem.ARQUIVAR, "Seguir em frente", ""),
                        ],
                        impacto_moral=-5,
                        competicao=comp,
                        time_nome=time.nome,
                    ))
        return msgs

    # ══════════════════════════════════════════════════════════
    #  MENSAGENS DURANTE DESEMPREGO
    # ══════════════════════════════════════════════════════════

    def _gerar_mensagens_desempregado(
        self, semana: int, temporada: int, todos_times: List["Time"],
    ) -> List[MensagemInbox]:
        msgs = []

        # Notícias de demissões em outros clubes
        if random.random() < 0.25 and todos_times:
            t = random.choice(todos_times)
            if t.diretoria.satisfacao < 25:
                msgs.append(self._criar_mensagem(
                    rodada=semana, temporada=temporada,
                    remetente_tipo=TipoRemetente.IMPRENSA,
                    remetente_nome="Imprensa Esportiva", remetente_cargo="",
                    categoria=CategoriaMensagem.DEMISSAO_OUTRO_TECNICO,
                    prioridade=PrioridadeMensagem.MEDIA,
                    titulo=f"Técnico do {t.nome} é demitido!",
                    texto=(
                        f"O treinador do {t.nome} foi demitido após resultados ruins. "
                        f"O clube já busca substituto no mercado."
                    ),
                    time_nome=t.nome,
                ))

        # Propostas de emprego
        if semana % 4 == 0 and random.random() < 0.4 and todos_times:
            # Clubes com satisfação baixa podem fazer proposta
            candidatos = [t for t in todos_times if t.diretoria.satisfacao < 40]
            if candidatos:
                t = random.choice(candidatos)
                msgs.append(self._criar_mensagem(
                    rodada=semana, temporada=temporada,
                    remetente_tipo=TipoRemetente.DIRETORIA,
                    remetente_nome=f"Diretoria do {t.nome}", remetente_cargo="Presidente",
                    categoria=CategoriaMensagem.VAGA_EMPREGO,
                    prioridade=PrioridadeMensagem.ALTA,
                    titulo=f"{t.nome} oferece cargo de treinador",
                    texto=(
                        f"O {t.nome} gostaria de contar com seus serviços como treinador. "
                        f"Divisão: {t.divisao}ª. Prestígio: {t.prestigio}. "
                        f"Orçamento de transferências: R$ {t.financas.orcamento_transferencias:,.0f}."
                    ),
                    acoes=[
                        AcaoMensagem(TipoAcaoMensagem.ACEITAR, "Aceitar proposta", f"aceitar_emprego_{t.nome}"),
                        AcaoMensagem(TipoAcaoMensagem.RECUSAR, "Recusar", "recusar_emprego"),
                        AcaoMensagem(TipoAcaoMensagem.NEGOCIAR, "Discutir termos", "negociar_emprego"),
                    ],
                    prazo_resposta=4,
                    time_nome=t.nome,
                ))

        # Notícias gerais do futebol
        if random.random() < 0.2:
            msgs.append(self._criar_mensagem(
                rodada=semana, temporada=temporada,
                remetente_tipo=TipoRemetente.SISTEMA,
                remetente_nome="Mundo do Futebol", remetente_cargo="",
                categoria=CategoriaMensagem.NOTICIA_TEMPORADA,
                prioridade=PrioridadeMensagem.BAIXA,
                titulo="Acompanhe as rodadas",
                texto="Enquanto você busca um novo clube, acompanhe os resultados das competições.",
                acoes=[
                    AcaoMensagem(TipoAcaoMensagem.ABRIR_TELA, "Ver classificação", "",
                                 tela_destino="classificacao"),
                ],
            ))

        if not msgs:
            ameacados = sorted(
                [t for t in todos_times if t.diretoria.satisfacao < 45],
                key=lambda t: t.diretoria.satisfacao,
            )[:3]
            resumo = ", ".join(t.nome for t in ameacados) if ameacados else "mercado estável"
            msgs.append(self._criar_mensagem(
                rodada=semana, temporada=temporada,
                remetente_tipo=TipoRemetente.SISTEMA,
                remetente_nome="Mercado de Técnicos", remetente_cargo="",
                categoria=CategoriaMensagem.NOTICIA_TEMPORADA,
                prioridade=PrioridadeMensagem.BAIXA,
                titulo="Panorama do mercado",
                texto=(
                    "Você segue sem clube, mas o mercado continua se movendo. "
                    f"Clubes sob pressão: {resumo}."
                ),
                acoes=[
                    AcaoMensagem(TipoAcaoMensagem.ABRIR_TELA, "Ver ofertas", "",
                                 tela_destino="desemprego"),
                ],
            ))

        return msgs

    # ══════════════════════════════════════════════════════════
    #  PROCESSAR AÇÃO DO TÉCNICO
    # ══════════════════════════════════════════════════════════

    def processar_acao(
        self, msg_id: int, acao_valor: str,
        time_jogador: Optional["Time"] = None,
    ) -> Dict:
        """Processa a ação escolhida pelo técnico em uma mensagem."""
        msg = self._buscar_mensagem(msg_id)
        if not msg:
            return {"ok": False, "erro": "Mensagem não encontrada"}
        if msg.status == StatusMensagem.RESPONDIDA:
            return {"ok": False, "erro": "Mensagem já respondida"}

        msg.status = StatusMensagem.RESPONDIDA
        msg.respondida_com = acao_valor

        resultado = {"ok": True, "impactos": {}}

        # Aplicar impactos da mensagem respondida
        if time_jogador:
            if msg.impacto_moral:
                for j in time_jogador.jogadores:
                    j.moral = max(0, min(100, j.moral + msg.impacto_moral))
                resultado["impactos"]["moral"] = msg.impacto_moral

            if msg.impacto_satisfacao_diretoria and acao_valor not in ("aceitar_ultimato", "aceitar_metas"):
                time_jogador.diretoria.satisfacao = max(0, min(100,
                    time_jogador.diretoria.satisfacao + msg.impacto_satisfacao_diretoria))
                resultado["impactos"]["satisfacao"] = msg.impacto_satisfacao_diretoria

        # Impactos específicos por ação
        if acao_valor == "promessa_minutos" and time_jogador:
            resultado["impactos"]["promessa"] = "O jogador espera titularidade nas próximas 4 rodadas."
        elif acao_valor == "aceitar_saida" and time_jogador:
            jog = time_jogador.jogador_por_id(msg.jogador_id)
            if jog:
                jog.quer_sair = True
            resultado["impactos"]["jogador"] = "Jogador colocado no mercado."
        elif acao_valor == "recusar_saida" and time_jogador:
            jog = time_jogador.jogador_por_id(msg.jogador_id)
            if jog:
                jog.moral = max(0, jog.moral - 10)
            resultado["impactos"]["jogador"] = "Jogador insatisfeito."
        elif acao_valor == "mediar_conflito" and time_jogador:
            for j in time_jogador.jogadores:
                j.moral = max(0, min(100, j.moral + 2))
            resultado["impactos"]["moral"] = 2
        elif acao_valor == "punir_conflito" and time_jogador:
            resultado["impactos"]["moral_grupo"] = "Alguns jogadores podem não gostar da punição."
        elif acao_valor == "entrevista_otimista":
            resultado["impactos"]["reputacao"] = 2
        elif acao_valor == "entrevista_autocritico":
            resultado["impactos"]["reputacao"] = 1
        elif acao_valor == "recusar_entrevista":
            resultado["impactos"]["reputacao"] = -2
        elif acao_valor == "adiar_renovacao" and time_jogador:
            jog = time_jogador.jogador_por_id(msg.jogador_id)
            if jog:
                jog.moral = max(0, jog.moral - 3)
            resultado["impactos"]["jogador"] = "Jogador frustrado, voltará a cobrar mais tarde."
        elif acao_valor == "iniciar_renovacao" and time_jogador:
            resultado["impactos"]["promessa"] = "Negociação de renovação em andamento."
        elif acao_valor == "negociar_metas" and time_jogador:
            time_jogador.diretoria.satisfacao = max(0, time_jogador.diretoria.satisfacao - 3)
            resultado["impactos"]["satisfacao"] = -3
            resultado["impactos"]["promessa"] = "Diretoria descontente, mas vai reavaliar as metas."
        elif acao_valor == "negociar_saida" and time_jogador:
            jog = time_jogador.jogador_por_id(msg.jogador_id)
            if jog:
                jog.moral = max(0, jog.moral - 3)
            resultado["impactos"]["jogador"] = "Jogador aberto à negociação pelo valor certo."
        elif acao_valor == "negociar_emprego":
            resultado["impactos"]["promessa"] = "Proposta em análise. O clube aguarda resposta."
        elif acao_valor == "cobrar_treino" and time_jogador:
            jog = time_jogador.jogador_por_id(msg.jogador_id)
            if jog:
                jog.moral = max(0, jog.moral - 5)
            resultado["impactos"]["jogador"] = "Jogador desmotivado com a cobrança."
        elif acao_valor == "liberar_jogador" and time_jogador:
            jog = time_jogador.jogador_por_id(msg.jogador_id)
            if jog:
                jog.quer_sair = True
            resultado["impactos"]["jogador"] = "Jogador liberado para buscar outro clube."
        elif acao_valor == "vender_para_equilibrar" and time_jogador:
            resultado["impactos"]["promessa"] = "Diretoria espera vendas nas próximas semanas."
        elif acao_valor == "aceitar_rotacao":
            resultado["impactos"]["promessa"] = "O elenco espera rotação nas próximas partidas."
        elif acao_valor == "ignorar_fadiga" and time_jogador:
            resultado["impactos"]["promessa"] = "Risco elevado de lesões mantido."

        self._historico_acoes.append({
            "msg_id": msg_id,
            "acao": acao_valor,
            "resultado": resultado,
        })

        return resultado

    # ══════════════════════════════════════════════════════════
    #  GERENCIAMENTO
    # ══════════════════════════════════════════════════════════

    def marcar_lida(self, msg_id: int) -> bool:
        msg = self._buscar_mensagem(msg_id)
        if msg and msg.status == StatusMensagem.NAO_LIDA:
            msg.status = StatusMensagem.LIDA
            return True
        return False

    def marcar_fixada(self, msg_id: int) -> bool:
        msg = self._buscar_mensagem(msg_id)
        if msg:
            msg.fixada = not msg.fixada
            return True
        return False

    def arquivar(self, msg_id: int) -> bool:
        msg = self._buscar_mensagem(msg_id)
        if msg:
            msg.arquivada = True
            msg.status = StatusMensagem.ARQUIVADA
            return True
        return False

    def _buscar_mensagem(self, msg_id: int) -> Optional[MensagemInbox]:
        try:
            msg_id = int(msg_id)
        except (TypeError, ValueError):
            return None
        for m in self._mensagens:
            if m.id == msg_id:
                return m
        return None

    def _expirar_mensagens(self, semana_atual: int) -> None:
        for m in self._mensagens:
            if (m.prazo_resposta > 0
                    and m.status == StatusMensagem.NAO_LIDA
                    and semana_atual - m.rodada >= m.prazo_resposta):
                m.status = StatusMensagem.EXPIRADA

    def filtrar(
        self,
        categoria: Optional[CategoriaMensagem] = None,
        remetente: Optional[TipoRemetente] = None,
        prioridade: Optional[PrioridadeMensagem] = None,
        status: Optional[StatusMensagem] = None,
        apenas_nao_arquivadas: bool = True,
    ) -> List[MensagemInbox]:
        result = self._mensagens
        if apenas_nao_arquivadas:
            result = [m for m in result if not m.arquivada]
        if categoria:
            result = [m for m in result if m.categoria == categoria]
        if remetente:
            result = [m for m in result if m.remetente_tipo == remetente]
        if prioridade:
            result = [m for m in result if m.prioridade == prioridade]
        if status:
            result = [m for m in result if m.status == status]
        return sorted(result, key=lambda m: (
            0 if m.prioridade == PrioridadeMensagem.CRITICA else
            1 if m.prioridade == PrioridadeMensagem.ALTA else
            2 if m.prioridade == PrioridadeMensagem.MEDIA else 3,
            -m.rodada,
        ))

    # ══════════════════════════════════════════════════════════
    #  SERIALIZAÇÃO
    # ══════════════════════════════════════════════════════════

    def to_api_list(
        self,
        limite: int = 50,
        categoria: Optional[str] = None,
        remetente: Optional[str] = None,
        prioridade: Optional[str] = None,
    ) -> List[Dict]:
        """Retorna mensagens formatadas para o frontend."""
        cat = CategoriaMensagem(categoria) if categoria else None
        rem = TipoRemetente(remetente) if remetente else None
        pri = PrioridadeMensagem(prioridade) if prioridade else None

        msgs = self.filtrar(categoria=cat, remetente=rem, prioridade=pri)
        return [self._msg_to_dict(m) for m in msgs[:limite]]

    def _msg_to_dict(self, m: MensagemInbox) -> Dict:
        return {
            "id": m.id,
            "rodada": m.rodada,
            "temporada": m.temporada,
            "remetente_tipo": m.remetente_tipo.value,
            "remetente_nome": m.remetente_nome,
            "remetente_cargo": m.remetente_cargo,
            "categoria": m.categoria.value,
            "prioridade": m.prioridade.value,
            "titulo": m.titulo,
            "texto": m.texto,
            "status": m.status.value,
            "acoes": [
                {"tipo": a.tipo.value, "label": a.label, "valor": a.valor,
                 "tela_destino": a.tela_destino}
                for a in m.acoes
            ],
            "prazo_resposta": m.prazo_resposta,
            "respondida_com": m.respondida_com,
            "jogador_id": m.jogador_id,
            "time_nome": m.time_nome,
            "competicao": m.competicao,
            "fixada": m.fixada,
            "arquivada": m.arquivada,
            "impacto_moral": m.impacto_moral,
            "impacto_reputacao": m.impacto_reputacao,
            "impacto_satisfacao": m.impacto_satisfacao_diretoria,
            "impacto_satisfacao_diretoria": m.impacto_satisfacao_diretoria,
            "impacto_financeiro": m.impacto_financeiro,
        }

    def to_save_dict(self) -> Dict:
        """Serializa estado completo para salvar no save."""
        return {
            "next_id": self._next_id,
            "mensagens": [self._msg_to_dict(m) for m in self._mensagens],
        }

    def from_save_dict(self, data: Dict) -> None:
        """Restaura estado do inbox a partir de save."""
        self._next_id = data.get("next_id", 1)
        self._mensagens = []
        for md in data.get("mensagens", []):
            acoes = [
                AcaoMensagem(
                    tipo=TipoAcaoMensagem(a["tipo"]),
                    label=a["label"],
                    valor=a["valor"],
                    tela_destino=a.get("tela_destino", ""),
                )
                for a in md.get("acoes", [])
            ]
            msg = MensagemInbox(
                id=md["id"],
                rodada=md["rodada"],
                temporada=md.get("temporada", 2026),
                remetente_tipo=TipoRemetente(md["remetente_tipo"]),
                remetente_nome=md["remetente_nome"],
                remetente_cargo=md.get("remetente_cargo", ""),
                categoria=CategoriaMensagem(md["categoria"]),
                prioridade=PrioridadeMensagem(md["prioridade"]),
                titulo=md["titulo"],
                texto=md["texto"],
                status=StatusMensagem(md["status"]),
                acoes=acoes,
                prazo_resposta=md.get("prazo_resposta", -1),
                respondida_com=md.get("respondida_com", ""),
                jogador_id=md.get("jogador_id", 0),
                time_nome=md.get("time_nome", ""),
                competicao=md.get("competicao", ""),
                fixada=md.get("fixada", False),
                arquivada=md.get("arquivada", False),
                impacto_moral=md.get("impacto_moral", 0),
                impacto_reputacao=md.get("impacto_reputacao", 0),
                impacto_satisfacao_diretoria=md.get(
                    "impacto_satisfacao_diretoria",
                    md.get("impacto_satisfacao", 0),
                ),
                impacto_financeiro=md.get("impacto_financeiro", 0),
            )
            self._mensagens.append(msg)
