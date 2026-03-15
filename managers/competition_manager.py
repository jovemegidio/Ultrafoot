# -*- coding: utf-8 -*-
"""
Gerenciador de competições: Brasileirão, Copa, Libertadores, Estadual.
Migrado do legacy competicoes.py com melhorias de organização.
"""
from __future__ import annotations

import random
from typing import List, Dict, Tuple, Optional

from core.models import Time, ResultadoPartida, Noticia
from core.enums import CategoriaNoticia
from engine.match_engine import MotorPartida
from utils.logger import get_logger

log = get_logger(__name__)


# ══════════════════════════════════════════════════════════════
#  CAMPEONATO (pontos corridos)
# ══════════════════════════════════════════════════════════════

class Campeonato:
    def __init__(self, nome: str, times: List[Time], turno_e_returno: bool = True):
        self.nome = nome
        self.times = times
        self.turno_e_returno = turno_e_returno
        self.rodada_atual = 0
        self.jogos: List[List[Tuple[int, int]]] = []
        self.resultados: List[List[ResultadoPartida]] = []
        self.encerrado = False
        self.motor = MotorPartida()
        # Per-competition standings (independent of global team stats)
        self._stats: Dict[int, Dict] = {
            t.id: {"pontos": 0, "v": 0, "e": 0, "d": 0, "gm": 0, "gs": 0}
            for t in times
        }
        self._gerar_tabela()

    def _gerar_tabela(self) -> None:
        ids = [t.id for t in self.times]
        n = len(ids)
        if n % 2 != 0:
            ids.append(-1)
            n += 1

        rotacao = ids[1:]
        rodadas_turno: List[List[Tuple[int, int]]] = []
        for r in range(n - 1):
            rodada: List[Tuple[int, int]] = []
            for i in range(n // 2):
                c = ids[0] if i == 0 else rotacao[i - 1]
                f = rotacao[n - 2 - i]
                if c == -1 or f == -1:
                    continue
                if r % 2 == 0:
                    rodada.append((c, f))
                else:
                    rodada.append((f, c))
            rodadas_turno.append(rodada)
            rotacao = [rotacao[-1]] + rotacao[:-1]

        self.jogos = rodadas_turno[:]
        if self.turno_e_returno:
            self.jogos += [[(f, c) for c, f in rd] for rd in rodadas_turno]

    @property
    def total_rodadas(self) -> int:
        return len(self.jogos)

    def _time_por_id(self, tid: int) -> Optional[Time]:
        for t in self.times:
            if t.id == tid:
                return t
        return None

    def jogar_rodada(self) -> List[ResultadoPartida]:
        if self.rodada_atual >= len(self.jogos):
            self.encerrado = True
            return []
        rodada = self.jogos[self.rodada_atual]
        resultados_rodada: List[ResultadoPartida] = []
        for c_id, f_id in rodada:
            c = self._time_por_id(c_id)
            f = self._time_por_id(f_id)
            if c and f:
                r = self.motor.simular(c, f)
                resultados_rodada.append(r)
                # Update per-competition standings
                sc = self._stats.get(c.id)
                sf = self._stats.get(f.id)
                if sc:
                    sc["gm"] += r.gols_casa; sc["gs"] += r.gols_fora
                if sf:
                    sf["gm"] += r.gols_fora; sf["gs"] += r.gols_casa
                if r.gols_casa > r.gols_fora:
                    if sc: sc["v"] += 1; sc["pontos"] += 3
                    if sf: sf["d"] += 1
                elif r.gols_casa < r.gols_fora:
                    if sf: sf["v"] += 1; sf["pontos"] += 3
                    if sc: sc["d"] += 1
                else:
                    if sc: sc["e"] += 1; sc["pontos"] += 1
                    if sf: sf["e"] += 1; sf["pontos"] += 1
        self.resultados.append(resultados_rodada)
        self.rodada_atual += 1
        if self.rodada_atual >= len(self.jogos):
            self.encerrado = True
        return resultados_rodada

    def get_stats(self, time_id: int) -> Dict:
        """Get per-competition stats for a team."""
        return self._stats.get(time_id, {"pontos": 0, "v": 0, "e": 0, "d": 0, "gm": 0, "gs": 0})

    def classificacao(self) -> List[Time]:
        return sorted(self.times,
                      key=lambda t: (
                          self._stats.get(t.id, {}).get("pontos", 0),
                          self._stats.get(t.id, {}).get("gm", 0) - self._stats.get(t.id, {}).get("gs", 0),
                          self._stats.get(t.id, {}).get("gm", 0),
                          self._stats.get(t.id, {}).get("v", 0),
                      ),
                      reverse=True)

    def jogo_do_jogador(self, time_jogador: Time) -> Optional[Tuple[Time, Time]]:
        if self.rodada_atual >= len(self.jogos):
            return None
        for c_id, f_id in self.jogos[self.rodada_atual]:
            if c_id == time_jogador.id or f_id == time_jogador.id:
                return self._time_por_id(c_id), self._time_por_id(f_id)
        return None


# ══════════════════════════════════════════════════════════════
#  COPA (mata-mata com ida e volta)
# ══════════════════════════════════════════════════════════════

class Copa:
    def __init__(self, nome: str, times: List[Time], seeded: bool = False,
                 ida_e_volta: bool = True, gol_fora: bool = True):
        self.nome = nome
        self.times_originais = times[:]
        self.fase_atual = 0
        self.fases: List[str] = []
        self.confrontos: List[List[Tuple[Optional[Time], Optional[Time]]]] = []
        self.resultados_ida: List[List[ResultadoPartida]] = []
        self.resultados_volta: List[List[ResultadoPartida]] = []
        self.classificados: List[List[Time]] = []
        self.campeao: Optional[Time] = None
        self.encerrado = False
        self.motor = MotorPartida()
        self.jogo_ida = True
        self._seeded = seeded
        self.ida_e_volta = ida_e_volta
        self.gol_fora = gol_fora
        self._gerar_chaveamento()

    def _gerar_chaveamento(self) -> None:
        times = self.times_originais[:]
        if not self._seeded:
            random.shuffle(times)
        # If seeded, times are already ordered: top seeds first.
        # Pair top seeds against bottom seeds (like real tournaments).
        n = 1
        while n < len(times):
            n *= 2
        while len(times) < n:
            times.append(None)

        if self._seeded:
            # Seeded bracket: top seeds get byes / face lowest seeds
            # Place seeds so they only meet in later rounds
            ordered = [None] * n
            ordered[0] = times[0]
            ordered[n - 1] = times[1] if len(self.times_originais) > 1 else None
            # Fill remaining using standard seeding pattern
            positions = list(range(n))
            filled = {0, n - 1}
            for seed_idx in range(2, len(self.times_originais)):
                # Find the slot that maximizes distance from other seeds
                best_pos = None
                best_min_dist = -1
                for p in positions:
                    if p in filled:
                        continue
                    min_dist = min(abs(p - f) for f in filled)
                    if min_dist > best_min_dist:
                        best_min_dist = min_dist
                        best_pos = p
                if best_pos is not None:
                    ordered[best_pos] = times[seed_idx]
                    filled.add(best_pos)
            times = ordered

        nomes_fases = {1: "Final", 2: "Semifinal", 4: "Quartas de Final",
                       8: "Oitavas de Final", 16: "Terceira Fase",
                       32: "Segunda Fase", 64: "Primeira Fase"}
        f = n // 2
        while f >= 1:
            self.fases.append(nomes_fases.get(f, f"Fase de {f*2}"))
            f //= 2
        confrontos: List[Tuple[Optional[Time], Optional[Time]]] = []
        for i in range(0, len(times), 2):
            t1 = times[i]
            t2 = times[i + 1] if i + 1 < len(times) else None
            confrontos.append((t1, t2))
        self.confrontos.append(confrontos)

    @property
    def fase_nome(self) -> str:
        if self.fase_atual < len(self.fases):
            return self.fases[self.fase_atual]
        return "Final"

    def jogo_do_jogador(self, time_jogador: Time) -> Optional[Tuple[Time, Time]]:
        """Retorna o confronto (casa, fora) do time do jogador na fase atual, ou None."""
        if self.encerrado or self.fase_atual >= len(self.confrontos):
            return None
        for t1, t2 in self.confrontos[self.fase_atual]:
            if t1 and t1.id == time_jogador.id:
                if t2:
                    return (t1, t2) if self.jogo_ida else (t2, t1)
                return None
            if t2 and t2.id == time_jogador.id:
                if t1:
                    return (t1, t2) if self.jogo_ida else (t2, t1)
                return None
        return None

    def jogar_fase_ida(self) -> List[ResultadoPartida]:
        if self.encerrado:
            return []
        resultados: List[ResultadoPartida] = []
        for t1, t2 in self.confrontos[self.fase_atual]:
            if t1 and t2:
                resultados.append(self.motor.simular(t1, t2))
        self.resultados_ida.append(resultados)
        if not self.ida_e_volta:
            self.classificados.append(self._resolver_classificados_ida(resultados))
            self._avancar_fase(self.classificados[-1])
            return resultados
        self.jogo_ida = False
        return resultados

    def _resolver_classificados_ida(self, resultados: List[ResultadoPartida]) -> List[Time]:
        classificados_fase: List[Time] = []
        por_confronto = {
            (r.time_casa, r.time_fora): r
            for r in resultados
        }
        for t1, t2 in self.confrontos[self.fase_atual]:
            if t1 is None and t2 is None:
                continue
            if t2 is None:
                if t1:
                    classificados_fase.append(t1)
                continue
            if t1 is None:
                classificados_fase.append(t2)
                continue
            res = por_confronto.get((t1.nome, t2.nome))
            if not res:
                classificados_fase.append(t1)
                continue
            if res.gols_casa > res.gols_fora:
                classificados_fase.append(t1)
            elif res.gols_fora > res.gols_casa:
                classificados_fase.append(t2)
            else:
                classificados_fase.append(random.choice([t1, t2]))
        return classificados_fase

    def _avancar_fase(self, classificados_fase: List[Time]) -> None:
        self.fase_atual += 1
        self.jogo_ida = True

        if not classificados_fase:
            self.encerrado = True
            return
        if len(classificados_fase) == 1:
            self.campeao = classificados_fase[0]
            self.encerrado = True
            return

        novos: List[Tuple[Optional[Time], Optional[Time]]] = []
        for i in range(0, len(classificados_fase), 2):
            a = classificados_fase[i]
            b = classificados_fase[i + 1] if i + 1 < len(classificados_fase) else None
            novos.append((a, b))
        self.confrontos.append(novos)

    def jogar_fase_volta(self) -> List[ResultadoPartida]:
        if self.encerrado:
            return []
        confrontos = self.confrontos[self.fase_atual]
        resultados: List[ResultadoPartida] = []
        classificados_fase: List[Time] = []

        for idx, (t1, t2) in enumerate(confrontos):
            if t1 is None and t2 is None:
                continue
            if t2 is None:
                if t1:
                    classificados_fase.append(t1)
                continue
            if t1 is None:
                classificados_fase.append(t2)
                continue
            resultado = self.motor.simular(t2, t1, neutro=False)
            resultados.append(resultado)

            ida = self.resultados_ida[self.fase_atual]
            res_ida = None
            for r in ida:
                if r.time_casa == t1.nome and r.time_fora == t2.nome:
                    res_ida = r
                    break

            if res_ida:
                g1 = res_ida.gols_casa + resultado.gols_fora
                g2 = res_ida.gols_fora + resultado.gols_casa
                if g1 > g2:
                    classificados_fase.append(t1)
                elif g2 > g1:
                    classificados_fase.append(t2)
                elif self.gol_fora:
                    gf1 = resultado.gols_fora
                    gf2 = res_ida.gols_fora
                    if gf1 > gf2:
                        classificados_fase.append(t1)
                    elif gf2 > gf1:
                        classificados_fase.append(t2)
                    else:
                        classificados_fase.append(random.choice([t1, t2]))
                else:
                    # Sem gol fora: empate no agregado vai direto para penaltis (random)
                    classificados_fase.append(random.choice([t1, t2]))
            else:
                classificados_fase.append(t1)

        self.resultados_volta.append(resultados)
        self.classificados.append(classificados_fase)
        self._avancar_fase(classificados_fase)
        return resultados


# ══════════════════════════════════════════════════════════════
#  CAMPEONATO COM GRUPOS (Série D)
# ══════════════════════════════════════════════════════════════

class CampeonatoComGrupos:
    """Competição com fase de grupos (turno simples) + mata-mata.
    Baseado na configuração do Brasfoot: 8 grupos, top 4 por grupo → knockout."""

    def __init__(self, nome: str, times: List[Time], n_grupos: int = 8,
                 classificados_por_grupo: int = 4,
                 turno_e_returno_grupos: bool = False,
                 mata_mata_ida_e_volta: bool = True):
        self.nome = nome
        self.times = times
        self.n_grupos = n_grupos
        self.classificados_por_grupo = classificados_por_grupo
        self._turno_e_returno_grupos = turno_e_returno_grupos
        self._mata_mata_ida_e_volta = mata_mata_ida_e_volta
        self.grupos: List[Campeonato] = []
        self.mata_mata: Optional[Copa] = None
        self.campeao: Optional[Time] = None
        self.encerrado = False
        self._em_mata_mata = False
        self.rodada_atual = 0
        self.motor = MotorPartida()
        self._criar_grupos()

    def _criar_grupos(self) -> None:
        ts = self.times[:]
        random.shuffle(ts)
        base = len(ts) // self.n_grupos
        extra = len(ts) % self.n_grupos
        idx = 0
        for g in range(self.n_grupos):
            size = base + (1 if g < extra else 0)
            grupo_times = ts[idx:idx + size]
            idx += size
            camp = Campeonato(f"{self.nome} - Grupo {chr(65 + g)}",
                              grupo_times, turno_e_returno=self._turno_e_returno_grupos)
            self.grupos.append(camp)

    @property
    def total_rodadas(self) -> int:
        if self.grupos:
            return max(g.total_rodadas for g in self.grupos)
        return 0

    @property
    def jogos(self) -> List[List[Tuple[int, int]]]:
        """Retorna todos os jogos (para agenda)."""
        all_jogos: List[List[Tuple[int, int]]] = []
        for g in self.grupos:
            for r, rodada in enumerate(g.jogos):
                while len(all_jogos) <= r:
                    all_jogos.append([])
                all_jogos[r].extend(rodada)
        return all_jogos

    @property
    def resultados(self) -> List[List[ResultadoPartida]]:
        """Retorna resultados agregados de todos os grupos (para agenda)."""
        all_res: List[List[ResultadoPartida]] = []
        for g in self.grupos:
            for r, rod_res in enumerate(g.resultados):
                while len(all_res) <= r:
                    all_res.append([])
                all_res[r].extend(rod_res)
        return all_res

    def _time_por_id(self, tid: int) -> Optional[Time]:
        for t in self.times:
            if t.id == tid:
                return t
        return None

    def classificacao(self) -> List[Time]:
        """Classificação geral (todos os times, agregando stats dos grupos)."""
        # Build aggregated stats from each grupo's per-competition _stats
        agg: Dict[int, Dict] = {}
        for g in self.grupos:
            for t in g.times:
                s = g.get_stats(t.id)
                if t.id not in agg:
                    agg[t.id] = {"pontos": 0, "v": 0, "e": 0, "d": 0, "gm": 0, "gs": 0}
                for k in agg[t.id]:
                    agg[t.id][k] += s.get(k, 0)
        return sorted(self.times,
                      key=lambda t: (
                          agg.get(t.id, {}).get("pontos", 0),
                          agg.get(t.id, {}).get("gm", 0) - agg.get(t.id, {}).get("gs", 0),
                          agg.get(t.id, {}).get("gm", 0),
                          agg.get(t.id, {}).get("v", 0),
                      ),
                      reverse=True)

    def classificacao_grupo(self, idx: int) -> List[Time]:
        if 0 <= idx < len(self.grupos):
            return self.grupos[idx].classificacao()
        return []

    def jogar_rodada(self) -> List[ResultadoPartida]:
        if self.encerrado:
            return []

        if not self._em_mata_mata:
            # Fase de grupos
            todos_encerrados = True
            resultados: List[ResultadoPartida] = []
            for g in self.grupos:
                if not g.encerrado:
                    resultados.extend(g.jogar_rodada())
                    todos_encerrados = False
            self.rodada_atual += 1
            if todos_encerrados:
                self._iniciar_mata_mata()
            return resultados
        else:
            return self._jogar_mata_mata()

    def _iniciar_mata_mata(self) -> None:
        classificados: List[Time] = []
        for g in self.grupos:
            top = g.classificacao()[:self.classificados_por_grupo]
            classificados.extend(top)
        if len(classificados) >= 2:
            self.mata_mata = Copa(
                f"{self.nome} - Mata-Mata",
                classificados,
                ida_e_volta=self._mata_mata_ida_e_volta,
            )
            self._em_mata_mata = True
        else:
            if classificados:
                self.campeao = classificados[0]
            self.encerrado = True

    def _jogar_mata_mata(self) -> List[ResultadoPartida]:
        if not self.mata_mata or self.mata_mata.encerrado:
            if self.mata_mata and self.mata_mata.campeao:
                self.campeao = self.mata_mata.campeao
            self.encerrado = True
            return []
        if self.mata_mata.jogo_ida:
            return self.mata_mata.jogar_fase_ida()
        else:
            return self.mata_mata.jogar_fase_volta()

    def jogo_do_jogador(self, time_jogador: Time) -> Optional[Tuple[Time, Time]]:
        if not self._em_mata_mata:
            for g in self.grupos:
                r = g.jogo_do_jogador(time_jogador)
                if r:
                    return r
        elif self.mata_mata:
            return self.mata_mata.jogo_do_jogador(time_jogador)
        return None


class Libertadores(CampeonatoComGrupos):
    """CONMEBOL Libertadores — formato real: 8 grupos de 4, turno e returno, top 2 → mata-mata."""
    def __init__(self, times: List[Time]):
        super().__init__("CONMEBOL Libertadores", times,
                         n_grupos=8, classificados_por_grupo=2,
                         turno_e_returno_grupos=True)


class SulAmericana(CampeonatoComGrupos):
    """CONMEBOL Sul-Americana — formato real: 8 grupos de 4, turno e returno, top 2 → mata-mata."""
    def __init__(self, times: List[Time]):
        super().__init__("CONMEBOL Sul-Americana", times,
                         n_grupos=8, classificados_por_grupo=2,
                         turno_e_returno_grupos=True)


# ══════════════════════════════════════════════════════════════
#  ESTADUAL
# ══════════════════════════════════════════════════════════════

# Limite realista de times por estado (primeira divisão)
ESTADUAL_MAX_TIMES: Dict[str, int] = {
    "SP": 16, "RJ": 12, "MG": 12, "RS": 12, "PR": 12,
    "SC": 12, "BA": 12, "PE": 10, "CE": 10, "GO": 10,
    "PA": 10, "ES": 10, "DF": 10, "AM": 10, "MA": 10,
}
_ESTADUAL_DEFAULT_MAX = 10

# Formato específico por estado (2026)
# tipo: "grupos" = fase de grupos + mata-mata (ex: Paulistão)
#       "pontos_corridos" = turno (ou turno+returno) + mata-mata (padrão)
ESTADUAL_FORMATO: Dict[str, Dict] = {
    # Paulistão 2026 — tabela única, 8 rodadas, top 8 → mata-mata
    "SP": {
        "n_classificados": 8,
        "n_rebaixados": 2,
        "max_rodadas": 8,
    },
    # Cariocão 2026 — 2 grupos de 6, jogos cruzados (intergrupos),
    # top 4 por grupo → quartas.
    "RJ": {
        "tipo": "intergrupos",
        "n_grupos": 2,
        "classificados_por_grupo": 4,
        "n_rebaixados": 1,
    },
    # Mineiro 2026 — 3 grupos de 4, intergrupos (8 jogos),
    # líderes + melhor 2º → semis, final jogo único.
    "MG": {
        "tipo": "intergrupos",
        "n_grupos": 3,
        "n_rebaixados": 2,
    },
    # Gauchão 2026 — 2 grupos de 6, dentro do grupo (round-robin),
    # top 4 por grupo → quartas.
    "RS": {
        "tipo": "grupos",
        "n_grupos": 2,
        "classificados_por_grupo": 4,
        "n_rebaixados": 2,
    },
    # Paranaense — turno único, top 4 → semis
    "PR": {"n_classificados": 4, "n_rebaixados": 2},
    # Catarinense — 2 grupos de 6, top 4 por grupo → quartas
    "SC": {
        "tipo": "grupos",
        "n_grupos": 2,
        "classificados_por_grupo": 4,
        "n_rebaixados": 2,
    },
    # Bahiano — 2 grupos de 6, top 4 por grupo → quartas
    "BA": {
        "tipo": "grupos",
        "n_grupos": 2,
        "classificados_por_grupo": 4,
        "n_rebaixados": 2,
    },
    # Pernambucano — turno único, top 4 → semis
    "PE": {"n_classificados": 4, "n_rebaixados": 2},
    # Cearense — 2 grupos de 5, top 2 por grupo → semis
    "CE": {
        "tipo": "grupos",
        "n_grupos": 2,
        "classificados_por_grupo": 2,
        "n_rebaixados": 2,
    },
    # Goiano — 2 grupos de 5, jogos cruzados (intergrupos)
    "GO": {
        "tipo": "intergrupos",
        "n_grupos": 2,
        "classificados_por_grupo": 2,
        "n_rebaixados": 2,
    },
}


class GruposEstadual:
    """Fase de grupos para estaduais no estilo Paulistão.

    Provê a mesma interface de ``Campeonato`` para que o resto do código
    (desktop_app, save_manager) possa usá-la de forma transparente.
    """

    def __init__(self, nome: str, times: List[Time], n_grupos: int = 4,
                 turno_e_returno: bool = False):
        self.nome = nome
        self.times = times
        self.n_grupos = n_grupos
        self._turno_e_returno = turno_e_returno
        self.grupos: List[Campeonato] = []
        self.encerrado = False
        self.rodada_atual = 0
        self._criar_grupos()

    def _criar_grupos(self) -> None:
        ts = self.times[:]
        random.shuffle(ts)
        base = len(ts) // self.n_grupos
        extra = len(ts) % self.n_grupos
        idx = 0
        for g in range(self.n_grupos):
            size = base + (1 if g < extra else 0)
            grupo_times = ts[idx:idx + size]
            idx += size
            camp = Campeonato(f"{self.nome} - Grupo {chr(65 + g)}",
                              grupo_times, turno_e_returno=self._turno_e_returno)
            self.grupos.append(camp)

    @property
    def total_rodadas(self) -> int:
        return max(g.total_rodadas for g in self.grupos) if self.grupos else 0

    @property
    def jogos(self) -> List[List[Tuple[int, int]]]:
        all_jogos: List[List[Tuple[int, int]]] = []
        for g in self.grupos:
            for r, rodada in enumerate(g.jogos):
                while len(all_jogos) <= r:
                    all_jogos.append([])
                all_jogos[r].extend(rodada)
        return all_jogos

    @property
    def resultados(self) -> List[List[ResultadoPartida]]:
        all_res: List[List[ResultadoPartida]] = []
        for g in self.grupos:
            for r, rod_res in enumerate(g.resultados):
                while len(all_res) <= r:
                    all_res.append([])
                all_res[r].extend(rod_res)
        return all_res

    def _time_por_id(self, tid: int) -> Optional[Time]:
        for t in self.times:
            if t.id == tid:
                return t
        return None

    def get_stats(self, tid: int) -> Dict:
        """Retorna stats do time em seu grupo."""
        for g in self.grupos:
            for t in g.times:
                if t.id == tid:
                    return g.get_stats(tid)
        return {"pontos": 0, "v": 0, "e": 0, "d": 0, "gm": 0, "gs": 0}

    def classificacao(self) -> List[Time]:
        """Classificação geral agregando stats de todos os grupos."""
        agg: Dict[int, Dict] = {}
        for g in self.grupos:
            for t in g.times:
                agg[t.id] = g.get_stats(t.id)
        return sorted(self.times,
                      key=lambda t: (
                          agg.get(t.id, {}).get("pontos", 0),
                          agg.get(t.id, {}).get("gm", 0) - agg.get(t.id, {}).get("gs", 0),
                          agg.get(t.id, {}).get("gm", 0),
                          agg.get(t.id, {}).get("v", 0),
                      ), reverse=True)

    def classificacao_grupo(self, idx: int) -> List[Time]:
        if 0 <= idx < len(self.grupos):
            return self.grupos[idx].classificacao()
        return []

    def jogar_rodada(self) -> List[ResultadoPartida]:
        if self.encerrado:
            return []
        todos_encerrados = True
        resultados: List[ResultadoPartida] = []
        for g in self.grupos:
            if not g.encerrado:
                resultados.extend(g.jogar_rodada())
                todos_encerrados = False
        self.rodada_atual += 1
        if todos_encerrados:
            self.encerrado = True
        return resultados

    def jogo_do_jogador(self, time_jogador: Time) -> Optional[Tuple[Time, Time]]:
        for g in self.grupos:
            r = g.jogo_do_jogador(time_jogador)
            if r:
                return r
        return None


class GruposIntergrupais:
    """Fase de grupos com jogos intergrupos (ex: Campeonato Mineiro 2026).

    Times são divididos em N grupos, mas cada time joga contra os adversários
    de OUTROS grupos.  Classificação é por grupo baseada nos resultados
    intergrupos.
    """

    def __init__(self, nome: str, times: List[Time], n_grupos: int = 3):
        self.nome = nome
        self.times = times
        self.n_grupos = n_grupos
        self.encerrado = False
        self.rodada_atual = 0
        self.motor = MotorPartida()
        self.grupos_times: List[List[Time]] = []
        self.jogos: List[List[Tuple[int, int]]] = []
        self.resultados: List[List[ResultadoPartida]] = []
        self._stats: Dict[int, Dict] = {
            t.id: {"pontos": 0, "v": 0, "e": 0, "d": 0, "gm": 0, "gs": 0}
            for t in times
        }
        self._criar_grupos()
        self._gerar_calendario()

    # ── Criação de grupos ──
    def _criar_grupos(self) -> None:
        ts = self.times[:]
        random.shuffle(ts)
        base = len(ts) // self.n_grupos
        extra = len(ts) % self.n_grupos
        idx = 0
        for g in range(self.n_grupos):
            size = base + (1 if g < extra else 0)
            self.grupos_times.append(ts[idx:idx + size])
            idx += size

    def _grupo_do_time(self, tid: int) -> int:
        for gi, grp in enumerate(self.grupos_times):
            for t in grp:
                if t.id == tid:
                    return gi
        return -1

    # ── Geração de calendário intergrupos ──
    def _gerar_calendario(self) -> None:
        all_matches: List[Tuple[int, int]] = []
        for gi in range(len(self.grupos_times)):
            for gj in range(gi + 1, len(self.grupos_times)):
                for ti in self.grupos_times[gi]:
                    for tj in self.grupos_times[gj]:
                        all_matches.append((ti.id, tj.id))
        random.shuffle(all_matches)

        n_per_round = len(self.times) // 2
        n_rounds = len(all_matches) // n_per_round if n_per_round else 1
        if n_rounds * n_per_round < len(all_matches):
            n_rounds += 1

        rounds: List[List[Tuple[int, int]]] = [[] for _ in range(n_rounds)]
        used: List[set] = [set() for _ in range(n_rounds)]

        for m in all_matches:
            for r in range(n_rounds):
                if (m[0] not in used[r] and m[1] not in used[r]
                        and len(rounds[r]) < n_per_round):
                    rounds[r].append(m)
                    used[r].add(m[0])
                    used[r].add(m[1])
                    break
            else:
                for r in range(n_rounds):
                    if len(rounds[r]) < n_per_round:
                        rounds[r].append(m)
                        break

        self.jogos = [r for r in rounds if r]
        self.resultados = []

    @property
    def total_rodadas(self) -> int:
        return len(self.jogos)

    def _time_por_id(self, tid: int) -> Optional[Time]:
        for t in self.times:
            if t.id == tid:
                return t
        return None

    def jogar_rodada(self) -> List[ResultadoPartida]:
        if self.rodada_atual >= len(self.jogos):
            self.encerrado = True
            return []
        rodada = self.jogos[self.rodada_atual]
        resultados_rodada: List[ResultadoPartida] = []
        for c_id, f_id in rodada:
            c = self._time_por_id(c_id)
            f = self._time_por_id(f_id)
            if c and f:
                r = self.motor.simular(c, f)
                resultados_rodada.append(r)
                sc = self._stats.get(c.id)
                sf = self._stats.get(f.id)
                if sc:
                    sc["gm"] += r.gols_casa
                    sc["gs"] += r.gols_fora
                if sf:
                    sf["gm"] += r.gols_fora
                    sf["gs"] += r.gols_casa
                if r.gols_casa > r.gols_fora:
                    if sc: sc["v"] += 1; sc["pontos"] += 3
                    if sf: sf["d"] += 1
                elif r.gols_casa < r.gols_fora:
                    if sf: sf["v"] += 1; sf["pontos"] += 3
                    if sc: sc["d"] += 1
                else:
                    if sc: sc["e"] += 1; sc["pontos"] += 1
                    if sf: sf["e"] += 1; sf["pontos"] += 1
        self.resultados.append(resultados_rodada)
        self.rodada_atual += 1
        if self.rodada_atual >= len(self.jogos):
            self.encerrado = True
        return resultados_rodada

    def get_stats(self, tid: int) -> Dict:
        return self._stats.get(tid, {"pontos": 0, "v": 0, "e": 0, "d": 0, "gm": 0, "gs": 0})

    def classificacao(self) -> List[Time]:
        return sorted(self.times, key=lambda t: (
            self._stats.get(t.id, {}).get("pontos", 0),
            self._stats.get(t.id, {}).get("gm", 0) - self._stats.get(t.id, {}).get("gs", 0),
            self._stats.get(t.id, {}).get("gm", 0),
            self._stats.get(t.id, {}).get("v", 0),
        ), reverse=True)

    def classificacao_grupo(self, idx: int) -> List[Time]:
        if 0 <= idx < len(self.grupos_times):
            return sorted(self.grupos_times[idx], key=lambda t: (
                self._stats.get(t.id, {}).get("pontos", 0),
                self._stats.get(t.id, {}).get("gm", 0) - self._stats.get(t.id, {}).get("gs", 0),
                self._stats.get(t.id, {}).get("gm", 0),
                self._stats.get(t.id, {}).get("v", 0),
            ), reverse=True)
        return []

    def jogo_do_jogador(self, time_jogador: Time) -> Optional[Tuple[Time, Time]]:
        if self.rodada_atual >= len(self.jogos):
            return None
        for c_id, f_id in self.jogos[self.rodada_atual]:
            if time_jogador.id in (c_id, f_id):
                return self._time_por_id(c_id), self._time_por_id(f_id)
        return None


class CampeonatoEstadual:
    """Campeonato estadual com formato configurável por estado.

    Formatos suportados (via ``ESTADUAL_FORMATO``):
    - **grupos** (Paulistão): 4 grupos de 4, top 2/grupo → quartas.
    - **pontos_corridos** (padrão): turno único ou turno+returno + mata-mata.

    Mata-mata sempre ida e volta, sem gol qualificado fora de casa.
    Melhor campanha decide em casa (jogo de volta).
    """
    def __init__(self, nome: str, estado: str, times: List[Time]):
        self.nome = nome
        self.estado = estado
        todos_estado = [t for t in times if t.estado == estado]
        max_times = ESTADUAL_MAX_TIMES.get(estado, _ESTADUAL_DEFAULT_MAX)
        todos_estado.sort(key=lambda t: t.prestigio, reverse=True)
        self.times = todos_estado[:max_times]
        self.campeao: Optional[Time] = None
        self.vice: Optional[Time] = None
        self.rebaixados: List[Time] = []
        self.encerrado = False
        self.fase_grupos = None  # Campeonato ou GruposEstadual
        self.mata_mata: Optional[Copa] = None
        self._em_mata_mata = False
        self._usa_grupos = False  # True quando formato é "grupos" ou "intergrupos"
        self._usa_intergrupos = False  # True quando formato é "intergrupos"

        fmt = ESTADUAL_FORMATO.get(estado, {})
        tipo = fmt.get("tipo", "pontos_corridos")
        self._n_rebaixados = fmt.get("n_rebaixados", min(2, max(0, len(self.times) - 4)))
        self._n_classificados = fmt.get("n_classificados", 8 if len(self.times) >= 8 else min(4, len(self.times)))
        self._max_rodadas = fmt.get("max_rodadas", 0)  # 0 = sem limite
        self._classificados_por_grupo = fmt.get("classificados_por_grupo", 0)
        turno_e_returno = fmt.get("turno_e_returno", False)

        if len(self.times) < 2:
            self.encerrado = True
        elif tipo == "intergrupos" and len(self.times) >= 6:
            n_grupos = fmt.get("n_grupos", 3)
            self._usa_grupos = True
            self._usa_intergrupos = True
            self.fase_grupos = GruposIntergrupais(
                f"{nome} - Fase de Grupos", self.times,
                n_grupos=n_grupos,
            )
        elif tipo == "grupos" and len(self.times) >= 8:
            n_grupos = fmt.get("n_grupos", 4)
            self._usa_grupos = True
            self.fase_grupos = GruposEstadual(
                f"{nome} - Fase de Grupos", self.times,
                n_grupos=n_grupos, turno_e_returno=turno_e_returno,
            )
        elif len(self.times) >= 2:
            self.fase_grupos = Campeonato(
                f"{nome} - Classificatória", self.times,
                turno_e_returno=turno_e_returno,
            )

    @property
    def semifinal(self) -> Optional[Copa]:
        """Backward compat alias."""
        return self.mata_mata

    def jogar_rodada(self) -> List[ResultadoPartida]:
        if self.encerrado:
            return []

        if not self._em_mata_mata:
            if self.fase_grupos and not self.fase_grupos.encerrado:
                resultado = self.fase_grupos.jogar_rodada()
                # Limitar rodadas (ex: Paulistão 8 rodadas de 15 possíveis)
                if self._max_rodadas and hasattr(self.fase_grupos, 'rodada_atual'):
                    if self.fase_grupos.rodada_atual >= self._max_rodadas:
                        self.fase_grupos.encerrado = True
                return resultado
            elif self.fase_grupos and self.fase_grupos.encerrado and not self._em_mata_mata:
                self._iniciar_mata_mata()
                return self._jogar_mata_mata()
        else:
            return self._jogar_mata_mata()

        return []

    def _iniciar_mata_mata(self) -> None:
        if not self.fase_grupos:
            return

        if self._usa_intergrupos and isinstance(self.fase_grupos, GruposIntergrupais):
            cpg = self._classificados_por_grupo
            if cpg > 0:
                # Top N de cada grupo (ex: Cariocão top 4/grupo)
                top: List[Time] = []
                for gi in range(self.fase_grupos.n_grupos):
                    classif_g = self.fase_grupos.classificacao_grupo(gi)
                    top.extend(classif_g[:cpg])
            else:
                # Líderes + melhor 2º colocado (ex: Mineiro)
                top: List[Time] = []
                segundos: List[Time] = []
                for gi in range(self.fase_grupos.n_grupos):
                    classif_g = self.fase_grupos.classificacao_grupo(gi)
                    if classif_g:
                        top.append(classif_g[0])
                    if len(classif_g) >= 2:
                        segundos.append(classif_g[1])
                if segundos:
                    segundos.sort(key=lambda t: (
                        self.fase_grupos.get_stats(t.id).get("pontos", 0),
                        self.fase_grupos.get_stats(t.id).get("gm", 0) - self.fase_grupos.get_stats(t.id).get("gs", 0),
                        self.fase_grupos.get_stats(t.id).get("gm", 0),
                    ), reverse=True)
                    top.append(segundos[0])
            classif_geral = self.fase_grupos.classificacao()
        elif self._usa_grupos and isinstance(self.fase_grupos, GruposEstadual):
            # Coletar top N de cada grupo
            cpg = self._classificados_por_grupo or 2
            top: List[Time] = []
            for g in self.fase_grupos.grupos:
                classif_g = g.classificacao()
                top.extend(classif_g[:cpg])
            # Rebaixamento por classificação geral
            classif_geral = self.fase_grupos.classificacao()
        else:
            classif_geral = self.fase_grupos.classificacao()
            n_class = self._n_classificados
            top = classif_geral[:n_class]

        # Rebaixamento: piores colocados
        if self._n_rebaixados > 0:
            self.rebaixados = classif_geral[-self._n_rebaixados:]

        if len(top) >= 2:
            self.mata_mata = Copa(f"{self.nome} - Mata-Mata", top,
                                  seeded=True, gol_fora=False)
            self._em_mata_mata = True
        else:
            if top:
                self.campeao = top[0]
            self.encerrado = True

    def _jogar_mata_mata(self) -> List[ResultadoPartida]:
        if not self.mata_mata or self.mata_mata.encerrado:
            if self.mata_mata and self.mata_mata.campeao:
                self.campeao = self.mata_mata.campeao
                # Vice = finalista que perdeu
                if self.mata_mata.confrontos:
                    final = self.mata_mata.confrontos[-1]
                    for t1, t2 in final:
                        if t1 and t2:
                            self.vice = t2 if t1 == self.campeao else t1
            self.encerrado = True
            return []
        if self.mata_mata.jogo_ida:
            return self.mata_mata.jogar_fase_ida()
        else:
            return self.mata_mata.jogar_fase_volta()


# ══════════════════════════════════════════════════════════════
#  GERENCIADOR DE COMPETIÇÕES
# ══════════════════════════════════════════════════════════════

ESTADOS_BR = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
    "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
    "SE", "SP", "TO",
]

