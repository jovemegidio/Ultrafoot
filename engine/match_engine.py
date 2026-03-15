# -*- coding: utf-8 -*-
"""
Motor de simulação de partidas — minuto a minuto.
Migrado do legacy motor_partida.py com melhorias:
  - usa constantes de config em vez de números mágicos
  - gera notas individuais e pontos fantasy
  - suporte a traits de jogador
"""
from __future__ import annotations

import random
from typing import List, Tuple, Optional, Dict

from core.enums import (
    Posicao, EstiloJogo, MarcacaoPressao, TraitJogador, TipoStaff,
    ClimaPartida,
)
from core.models import (
    Time, Jogador, ResultadoPartida, EventoPartida, StatusLesao,
    CondicoesPartida,
)
from core.constants import (
    PESO_FINALIZACAO, SETOR_POSICOES, ESTILO_MULT_FINALIZACAO,
    FANTASY_PONTOS,
)
from config import (
    SIM_CHANCE_FINALIZACAO_BASE, SIM_CHANCE_FALTA, SIM_CHANCE_ESCANTEIO,
    SIM_CHANCE_IMPEDIMENTO, SIM_CHANCE_LESAO_JOGO, SIM_VANTAGEM_CASA,
)
from utils.logger import get_logger

log = get_logger(__name__)

# ── Narration Templates ──────────────────────────────────────
_NARR_GOL = [
    "{jogador} chuta com precisão — GOOOOL!",
    "Bola no ângulo! {jogador} marca um golaço!",
    "{jogador} aproveita a oportunidade e balança a rede!",
    "Finalização certeira de {jogador}! A torcida explode!",
    "{jogador} não perdoa e manda para o fundo das redes!",
    "É GOL! {jogador} amplia o placar!",
    "Que jogada! {jogador} conclui com categoria!",
    "{jogador} domina, gira e chuta — GOL!",
    "Bola no canto! {jogador} não dá chance ao goleiro!",
    "Linda cobrança de {jogador}! Golaço!",
]
_NARR_GOL_ASSIST = [
    "{jogador} recebe de {assist} e finaliza — GOL!",
    "Passe genial de {assist}! {jogador} só empurra para a rede!",
    "{assist} acha {jogador} livre, que não desperdiça — GOOOOL!",
    "Assistência de luxo de {assist} para o gol de {jogador}!",
    "Combinação perfeita: {assist} toca, {jogador} faz!",
]
_NARR_GOL_FALTA = [
    "{jogador} cobra a falta com maestria — GOOOOL!",
    "Cobrança perfeita de {jogador}! A barreira nem pulou!",
    "Que falta! {jogador} coloca a bola onde o goleiro não alcança!",
]
_NARR_GOL_PENALTI = [
    "{jogador} bate firme o pênalti — GOL!",
    "Cobrança segura de {jogador}! Deslocou o goleiro!",
    "{jogador} converte o pênalti sem chance para o goleiro!",
]
_NARR_FALTA = [
    "{jogador} comete falta dura no meio-campo.",
    "Falta de {jogador}. Jogo parado pelo árbitro.",
    "{jogador} derruba o adversário. Falta marcada.",
]
_NARR_AMARELO = [
    "Cartão amarelo para {jogador}! Falta imprudente.",
    "{jogador} recebe o cartão amarelo do árbitro.",
    "Amarelo! {jogador} precisa ter mais cuidado.",
    "O juiz mostra o amarelo para {jogador}.",
]
_NARR_VERMELHO = [
    "CARTÃO VERMELHO! {jogador} é expulso de campo!",
    "Fora! {jogador} recebe o vermelho direto!",
    "{jogador} está fora do jogo! Entrada violenta!",
]
_NARR_VERMELHO_2AM = [
    "Segundo amarelo para {jogador}! Está expulso!",
    "{jogador} toma o segundo amarelo e deixa o time com um a menos!",
]
_NARR_LESAO = [
    "{jogador} fica caído no gramado. Problema físico.",
    "Preocupação! {jogador} sente dores e pede atendimento.",
    "{jogador} sai de campo lesionado. Maca em campo!",
]
_NARR_ESCANTEIO = [
    "Escanteio para {time}! Bola desviada pela defesa.",
    "Cobrança de escanteio para {time}.",
]
_NARR_IMPEDIMENTO = [
    "{jogador} estava impedido. Lance anulado.",
    "Bandeirinha marca impedimento de {jogador}.",
]
_NARR_PENALTY = [
    "Penalti para {time}! {faltoso} derruba {alvo} na area.",
    "O arbitro aponta para a marca da cal! {faltoso} chega atrasado em {alvo}.",
    "Penalti marcado para {time}. {alvo} sofre a carga de {faltoso}.",
]
_NARR_DEFESA = [
    "{goleiro} salva o time depois da finalizacao de {jogador}.",
    "{goleiro} fecha o angulo e evita o gol de {jogador}.",
    "Grande defesa de {goleiro} no chute de {jogador}.",
]

def _narr(templates, **kw):
    return random.choice(templates).format(**kw)


