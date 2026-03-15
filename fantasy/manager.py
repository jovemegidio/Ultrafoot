# -*- coding: utf-8 -*-
"""Fantasy Manager — orquestra a liga fantasy durante a temporada."""
from __future__ import annotations

import random
from typing import List, Dict, Optional

from fantasy.models import LigaFantasy, TimeFantasy, EscalacaoFantasy
from fantasy.scoring import calcular_pontos_fantasy
from core.models import Time, ResultadoPartida


class FantasyManager:
    """Gerencia uma liga fantasy com participantes CPU e o jogador humano."""

    def __init__(self, nome_liga: str = "Liga Ultrafoot") -> None:
        self.liga = LigaFantasy(nome=nome_liga)

    # ── Inicialização ─────────────────────────────────────────

    def criar_liga(self, times_reais: List[Time],
                   nome_jogador: str = "Meu Fantasy",
                   num_cpus: int = 7) -> None:
        """Cria liga com 1 humano + N CPUs."""
        self.liga.times.clear()

        # Time do jogador humano
        self.liga.times.append(TimeFantasy(
            id=1, nome=nome_jogador, dono="jogador", saldo=100,
        ))

        # Times CPU
        nomes_cpu = [
            "Cartola FC", "Boleiros United", "Gol de Placa",
            "Miteiros FC", "Pelada Stars", "Resenha FC",
            "Caneta FC", "Drible Team", "Hat-trick FC",
            "Golaço Squad",
        ]
        for i in range(num_cpus):
            nome = nomes_cpu[i] if i < len(nomes_cpu) else f"CPU {i + 1}"
            self.liga.times.append(TimeFantasy(
                id=i + 2, nome=nome, dono="cpu", saldo=100,
            ))

        # Auto-escalar CPUs com jogadores aleatórios
        todos_jogadores = []
        for t in times_reais:
            for j in t.jogadores:
                todos_jogadores.append((j, t.nome))

        for tf in self.liga.times:
            if tf.dono == "cpu":
                self._escalar_cpu(tf, todos_jogadores)

    def _escalar_cpu(self, tf: TimeFantasy,
                     pool: List[tuple]) -> None:
        """Escalação automática de CPU — 11 jogadores (1 GOL + 10 linha)."""
        random.shuffle(pool)
        escalados: list[EscalacaoFantasy] = []
        tem_goleiro = False

        for jog, time_nome in pool:
            if len(escalados) >= 11:
                break
            if jog.posicao.name == "GOL" and not tem_goleiro:
                escalados.append(EscalacaoFantasy(
                    jogador_id=jog.id, jogador_nome=jog.nome,
                    time_real=time_nome, posicao=jog.posicao.name,
                ))
                tem_goleiro = True
            elif jog.posicao.name != "GOL" and len(escalados) < 11:
                escalados.append(EscalacaoFantasy(
                    jogador_id=jog.id, jogador_nome=jog.nome,
                    time_real=time_nome, posicao=jog.posicao.name,
                ))

        # Capitão = jogador com id mais alto (proxy para "melhor")
        if escalados:
            escalados[0].capitao = True

        tf.escalacao = escalados

    # ── Processamento de rodada ───────────────────────────────

    def processar_rodada(self, resultados: List[ResultadoPartida],
                         times_casa: List[Time],
                         times_fora: List[Time]) -> None:
        """Processa todos os resultados de uma rodada e atualiza pontuações."""
        # Consolidar pontos fantasy de todos os jogos
        pontos_globais: Dict[int, float] = {}
        for res, tc, tf in zip(resultados, times_casa, times_fora):
            pts_jogo = calcular_pontos_fantasy(res, tc, tf)
            for jid, pts in pts_jogo.items():
                pontos_globais[jid] = pontos_globais.get(jid, 0.0) + pts

        self.liga.rodada_atual += 1

        # Calcular pontuação de cada time fantasy
        for tf in self.liga.times:
            rodada_pts = 0.0
            for esc in tf.escalacao:
                base = pontos_globais.get(esc.jogador_id, 0.0)
                esc.pontos = base * 2 if esc.capitao else base
                rodada_pts += esc.pontos

            tf.pontos_rodada = round(rodada_pts, 1)
            tf.pontos_total = round(tf.pontos_total + rodada_pts, 1)
            tf.historico_rodadas.append(tf.pontos_rodada)

    # ── API para a UI ─────────────────────────────────────────

    def classificacao(self) -> List[TimeFantasy]:
        return self.liga.classificacao()

    def time_jogador(self) -> Optional[TimeFantasy]:
        for t in self.liga.times:
            if t.dono == "jogador":
                return t
        return None

    def escalar_jogador(self, time_fantasy_id: int,
                        escalacao: List[EscalacaoFantasy]) -> bool:
        """Define a escalação do time fantasy do jogador humano."""
        tf = self.liga.time_por_id(time_fantasy_id)
        if tf is None or tf.dono != "jogador":
            return False
        if len(escalacao) != 11:
            return False
        tf.escalacao = escalacao
        return True