ESTADO_NOME = {
    "AC": "Acreano", "AL": "Alagoano", "AM": "Amazonense", "AP": "Amapaense",
    "BA": "Baiano", "CE": "Cearense", "DF": "Brasiliense", "ES": "Capixaba",
    "GO": "Goiano", "MA": "Maranhense", "MG": "Mineiro", "MS": "Sul-Mato-Grossense",
    "MT": "Mato-Grossense", "PA": "Paraense", "PB": "Paraibano", "PE": "Pernambucano",
    "PI": "Piauiense", "PR": "Paranaense", "RJ": "Carioca", "RN": "Potiguar",
    "RO": "Rondoniense", "RR": "Roraimense", "RS": "Gaúcho", "SC": "Catarinense",
    "SE": "Sergipano", "SP": "Paulista", "TO": "Tocantinense",
}

# Nomes comerciais dos estaduais (patrocínio)
ESTADUAL_NOME_COMERCIAL = {
    "SP": "Paulistão Casas Bahia",
    "RJ": "Cariocão Betano",
    "MG": "Campeonato Mineiro Betano",
    "RS": "Gauchão Ipiranga",
    "PR": "Campeonato Paranaense Água Ouro Fino",
    "BA": "Baianão Série A",
    "CE": "Cearense Série A",
    "PE": "Pernambucano Série A1",
    "SC": "Campeonato Catarinense Série A",
    "GO": "Goianão",
    "PA": "Parazão",
    "AM": "Barezão",
    "RN": "Campeonato Potiguar",
    "PB": "Campeonato Paraibano",
    "SE": "Campeonato Sergipano",
    "PI": "Campeonato Piauiense",
    "ES": "Campeonato Capixaba",
    "MT": "Campeonato Mato-Grossense",
    "MS": "Campeonato Sul-Mato-Grossense",
    "AL": "Campeonato Alagoano",
    "MA": "Campeonato Maranhense",
    "AC": "Campeonato Acreano",
    "AP": "Campeonato Amapaense",
    "DF": "Campeonato Brasiliense",
    "RO": "Campeonato Rondoniense",
    "RR": "Campeonato Roraimense",
    "TO": "Campeonato Tocantinense",
}