class MotorPartida:
    """Simula partidas com eventos detalhados, notas e fantasy."""

    def __init__(self) -> None:
        self.eventos: List[EventoPartida] = []
        self._notas: Dict[int, List[float]] = {}      # jogador_id → acumulado
        self._fantasy: Dict[int, float] = {}           # jogador_id → pontos
        self._xg_casa: float = 0.0
        self._xg_fora: float = 0.0
        self._xa_casa: float = 0.0
        self._xa_fora: float = 0.0
        self._momentum: List[Dict] = []                # [{min, time, intensidade}]

    # ═══════════════════════════════════════════════════════════
    #  SIMULAÇÃO PRINCIPAL
    # ═══════════════════════════════════════════════════════════

    def simular(self, casa: Time, fora: Time, *, neutro: bool = False,
                seed: int | None = None,
                substituicoes: list | None = None,
                aplicar_pos_jogo: bool = True,
                condicoes: CondicoesPartida | None = None,
                eh_derby: bool = False) -> ResultadoPartida:
        """
        Simula uma partida completa.

        Args:
            seed: semente RNG para replay determinístico.
            substituicoes: lista de dicts {minuto, sai_id, entra_id, time_nome}
            aplicar_pos_jogo: se False, não altera stats de times/jogadores.
        """
        # Deterministic replay support
        if seed is not None:
            self._saved_rng_state = random.getstate()
            random.seed(seed)
        else:
            seed = random.randint(0, 2**31)
            self._saved_rng_state = random.getstate()
            random.seed(seed)
        self.ultimo_seed = seed

        self.eventos = []
        self._notas = {}
        self._fantasy = {}
        self._xg_casa = 0.0
        self._xg_fora = 0.0
        self._xa_casa = 0.0
        self._xa_fora = 0.0
        self._momentum = []
        self._time_casa_nome = casa.nome
        self._participantes: Dict[str, set] = {casa.nome: set(), fora.nome: set()}

        # Inicializar árbitro com personalidade para esta partida
        self._init_arbitro()

        # Track original titulares to restore after simulation
        orig_tit_casa = list(casa.titulares)
        orig_tit_fora = list(fora.titulares)

        # Record initial titulares as participants
        for jid in casa.titulares:
            self._participantes[casa.nome].add(jid)
        for jid in fora.titulares:
            self._participantes[fora.nome].add(jid)

        resultado = ResultadoPartida(time_casa=casa.nome, time_fora=fora.nome)
        resultado.arbitro = getattr(self, '_arb_nome', '')

        # Gravar escalações iniciais (nomes dos titulares)
        _jmap_c = {j.id: j for j in casa.jogadores}
        _jmap_f = {j.id: j for j in fora.jogadores}
        resultado.escalacao_casa = [_jmap_c[jid].nome for jid in orig_tit_casa if jid in _jmap_c]
        resultado.escalacao_fora = [_jmap_f[jid].nome for jid in orig_tit_fora if jid in _jmap_f]

        # — condições de jogo (clima / gramado) —
        if condicoes is None:
            condicoes = self._gerar_condicoes()
        resultado.clima = condicoes.clima.value
        resultado.nivel_gramado = condicoes.nivel_gramado
        f_cond = condicoes.fator_clima * condicoes.fator_gramado

        # — forças —
        forca_casa = self._calcular_forca_efetiva(casa) * f_cond
        forca_fora = self._calcular_forca_efetiva(fora) * f_cond
        if not neutro:
            forca_casa *= SIM_VANTAGEM_CASA
        # Derby bonus: mais motivação apenas para o mandante
        if eh_derby:
            forca_casa *= 1.06

        b_casa, b_fora = self._calcular_bonus_tatico(casa, fora)
        forca_casa *= b_casa
        forca_fora *= b_fora

        # — posse (calculada inicialmente, atualizada após mudanças) —
        mc = self._forca_setor(casa, "meio")
        mf = self._forca_setor(fora, "meio")
        total = mc + mf
        resultado.posse_casa = round(mc / total * 100, 1) if total > 0 else 50.0

        vm_casa = vm_fora = 0  # cartões vermelhos

        # — IA: gerar substituições automáticas para ambos os times —
        subs_ia = self._gerar_subs_ia(casa, fora, substituicoes)
        all_subs = list(substituicoes or []) + subs_ia

        # — minuto a minuto —
        for minuto in range(1, 96):
            if 48 < minuto <= 50:
                continue  # intervalo

            # ── Substituições (humano + IA) ──
            for sub in all_subs:
                if sub.get("minuto") == minuto:
                    time_sub = casa if sub.get("time_nome") == casa.nome else fora
                    sai_id = sub["sai_id"]
                    entra_id = sub["entra_id"]
                    if sai_id in time_sub.titulares:
                        time_sub.titulares.remove(sai_id)
                        if entra_id not in time_sub.titulares:
                            time_sub.titulares.append(entra_id)
                        self._participantes[time_sub.nome].add(entra_id)
                        j_sai = time_sub.jogador_por_id(sai_id)
                        j_entra = time_sub.jogador_por_id(entra_id)
                        self.eventos.append(EventoPartida(
                            minuto=minuto, tipo="substituicao",
                            jogador_nome=f"{j_entra.nome if j_entra else '?'} ↔ {j_sai.nome if j_sai else '?'}",
                            jogador_id=entra_id,
                            time=time_sub.nome,
                            detalhe=f"Entra {j_entra.nome if j_entra else '?'}, sai {j_sai.nome if j_sai else '?'}",
                        ))
                        # Recalculate forces after sub
                        forca_casa = self._calcular_forca_efetiva(casa) * f_cond
                        forca_fora = self._calcular_forca_efetiva(fora) * f_cond
                        if not neutro:
                            forca_casa *= SIM_VANTAGEM_CASA
                        if eh_derby:
                            forca_casa *= 1.06
                        b_casa, b_fora = self._calcular_bonus_tatico(casa, fora)
                        forca_casa *= b_casa
                        forca_fora *= b_fora
                        # Recalculate possession
                        mc = self._forca_setor(casa, "meio")
                        mf = self._forca_setor(fora, "meio")
                        total = mc + mf
                        if total > 0:
                            resultado.posse_casa = round(mc / total * 100, 1)

            # Fator de expulsão — mais punitivo
            fator_c = max(0.45, 1.0 - vm_casa * 0.13)
            fator_f = max(0.45, 1.0 - vm_fora * 0.13)

            # Pressão nos minutos finais (75+): times perdendo atacam mais
            fator_pressao_casa = 1.0
            fator_pressao_fora = 1.0
            if minuto >= 75:
                dif = resultado.gols_casa - resultado.gols_fora
                pressao_min = 1.0 + (minuto - 75) * 0.008  # até +16% no min 95
                if dif < 0:
                    fator_pressao_casa = pressao_min
                elif dif > 0:
                    fator_pressao_fora = pressao_min
                # Times empatando também pressionam levemente
                if dif == 0 and minuto >= 85:
                    fator_pressao_casa = 1.0 + (minuto - 85) * 0.005
                    fator_pressao_fora = 1.0 + (minuto - 85) * 0.005

            fc = forca_casa * fator_c * fator_pressao_casa
            ff = forca_fora * fator_f * fator_pressao_fora

            if random.random() < self._chance_ataque_contextual(casa, fc, ff):
                dv_c, dv_f = self._simular_fase_ofensiva(casa, fora, minuto, resultado, fc, ff)
                vm_casa += dv_c
                vm_fora += dv_f

            if random.random() < self._chance_ataque_contextual(fora, ff, fc):
                dv_c, dv_f = self._simular_fase_ofensiva(fora, casa, minuto, resultado, ff, fc)
                vm_casa += dv_c
                vm_fora += dv_f

            # Lesões
            for t in (casa, fora):
                if random.random() < SIM_CHANCE_LESAO_JOGO:
                    evt = self._resolver_lesao(t, minuto)
                    if evt:
                        self.eventos.append(evt)

        # Público & renda (derby boost de público)
        atratividade = min(1.0, (casa.prestigio + fora.prestigio) / 160)
        if eh_derby:
            atratividade = min(1.0, atratividade * 1.25)
        resultado.publico = casa.estadio.publico_estimado(atratividade)
        resultado.renda = resultado.publico * casa.estadio.preco_ingresso
        resultado.eh_derby = eh_derby
        resultado.eventos = self.eventos

        # Notas & Fantasy
        self._calcular_notas(casa, fora, resultado)
        resultado.notas_jogadores = {k: round(sum(v) / len(v), 1)
                                     for k, v in self._notas.items() if v}
        resultado.fantasy_pontos = dict(self._fantasy)

        # xG / xA metrics
        resultado.xg_casa = round(self._xg_casa, 2)
        resultado.xg_fora = round(self._xg_fora, 2)
        resultado.xa_casa = round(self._xa_casa, 2)
        resultado.xa_fora = round(self._xa_fora, 2)
        resultado.momentum = list(self._momentum)

        # Pós-jogo (pode ser adiado para re-simulação com substituições)
        if aplicar_pos_jogo:
            self._atualizar_stats_times(casa, fora, resultado)
            self._atualizar_jogadores_pos_jogo(casa, fora, resultado)

        # Restore original titulares (subs are match-only, don't persist)
        casa.titulares = orig_tit_casa
        fora.titulares = orig_tit_fora

        # Restore RNG state
        random.setstate(self._saved_rng_state)

        return resultado

    def aplicar_resultado_pos_jogo(self, casa: Time, fora: Time,
                                    resultado: ResultadoPartida) -> None:
        """Apply post-match stats. Call after finalizing subs."""
        self._atualizar_stats_times(casa, fora, resultado)
        self._atualizar_jogadores_pos_jogo(casa, fora, resultado)

    # ═══════════════════════════════════════════════════════════
    #  CÁLCULOS INTERNOS
    # ═══════════════════════════════════════════════════════════

    def _gerar_condicoes(self) -> CondicoesPartida:
        """Gera condições aleatórias de clima e gramado para a partida."""
        clima = random.choices(
            list(ClimaPartida),
            weights=[40, 25, 15, 8, 2, 10],  # SOL, NUBLADO, CHUVA, CHUVA_FORTE, NEVE, CALOR
            k=1,
        )[0]
        temperatura = {
            ClimaPartida.SOL: random.randint(22, 35),
            ClimaPartida.NUBLADO: random.randint(15, 25),
            ClimaPartida.CHUVA: random.randint(12, 22),
            ClimaPartida.CHUVA_FORTE: random.randint(10, 20),
            ClimaPartida.NEVE: random.randint(-5, 5),
            ClimaPartida.CALOR_EXTREMO: random.randint(35, 42),
        }.get(clima, 25)
        nivel_gramado = random.randint(50, 100)
        vento = random.randint(0, 60)
        return CondicoesPartida(
            clima=clima, temperatura=temperatura,
            nivel_gramado=nivel_gramado, vento=vento,
        )

    def _calcular_forca_efetiva(self, time: Time) -> float:
        tits = self._titulares(time)
        if not tits:
            return 30.0
        ovr = sum(j.overall for j in tits) / len(tits)
        moral = sum(j.moral for j in tits) / len(tits)
        cond = sum(j.condicao_fisica for j in tits) / len(tits)
        fm = 0.85 + (moral / 100) * 0.30
        fc = 0.70 + (cond / 100) * 0.30
        fs = 1.0
        treinador = time.staff_por_tipo(TipoStaff.TREINADOR)
        if treinador:
            fs += (treinador.habilidade - 50) / 200
        return ovr * fm * fc * fs

    def _calcular_bonus_tatico(self, casa: Time, fora: Time) -> Tuple[float, float]:
        bc, bf = 1.0, 1.0
        if casa.tatica.contra_ataque and fora.tatica.estilo in (
            EstiloJogo.OFENSIVO, EstiloJogo.MUITO_OFENSIVO
        ):
            bc *= 1.06
        if fora.tatica.contra_ataque and casa.tatica.estilo in (
            EstiloJogo.OFENSIVO, EstiloJogo.MUITO_OFENSIVO
        ):
            bf *= 1.06

        # Marcação Alta: pressiona adversário mas abre espaço se ele usa toque curto
        if casa.tatica.marcacao == MarcacaoPressao.ALTA:
            if fora.tatica.toque_curto:
                bf *= 1.03
            else:
                bc *= 1.04
        if fora.tatica.marcacao == MarcacaoPressao.ALTA:
            if casa.tatica.toque_curto:
                bc *= 1.03
            else:
                bf *= 1.04

        # Marcação Recuada: melhora defesa mas reduz ataque
        if casa.tatica.marcacao == MarcacaoPressao.RECUADA:
            bc *= 0.94   # menos ataque
            bf *= 0.95   # adversário cria menos chances claras
        if fora.tatica.marcacao == MarcacaoPressao.RECUADA:
            bf *= 0.94
            bc *= 0.95

        # Pressão na saída de bola: rouba mais bola mas expõe defesa
        if casa.tatica.pressao_saida_bola:
            bc *= 1.03
            if fora.tatica.bola_longa:
                bf *= 1.04  # bola longa bypassa a pressão
        if fora.tatica.pressao_saida_bola:
            bf *= 1.03
            if casa.tatica.bola_longa:
                bc *= 1.04

        return bc, bf

    def _gerar_subs_ia(
        self,
        casa: Time,
        fora: Time,
        subs_humano: list | None,
    ) -> list:
        """Gera até 3 substituições automáticas para cada time AI.

        Times controlados pelo jogador humano (os que já têm subs manuais)
        não recebem subs automáticas.
        """
        subs = []
        times_com_sub_manual = set()
        if subs_humano:
            for s in subs_humano:
                times_com_sub_manual.add(s.get("time_nome", ""))

        for time in (casa, fora):
            if time.nome in times_com_sub_manual:
                continue
            reservas = [
                j for j in time.jogadores
                if j.id not in time.titulares
                and j.status_lesao is None
                and j.suspensao_jogos == 0
            ]
            if not reservas:
                continue
            # Ordenar titulares pela "necessidade de substituição"
            # (menor overall + menor condição → sai primeiro)
            tits = self._titulares(time)
            tits_sorted = sorted(
                tits,
                key=lambda j: j.overall * 0.5 + j.condicao_fisica * 0.5,
            )
            # Reservas por melhor overall
            reservas_sorted = sorted(reservas, key=lambda j: j.overall, reverse=True)
            n_subs = min(3, len(reservas_sorted))
            # Distribuir subs em minutos fixos para determinismo
            minutos_sub = [58, 68, 78]
            sub_count = 0
            tit_ids_subbed = set()
            for i in range(n_subs):
                if sub_count >= 3:
                    break
                # Encontrar titular p/ sair (mesmo posição se possível)
                candidato_sai = None
                reserva_entra = None
                for res in reservas_sorted:
                    if res.id in tit_ids_subbed:
                        continue
                    # Preferir substituir titular de mesma posição
                    for t in tits_sorted:
                        if t.id in tit_ids_subbed:
                            continue
                        if t.posicao == Posicao.GOL and res.posicao != Posicao.GOL:
                            continue
                        if t.posicao != Posicao.GOL and res.posicao == Posicao.GOL:
                            continue
                        candidato_sai = t
                        reserva_entra = res
                        break
                    if candidato_sai:
                        break
                if not candidato_sai or not reserva_entra:
                    # Fallback: substituir o pior titular por melhor reserva disponível
                    for t in tits_sorted:
                        if t.id in tit_ids_subbed or t.posicao == Posicao.GOL:
                            continue
                        for res in reservas_sorted:
                            if res.id in tit_ids_subbed and res.posicao != Posicao.GOL:
                                continue
                            candidato_sai = t
                            reserva_entra = res
                            break
                        if candidato_sai:
                            break
                if candidato_sai and reserva_entra:
                    subs.append({
                        "minuto": minutos_sub[i],
                        "sai_id": candidato_sai.id,
                        "entra_id": reserva_entra.id,
                        "time_nome": time.nome,
                    })
                    tit_ids_subbed.add(candidato_sai.id)
                    tit_ids_subbed.add(reserva_entra.id)
                    sub_count += 1
        return subs

    def _forca_setor(self, time: Time, setor: str) -> float:
        posicoes = SETOR_POSICOES.get(setor, set())
        tits = self._titulares(time)
        jogadores = [j for j in tits if j.posicao.name in posicoes]
        if not jogadores:
            return 40.0
        return sum(j.overall for j in jogadores) / len(jogadores)

    def _chance_finalizacao(self, atacante: Time, f_atk: float, f_def: float) -> float:
        mult = ESTILO_MULT_FINALIZACAO.get(atacante.tatica.estilo.value, 1.0)
        ratio = f_atk / max(1, f_def)
        return SIM_CHANCE_FINALIZACAO_BASE * mult * (0.7 + ratio * 0.3)

    # ─── finalização ──────────────────────────────────────────

    def _chance_ataque_contextual(self, atacante: Time, f_atk: float, f_def: float) -> float:
        mult = ESTILO_MULT_FINALIZACAO.get(atacante.tatica.estilo.value, 1.0)
        velocidade = {
            "Lento": 0.94,
            "Normal": 1.0,
            "Rápido": 1.08,
        }.get(atacante.tatica.velocidade.value, 1.0)
        ratio = f_atk / max(1.0, f_def)
        raw = SIM_CHANCE_FINALIZACAO_BASE * 6.4 * mult * velocidade * (0.82 + ratio * 0.18)
        return max(0.08, min(0.26, raw))

    def _simular_fase_ofensiva(
        self,
        atacante: Time,
        defensor: Time,
        minuto: int,
        resultado: ResultadoPartida,
        f_atk: float,
        f_def: float,
    ) -> Tuple[int, int]:
        estilo = self._escolher_estilo_jogada(atacante, defensor)
        criador = self._escolher_criador_contextual(atacante, estilo)
        ruptura = self._escolher_jogador_ruptura(atacante, estilo, criador)
        marcador = self._escolher_marcador_contextual(defensor, estilo)
        if not criador or not ruptura or not marcador:
            return 0, 0

        qualidade = self._nota_construcao(atacante, criador, ruptura, estilo, f_atk)
        pressao = self._nota_pressao(defensor, marcador, estilo, f_def)
        chance_progressao = 0.44 + (qualidade - pressao) / 230
        if atacante.tatica.toque_curto:
            chance_progressao += 0.03
        if atacante.tatica.contra_ataque and estilo == "contra":
            chance_progressao += 0.05
        if defensor.tatica.marcacao == MarcacaoPressao.ALTA:
            chance_progressao -= 0.02
        chance_progressao = max(0.24, min(0.8, chance_progressao))

        zona = self._definir_zona_ataque(estilo, qualidade, pressao)
        if estilo in {"direto", "contra", "centro", "curto"}:
            chance_impedimento = self._chance_impedimento_contextual(defensor, criador, ruptura, estilo)
            if random.random() < chance_impedimento:
                self._incrementar_stat(resultado, atacante, "impedimentos")
                self.eventos.append(EventoPartida(
                    minuto=minuto,
                    tipo="impedimento",
                    jogador_nome=ruptura.nome,
                    jogador_id=ruptura.id,
                    time=atacante.nome,
                    detalhe=_narr(_NARR_IMPEDIMENTO, jogador=ruptura.nome),
                ))
                self._registrar_momentum(minuto, atacante.nome, 1)
                return 0, 0

        if random.random() > chance_progressao:
            chance_falta = self._chance_falta_contextual(ruptura, marcador, zona, estilo, defensor) * 1.35
            if random.random() < chance_falta:
                if zona == "area":
                    zona_falta = "area" if random.random() < 0.25 else "entrada_area"
                else:
                    zona_falta = zona
                return self._resolver_falta_contextual(
                    atacante, defensor, minuto, resultado, criador, ruptura, marcador, zona_falta
                )
            if estilo in {"lateral", "direto"} and random.random() < (0.2 + max(0.0, qualidade - pressao) / 420):
                return self._resolver_escanteio_contextual(atacante, defensor, minuto, resultado, criador)
            return 0, 0

        chance_falta = self._chance_falta_contextual(ruptura, marcador, zona, estilo, defensor)
        if random.random() < chance_falta:
            return self._resolver_falta_contextual(atacante, defensor, minuto, resultado, criador, ruptura, marcador, zona)

        if estilo == "lateral" and random.random() < 0.4:
            return self._resolver_escanteio_contextual(atacante, defensor, minuto, resultado, criador)

        perfil, base_xg = self._definir_perfil_finalizacao(estilo, zona, qualidade, pressao)
        finalizador = self._escolher_finalizador_contextual(atacante, perfil, ruptura)
        assistente = criador if criador.id != finalizador.id else self._escolher_assistente(self._titulares(atacante), finalizador)
        self._resolver_finalizacao_contextual(
            atacante=atacante,
            defensor=defensor,
            minuto=minuto,
            resultado=resultado,
            finalizador=finalizador,
            assistente=assistente,
            perfil=perfil,
            base_xg=base_xg,
            tipo_gol="gol",
            permitir_escanteio=True,
        )
        return 0, 0

    def _escolher_estilo_jogada(self, atacante: Time, defensor: Time) -> str:
        pesos = {
            "curto": 1.0,
            "direto": 0.8,
            "lateral": 0.9,
            "centro": 0.9,
            "contra": 0.7,
        }
        if atacante.tatica.toque_curto:
            pesos["curto"] += 1.2
        if atacante.tatica.bola_longa:
            pesos["direto"] += 1.5
        if atacante.tatica.jogo_pelas_laterais:
            pesos["lateral"] += 1.6
        if atacante.tatica.jogo_pelo_centro:
            pesos["centro"] += 1.6
        if atacante.tatica.contra_ataque:
            pesos["contra"] += 1.4
        if defensor.tatica.zaga_adiantada or defensor.tatica.linha_alta:
            pesos["direto"] += 0.5
            pesos["contra"] += 0.5
        estilos = list(pesos.keys())
        return random.choices(estilos, weights=[pesos[e] for e in estilos], k=1)[0]

    def _escolher_criador_contextual(self, time: Time, estilo: str) -> Optional[Jogador]:
        posicoes = {
            "curto": {"MC", "MEI", "VOL", "ME", "MD", "CA", "SA"},
            "direto": {"ZAG", "VOL", "MC", "MEI", "LD", "LE"},
            "lateral": {"LD", "LE", "ME", "MD", "PE", "PD", "MC"},
            "centro": {"MEI", "MC", "VOL", "SA", "CA"},
            "contra": {"VOL", "MC", "MEI", "PE", "PD", "CA", "SA"},
        }.get(estilo, {"MC", "MEI", "VOL"})
        cands = self._filtrar_titulares(time, posicoes)
        return self._escolher_jogador(cands, lambda j: self._peso_criador(j, estilo))

    def _escolher_jogador_ruptura(self, time: Time, estilo: str, criador: Optional[Jogador]) -> Optional[Jogador]:
        posicoes = {
            "curto": {"CA", "SA", "PE", "PD", "MEI"},
            "direto": {"CA", "SA", "PE", "PD"},
            "lateral": {"CA", "SA", "PE", "PD", "ME", "MD"},
            "centro": {"CA", "SA", "MEI", "MC"},
            "contra": {"CA", "SA", "PE", "PD", "MEI"},
        }.get(estilo, {"CA", "SA"})
        excluir = {criador.id} if criador else set()
        cands = self._filtrar_titulares(time, posicoes, excluir)
        return self._escolher_jogador(cands, lambda j: self._peso_ruptura(j, estilo))

    def _escolher_marcador_contextual(self, time: Time, estilo: str) -> Optional[Jogador]:
        posicoes = {
            "lateral": {"LD", "LE", "ZAG", "VOL"},
            "centro": {"ZAG", "VOL", "MC"},
            "direto": {"ZAG", "VOL"},
            "contra": {"ZAG", "VOL", "LD", "LE"},
            "curto": {"VOL", "MC", "ZAG"},
        }.get(estilo, {"ZAG", "VOL"})
        cands = self._filtrar_titulares(time, posicoes)
        return self._escolher_jogador(
            cands,
            lambda j: (j.tecnicos.desarme + j.tecnicos.marcacao + j.mentais.posicionamento + j.mentais.agressividade) / 4,
        )

    def _peso_criador(self, jogador: Jogador, estilo: str) -> float:
        base = jogador.tecnicos.passe_curto + jogador.mentais.visao_jogo + jogador.mentais.decisao
        if estilo == "direto":
            base = jogador.tecnicos.passe_longo + jogador.tecnicos.lancamento + jogador.mentais.visao_jogo
        elif estilo == "lateral":
            base = jogador.tecnicos.cruzamento + jogador.tecnicos.passe_curto + jogador.mentais.visao_jogo
        elif estilo == "contra":
            base += jogador.fisicos.aceleracao + jogador.mentais.criatividade
        elif estilo == "centro":
            base += jogador.tecnicos.controle_bola + jogador.mentais.criatividade
        if jogador.tem_trait(TraitJogador.ASSISTENTE):
            base *= 1.15
        return max(1.0, base)

    def _peso_ruptura(self, jogador: Jogador, estilo: str) -> float:
        base = jogador.fisicos.velocidade + jogador.fisicos.aceleracao + jogador.mentais.antecipacao
        base += jogador.tecnicos.finalizacao + jogador.mentais.compostura
        if estilo == "lateral":
            base += jogador.tecnicos.cabeceio + jogador.fisicos.salto
        elif estilo == "contra":
            base += jogador.tecnicos.drible + jogador.mentais.decisao
        return max(1.0, base)

    def _nota_construcao(
        self,
        atacante: Time,
        criador: Jogador,
        ruptura: Jogador,
        estilo: str,
        f_atk: float,
    ) -> float:
        nota = self._peso_criador(criador, estilo) * 0.55 + self._peso_ruptura(ruptura, estilo) * 0.45
        nota /= 100
        nota += self._forca_setor(atacante, "meio") / 100
        nota += f_atk / 120
        return nota

    def _nota_pressao(self, defensor: Time, marcador: Jogador, estilo: str, f_def: float) -> float:
        nota = (
            marcador.tecnicos.desarme
            + marcador.tecnicos.marcacao
            + marcador.mentais.posicionamento
            + marcador.mentais.antecipacao
        ) / 65
        nota += self._forca_setor(defensor, "defesa") / 100
        nota += f_def / 125
        if defensor.tatica.marcacao == MarcacaoPressao.ALTA:
            nota += 0.25
        if estilo == "lateral":
            nota += 0.1
        return nota

    def _definir_zona_ataque(self, estilo: str, qualidade: float, pressao: float) -> str:
        vantagem = qualidade - pressao
        if estilo == "lateral":
            return "entrada_area" if vantagem > 0.3 and random.random() < 0.4 else "lateral"
        if estilo == "contra":
            return "area" if vantagem > 0.1 or random.random() < 0.55 else "entrada_area"
        if estilo == "direto":
            return "area" if random.random() < 0.5 else "entrada_area"
        if estilo == "centro":
            return "area" if vantagem > -0.05 and random.random() < 0.45 else "entrada_area"
        return "area" if vantagem > 0.1 and random.random() < 0.4 else "entrada_area"

    def _chance_impedimento_contextual(
        self,
        defensor: Time,
        criador: Jogador,
        ruptura: Jogador,
        estilo: str,
    ) -> float:
        chance = SIM_CHANCE_IMPEDIMENTO + 0.075
        if estilo == "direto":
            chance += 0.06
        elif estilo == "contra":
            chance += 0.05
        elif estilo == "centro":
            chance += 0.03
        if defensor.tatica.zaga_adiantada or defensor.tatica.linha_alta:
            chance += 0.04
        if defensor.tatica.marcacao == MarcacaoPressao.ALTA:
            chance += 0.02
        chance -= (criador.mentais.visao_jogo - 50) / 700
        chance -= (ruptura.mentais.antecipacao - 50) / 600
        chance -= (ruptura.mentais.decisao - 50) / 750
        return max(0.05, min(0.38, chance))

    def _chance_falta_contextual(
        self,
        alvo: Jogador,
        marcador: Jogador,
        zona: str,
        estilo: str,
        defensor: Time,
    ) -> float:
        duelo = (alvo.tecnicos.drible + alvo.fisicos.aceleracao + alvo.mentais.decisao) / 3
        combate = (
            marcador.tecnicos.desarme
            + marcador.tecnicos.marcacao
            + marcador.mentais.agressividade
            + marcador.mentais.bravura
        ) / 4
        chance = SIM_CHANCE_FALTA * 1.9 + 0.095 + (combate - duelo) / 280
        if defensor.tatica.marcacao == MarcacaoPressao.ALTA:
            chance += 0.06
        if zona == "area":
            chance += 0.04
        elif zona == "entrada_area":
            chance += 0.03
        if estilo == "contra":
            chance += 0.02
        return max(0.12, min(0.42, chance))

    def _resolver_falta_contextual(
        self,
        atacante: Time,
        defensor: Time,
        minuto: int,
        resultado: ResultadoPartida,
        criador: Jogador,
        alvo: Jogador,
        marcador: Jogador,
        zona: str,
    ) -> Tuple[int, int]:
        faltoso = marcador
        self._incrementar_stat(resultado, defensor, "faltas")
        self._add_fantasy(faltoso.id, FANTASY_PONTOS["falta_cometida"])
        self._add_fantasy(alvo.id, FANTASY_PONTOS["falta_sofrida"])

        detalhe = {
            "area": f"{faltoso.nome} atropela {alvo.nome} dentro da area.",
            "entrada_area": f"{faltoso.nome} derruba {alvo.nome} na entrada da area.",
            "lateral": f"{faltoso.nome} para {alvo.nome} pelo lado do campo.",
            "meio": f"{faltoso.nome} interrompe {alvo.nome} com falta no meio-campo.",
        }.get(zona, _narr(_NARR_FALTA, jogador=faltoso.nome))
        self.eventos.append(EventoPartida(
            minuto=minuto,
            tipo="falta",
            jogador_nome=faltoso.nome,
            jogador_id=faltoso.id,
            time=defensor.nome,
            detalhe=detalhe,
        ))

        dv_c, dv_f = self._aplicar_cartao_contextual(faltoso, defensor, minuto, zona)
        if zona == "area":
            pen_c, pen_f = self._resolver_penalti_contextual(
                atacante, defensor, minuto, resultado, alvo=alvo, faltoso=faltoso
            )
            dv_c += pen_c
            dv_f += pen_f
        elif zona in {"entrada_area", "lateral"}:
            fk_c, fk_f = self._resolver_falta_bolaparada(
                atacante, defensor, minuto, resultado, criador=criador, zona=zona
            )
            dv_c += fk_c
            dv_f += fk_f
        else:
            self._registrar_momentum(minuto, atacante.nome, 1)
        return dv_c, dv_f

    def _aplicar_cartao_contextual(
        self,
        faltoso: Jogador,
        time_faltoso: Time,
        minuto: int,
        zona: str,
    ) -> Tuple[int, int]:
        chance_vermelho = 0.003 + max(0, faltoso.mentais.agressividade - 70) / 1100
        chance_amarelo = 0.1 + max(0, faltoso.mentais.agressividade - 50) / 450
        if zona == "area":
            chance_vermelho += 0.012
            chance_amarelo += 0.03
        elif zona == "entrada_area":
            chance_amarelo += 0.02

        if random.random() < chance_vermelho:
            faltoso.suspensao_jogos += 2
            faltoso.historico_temporada.cartoes_vermelhos += 1
            self._add_fantasy(faltoso.id, FANTASY_PONTOS["cartao_vermelho"])
            self.eventos.append(EventoPartida(
                minuto=minuto,
                tipo="cartao_vermelho",
                jogador_nome=faltoso.nome,
                jogador_id=faltoso.id,
                time=time_faltoso.nome,
                detalhe=_narr(_NARR_VERMELHO, jogador=faltoso.nome),
            ))
            return self._delta_vermelho(time_faltoso)

        if random.random() < chance_amarelo:
            faltoso.cartao_amarelo_acumulado += 1
            faltoso.historico_temporada.cartoes_amarelos += 1
            self._add_fantasy(faltoso.id, FANTASY_PONTOS["cartao_amarelo"])
            if faltoso.cartao_amarelo_acumulado >= 2:
                faltoso.cartao_amarelo_acumulado = 0
                faltoso.suspensao_jogos += 1
                faltoso.historico_temporada.cartoes_vermelhos += 1
                self._add_fantasy(faltoso.id, FANTASY_PONTOS["cartao_vermelho"])
                self.eventos.append(EventoPartida(
                    minuto=minuto,
                    tipo="cartao_vermelho",
                    jogador_nome=faltoso.nome,
                    jogador_id=faltoso.id,
                    time=time_faltoso.nome,
                    detalhe=_narr(_NARR_VERMELHO_2AM, jogador=faltoso.nome),
                ))
                return self._delta_vermelho(time_faltoso)
            self.eventos.append(EventoPartida(
                minuto=minuto,
                tipo="cartao_amarelo",
                jogador_nome=faltoso.nome,
                jogador_id=faltoso.id,
                time=time_faltoso.nome,
                detalhe=_narr(_NARR_AMARELO, jogador=faltoso.nome),
            ))
        return 0, 0

    def _resolver_penalti_contextual(
        self,
        atacante: Time,
        defensor: Time,
        minuto: int,
        resultado: ResultadoPartida,
        alvo: Jogador,
        faltoso: Jogador,
    ) -> Tuple[int, int]:
        cobrador = self._escolher_cobrador(atacante, "penalti")
        detalhe = _narr(
            _NARR_PENALTY,
            time=atacante.nome,
            faltoso=faltoso.nome,
            alvo=alvo.nome,
        )
        self.eventos.append(EventoPartida(
            minuto=minuto,
            tipo="penalty",
            jogador_nome=cobrador.nome,
            jogador_id=cobrador.id,
            time=atacante.nome,
            detalhe=detalhe,
        ))
        self._resolver_finalizacao_contextual(
            atacante=atacante,
            defensor=defensor,
            minuto=minuto,
            resultado=resultado,
            finalizador=cobrador,
            assistente=None,
            perfil="penalti",
            base_xg=0.76 + (cobrador.tecnicos.penalti - 50) / 500,
            tipo_gol="gol",
            narrativa_gol=_narr(_NARR_GOL_PENALTI, jogador=cobrador.nome),
            permitir_escanteio=False,
        )
        return 0, 0

    def _resolver_falta_bolaparada(
        self,
        atacante: Time,
        defensor: Time,
        minuto: int,
        resultado: ResultadoPartida,
        criador: Jogador,
        zona: str,
    ) -> Tuple[int, int]:
        cobrador = self._escolher_cobrador(atacante, "falta")
        if zona == "entrada_area" and (cobrador.tecnicos.falta >= 77 or random.random() < 0.22):
            self._resolver_finalizacao_contextual(
                atacante=atacante,
                defensor=defensor,
                minuto=minuto,
                resultado=resultado,
                finalizador=cobrador,
                assistente=None,
                perfil="falta",
                base_xg=0.05 + (cobrador.tecnicos.falta - 50) / 760,
                tipo_gol="gol_falta",
                narrativa_gol=_narr(_NARR_GOL_FALTA, jogador=cobrador.nome),
                permitir_escanteio=True,
            )
            return 0, 0

        alvo = self._escolher_jogador(
            self._filtrar_titulares(atacante, {"CA", "SA", "ZAG", "VOL", "PE", "PD"}, {cobrador.id}),
            lambda j: j.tecnicos.cabeceio + j.fisicos.salto + j.tecnicos.finalizacao,
        ) or criador
        self._resolver_finalizacao_contextual(
            atacante=atacante,
            defensor=defensor,
            minuto=minuto,
            resultado=resultado,
            finalizador=alvo,
            assistente=cobrador,
            perfil="cabecada",
            base_xg=0.13 if zona == "entrada_area" else 0.1,
            tipo_gol="gol",
            permitir_escanteio=True,
        )
        return 0, 0

    def _resolver_escanteio_contextual(
        self,
        atacante: Time,
        defensor: Time,
        minuto: int,
        resultado: ResultadoPartida,
        origem: Optional[Jogador] = None,
    ) -> Tuple[int, int]:
        self._incrementar_stat(resultado, atacante, "escanteios")
        self.eventos.append(EventoPartida(
            minuto=minuto,
            tipo="escanteio",
            jogador_nome=origem.nome if origem else atacante.nome,
            jogador_id=origem.id if origem else 0,
            time=atacante.nome,
            detalhe=_narr(_NARR_ESCANTEIO, time=atacante.nome),
        ))

        cobrador = self._escolher_cobrador(atacante, "escanteio")
        chance_cabecada = 0.34 + (cobrador.tecnicos.cruzamento - 50) / 360
        chance_cabecada += (self._forca_setor(atacante, "ataque") - self._forca_setor(defensor, "defesa")) / 500
        if random.random() >= max(0.18, min(0.5, chance_cabecada)):
            self._registrar_momentum(minuto, atacante.nome, 1)
            return 0, 0

        alvo = self._escolher_jogador(
            self._filtrar_titulares(atacante, {"CA", "SA", "ZAG", "VOL", "PE", "PD"}, {cobrador.id}),
            lambda j: j.tecnicos.cabeceio + j.fisicos.salto + j.mentais.bravura + j.tecnicos.finalizacao,
        )
        if not alvo:
            return 0, 0
        self._resolver_finalizacao_contextual(
            atacante=atacante,
            defensor=defensor,
            minuto=minuto,
            resultado=resultado,
            finalizador=alvo,
            assistente=cobrador,
            perfil="cabecada",
            base_xg=0.09 + (alvo.tecnicos.cabeceio - 50) / 500,
            tipo_gol="gol",
            permitir_escanteio=False,
        )
        return 0, 0

    def _definir_perfil_finalizacao(
        self,
        estilo: str,
        zona: str,
        qualidade: float,
        pressao: float,
    ) -> Tuple[str, float]:
        vantagem = qualidade - pressao
        if estilo == "lateral":
            if random.random() < 0.58:
                return "cabecada", 0.14 + vantagem / 18
            return "cutback", 0.18 + vantagem / 16
        if estilo == "contra":
            if random.random() < 0.55:
                return "cara_a_cara", 0.3 + vantagem / 14
            return "area", 0.2 + vantagem / 18
        if estilo == "direto":
            if zona == "area" and random.random() < 0.45:
                return "cara_a_cara", 0.26 + vantagem / 16
            if random.random() < 0.35:
                return "cabecada", 0.13 + vantagem / 20
            return "longa", 0.08 + vantagem / 24
        if estilo == "centro":
            if zona == "area":
                return "area", 0.22 + vantagem / 16
            return "media", 0.11 + vantagem / 20
        if zona == "area":
            return "area", 0.2 + vantagem / 18
        if random.random() < 0.3:
            return "longa", 0.07 + vantagem / 26
        return "media", 0.1 + vantagem / 22

    def _escolher_finalizador_contextual(
        self,
        time: Time,
        perfil: str,
        preferido: Optional[Jogador],
    ) -> Jogador:
        posicoes = {
            "cabecada": {"CA", "SA", "ZAG", "VOL", "PE", "PD"},
            "cutback": {"CA", "SA", "PE", "PD", "MEI"},
            "cara_a_cara": {"CA", "SA", "PE", "PD", "MEI"},
            "area": {"CA", "SA", "PE", "PD", "MEI"},
            "media": {"MEI", "MC", "CA", "SA", "PE", "PD"},
            "longa": {"MC", "MEI", "VOL", "CA", "SA"},
            "falta": {"MEI", "MC", "PE", "PD", "CA"},
            "penalti": {"CA", "SA", "MEI", "MC", "PE", "PD"},
        }.get(perfil, {"CA", "SA", "MEI"})
        cands = self._filtrar_titulares(time, posicoes)
        if preferido and preferido in cands and random.random() < 0.55:
            return preferido
        return self._escolher_jogador(cands, lambda j: self._peso_finalizador(j, perfil)) or preferido or self._titulares(time)[0]

    def _peso_finalizador(self, jogador: Jogador, perfil: str) -> float:
        if perfil == "cabecada":
            base = jogador.tecnicos.cabeceio + jogador.fisicos.salto + jogador.mentais.bravura
        elif perfil == "longa":
            base = jogador.tecnicos.chute_longa_dist + jogador.mentais.compostura + jogador.mentais.criatividade
        elif perfil == "falta":
            base = jogador.tecnicos.falta + jogador.mentais.compostura + jogador.mentais.decisao
        elif perfil == "penalti":
            base = jogador.tecnicos.penalti + jogador.mentais.compostura + jogador.mentais.decisao
        else:
            base = jogador.tecnicos.finalizacao + jogador.mentais.compostura + jogador.tecnicos.controle_bola
        if jogador.tem_trait(TraitJogador.ARTILHEIRO):
            base *= 1.12
        return max(1.0, base)

    def _resolver_finalizacao_contextual(
        self,
        atacante: Time,
        defensor: Time,
        minuto: int,
        resultado: ResultadoPartida,
        finalizador: Jogador,
        assistente: Optional[Jogador],
        perfil: str,
        base_xg: float,
        tipo_gol: str,
        narrativa_gol: Optional[str] = None,
        permitir_escanteio: bool = True,
    ) -> Tuple[bool, bool]:
        self._incrementar_stat(resultado, atacante, "finalizacoes")
        goleiro = self._goleiro(defensor)
        defesa_gol = int(goleiro.goleiro.overall()) if goleiro else 50
        pressao_def = self._forca_setor(defensor, "defesa")

        tecnica = self._peso_finalizador(finalizador, perfil) / 3
        chance_no_alvo = 0.28 + (tecnica - 50) / 220 + (finalizador.mentais.compostura - 50) / 450
        if perfil == "penalti":
            chance_no_alvo += 0.3
        elif perfil == "cara_a_cara":
            chance_no_alvo += 0.1
        elif perfil == "cabecada":
            chance_no_alvo -= 0.05
        elif perfil in {"longa", "media"}:
            chance_no_alvo -= 0.06
        chance_no_alvo = max(0.22, min(0.84, chance_no_alvo))

        xg_shot = base_xg
        xg_shot += (tecnica - 50) / 280
        xg_shot -= (pressao_def - 50) / 360
        xg_shot -= (defesa_gol - 50) / 500
        if assistente:
            xg_shot += (assistente.mentais.visao_jogo - 50) / 650
        if finalizador.tem_trait(TraitJogador.ARTILHEIRO):
            xg_shot += 0.02
        if perfil not in {"falta", "penalti"}:
            xg_shot += 0.018
        xg_shot = round(max(0.03, min(0.88, xg_shot)), 3)
        self._registrar_xg(atacante, xg_shot)

        if random.random() >= chance_no_alvo:
            if permitir_escanteio and random.random() < {
                "cabecada": 0.34,
                "cutback": 0.32,
                "media": 0.22,
                "longa": 0.16,
            }.get(perfil, 0.0):
                self._resolver_escanteio_contextual(atacante, defensor, minuto, resultado, assistente or finalizador)
            return False, False

        self._incrementar_stat(resultado, atacante, "finalizacoes_gol")
        self._add_fantasy(finalizador.id, FANTASY_PONTOS["finalizacao_gol"])

        chance_gol_condicional = max(0.08, min(0.94, xg_shot / max(0.18, chance_no_alvo)))
        gol = random.random() < chance_gol_condicional
        if gol:
            self._registrar_gol_contextual(
                atacante=atacante,
                resultado=resultado,
                minuto=minuto,
                finalizador=finalizador,
                assistente=assistente,
                xg_shot=xg_shot,
                tipo_gol=tipo_gol,
                narrativa_gol=narrativa_gol,
            )
            return True, True

        if goleiro:
            self._add_fantasy(goleiro.id, FANTASY_PONTOS["defesa_dificil"])
            self.eventos.append(EventoPartida(
                minuto=minuto,
                tipo="defesa_dificil",
                jogador_nome=goleiro.nome,
                jogador_id=goleiro.id,
                time=defensor.nome,
                detalhe=_narr(_NARR_DEFESA, goleiro=goleiro.nome, jogador=finalizador.nome),
            ))
        if perfil == "penalti":
            self._add_fantasy(finalizador.id, FANTASY_PONTOS["penalti_perdido"])
            if goleiro:
                self._add_fantasy(goleiro.id, FANTASY_PONTOS["defesa_penalti"])
        elif permitir_escanteio and random.random() < {
            "cabecada": 0.42,
            "cutback": 0.38,
            "media": 0.28,
            "longa": 0.18,
        }.get(perfil, 0.0):
            self._resolver_escanteio_contextual(atacante, defensor, minuto, resultado, assistente or finalizador)
        self._registrar_momentum(minuto, atacante.nome, 1)
        return False, True

    def _registrar_gol_contextual(
        self,
        atacante: Time,
        resultado: ResultadoPartida,
        minuto: int,
        finalizador: Jogador,
        assistente: Optional[Jogador],
        xg_shot: float,
        tipo_gol: str,
        narrativa_gol: Optional[str],
    ) -> None:
        if atacante.nome == resultado.time_casa:
            resultado.gols_casa += 1
        else:
            resultado.gols_fora += 1

        detalhe = narrativa_gol or _narr(_NARR_GOL, jogador=finalizador.nome)
        if assistente and assistente.id != finalizador.id and tipo_gol == "gol" and narrativa_gol is None:
            detalhe = _narr(_NARR_GOL_ASSIST, jogador=finalizador.nome, assist=assistente.nome)
            assistente.historico_temporada.assistencias += 1
            self._add_fantasy(assistente.id, FANTASY_PONTOS["assistencia"])
            self._registrar_xa(atacante, round(xg_shot * 0.78, 3))

        self.eventos.append(EventoPartida(
            minuto=minuto,
            tipo=tipo_gol,
            jogador_nome=finalizador.nome,
            jogador_id=finalizador.id,
            time=atacante.nome,
            detalhe=detalhe,
        ))
        finalizador.historico_temporada.gols += 1
        finalizador.moral = min(100, finalizador.moral + 5)
        setor = self._setor_jogador(finalizador)
        self._add_fantasy(finalizador.id, FANTASY_PONTOS.get(f"gol_{setor}", 8.0))
        self._registrar_momentum(minuto, atacante.nome, 3)

    def _filtrar_titulares(
        self,
        time: Time,
        posicoes: Optional[set] = None,
        excluir_ids: Optional[set] = None,
    ) -> List[Jogador]:
        jogadores = self._titulares(time)
        if posicoes:
            jogadores = [j for j in jogadores if j.posicao.name in posicoes]
        if excluir_ids:
            jogadores = [j for j in jogadores if j.id not in excluir_ids]
        if jogadores:
            return jogadores
        return [j for j in self._titulares(time) if not excluir_ids or j.id not in excluir_ids]

    def _escolher_jogador(self, jogadores: List[Jogador], peso_fn) -> Optional[Jogador]:
        if not jogadores:
            return None
        pesos = [max(0.1, float(peso_fn(j))) for j in jogadores]
        return random.choices(jogadores, weights=pesos, k=1)[0]

    def _escolher_cobrador(self, time: Time, tipo: str) -> Jogador:
        preferido = {
            "falta": time.tatica.cobrador_falta,
            "penalti": time.tatica.cobrador_penalti,
            "escanteio": time.tatica.cobrador_escanteio,
        }.get(tipo)
        titular_ids = {j.id for j in self._titulares(time)}
        if preferido and preferido in titular_ids:
            jogador = time.jogador_por_id(preferido)
            if jogador:
                return jogador
        pesos = {
            "falta": lambda j: j.tecnicos.falta + j.mentais.compostura + j.mentais.criatividade,
            "penalti": lambda j: j.tecnicos.penalti + j.mentais.compostura + j.mentais.decisao,
            "escanteio": lambda j: j.tecnicos.cruzamento + j.tecnicos.passe_curto + j.mentais.visao_jogo,
        }[tipo]
        return self._escolher_jogador(self._titulares(time), pesos) or self._titulares(time)[0]

    def _incrementar_stat(self, resultado: ResultadoPartida, time: Time, base: str, valor: int = 1) -> None:
        lado = "casa" if time.nome == resultado.time_casa else "fora"
        campo = f"{base}_{lado}"
        setattr(resultado, campo, getattr(resultado, campo) + valor)

    def _registrar_xg(self, time: Time, valor: float) -> None:
        if time.nome == self._time_casa_nome:
            self._xg_casa += valor
        else:
            self._xg_fora += valor

    def _registrar_xa(self, time: Time, valor: float) -> None:
        if time.nome == self._time_casa_nome:
            self._xa_casa += valor
        else:
            self._xa_fora += valor

    def _registrar_momentum(self, minuto: int, time_nome: str, intensidade: int) -> None:
        self._momentum.append({"min": minuto, "time": time_nome, "intensidade": intensidade})

    def _delta_vermelho(self, time: Time) -> Tuple[int, int]:
        if time.nome == self._time_casa_nome:
            return 1, 0
        return 0, 1

    def _resolver_finalizacao(
        self, atacante: Time, defensor: Time, minuto: int
    ) -> Tuple[bool, bool, Optional[EventoPartida], float]:
        tits_atk = self._titulares(atacante)
        if not tits_atk:
            return False, False, None, 0.0

        # Peso por posição
        pesos = [PESO_FINALIZACAO.get(j.posicao.name, 0.5) for j in tits_atk]
        total = sum(pesos)
        if total == 0:
            return False, False, None, 0.0
        pesos_n = [p / total for p in pesos]
        finalizador: Jogador = random.choices(tits_atk, weights=pesos_n, k=1)[0]

        # Chance no gol
        fin = finalizador.tecnicos.finalizacao
        comp = finalizador.mentais.compostura
        bonus_trait = 5 if finalizador.tem_trait(TraitJogador.ARTILHEIRO) else 0
        chance_target = 0.35 + (fin + bonus_trait - 50) / 300 + (comp - 50) / 500

        # ── xG: probabilidade pré-resolução de ser gol ──
        goleiro = self._goleiro(defensor)
        def_gol = int(goleiro.goleiro.overall()) if goleiro else 50
        forca_def = self._forca_setor(defensor, "defesa")
        chance_defesa_xg = 0.45 + (def_gol - 50) / 250 - (fin - 50) / 350
        chance_defesa_xg += (forca_def - 50) / 600
        chance_defesa_xg = max(0.15, min(0.85, chance_defesa_xg))
        xg_shot = round(max(0.0, min(1.0, chance_target * (1.0 - chance_defesa_xg))), 3)

        if random.random() >= chance_target:
            return False, False, None, xg_shot  # para fora

        # Goleiro adversário
        chance_defesa = chance_defesa_xg  # already computed
        gol = random.random() > chance_defesa

        if gol:
            assistente = self._escolher_assistente(tits_atk, finalizador)
            detalhe = _narr(_NARR_GOL, jogador=finalizador.nome)
            xa_shot = 0.0
            if assistente:
                detalhe = _narr(_NARR_GOL_ASSIST, jogador=finalizador.nome, assist=assistente.nome)
                assistente.historico_temporada.assistencias += 1
                self._add_fantasy(assistente.id, FANTASY_PONTOS["assistencia"])
                # xA: credit assist contribution
                xa_shot = round(xg_shot * 0.8, 3)
                if atacante.nome == self._time_casa_nome:
                    self._xa_casa += xa_shot
                else:
                    self._xa_fora += xa_shot

            tipo_gol = "gol"
            if random.random() < 0.08:
                tipo_gol = "gol_falta"
                detalhe = _narr(_NARR_GOL_FALTA, jogador=finalizador.nome)
            elif random.random() < 0.05:
                detalhe = _narr(_NARR_GOL_PENALTI, jogador=finalizador.nome)

            evt = EventoPartida(
                minuto=minuto, tipo=tipo_gol,
                jogador_nome=finalizador.nome,
                jogador_id=finalizador.id,
                time=atacante.nome, detalhe=detalhe,
            )
            finalizador.historico_temporada.gols += 1
            finalizador.moral = min(100, finalizador.moral + 5)

            # Fantasy — gol
            setor = self._setor_jogador(finalizador)
            chave = f"gol_{setor}"
            self._add_fantasy(finalizador.id, FANTASY_PONTOS.get(chave, 8.0))

            return True, True, evt, xg_shot

        # Defesa do goleiro (sem evento público)
        if goleiro:
            self._add_fantasy(goleiro.id, FANTASY_PONTOS["defesa_dificil"])
        return False, True, None, xg_shot

    # ─── assistência ──────────────────────────────────────────

    def _escolher_assistente(self, titulares: List[Jogador], finalizador: Jogador) -> Optional[Jogador]:
        if random.random() > 0.65:
            return None
        cands = [j for j in titulares if j.id != finalizador.id]
        if not cands:
            return None
        pesos = []
        for j in cands:
            p = j.tecnicos.passe_curto / 50 + j.mentais.visao_jogo / 50
            if j.posicao in (Posicao.MC, Posicao.MEI, Posicao.ME, Posicao.MD):
                p *= 2.0
            elif j.posicao in (Posicao.PE, Posicao.PD, Posicao.LD, Posicao.LE):
                p *= 1.5
            if j.tem_trait(TraitJogador.ASSISTENTE):
                p *= 1.4
            pesos.append(max(0.1, p))
        return random.choices(cands, weights=pesos, k=1)[0]

    # ─── faltas & cartões (sistema de árbitro realista) ──────

    def _init_arbitro(self) -> None:
        """Gera personalidade do árbitro para a partida."""
        # Rigor: 0.0 (permissivo) a 1.0 (rigoroso)
        self._arb_rigor = random.betavariate(2.5, 2.5)
        # Tolerância diminui ao longo do jogo (faltas acumuladas)
        self._arb_faltas_total = 0
        # Cartões já dados — árbitro fica mais criterioso após muitos
        self._arb_amarelos_dados = 0
        self._arb_vermelhos_dados = 0
        # Vantagem: árbitro pode "guardar" punição se lance não parou
        self._arb_nome = random.choice([
            "Anderson Daronco", "Wilton Pereira Sampaio", "Raphael Claus",
            "Bruno Arleu de Araújo", "Bráulio da Silva Machado",
            "Flávio Rodrigues de Souza", "Ramon Abatti Abel",
            "Luiz Flávio de Oliveira", "Wagner do Nascimento Magalhães",
            "Savio Pereira Sampaio", "Paulo César Zanovelli",
        ])

    def _resolver_falta(self, time: Time, minuto: int) -> Optional[EventoPartida]:
        tits = self._titulares(time)
        if not tits:
            return None
        # Escolher faltoso baseado na agressividade
        pesos = [max(1, j.mentais.agressividade) for j in tits]
        faltoso: Jogador = random.choices(tits, weights=pesos, k=1)[0]
        self._arb_faltas_total += 1

        # Gravidade da falta: baseada na agressividade do jogador
        agr = faltoso.mentais.agressividade
        gravidade = random.random() * (0.5 + agr / 100)  # 0-1 scale

        # Contexto: faltas mais graves perto do gol, em jogadas perigosas
        if minuto >= 80:
            gravidade *= 1.15  # Árbitro menos tolerante no final
        if self._arb_faltas_total > 20:
            gravidade *= 1.10  # Jogo "quente" — mais rigidez

        # Rigor do árbitro afeta a decisão
        rigor = self._arb_rigor

        # --- Cartão vermelho direto ---
        # Falta muito grave + árbitro rigoroso = expulsão
        chance_vermelho = 0.015 + gravidade * 0.02 + rigor * 0.015
        # Jogador já amarelado faz falta mais "cuidadosa" (reduz vermelho direto)
        if faltoso.cartao_amarelo_acumulado > 0:
            chance_vermelho *= 0.5
        chance_vermelho = min(0.06, chance_vermelho)

        if random.random() < chance_vermelho:
            faltoso.suspensao_jogos += 2
            faltoso.historico_temporada.cartoes_vermelhos += 1
            self._arb_vermelhos_dados += 1
            self._add_fantasy(faltoso.id, FANTASY_PONTOS["cartao_vermelho"])
            return EventoPartida(
                minuto=minuto, tipo="cartao_vermelho",
                jogador_nome=faltoso.nome, jogador_id=faltoso.id,
                time=time.nome, detalhe=_narr(_NARR_VERMELHO, jogador=faltoso.nome),
            )

        # --- Cartão amarelo ---
        # Base ~18% + rigor do árbitro + gravidade da falta
        chance_amarelo = 0.10 + rigor * 0.12 + gravidade * 0.08
        # Jogador reincidente — árbitro fica de olho
        if faltoso.cartao_amarelo_acumulado > 0:
            chance_amarelo *= 1.3
        # Árbitro com muitos cartões dados fica mais contido
        if self._arb_amarelos_dados >= 6:
            chance_amarelo *= 0.85
        chance_amarelo = min(0.40, chance_amarelo)

        if random.random() < chance_amarelo:
            faltoso.cartao_amarelo_acumulado += 1
            faltoso.historico_temporada.cartoes_amarelos += 1
            self._arb_amarelos_dados += 1
            self._add_fantasy(faltoso.id, FANTASY_PONTOS["cartao_amarelo"])

            if faltoso.cartao_amarelo_acumulado >= 2:
                faltoso.cartao_amarelo_acumulado = 0
                faltoso.suspensao_jogos += 1
                faltoso.historico_temporada.cartoes_vermelhos += 1
                self._arb_vermelhos_dados += 1
                self._add_fantasy(faltoso.id, FANTASY_PONTOS["cartao_vermelho"])
                return EventoPartida(
                    minuto=minuto, tipo="cartao_vermelho",
                    jogador_nome=faltoso.nome, jogador_id=faltoso.id,
                    time=time.nome, detalhe=_narr(_NARR_VERMELHO_2AM, jogador=faltoso.nome),
                )
            return EventoPartida(
                minuto=minuto, tipo="cartao_amarelo",
                jogador_nome=faltoso.nome, jogador_id=faltoso.id,
                time=time.nome, detalhe=_narr(_NARR_AMARELO, jogador=faltoso.nome),
            )
        return None

    # ─── lesão ────────────────────────────────────────────────

    def _resolver_lesao(self, time: Time, minuto: int) -> Optional[EventoPartida]:
        tits = self._titulares(time)
        if not tits:
            return None
        alvo: Jogador = random.choice(tits)
        if alvo.tem_trait(TraitJogador.VIDRACEIRO):
            chance = 0.7
        else:
            chance = 0.5
        if random.random() > chance:
            return None

        gravidade = random.choices(
            [StatusLesao.LEVE, StatusLesao.MEDIA, StatusLesao.GRAVE],
            weights=[60, 30, 10], k=1,
        )[0]
        dias = {StatusLesao.LEVE: (3, 14), StatusLesao.MEDIA: (14, 42),
                StatusLesao.GRAVE: (42, 120)}
        alvo.status_lesao = gravidade
        alvo.dias_lesao = random.randint(*dias[gravidade])
        alvo.condicao_fisica = max(0, alvo.condicao_fisica - 30)
        return EventoPartida(
            minuto=minuto, tipo="lesao",
            jogador_nome=alvo.nome, jogador_id=alvo.id,
            time=time.nome, detalhe=_narr(_NARR_LESAO, jogador=alvo.nome) + f" ({gravidade.value})",
        )

    # ═══════════════════════════════════════════════════════════
    #  PÓS-JOGO
    # ═══════════════════════════════════════════════════════════

    def _atualizar_stats_times(self, casa: Time, fora: Time, r: ResultadoPartida) -> None:
        casa.gols_marcados += r.gols_casa
        casa.gols_sofridos += r.gols_fora
        fora.gols_marcados += r.gols_fora
        fora.gols_sofridos += r.gols_casa
        if r.gols_casa > r.gols_fora:
            casa.vitorias += 1; casa.pontos += 3
            fora.derrotas += 1
        elif r.gols_casa < r.gols_fora:
            fora.vitorias += 1; fora.pontos += 3
            casa.derrotas += 1
        else:
            casa.empates += 1; casa.pontos += 1
            fora.empates += 1; fora.pontos += 1
        # Creditar renda da partida ao time da casa
        if r.renda > 0:
            casa.financas.saldo += int(r.renda)

    def _atualizar_jogadores_pos_jogo(self, casa: Time, fora: Time,
                                       r: ResultadoPartida) -> None:
        for time_obj, gols in [(casa, r.gols_casa), (fora, r.gols_fora)]:
            participantes = self._participantes.get(time_obj.nome, set(time_obj.titulares))
            for j in time_obj.jogadores:
                if j.id in participantes:
                    j.condicao_fisica = max(0, j.condicao_fisica - random.randint(15, 30))
                    j.historico_temporada.jogos += 1
                    vitoria = (gols > (r.gols_fora if time_obj == casa else r.gols_casa))
                    derrota = (gols < (r.gols_fora if time_obj == casa else r.gols_casa))
                    if vitoria:
                        j.moral = min(100, j.moral + random.randint(2, 6))
                    elif derrota:
                        j.moral = max(0, j.moral - random.randint(1, 5))

    # ── notas individuais ─────────────────────────────────────

    def _calcular_notas(self, casa: Time, fora: Time, r: ResultadoPartida) -> None:
        for time_obj in (casa, fora):
            for j in time_obj.jogadores:
                if j.id not in time_obj.titulares:
                    continue
                base = 6.0
                for evt in r.eventos:
                    if evt.jogador_id != j.id:
                        continue
                    if evt.tipo in ("gol", "gol_falta"):
                        base += 1.0
                    elif evt.tipo == "cartao_amarelo":
                        base -= 0.5
                    elif evt.tipo == "cartao_vermelho":
                        base -= 2.0
                    elif evt.tipo == "lesao":
                        base -= 1.0
                self._notas.setdefault(j.id, []).append(max(2.0, min(10.0, base)))

    # ═══════════════════════════════════════════════════════════
    #  HELPERS
    # ═══════════════════════════════════════════════════════════

    def _titulares(self, time: Time) -> List[Jogador]:
        tits = [j for j in time.jogadores if j.id in time.titulares]
        if not tits:
            return sorted(time.jogadores, key=lambda j: j.overall, reverse=True)[:11]
        return tits

    def _goleiro(self, time: Time) -> Optional[Jogador]:
        for j in time.jogadores:
            if j.id in time.titulares and j.posicao == Posicao.GOL:
                return j
        for j in time.jogadores:
            if j.posicao == Posicao.GOL:
                return j
        return None

    @staticmethod
    def _setor_jogador(j: Jogador) -> str:
        nome = j.posicao.name
        if nome == "GOL":
            return "goleiro"
        if nome in ("ZAG", "LD", "LE"):
            return "defensor"
        if nome in ("CA", "SA", "PE", "PD"):
            return "atacante"
        return "meia"

    def _add_fantasy(self, jid: int, pts: float) -> None:
        self._fantasy[jid] = self._fantasy.get(jid, 0.0) + pts
