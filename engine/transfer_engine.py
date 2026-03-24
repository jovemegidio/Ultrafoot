# -*- coding: utf-8 -*-
"""
Motor de transferências: ofertas, IA de avaliação, jogadores livres.
"""
from __future__ import annotations

import random
from typing import List, Optional

from core.enums import (
    Posicao, TipoContrato, StatusOferta, TipoOferta, CategoriaNoticia,
)
from core.models import (
    Time, Jogador, OfertaTransferencia, ContratoJogador, Noticia,
)
from config import (
    TRANSFER_SCORE_ACEITE, TRANSFER_SCORE_CHANCE,
    TRANSFER_SCORE_BAIXA, TRANSFER_CHANCE_IA,
    JOGADORES_LIVRES_INICIAL,
)
from utils.name_generator import gerar_nome_brasileiro
from utils.logger import get_logger

log = get_logger(__name__)


class MotorTransferencias:
    """Gerencia todo o mercado de transferências."""

    def __init__(self) -> None:
        self.ofertas_pendentes: List[OfertaTransferencia] = []
        self.ofertas_historico: List[OfertaTransferencia] = []
        self.jogadores_livres: List[Jogador] = []
        self.noticias: List[Noticia] = []
        self._id_counter = 0

    # ── Gerar mercado livre ───────────────────────────────────

    def gerar_jogadores_livres(self, quantidade: int, id_base: int) -> List[Jogador]:
        from data.seeds.seed_loader import gerar_atributos_jogador

        livres: List[Jogador] = []
        pesos_idade = [3, 4, 5, 6, 7, 8, 8, 8, 7, 6, 5, 4, 3, 2, 2, 1, 1, 1, 1, 1]
        for i in range(quantidade):
            idade = random.choices(range(18, 38), weights=pesos_idade, k=1)[0]
            posicao = random.choice(list(Posicao))
            if idade < 22:
                base = random.randint(30, 55)
            elif idade < 28:
                base = random.randint(35, 60)
            elif idade < 33:
                base = random.randint(30, 55)
            else:
                base = random.randint(25, 45)

            j = Jogador(
                id=id_base + i,
                nome=gerar_nome_brasileiro(),
                idade=idade,
                posicao=posicao,
                potencial=min(99, base + random.randint(5, 25)),
                contrato=ContratoJogador(tipo=TipoContrato.PROFISSIONAL,
                                         salario=0, multa_rescisoria=0,
                                         duracao_meses=0, meses_restantes=0),
            )
            gerar_atributos_jogador(j, base)
            livres.append(j)
        self.jogadores_livres = livres
        return livres

    # ── Ofertas ───────────────────────────────────────────────

    def fazer_oferta(self, comprador: Time, vendedor: Time,
                     jogador: Jogador, valor: int, salario: int,
                     tipo: TipoOferta = TipoOferta.COMPRA) -> OfertaTransferencia:
        self._id_counter += 1
        oferta = OfertaTransferencia(
            id=self._id_counter,
            jogador_id=jogador.id, jogador_nome=jogador.nome,
            time_origem=vendedor.nome, time_destino=comprador.nome,
            valor=valor, salario_oferecido=salario, tipo=tipo,
        )
        self.ofertas_pendentes.append(oferta)
        return oferta

    def avaliar_oferta_ia(self, oferta: OfertaTransferencia,
                          vendedor: Time, jogador: Jogador) -> StatusOferta:
        vm = max(1, jogador.valor_mercado)
        fv = oferta.valor / vm
        mesma_pos = [j for j in vendedor.jogadores
                     if j.posicao == jogador.posicao and j.id != jogador.id]
        fn = 0.7 if len(mesma_pos) < 2 else (1.3 if len(mesma_pos) >= 4 else 1.0)
        if jogador.quer_sair:
            fn *= 1.2
        score = fv * fn
        if score >= TRANSFER_SCORE_ACEITE:
            return StatusOferta.ACEITA
        if score >= TRANSFER_SCORE_CHANCE and random.random() < 0.5:
            return StatusOferta.ACEITA
        if score >= TRANSFER_SCORE_BAIXA and random.random() < 0.2:
            return StatusOferta.ACEITA
        return StatusOferta.RECUSADA

    def processar_ofertas_ia(self, times: List[Time]) -> None:
        time_map = {t.nome: t for t in times}
        for oferta in self.ofertas_pendentes[:]:
            if oferta.status != StatusOferta.PENDENTE:
                continue
            vendedor = time_map.get(oferta.time_origem)
            if not vendedor or vendedor.eh_jogador:
                continue
            jogador = vendedor.jogador_por_id(oferta.jogador_id)
            if not jogador:
                oferta.status = StatusOferta.CANCELADA
                continue
            oferta.status = self.avaliar_oferta_ia(oferta, vendedor, jogador)
            if oferta.status == StatusOferta.ACEITA:
                self._executar_transferencia(oferta, times, _time_map=time_map)

    # ── Execução ──────────────────────────────────────────────

    def _executar_transferencia(self, oferta: OfertaTransferencia,
                                times: List[Time], *, _time_map: dict | None = None) -> None:
        tm = _time_map or {t.nome: t for t in times}
        origem = tm.get(oferta.time_origem)
        destino = tm.get(oferta.time_destino)
        if not origem or not destino:
            return
        jogador = origem.jogador_por_id(oferta.jogador_id)
        if not jogador:
            return

        if oferta.tipo == TipoOferta.COMPRA:
            destino.financas.saldo -= oferta.valor
            origem.financas.saldo += oferta.valor
            origem.jogadores.remove(jogador)
            if jogador.id in origem.titulares:
                origem.titulares.remove(jogador.id)
            if jogador.id in origem.reservas:
                origem.reservas.remove(jogador.id)
            jogador.contrato = ContratoJogador(
                tipo=TipoContrato.PROFISSIONAL,
                salario=oferta.salario_oferecido,
                multa_rescisoria=oferta.valor * 2,
                duracao_meses=random.choice([24, 36, 48, 60]),
                meses_restantes=random.choice([24, 36, 48, 60]),
            )
            jogador.moral = 75
            destino.jogadores.append(jogador)

        elif oferta.tipo == TipoOferta.EMPRESTIMO:
            origem.jogadores.remove(jogador)
            if jogador.id in origem.titulares:
                origem.titulares.remove(jogador.id)
            jogador.contrato = ContratoJogador(
                tipo=TipoContrato.EMPRESTIMO,
                salario=oferta.salario_oferecido,
                duracao_meses=12, meses_restantes=12,
                time_origem=origem.nome,
                clausula_compra=oferta.valor,
            )
            destino.jogadores.append(jogador)

        self.noticias.append(Noticia(
            titulo=f"TRANSFERÊNCIA: {jogador.nome}",
            texto=(f"{jogador.nome} é o novo reforço do {destino.nome}! "
                   f"Veio do {origem.nome} por R$ {oferta.valor:,.0f}."),
            categoria=CategoriaNoticia.TRANSFERENCIA,
        ))
        self.ofertas_historico.append(oferta)

    # ── Contratar livre ───────────────────────────────────────

    def contratar_livre(self, time: Time, jogador: Jogador,
                        salario: int, duracao: int = 24) -> bool:
        if jogador not in self.jogadores_livres:
            return False
        jogador.contrato = ContratoJogador(
            tipo=TipoContrato.PROFISSIONAL,
            salario=salario, multa_rescisoria=salario * 12,
            duracao_meses=duracao, meses_restantes=duracao,
        )
        jogador.moral = 70
        time.jogadores.append(jogador)
        self.jogadores_livres.remove(jogador)
        self.noticias.append(Noticia(
            titulo=f"CONTRATAÇÃO: {jogador.nome}",
            texto=f"{jogador.nome} assinou com o {time.nome} (livre).",
            categoria=CategoriaNoticia.TRANSFERENCIA,
        ))
        return True

    # ── Dispensar ─────────────────────────────────────────────

    def dispensar_jogador(self, time: Time, jogador: Jogador) -> int:
        multa = 0
        if jogador.contrato.meses_restantes > 0:
            multa = jogador.contrato.salario * jogador.contrato.meses_restantes // 2
        if jogador in time.jogadores:
            time.jogadores.remove(jogador)
        if jogador.id in time.titulares:
            time.titulares.remove(jogador.id)
        if jogador.id in time.reservas:
            time.reservas.remove(jogador.id)
        time.financas.saldo -= multa
        jogador.contrato = ContratoJogador()
        self.jogadores_livres.append(jogador)
        return multa

    # ── Renovação ─────────────────────────────────────────────

    @staticmethod
    def renovar_contrato(jogador: Jogador, salario: int,
                         duracao: int, multa: int) -> bool:
        from core.enums import TraitJogador
        chance_recusa = 0.0
        if jogador.moral < 30:
            chance_recusa += 0.6
        if jogador.quer_sair:
            chance_recusa += 0.8
        # Traits afetam disposição
        if jogador.tem_trait(TraitJogador.PROFISSIONAL):
            chance_recusa -= 0.2
        if jogador.tem_trait(TraitJogador.LIDERANCA_NATO):
            chance_recusa -= 0.15
        if jogador.tem_trait(TraitJogador.PANELEIRO):
            chance_recusa += 0.15
        if jogador.tem_trait(TraitJogador.INCONSISTENTE):
            chance_recusa += 0.1
        chance_recusa = max(0.0, min(0.95, chance_recusa))
        if random.random() < chance_recusa:
            return False
        jogador.contrato.salario = salario
        jogador.contrato.duracao_meses = duracao
        jogador.contrato.meses_restantes = duracao
        jogador.contrato.multa_rescisoria = multa
        jogador.moral = min(100, jogador.moral + 10)
        jogador.quer_sair = False
        return True

    # ── IA entre times ────────────────────────────────────────

    def ia_fazer_transferencias(self, times: List[Time]) -> None:
        pool = [
            t for t in times
            if not t.eh_jogador and getattr(t, "divisao", 99) != 5 and len(t.jogadores) >= 18
        ]
        if len(pool) > 72:
            pool = random.sample(pool, 72)

        for time in pool:
            if random.random() > TRANSFER_CHANCE_IA:
                continue
            necessidades = self._identificar_necessidades(time)
            if not necessidades:
                continue
            pos_alvo = random.choice(necessidades)
            vendedores = [
                outro for outro in pool
                if outro != time and len(outro.jogadores) >= 18
            ]
            if len(vendedores) > 12:
                vendedores = random.sample(vendedores, 12)
            for outro in vendedores:
                cands = [j for j in outro.jogadores if j.posicao == pos_alvo]
                if not cands:
                    continue
                alvo = random.choice(cands)
                valor = int(alvo.valor_mercado * random.uniform(0.8, 1.3))
                if valor > time.financas.saldo * 0.4:
                    continue
                # Validar teto salarial: salário não pode exceder 15% da folha atual
                folha_atual = time.folha_salarial
                if folha_atual > 0 and alvo.contrato.salario > folha_atual * 0.15:
                    continue
                oferta = self.fazer_oferta(time, outro, alvo, valor,
                                           alvo.contrato.salario)
                oferta.status = self.avaliar_oferta_ia(oferta, outro, alvo)
                if oferta.status == StatusOferta.ACEITA:
                    self._executar_transferencia(oferta, times)
                    break

    @staticmethod
    def _identificar_necessidades(time: Time) -> List[Posicao]:
        contagem = {pos: 0 for pos in Posicao}
        for j in time.jogadores:
            contagem[j.posicao] += 1
        resultado: List[Posicao] = []
        if contagem[Posicao.GOL] < 2:
            resultado.append(Posicao.GOL)
        for pos in Posicao:
            if pos != Posicao.GOL and contagem[pos] < 2:
                resultado.append(pos)
        return resultado

    # ── Fim de temporada ──────────────────────────────────────

    def fim_temporada_contratos(self, times: List[Time]) -> None:
        time_map = {t.nome: t for t in times}
        for time in times:
            for jogador in time.jogadores[:]:
                jogador.contrato.meses_restantes = max(0, jogador.contrato.meses_restantes - 12)
                if jogador.contrato.meses_restantes <= 0:
                    if jogador.contrato.tipo == TipoContrato.EMPRESTIMO:
                        clausula = getattr(jogador.contrato, 'clausula_compra', 0) or 0
                        dono = time_map.get(jogador.contrato.time_origem)
                        # Exercer cláusula de compra (IA automática)
                        if clausula > 0 and not time.eh_jogador and time.financas.saldo >= clausula:
                            time.financas.saldo -= clausula
                            if dono:
                                dono.financas.saldo += clausula
                            jogador.contrato = ContratoJogador(
                                tipo=TipoContrato.PROFISSIONAL,
                                salario=jogador.contrato.salario,
                                duracao_meses=48, meses_restantes=48,
                            )
                            self.noticias.append(Noticia(
                                titulo=f"COMPRA DEFINITIVA — {jogador.nome}",
                                texto=f"{time.nome} exerceu a cláusula de compra de {jogador.nome} por R$ {clausula:,.0f}.",
                                categoria=CategoriaNoticia.TRANSFERENCIA,
                            ))
                        else:
                            # Devolver ao time de origem
                            time.jogadores.remove(jogador)
                            if dono:
                                dono.jogadores.append(jogador)
                                jogador.contrato = ContratoJogador(
                                    tipo=TipoContrato.PROFISSIONAL,
                                    salario=jogador.contrato.salario,
                                    meses_restantes=12, duracao_meses=12,
                                )
                            else:
                                # Dono não encontrado — jogador vira agente livre
                                jogador.contrato = ContratoJogador()
                                if jogador not in self.jogadores_livres:
                                    self.jogadores_livres.append(jogador)
                    else:
                        time.jogadores.remove(jogador)
                        if jogador.id in time.titulares:
                            time.titulares.remove(jogador.id)
                        if jogador.id in time.reservas:
                            time.reservas.remove(jogador.id)
                        jogador.contrato = ContratoJogador()
                        if jogador not in self.jogadores_livres:
                            self.jogadores_livres.append(jogador)