_EUROPE_CODES = {
    "ING", "ESP", "ITA", "ALE", "FRA", "POR", "HOL", "BEL",
    "TUR", "RUS", "ESC", "SUI", "AUT", "GRE",
    "CRO", "SER", "DIN", "NOR", "SUE", "UCR",
}

_ASIA_CODES = {
    "JAP", "CHN", "ARS", "EMI", "AUS", "CAT",
}

_SOUTH_AMERICA_CODES = {
    "BRA", "ARG", "BOL", "CHI", "COL", "EQU", "PAR", "PER", "URU", "VEN",
}

_INT_LEAGUE_NAMES = {
    "ING": {1: "Premier League", 2: "Championship", 3: "League One", 4: "League Two"},
    "ESP": {1: "LaLiga", 2: "LaLiga 2", 3: "Primera Federacion", 4: "Segunda Federacion"},
    "ITA": {1: "Serie A TIM", 2: "Serie B", 3: "Serie C", 4: "Serie D"},
    "ALE": {1: "Bundesliga", 2: "2. Bundesliga", 3: "3. Liga", 4: "Regionalliga"},
    "FRA": {1: "Ligue 1", 2: "Ligue 2", 3: "National", 4: "National 2"},
    "POR": {1: "Liga Portugal", 2: "Liga Portugal 2"},
    "HOL": {1: "Eredivisie", 2: "Eerste Divisie"},
    "BEL": {1: "Pro League", 2: "Challenger Pro League"},
    "TUR": {1: "Super Lig", 2: "1. Lig"},
    "RUS": {1: "Russian Premier League", 2: "First League"},
    "ESC": {1: "Scottish Premiership", 2: "Scottish Championship"},
    "SUI": {1: "Swiss Super League"},
    "AUT": {1: "Austrian Bundesliga"},
    "GRE": {1: "Greek Super League"},
    "ARG": {1: "Liga Profesional", 2: "Primera Nacional", 3: "Primera B Metropolitana", 4: "Primera C"},
    "BOL": {1: "Division Profesional", 2: "Copa Simon Bolivar", 3: "Primera Regional"},
    "CHI": {1: "Primera Division", 2: "Primera B", 3: "Segunda Division", 4: "Tercera Division"},
    "COL": {1: "Liga BetPlay", 2: "Torneo BetPlay", 3: "Primera C"},
    "EQU": {1: "LigaPro Serie A", 2: "LigaPro Serie B"},
    "PAR": {1: "Primera Division", 2: "Division Intermedia", 3: "Primera B Nacional"},
    "PER": {1: "Liga 1", 2: "Liga 2", 3: "Liga 3"},
    "URU": {1: "Primera Division", 2: "Segunda Division"},
    "VEN": {1: "Liga FUTVE", 2: "Liga FUTVE 2", 3: "Tercera Division"},
    "MEX": {1: "Liga MX", 2: "Liga de Expansion MX", 3: "Liga Premier", 4: "Serie B"},
    "EUA": {1: "MLS", 2: "USL Championship", 3: "USL League One"},
    "JAP": {1: "J1 League", 2: "J2 League", 3: "J3 League"},
    "CHN": {1: "Chinese Super League", 2: "China League One"},
    "ARS": {1: "Saudi Pro League", 2: "Saudi First Division"},
    "EMI": {1: "UAE Pro League"},
    "AUS": {1: "A-League Men"},
    "CAT": {1: "Qatar Stars League"},
    "CRO": {1: "HNL"},
    "SER": {1: "Serbian SuperLiga"},
    "DIN": {1: "Danish Superliga"},
    "NOR": {1: "Eliteserien"},
    "SUE": {1: "Allsvenskan"},
    "UCR": {1: "Ukrainian Premier League"},
    "MAR": {1: "Botola Pro"},
    "EGI": {1: "Egyptian Premier League"},
    "AFG": {1: "Afghan Premier League"},
    "AFS": {1: "PSL"},
}


class GerenciadorCompeticoes:
    def __init__(self) -> None:
        self.brasileirao_a: Optional[Campeonato] = None
        self.brasileirao_b: Optional[Campeonato] = None
        self.brasileirao_c = None  # Campeonato ou CampeonatoComGrupos
        self.brasileirao_d: Optional[CampeonatoComGrupos] = None
        self.copa_brasil: Optional[Copa] = None
        self.libertadores: Optional[Libertadores] = None
        self.sul_americana: Optional[SulAmericana] = None
        self.estaduais: Dict[str, CampeonatoEstadual] = {}
        self.ligas_europeias: Dict[str, Dict[int, Campeonato]] = {}  # {pais: {div: Campeonato}}
        self.champions_league: Optional[CampeonatoComGrupos] = None
        self.europa_league: Optional[CampeonatoComGrupos] = None
        self.conference_league: Optional[CampeonatoComGrupos] = None
        self.afc_champions: Optional[CampeonatoComGrupos] = None
        self.copa_mundo: Optional[CampeonatoComGrupos] = None
        self.eurocopa: Optional[CampeonatoComGrupos] = None
        self.copa_america: Optional[CampeonatoComGrupos] = None
        self.copa_nordeste: Optional[CampeonatoComGrupos] = None
        self.copa_verde: Optional[CampeonatoComGrupos] = None
        self.supercopa_rei: Optional[Dict] = None  # {time1, time2, resultado, campeao}
        self.temporada: int = 2026
        self.semana_atual: int = 0
        self.noticias: List[Noticia] = []
        self.calendario: Dict[int, List[str]] = {}

    def iniciar_temporada(self, times_a: List[Time], times_b: List[Time],
                          times_c: List[Time], times_d: List[Time],
                          times_sem_divisao: List[Time],
                          times_lib: List[Time], estado_jogador: str,
                          resetar: bool = True,
                          times_europeus: Optional[Dict] = None,
                          times_sul_america: Optional[List[Time]] = None,
                          selecoes: Optional[Dict[str, List[Time]]] = None,
                          supercopa_times: Optional[tuple] = None) -> None:
        self.semana_atual = 0
        todos = times_a + times_b + times_c + times_d + times_sem_divisao
        if resetar:
            for t in todos:
                t.resetar_temporada()

        self.brasileirao_a = Campeonato(f"Brasileirão Betano Série A {self.temporada}", times_a)
        if times_b:
            self.brasileirao_b = Campeonato(f"Brasileirão Betano Série B {self.temporada}", times_b)
        if times_c:
            n_grupos_c = 2 if len(times_c) >= 8 else 1
            if n_grupos_c >= 2:
                self.brasileirao_c = CampeonatoComGrupos(
                    f"Brasileirão Betano Série C {self.temporada}", times_c,
                    n_grupos=n_grupos_c, classificados_por_grupo=4,
                    turno_e_returno_grupos=True,
                )
            else:
                self.brasileirao_c = Campeonato(f"Brasileirão Betano Série C {self.temporada}", times_c)
        if times_d:
            self.brasileirao_d = CampeonatoComGrupos(
                f"Brasileirão Betano Série D {self.temporada}", times_d,
                n_grupos=16, classificados_por_grupo=2,
                turno_e_returno_grupos=False,
            )

        # Copa do Brasil — seleção realista por divisão
        # Série A (20) + Série B (20) + Série C (20) + top Série D (20 por prestígio) = 80
        copa_times: List[Time] = []
        copa_times.extend(times_a)
        copa_times.extend(times_b)
        copa_times.extend(times_c)
        times_d_sorted = sorted(times_d, key=lambda t: t.prestigio, reverse=True)
        restantes_d = times_d_sorted[:20] if len(times_d_sorted) >= 20 else times_d_sorted[:]
        copa_times.extend(restantes_d)
        # Seeding: Série A são cabeças-de-chave, depois B, C, D
        # Garante que Série A entra nas posições altas do bracket
        seeded_a = list(times_a); random.shuffle(seeded_a)
        seeded_b = list(times_b); random.shuffle(seeded_b)
        lower = list(times_c) + restantes_d; random.shuffle(lower)
        copa_seeded = seeded_a + seeded_b + lower
        self.copa_brasil = Copa(f"Copa Betano do Brasil {self.temporada}", copa_seeded, seeded=True, gol_fora=False)

        if times_lib:
            self.libertadores = Libertadores(times_lib[:32])

        # Sul-Americana: preencher bracket jogável de 32 clubes sem depender
        # do ranking da temporada anterior no primeiro save.
        ids_lib = {t.id for t in (times_lib[:32] if times_lib else [])}
        pool_sula = [
            t for t in (times_sul_america or (list(times_a) + list(times_b) + list(times_c) + list(times_d) + list(times_sem_divisao)))
            if t.id not in ids_lib
        ]
        pool_sula = sorted(pool_sula, key=lambda t: t.prestigio, reverse=True)
        times_sula = pool_sula[:32]
        if len(times_sula) >= 8:
            self.sul_americana = SulAmericana(times_sula)

        # Criar estaduais para todos os 27 estados
        self.estaduais = {}
        for uf in ESTADOS_BR:
            nome_camp = ESTADUAL_NOME_COMERCIAL.get(uf)
            if not nome_camp:
                nome_generico = ESTADO_NOME.get(uf, uf)
                nome_camp = f"Campeonato {nome_generico}"
            est = CampeonatoEstadual(
                f"{nome_camp} {self.temporada}", uf, todos,
            )
            if not est.encerrado:
                self.estaduais[uf] = est

        # Copa do Nordeste — times do Nordeste (top por prestígio)
        _ESTADOS_NORDESTE = {'BA', 'CE', 'PE', 'RN', 'PB', 'AL', 'MA', 'PI', 'SE'}
        pool_ne = sorted(
            [t for t in todos if t.estado in _ESTADOS_NORDESTE],
            key=lambda t: t.prestigio, reverse=True,
        )[:16]
        if len(pool_ne) >= 8:
            self.copa_nordeste = CampeonatoComGrupos(
                f"Copa do Nordeste {self.temporada}", pool_ne,
                n_grupos=4, classificados_por_grupo=2,
                turno_e_returno_grupos=False,
            )

        # Copa Verde — times do Norte, Centro-Oeste + ES + MT + MS
        _ESTADOS_VERDE = {'PA', 'AM', 'AP', 'RO', 'RR', 'AC', 'TO',
                          'GO', 'MT', 'MS', 'DF', 'ES', 'MA'}
        pool_cv = sorted(
            [t for t in todos if t.estado in _ESTADOS_VERDE],
            key=lambda t: t.prestigio, reverse=True,
        )[:16]
        if len(pool_cv) >= 8:
            self.copa_verde = CampeonatoComGrupos(
                f"Copa Verde {self.temporada}", pool_cv,
                n_grupos=4, classificados_por_grupo=2,
                turno_e_returno_grupos=False,
            )

        # ── Ligas Europeias ──
        self.ligas_europeias = {}
        if times_europeus:
            for pais, divs in times_europeus.items():
                league_names = _INT_LEAGUE_NAMES.get(pais, {})
                pais_ligas = {}
                for div_num, times_div in divs.items():
                    if len(times_div) < 4:
                        continue
                    if resetar:
                        for t in times_div:
                            t.resetar_temporada()
                    nome = league_names.get(div_num, f"Liga {pais} Div {div_num}")
                    liga = Campeonato(f"{nome} {self.temporada}", times_div)
                    pais_ligas[div_num] = liga
                if pais_ligas:
                    self.ligas_europeias[pais] = pais_ligas

            # Champions League 2025+: 36 times, 9 grupos de 4
            cl_times = []
            for pais, n_vagas in [("ING", 5), ("ESP", 5), ("ITA", 5), ("ALE", 5),
                                   ("FRA", 3), ("POR", 3), ("HOL", 2), ("BEL", 2),
                                   ("TUR", 1), ("RUS", 1), ("ESC", 1), ("SUI", 1),
                                   ("AUT", 1), ("GRE", 1)]:
                if pais in times_europeus and 1 in times_europeus[pais]:
                    div1 = times_europeus[pais][1]
                    top = sorted(div1, key=lambda t: t.prestigio, reverse=True)[:n_vagas]
                    cl_times.extend(top)
            if len(cl_times) >= 8:
                while len(cl_times) % 4 != 0:
                    cl_times = cl_times[:-1]
                n_grupos = max(len(cl_times) // 4, 2)
                self.champions_league = CampeonatoComGrupos(
                    f"UEFA Champions League {self.temporada}",
                    cl_times, n_grupos=n_grupos, classificados_por_grupo=2,
                    turno_e_returno_grupos=True,
                )

            # Europa League 2025+: 36 times, 9 grupos de 4
            el_times = []
            for pais, vagas_el in [("ING", (6, 8)), ("ESP", (6, 8)), ("ITA", (6, 8)),
                                    ("ALE", (6, 8)), ("FRA", (4, 6)), ("POR", (4, 6)),
                                    ("HOL", (3, 5)), ("BEL", (3, 4)), ("TUR", (2, 3)),
                                    ("RUS", (2, 3)), ("ESC", (2, 3)), ("SUI", (2, 2)),
                                    ("AUT", (2, 2)), ("GRE", (2, 3)),
                                    ("CRO", (1, 1)), ("SER", (1, 1)),
                                    ("DIN", (1, 1)), ("NOR", (1, 1)),
                                    ("SUE", (1, 1)), ("UCR", (1, 1))]:
                if pais in times_europeus and 1 in times_europeus[pais]:
                    div1 = times_europeus[pais][1]
                    top = sorted(div1, key=lambda t: t.prestigio, reverse=True)
                    inicio, fim = vagas_el
                    el_times.extend(top[inicio - 1:fim])
            if len(el_times) >= 8:
                while len(el_times) % 4 != 0:
                    el_times = el_times[:-1]
                n_grupos_el = max(len(el_times) // 4, 2)
                self.europa_league = CampeonatoComGrupos(
                    f"UEFA Europa League {self.temporada}",
                    el_times, n_grupos=n_grupos_el, classificados_por_grupo=2,
                    turno_e_returno_grupos=True,
                )

            # Conference League 2025+: 36 times, 9 grupos de 4
            ecl_times = []
            cl_el_ids = {t.id for t in cl_times + el_times}
            for pais, vagas_ecl in [("HOL", (6, 7)), ("BEL", (5, 6)), ("TUR", (4, 5)),
                                     ("RUS", (4, 5)), ("ESC", (4, 5)), ("SUI", (3, 4)),
                                     ("AUT", (3, 4)), ("GRE", (4, 5)),
                                     ("CRO", (2, 3)), ("SER", (2, 3)),
                                     ("DIN", (2, 3)), ("NOR", (2, 3)),
                                     ("SUE", (2, 3)), ("UCR", (2, 3)),
                                     ("ING", (9, 10)), ("ESP", (9, 10)),
                                     ("ITA", (9, 10)), ("ALE", (9, 10)),
                                     ("FRA", (7, 8)), ("POR", (7, 8))]:
                if pais in times_europeus and 1 in times_europeus[pais]:
                    div1 = times_europeus[pais][1]
                    top = sorted(div1, key=lambda t: t.prestigio, reverse=True)
                    inicio, fim = vagas_ecl
                    for tt in top[inicio - 1:fim]:
                        if tt.id not in cl_el_ids:
                            ecl_times.append(tt)
            if len(ecl_times) >= 8:
                while len(ecl_times) % 4 != 0:
                    ecl_times = ecl_times[:-1]
                n_grupos_ecl = max(len(ecl_times) // 4, 2)
                self.conference_league = CampeonatoComGrupos(
                    f"UEFA Conference League {self.temporada}",
                    ecl_times, n_grupos=n_grupos_ecl, classificados_por_grupo=2,
                    turno_e_returno_grupos=True,
                )

        # ── AFC Champions League Elite ──
        if times_europeus:
            afc_times = []
            for pais, n_vagas in [("JAP", 4), ("ARS", 4), ("AUS", 2), ("CHN", 2),
                                   ("EMI", 2), ("CAT", 2)]:
                if pais in times_europeus and 1 in times_europeus[pais]:
                    div1 = times_europeus[pais][1]
                    top = sorted(div1, key=lambda t: t.prestigio, reverse=True)[:n_vagas]
                    afc_times.extend(top)
            if len(afc_times) >= 8:
                while len(afc_times) % 4 != 0:
                    afc_times = afc_times[:-1]
                n_grupos_afc = max(len(afc_times) // 4, 2)
                self.afc_champions = CampeonatoComGrupos(
                    f"AFC Champions League Elite {self.temporada}",
                    afc_times, n_grupos=n_grupos_afc, classificados_por_grupo=2,
                )

        self.copa_mundo = None
        self.eurocopa = None
        self.copa_america = None
        if selecoes:
            mundo = list(selecoes.get("mundo", []))
            europa = list(selecoes.get("europa", []))
            america = list(selecoes.get("america_sul", []))

            if len(mundo) >= 4 and self.temporada % 4 == 2:
                # Copa do Mundo 2026+: formato expandido com 48 seleções
                n_times = min(48, len(mundo))
                n_grp = max(2, n_times // 4)
                self.copa_mundo = CampeonatoComGrupos(
                    f"Copa do Mundo {self.temporada}",
                    mundo[:n_times],
                    n_grupos=n_grp,
                    classificados_por_grupo=2,
                    turno_e_returno_grupos=False,
                    mata_mata_ida_e_volta=False,
                )

            if len(europa) >= 4 and self.temporada % 4 == 0:
                n_times = min(24, len(europa))
                self.eurocopa = CampeonatoComGrupos(
                    f"Eurocopa {self.temporada}",
                    europa[:n_times],
                    n_grupos=max(2, n_times // 4),
                    classificados_por_grupo=2,
                    turno_e_returno_grupos=False,
                    mata_mata_ida_e_volta=False,
                )

            if len(america) >= 4 and self.temporada % 4 == 1:
                n_times = min(12, len(america))
                self.copa_america = CampeonatoComGrupos(
                    f"Copa America {self.temporada}",
                    america[:n_times],
                    n_grupos=max(2, n_times // 4),
                    classificados_por_grupo=2,
                    turno_e_returno_grupos=False,
                    mata_mata_ida_e_volta=False,
                )

        # Supercopa Rei: campeão Brasileiro × campeão Copa do Brasil
        if supercopa_times:
            self.supercopa_rei = {
                "time1": supercopa_times[0],
                "time2": supercopa_times[1],
                "resultado": None,
                "campeao": None,
                "encerrado": False,
            }
        else:
            self.supercopa_rei = None

        self._gerar_calendario()

    def _gerar_calendario(self) -> None:
        """Calendário menos congestionado para preservar a jogabilidade."""
        self.calendario = {}

        # Semanas 1-4 reservadas para pré-temporada.

        # Supercopa Rei: semana 5 (abertura da temporada)
        if self.supercopa_rei:
            self.calendario.setdefault(5, []).insert(0, "supercopa_rei")

        # Estaduais: semanas 5-24 (fase classificatória + mata-mata)
        # SP(16 times) = 15 rodadas + 6 mata-mata (quartas+semi+final ida/volta) = 21
        # 12 times = 11 + 6 = 17; 10 times = 9 + 4 = 13
        for s in range(5, 25):
            self.calendario[s] = ["estadual"]

        total_a = self.brasileirao_a.total_rodadas if self.brasileirao_a else 38
        for s in range(13, 13 + total_a):
            self.calendario.setdefault(s, []).append("brasileirao")

        if self.brasileirao_b:
            total_b = self.brasileirao_b.total_rodadas
            for s in range(16, 16 + total_b):
                self.calendario.setdefault(s, []).append("serie_b_exclusiva")

        if self.brasileirao_c:
            total_c = self.brasileirao_c.total_rodadas + 12  # +12 para mata-mata
            for s in range(18, 18 + total_c):
                self.calendario.setdefault(s, []).append("brasileirao_c")

        if self.brasileirao_d:
            total_d = self.brasileirao_d.total_rodadas + 12
            for s in range(18, 18 + total_d):
                self.calendario.setdefault(s, []).append("brasileirao_d")

        for s in [15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45, 48, 51, 53]:
            self.calendario.setdefault(s, []).append("copa_brasil")

        for s in range(17, 17 + 24, 2):
            self.calendario.setdefault(s, []).append("libertadores")

        for s in range(18, 18 + 24, 2):
            self.calendario.setdefault(s, []).append("sul_americana")

        # Copa do Nordeste: semanas 6-20 (intercalado com estaduais)
        if self.copa_nordeste:
            for s in range(6, 21, 2):
                self.calendario.setdefault(s, []).append("copa_nordeste")

        # Copa Verde: semanas 7-21
        if self.copa_verde:
            for s in range(7, 22, 2):
                self.calendario.setdefault(s, []).append("copa_verde")

        if self.ligas_europeias:
            for s in range(13, 51):
                self.calendario.setdefault(s, []).append("europeias")

        if self.champions_league:
            for s in range(17, 17 + 24, 2):
                self.calendario.setdefault(s, []).append("champions_league")

        if self.europa_league:
            for s in range(18, 18 + 24, 2):
                self.calendario.setdefault(s, []).append("europa_league")

        if self.conference_league:
            for s in range(19, 19 + 20, 2):
                self.calendario.setdefault(s, []).append("conference_league")

        if self.afc_champions:
            for s in range(17, 17 + 24, 2):
                self.calendario.setdefault(s, []).append("afc_champions")

        if self.copa_mundo:
            for s in range(7, 15):
                self.calendario.setdefault(s, []).append("copa_mundo")

        if self.eurocopa:
            for s in range(7, 14):
                self.calendario.setdefault(s, []).append("eurocopa")

        if self.copa_america:
            for s in range(7, 14):
                self.calendario.setdefault(s, []).append("copa_america")

    def competicoes_da_semana(self) -> List[str]:
        return self.calendario.get(self.semana_atual, [])

    def avancar_semana(self) -> Dict[str, List[ResultadoPartida]]:
        self.semana_atual += 1
        resultados: Dict[str, List[ResultadoPartida]] = {}
        for comp in self.competicoes_da_semana():
            if comp == "supercopa_rei" and self.supercopa_rei and not self.supercopa_rei.get("encerrado"):
                sc = self.supercopa_rei
                t1, t2 = sc["time1"], sc["time2"]
                from engine.match_engine import simular_partida
                res = simular_partida(t1, t2)
                sc["resultado"] = res
                sc["campeao"] = t1 if res.gols_casa > res.gols_fora else (t2 if res.gols_fora > res.gols_casa else (t1 if random.random() < 0.5 else t2))
                sc["encerrado"] = True
                resultados["supercopa_rei"] = [res]
            elif comp == "brasileirao":
                if self.brasileirao_a and not self.brasileirao_a.encerrado:
                    resultados["serie_a"] = self.brasileirao_a.jogar_rodada()
                if self.brasileirao_b and not self.brasileirao_b.encerrado:
                    resultados["serie_b"] = self.brasileirao_b.jogar_rodada()
            elif comp == "serie_b_exclusiva":
                if self.brasileirao_b and not self.brasileirao_b.encerrado:
                    resultados["serie_b"] = self.brasileirao_b.jogar_rodada()
            elif comp == "brasileirao_c":
                if self.brasileirao_c and not self.brasileirao_c.encerrado:
                    resultados["serie_c"] = self.brasileirao_c.jogar_rodada()
            elif comp == "brasileirao_d":
                if self.brasileirao_d and not self.brasileirao_d.encerrado:
                    resultados["serie_d"] = self.brasileirao_d.jogar_rodada()
            elif comp == "copa_brasil" and self.copa_brasil and not self.copa_brasil.encerrado:
                resultados["copa_brasil"] = (
                    self.copa_brasil.jogar_fase_ida()
                    if self.copa_brasil.jogo_ida
                    else self.copa_brasil.jogar_fase_volta()
                )
            elif comp == "libertadores" and self.libertadores and not self.libertadores.encerrado:
                resultados["libertadores"] = self.libertadores.jogar_rodada()
            elif comp == "sul_americana" and self.sul_americana and not self.sul_americana.encerrado:
                resultados["sul_americana"] = self.sul_americana.jogar_rodada()
            elif comp == "estadual":
                for uf, est in self.estaduais.items():
                    if not est.encerrado:
                        res = est.jogar_rodada()
                        if res:
                            resultados[f"estadual_{uf}"] = res
            elif comp == "europeias":
                for pais, divs in self.ligas_europeias.items():
                    for div_num, liga in divs.items():
                        if not liga.encerrado:
                            res = liga.jogar_rodada()
                            if res:
                                resultados[f"liga_{pais}_{div_num}"] = res
            elif comp == "champions_league" and self.champions_league and not self.champions_league.encerrado:
                resultados["champions_league"] = self.champions_league.jogar_rodada()
            elif comp == "europa_league" and self.europa_league and not self.europa_league.encerrado:
                resultados["europa_league"] = self.europa_league.jogar_rodada()
            elif comp == "conference_league" and self.conference_league and not self.conference_league.encerrado:
                resultados["conference_league"] = self.conference_league.jogar_rodada()
            elif comp == "afc_champions" and self.afc_champions and not self.afc_champions.encerrado:
                resultados["afc_champions"] = self.afc_champions.jogar_rodada()
            elif comp == "copa_mundo" and self.copa_mundo and not self.copa_mundo.encerrado:
                resultados["copa_mundo"] = self.copa_mundo.jogar_rodada()
            elif comp == "eurocopa" and self.eurocopa and not self.eurocopa.encerrado:
                resultados["eurocopa"] = self.eurocopa.jogar_rodada()
            elif comp == "copa_america" and self.copa_america and not self.copa_america.encerrado:
                resultados["copa_america"] = self.copa_america.jogar_rodada()
            elif comp == "copa_nordeste" and self.copa_nordeste and not self.copa_nordeste.encerrado:
                resultados["copa_nordeste"] = self.copa_nordeste.jogar_rodada()
            elif comp == "copa_verde" and self.copa_verde and not self.copa_verde.encerrado:
                resultados["copa_verde"] = self.copa_verde.jogar_rodada()
        return resultados

    def temporada_encerrada(self) -> bool:
        br_a = self.brasileirao_a is None or self.brasileirao_a.encerrado
        br_b = self.brasileirao_b is None or self.brasileirao_b.encerrado
        br_c = self.brasileirao_c is None or self.brasileirao_c.encerrado
        br_d = self.brasileirao_d is None or self.brasileirao_d.encerrado
        copa = self.copa_brasil is None or self.copa_brasil.encerrado
        lib = self.libertadores is None or self.libertadores.encerrado
        sula = self.sul_americana is None or self.sul_americana.encerrado
        eu = all(
            liga.encerrado
            for divs in self.ligas_europeias.values()
            for liga in divs.values()
        ) if self.ligas_europeias else True
        cl = self.champions_league is None or self.champions_league.encerrado
        el = self.europa_league is None or self.europa_league.encerrado
        ecl = self.conference_league is None or self.conference_league.encerrado
        afc = self.afc_champions is None or self.afc_champions.encerrado
        wc = self.copa_mundo is None or self.copa_mundo.encerrado
        euro = self.eurocopa is None or self.eurocopa.encerrado
        america = self.copa_america is None or self.copa_america.encerrado
        cne = self.copa_nordeste is None or self.copa_nordeste.encerrado
        cvr = self.copa_verde is None or self.copa_verde.encerrado
        return br_a and br_b and br_c and br_d and copa and lib and sula and eu and cl and el and ecl and afc and wc and euro and america and cne and cvr
