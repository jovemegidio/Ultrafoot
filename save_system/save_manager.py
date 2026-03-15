# -*- coding: utf-8 -*-
"""
Save Manager — serializa / desserializa o estado do jogo em JSON.
Funções públicas:
    - serializar_jogo(game_manager) -> str   (JSON)
    - desserializar_jogo(game_manager, json_str) -> None
"""
from __future__ import annotations

import json
try:
    import orjson as _json_fast
    _HAS_ORJSON = True
except ImportError:
    _HAS_ORJSON = False
from typing import Any, Dict, List

from core.enums import (
    Posicao, PePreferido, StatusLesao, TipoContrato,
    NivelTreinamento, FormacaoTatica, EstiloJogo,
    VelocidadeJogo, MarcacaoPressao, TipoStaff,
    TraitJogador, StatusOferta, TipoOferta,
)
from core.models import (
    Time, Jogador, Estadio, Financas, BaseJuvenil,
    Tatica, Treinamento, ContratoJogador, StaffMembro,
    Historico, AtributosTecnicos, AtributosFisicos,
    AtributosMentais, AtributosGoleiro, OfertaTransferencia,
)
from fantasy.models import LigaFantasy, TimeFantasy, EscalacaoFantasy
from utils.helpers import enum_val


# ══════════════════════════════════════════════════════════════
#  JOGADOR → DICT / DICT → JOGADOR
# ══════════════════════════════════════════════════════════════

# ── Compact numeric attribute packing (saves ~40% per player) ──
_TEC_KEYS = ("pc","pl","cr","fi","cl","cb","dr","co","fa","pe","de","ma","la")
_FIS_KEYS = ("ve","ac","re","fo","ag","sa","eq")
_MEN_KEYS = ("vj","dc","cn","dt","li","te","cr","cp","ag","po","an","br")
_GOL_KEYS = ("rf","pg","ja","d1","rp","jp","pu","el","ca")

def _pack_attrs(j: Jogador) -> list:
    """Pack all 41 numeric attributes into a flat int list."""
    t = j.tecnicos; f = j.fisicos; m = j.mentais; g = j.goleiro
    return [
        t.passe_curto, t.passe_longo, t.cruzamento, t.finalizacao,
        t.chute_longa_dist, t.cabeceio, t.drible, t.controle_bola,
        t.falta, t.penalti, t.desarme, t.marcacao, t.lancamento,
        f.velocidade, f.aceleracao, f.resistencia, f.forca,
        f.agilidade, f.salto, f.equilibrio,
        m.visao_jogo, m.decisao, m.concentracao, m.determinacao,
        m.lideranca, m.trabalho_equipe, m.criatividade, m.compostura,
        m.agressividade, m.posicionamento, m.antecipacao, m.bravura,
        g.reflexos, g.posicionamento_gol, g.jogo_aereo, g.defesa_1v1,
        g.reposicao, g.jogo_com_pes, g.punho, g.elasticidade,
        g.comando_area,
    ]

def _unpack_attrs(a: list, j: Jogador) -> None:
    """Unpack flat int list back into attribute objects."""
    j.tecnicos = AtributosTecnicos(
        passe_curto=a[0], passe_longo=a[1], cruzamento=a[2], finalizacao=a[3],
        chute_longa_dist=a[4], cabeceio=a[5], drible=a[6], controle_bola=a[7],
        falta=a[8], penalti=a[9], desarme=a[10], marcacao=a[11], lancamento=a[12],
    )
    j.fisicos = AtributosFisicos(
        velocidade=a[13], aceleracao=a[14], resistencia=a[15], forca=a[16],
        agilidade=a[17], salto=a[18], equilibrio=a[19],
    )
    j.mentais = AtributosMentais(
        visao_jogo=a[20], decisao=a[21], concentracao=a[22], determinacao=a[23],
        lideranca=a[24], trabalho_equipe=a[25], criatividade=a[26], compostura=a[27],
        agressividade=a[28], posicionamento=a[29], antecipacao=a[30], bravura=a[31],
    )
    j.goleiro = AtributosGoleiro(
        reflexos=a[32], posicionamento_gol=a[33], jogo_aereo=a[34], defesa_1v1=a[35],
        reposicao=a[36], jogo_com_pes=a[37], punho=a[38], elasticidade=a[39],
        comando_area=a[40],
    )


def _jogador_to_dict(j: Jogador) -> dict:
    return {
        "id": j.id, "nome": j.nome, "idade": j.idade,
        "nacionalidade": j.nacionalidade,
        "posicao": j.posicao.name,
        "posicoes_alt": [p.name for p in j.posicoes_alternativas],
        "pe": j.pe_preferido.name,
        "camisa": j.numero_camisa,
        "altura": j.altura, "peso": j.peso,
        "a": _pack_attrs(j),
        "moral": j.moral, "cond": j.condicao_fisica,
        "lesao": j.status_lesao.name, "dias_lesao": j.dias_lesao,
        "am_acum": j.cartao_amarelo_acumulado,
        "susp": j.suspensao_jogos,
        "contrato": {
            "tipo": j.contrato.tipo.name,
            "salario": j.contrato.salario,
            "multa": j.contrato.multa_rescisoria,
            "dur": j.contrato.duracao_meses,
            "rest": j.contrato.meses_restantes,
            "origem": j.contrato.time_origem,
            "clausula": j.contrato.clausula_compra,
        },
        "potencial": j.potencial, "talento": j.talento_oculto,
        "traits": [tr.name for tr in j.traits],
        "historico": [
            {"temp": h.temporada, "time": h.time, "j": h.jogos, "g": h.gols,
             "a": h.assistencias, "am": h.cartoes_amarelos, "vm": h.cartoes_vermelhos,
             "nota": h.nota_media}
            for h in j.historico
        ],
        "hist_temp": {
            "jogos": j.historico_temporada.jogos,
            "gols": j.historico_temporada.gols,
            "assist": j.historico_temporada.assistencias,
            "am": j.historico_temporada.cartoes_amarelos,
            "vm": j.historico_temporada.cartoes_vermelhos,
            "nota": j.historico_temporada.nota_media,
        },
        "quer_sair": j.quer_sair, "feliz": j.feliz,
        "adaptacao": j.adaptacao,
    }


def _dict_to_jogador(d: dict) -> Jogador:
    j = Jogador()
    j.id = d["id"]
    j.nome = d["nome"]
    j.idade = d["idade"]
    j.nacionalidade = d.get("nacionalidade", "Brasil")
    j.posicao = enum_val(Posicao, d["posicao"])
    j.posicoes_alternativas = [enum_val(Posicao, p) for p in d.get("posicoes_alt", [])]
    j.pe_preferido = enum_val(PePreferido, d.get("pe", "DIREITO"))
    j.numero_camisa = d.get("camisa", 0)
    j.altura = d.get("altura", 1.80)
    j.peso = d.get("peso", 78.0)

    # New compact format: flat list "a" with 41 ints
    a = d.get("a")
    if a is not None:
        _unpack_attrs(a, j)
    else:
        # Legacy format: nested dicts
        t = d.get("tec", {})
        j.tecnicos = AtributosTecnicos(
            passe_curto=t.get("pc", 50), passe_longo=t.get("pl", 50),
            cruzamento=t.get("cr", 50), finalizacao=t.get("fi", 50),
            chute_longa_dist=t.get("cl", 50), cabeceio=t.get("cb", 50),
            drible=t.get("dr", 50), controle_bola=t.get("co", 50),
            falta=t.get("fa", 50), penalti=t.get("pe", 50),
            desarme=t.get("de", 50), marcacao=t.get("ma", 50),
            lancamento=t.get("la", 50),
        )

        f = d.get("fis", {})
        j.fisicos = AtributosFisicos(
            velocidade=f.get("ve", 50), aceleracao=f.get("ac", 50),
            resistencia=f.get("re", 50), forca=f.get("fo", 50),
            agilidade=f.get("ag", 50), salto=f.get("sa", 50),
            equilibrio=f.get("eq", 50),
        )

        m = d.get("men", {})
        j.mentais = AtributosMentais(
            visao_jogo=m.get("vj", 50), decisao=m.get("dc", 50),
            concentracao=m.get("cn", 50), determinacao=m.get("dt", 50),
            lideranca=m.get("li", 50), trabalho_equipe=m.get("te", 50),
            criatividade=m.get("cr", 50), compostura=m.get("cp", 50),
            agressividade=m.get("ag", 50), posicionamento=m.get("po", 50),
            antecipacao=m.get("an", 50), bravura=m.get("br", 50),
        )

        g = d.get("gol", {})
        j.goleiro = AtributosGoleiro(
            reflexos=g.get("rf", 50), posicionamento_gol=g.get("pg", 50),
            jogo_aereo=g.get("ja", 50), defesa_1v1=g.get("d1", 50),
            reposicao=g.get("rp", 50), jogo_com_pes=g.get("jp", 50),
            punho=g.get("pu", 50), elasticidade=g.get("el", 50),
            comando_area=g.get("ca", 50),
        )

    j.moral = d.get("moral", 70)
    j.condicao_fisica = d.get("cond", 100)
    j.status_lesao = enum_val(StatusLesao, d.get("lesao", "SAUDAVEL"))
    j.dias_lesao = d.get("dias_lesao", 0)
    j.cartao_amarelo_acumulado = d.get("am_acum", 0)
    j.suspensao_jogos = d.get("susp", 0)

    c = d.get("contrato", {})
    j.contrato = ContratoJogador(
        tipo=enum_val(TipoContrato, c.get("tipo", "PROFISSIONAL")),
        salario=c.get("salario", 50_000),
        multa_rescisoria=c.get("multa", 1_000_000),
        duracao_meses=c.get("dur", 24),
        meses_restantes=c.get("rest", 24),
        time_origem=c.get("origem", ""),
        clausula_compra=c.get("clausula", 0),
    )

    j.potencial = d.get("potencial", 70)
    j.talento_oculto = d.get("talento", 50)

    # Traits (novo)
    j.traits = [enum_val(TraitJogador, tr) for tr in d.get("traits", [])]

    # Histórico completo
    j.historico = []
    for hd in d.get("historico", []):
        j.historico.append(Historico(
            temporada=hd.get("temp", 2026), time=hd.get("time", ""),
            jogos=hd.get("j", 0), gols=hd.get("g", 0),
            assistencias=hd.get("a", 0),
            cartoes_amarelos=hd.get("am", 0), cartoes_vermelhos=hd.get("vm", 0),
            nota_media=hd.get("nota", 6.0),
        ))

    # Histórico temporada
    ht = d.get("hist_temp", {})
    j.historico_temporada = Historico(
        jogos=ht.get("jogos", 0), gols=ht.get("gols", 0),
        assistencias=ht.get("assist", 0),
        cartoes_amarelos=ht.get("am", 0), cartoes_vermelhos=ht.get("vm", 0),
        nota_media=ht.get("nota", 6.0),
    )

    j.quer_sair = d.get("quer_sair", False)
    j.feliz = d.get("feliz", True)
    j.adaptacao = d.get("adaptacao", 100)
    return j


def _jogador_to_dict_slim(j: Jogador) -> dict:
    """Compact format for AI team players — skip historico, traits, hist_temp."""
    return {
        "id": j.id, "nome": j.nome, "idade": j.idade,
        "nacionalidade": j.nacionalidade,
        "posicao": j.posicao.name,
        "posicoes_alt": [p.name for p in j.posicoes_alternativas],
        "pe": j.pe_preferido.name,
        "camisa": j.numero_camisa,
        "altura": j.altura, "peso": j.peso,
        "a": _pack_attrs(j),
        "moral": j.moral, "cond": j.condicao_fisica,
        "lesao": j.status_lesao.name, "dias_lesao": j.dias_lesao,
        "am_acum": j.cartao_amarelo_acumulado,
        "susp": j.suspensao_jogos,
        "contrato": {
            "tipo": j.contrato.tipo.name,
            "salario": j.contrato.salario,
            "multa": j.contrato.multa_rescisoria,
            "dur": j.contrato.duracao_meses,
            "rest": j.contrato.meses_restantes,
            "origem": j.contrato.time_origem,
            "clausula": j.contrato.clausula_compra,
        },
        "potencial": j.potencial, "talento": j.talento_oculto,
        "quer_sair": j.quer_sair, "feliz": j.feliz,
        "adaptacao": j.adaptacao,
        "_slim": True,
    }


# ══════════════════════════════════════════════════════════════
#  TIME → DICT / DICT → TIME
# ══════════════════════════════════════════════════════════════

def _time_to_dict(t: Time, slim: bool = False) -> dict:
    _j2d = _jogador_to_dict_slim if slim else _jogador_to_dict
    return {
        "id": t.id, "nome": t.nome, "nc": t.nome_curto,
        "cidade": t.cidade, "estado": t.estado,
        "cor1": t.cor_principal, "cor2": t.cor_secundaria,
        "div": t.divisao, "prest": t.prestigio,
        "torcida": t.torcida_tamanho,
        "jogadores": [_j2d(j) for j in t.jogadores],
        "staff": [{
            "id": s.id, "nome": s.nome, "idade": s.idade,
            "tipo": s.tipo.name, "hab": s.habilidade,
            "sal": s.salario, "espec": s.especializacao,
        } for s in t.staff],
        "estadio": {
            "nome": t.estadio.nome, "cap": t.estadio.capacidade,
            "gra": t.estadio.nivel_gramado, "est": t.estadio.nivel_estrutura,
            "ing": t.estadio.preco_ingresso, "man": t.estadio.custo_manutencao,
        },
        "fin": {
            "saldo": t.financas.saldo,
            "orc_sal": t.financas.orcamento_salarios,
            "orc_tr": t.financas.orcamento_transferencias,
            "patr": t.financas.patrocinador_principal,
            "rec_pat": t.financas.receita_patrocinio_mensal,
            "cont_pat": t.financas.contrato_patrocinio_meses,
            "mat_esp": t.financas.material_esportivo,
            "patr_cos": t.financas.patrocinador_costas,
            "patr_man": t.financas.patrocinador_manga,
            "rec_tv": t.financas.receita_tv_mensal,
            "socios": t.financas.num_socios,
            "mens": t.financas.mensalidade_socio,
        },
        "base": {
            "nivel": t.base_juvenil.nivel,
            "invest": t.base_juvenil.investimento_mensal,
        },
        "tat": {
            "form": t.tatica.formacao.name,
            "estilo": t.tatica.estilo.name,
            "vel": t.tatica.velocidade.name,
            "marc": t.tatica.marcacao.name,
            "la": t.tatica.linha_alta,
            "ca": t.tatica.contra_ataque,
            "lat": t.tatica.jogo_pelas_laterais,
            "cen": t.tatica.jogo_pelo_centro,
            "bl": t.tatica.bola_longa,
            "tc": t.tatica.toque_curto,
            "psb": t.tatica.pressao_saida_bola,
            "za": t.tatica.zaga_adiantada,
            "cf": t.tatica.cobrador_falta,
            "cp": t.tatica.cobrador_penalti,
            "ce": t.tatica.cobrador_escanteio,
            "cap": t.tatica.capitao,
        },
        "tre": {
            "ft": t.treinamento.foco_tecnico,
            "ff": t.treinamento.foco_fisico,
            "ftat": t.treinamento.foco_tatico,
            "int": t.treinamento.intensidade.name,
        },
        "tit": t.titulares, "res": t.reservas,
        "stats": {
            "v": t.vitorias, "e": t.empates, "d": t.derrotas,
            "gm": t.gols_marcados, "gs": t.gols_sofridos, "p": t.pontos,
        },
        "eh_jog": t.eh_jogador,
    }


def _dict_to_time(d: dict) -> Time:
    t = Time()
    t.id = d["id"]
    t.nome = d["nome"]
    t.nome_curto = d.get("nc", d.get("nome_curto", ""))
    t.cidade = d["cidade"]
    t.estado = d["estado"]
    t.cor_principal = d.get("cor1", "")
    t.cor_secundaria = d.get("cor2", "")
    t.divisao = d.get("div", d.get("divisao", 1))
    t.prestigio = d.get("prest", d.get("prestigio", 50))
    t.torcida_tamanho = d.get("torcida", 1_000_000)

    t.jogadores = [_dict_to_jogador(jd) for jd in d.get("jogadores", [])]

    t.staff = []
    for sd in d.get("staff", []):
        t.staff.append(StaffMembro(
            id=sd["id"], nome=sd["nome"], idade=sd["idade"],
            tipo=enum_val(TipoStaff, sd["tipo"]),
            habilidade=sd["hab"], salario=sd.get("sal", sd.get("salario", 0)),
            especializacao=sd.get("espec", ""),
        ))

    est = d.get("estadio", {})
    t.estadio = Estadio(
        nome=est.get("nome", ""), capacidade=est.get("cap", 30_000),
        nivel_gramado=est.get("gra", est.get("gramado", 50)),
        nivel_estrutura=est.get("est", est.get("estrutura", 50)),
        preco_ingresso=est.get("ing", est.get("ingresso", 50)),
        custo_manutencao=est.get("man", est.get("manutencao", 200_000)),
    )

    fin = d.get("fin", d.get("financas", {}))
    t.financas = Financas(
        saldo=fin.get("saldo", 5_000_000),
        orcamento_salarios=fin.get("orc_sal", 2_000_000),
        orcamento_transferencias=fin.get("orc_tr", fin.get("orc_transf", 10_000_000)),
        patrocinador_principal=fin.get("patr", fin.get("patrocinador", "")),
        receita_patrocinio_mensal=fin.get("rec_pat", fin.get("rec_patr", 500_000)),
        contrato_patrocinio_meses=fin.get("cont_pat", fin.get("cont_patr", 12)),
        material_esportivo=fin.get("mat_esp", ""),
        patrocinador_costas=fin.get("patr_cos", ""),
        patrocinador_manga=fin.get("patr_man", ""),
        receita_tv_mensal=fin.get("rec_tv", 300_000),
        num_socios=fin.get("socios", 10_000),
        mensalidade_socio=fin.get("mens", fin.get("mens_socio", 50)),
    )

    base = d.get("base", {})
    t.base_juvenil = BaseJuvenil(
        nivel=base.get("nivel", 50),
        investimento_mensal=base.get("invest", 100_000),
    )

    tat = d.get("tat", d.get("tatica", {}))
    t.tatica = Tatica(
        formacao=enum_val(FormacaoTatica, tat.get("form", tat.get("formacao", "F442"))),
        estilo=enum_val(EstiloJogo, tat.get("estilo", "EQUILIBRADO")),
        velocidade=enum_val(VelocidadeJogo, tat.get("vel", tat.get("velocidade", "NORMAL"))),
        marcacao=enum_val(MarcacaoPressao, tat.get("marc", tat.get("marcacao", "NORMAL"))),
        linha_alta=tat.get("la", tat.get("linha_alta", False)),
        contra_ataque=tat.get("ca", tat.get("contra_ataque", False)),
        jogo_pelas_laterais=tat.get("lat", tat.get("laterais", False)),
        jogo_pelo_centro=tat.get("cen", tat.get("centro", False)),
        bola_longa=tat.get("bl", tat.get("bola_longa", False)),
        toque_curto=tat.get("tc", tat.get("toque_curto", True)),
        pressao_saida_bola=tat.get("psb", tat.get("pressao_saida", False)),
        zaga_adiantada=tat.get("za", tat.get("zaga_adiantada", False)),
        cobrador_falta=tat.get("cf", tat.get("cobrador_falta")),
        cobrador_penalti=tat.get("cp", tat.get("cobrador_penalti")),
        cobrador_escanteio=tat.get("ce", tat.get("cobrador_escanteio")),
        capitao=tat.get("cap", tat.get("capitao")),
    )

    tre = d.get("tre", d.get("treinamento", {}))
    t.treinamento = Treinamento(
        foco_tecnico=tre.get("ft", tre.get("foco_tec", "Geral")),
        foco_fisico=tre.get("ff", tre.get("foco_fis", "Geral")),
        foco_tatico=tre.get("ftat", tre.get("foco_tat", "Geral")),
        intensidade=enum_val(NivelTreinamento, tre.get("int", tre.get("intensidade", "NORMAL"))),
    )

    t.titulares = d.get("tit", d.get("titulares", []))
    t.reservas = d.get("res", d.get("reservas", []))

    stats = d.get("stats", {})
    t.vitorias = stats.get("v", 0)
    t.empates = stats.get("e", 0)
    t.derrotas = stats.get("d", 0)
    t.gols_marcados = stats.get("gm", 0)
    t.gols_sofridos = stats.get("gs", 0)
    t.pontos = stats.get("p", 0)

    t.eh_jogador = d.get("eh_jog", d.get("eh_jogador", False))
    return t


# ══════════════════════════════════════════════════════════════
#  SERIALIZAÇÃO / DESSERIALIZAÇÃO DE COMPETIÇÕES
# ══════════════════════════════════════════════════════════════

def _resultado_to_dict(r) -> dict:
    """Converte ResultadoPartida para dict."""
    return {
        "tc": r.time_casa, "tf": r.time_fora,
        "gc": r.gols_casa, "gf": r.gols_fora,
    }


def _dict_to_resultado(d: dict):
    """Converte dict para ResultadoPartida."""
    from core.models import ResultadoPartida
    r = ResultadoPartida.__new__(ResultadoPartida)
    r.time_casa = d["tc"]
    r.time_fora = d["tf"]
    r.gols_casa = d["gc"]
    r.gols_fora = d["gf"]
    r.gols = []
    r.cartoes = []
    r.lesoes = []
    r.substituicoes = []
    r.eventos = []
    r.publico = 0
    r.posse_casa = 50
    r.posse_fora = 50
    r.finalizacoes_casa = 0
    r.finalizacoes_fora = 0
    r.escanteios_casa = 0
    r.escanteios_fora = 0
    r.faltas_casa = 0
    r.faltas_fora = 0
    r.impedimentos_casa = 0
    r.impedimentos_fora = 0
    r.defesas_goleiro_casa = 0
    r.defesas_goleiro_fora = 0
    r.notas_casa = {}
    r.notas_fora = {}
    return r


def _serializar_campeonato(camp) -> dict:
    """Serializa um Campeonato (liga pontos corridos)."""
    if not camp:
        return {}
    # Convert _stats keys from int to str for JSON
    stats_ser = {str(k): v for k, v in camp._stats.items()} if hasattr(camp, '_stats') else {}
    return {
        "ra": camp.rodada_atual,
        "enc": camp.encerrado,
        "res": [[_resultado_to_dict(r) for r in rodada] for rodada in camp.resultados],
        "st": stats_ser,
    }


def _serializar_copa(copa) -> dict:
    """Serializa uma Copa/Libertadores/SulAmericana."""
    if not copa:
        return {}
    # Salvar confrontos como nomes de times
    confrontos_ser = []
    for fase_confrontos in copa.confrontos:
        fase = []
        for t1, t2 in fase_confrontos:
            fase.append([t1.nome if t1 else None, t2.nome if t2 else None])
        confrontos_ser.append(fase)

    return {
        "fa": copa.fase_atual,
        "enc": copa.encerrado,
        "ida": copa.jogo_ida,
        "fases": copa.fases,
        "camp": copa.campeao.nome if copa.campeao else None,
        "conf": confrontos_ser,
        "ri": [[_resultado_to_dict(r) for r in fase] for fase in copa.resultados_ida],
        "rv": [[_resultado_to_dict(r) for r in fase] for fase in copa.resultados_volta],
        "clas": [[t.nome for t in fase] for fase in copa.classificados],
    }


def _serializar_estadual(est) -> dict:
    """Serializa um CampeonatoEstadual (pontos corridos ou fase de grupos)."""
    if not est:
        return {}
    d = {
        "enc": est.encerrado,
        "mm": est._em_mata_mata,
        "camp": est.campeao.nome if est.campeao else None,
        "usa_grupos": getattr(est, '_usa_grupos', False),
        "usa_intergrupos": getattr(est, '_usa_intergrupos', False),
    }
    if est.fase_grupos:
        from managers.competition_manager import GruposEstadual, GruposIntergrupais
        if isinstance(est.fase_grupos, GruposIntergrupais):
            d["fg_intergrupos"] = {
                "enc": est.fase_grupos.encerrado,
                "rodada": est.fase_grupos.rodada_atual,
                "grupos_times": [[t.nome for t in g] for g in est.fase_grupos.grupos_times],
                "stats": {str(tid): s for tid, s in est.fase_grupos._stats.items()},
                "jogos": est.fase_grupos.jogos,
                "resultados": [[_resultado_to_dict(r) for r in rod] for rod in est.fase_grupos.resultados],
            }
        elif isinstance(est.fase_grupos, GruposEstadual):
            d["fg_grupos"] = [_serializar_campeonato(g) for g in est.fase_grupos.grupos]
            d["fg_grupos_times"] = [[t.nome for t in g.times] for g in est.fase_grupos.grupos]
        else:
            d["fg"] = _serializar_campeonato(est.fase_grupos)
    if est.semifinal:
        d["sf"] = _serializar_copa(est.semifinal)
    return d


def _serializar_ccg(ccg) -> dict:
    """Serializa um CampeonatoComGrupos (Brasileirão D, Libertadores, Sul-Americana, Champions League)."""
    if not ccg:
        return {}
    d_state = {
        "enc": ccg.encerrado,
        "mm": ccg._em_mata_mata,
        "camp": ccg.campeao.nome if ccg.campeao else None,
    }
    d_state["grupos"] = [_serializar_campeonato(g) for g in ccg.grupos]
    # Save team names per group so we can reconstruct exact group composition on load
    d_state["grupos_times"] = [[t.nome for t in g.times] for g in ccg.grupos]
    if ccg.mata_mata:
        d_state["mk"] = _serializar_copa(ccg.mata_mata)
    return d_state


def _serializar_competicoes(comp: Any) -> Dict[str, Any]:
    """Serializa o estado completo das competições."""
    state: Dict[str, Any] = {
        "semana_atual": comp.semana_atual,
        "temporada": comp.temporada,
    }
    for key in ['brasileirao_a', 'brasileirao_b']:
        camp = getattr(comp, key, None)
        if camp:
            state[key] = _serializar_campeonato(camp)
    # Brasileirão C (pode ser Campeonato ou CampeonatoComGrupos)
    if comp.brasileirao_c:
        from managers.competition_manager import CampeonatoComGrupos
        if isinstance(comp.brasileirao_c, CampeonatoComGrupos):
            state["brasileirao_c"] = _serializar_ccg(comp.brasileirao_c)
            state["brasileirao_c_tipo"] = "ccg"
        else:
            state["brasileirao_c"] = _serializar_campeonato(comp.brasileirao_c)
    # Brasileirão D (CampeonatoComGrupos)
    if comp.brasileirao_d:
        state["brasileirao_d"] = _serializar_ccg(comp.brasileirao_d)

    # Copa do Brasil (Copa pura)
    if comp.copa_brasil:
        state['copa_brasil'] = _serializar_copa(comp.copa_brasil)

    # Libertadores e Sul-Americana (CampeonatoComGrupos)
    for key in ['libertadores', 'sul_americana']:
        ccg = getattr(comp, key, None)
        if ccg:
            state[key] = _serializar_ccg(ccg)

    # Estaduais
    estaduais_ser = {}
    for uf, est in comp.estaduais.items():
        estaduais_ser[uf] = _serializar_estadual(est)
    if estaduais_ser:
        state["estaduais"] = estaduais_ser

    # Copa do Nordeste / Copa Verde (CampeonatoComGrupos)
    for key in ['copa_nordeste', 'copa_verde']:
        ccg = getattr(comp, key, None)
        if ccg:
            state[key] = _serializar_ccg(ccg)

    # Ligas europeias
    ligas_eu_ser = {}
    for pais, divs in getattr(comp, 'ligas_europeias', {}).items():
        ligas_eu_ser[pais] = {}
        for div_num, camp in divs.items():
            ligas_eu_ser[pais][str(div_num)] = _serializar_campeonato(camp)
    if ligas_eu_ser:
        state["ligas_europeias"] = ligas_eu_ser

    for key in ["champions_league", "europa_league", "copa_mundo", "eurocopa", "copa_america"]:
        ccg = getattr(comp, key, None)
        if ccg:
            state[key] = _serializar_ccg(ccg)

    return state


def _desserializar_competicoes(gm: Any, comp_data: Dict[str, Any]) -> None:
    """Restaura competições reconstruindo estado sem re-simular."""
    # Primeiro inicializar para criar estruturas com os times corretos (sem resetar stats)
    gm._iniciar_temporada(resetar=False)
    comp = gm.competicoes
    comp.semana_atual = comp_data.get("semana_atual", 0)

    # Helper: encontrar time por nome em todos os times
    _time_cache = {t.nome: t for t in gm.todos_times()}

    def _find_time(nome):
        return _time_cache.get(nome)

    def _restaurar_campeonato(camp, data):
        """Restaura campeonato sem re-simular — apenas seta rodada/encerrado e resultados."""
        if not camp or not data:
            return
        camp.rodada_atual = data.get("ra", 0)
        camp.encerrado = data.get("enc", False)
        camp.resultados = [
            [_dict_to_resultado(rd) for rd in rodada]
            for rodada in data.get("res", [])
        ]
        # Restore per-competition standings
        saved_stats = data.get("st", {})
        if saved_stats:
            camp._stats = {int(k): v for k, v in saved_stats.items()}

    def _restaurar_copa(copa, data):
        """Restaura copa sem re-simular — reconstrói bracket e resultados."""
        if not copa or not data:
            return
        copa.fase_atual = data.get("fa", 0)
        copa.encerrado = data.get("enc", False)
        copa.jogo_ida = data.get("ida", True)
        copa.fases = data.get("fases", copa.fases)
        camp_nome = data.get("camp")
        copa.campeao = _find_time(camp_nome) if camp_nome else None

        # Restaurar confrontos
        conf_data = data.get("conf", [])
        copa.confrontos = []
        for fase_data in conf_data:
            fase = []
            for pair in fase_data:
                t1 = _find_time(pair[0]) if pair[0] else None
                t2 = _find_time(pair[1]) if pair[1] else None
                fase.append((t1, t2))
            copa.confrontos.append(fase)

        # Restaurar resultados ida/volta
        copa.resultados_ida = [
            [_dict_to_resultado(rd) for rd in fase]
            for fase in data.get("ri", [])
        ]
        copa.resultados_volta = [
            [_dict_to_resultado(rd) for rd in fase]
            for fase in data.get("rv", [])
        ]
        # Restaurar classificados
        copa.classificados = [
            [t for nome in fase if (t := _find_time(nome))]
            for fase in data.get("clas", [])
        ]

    # Restaurar brasileirão A, B (Campeonato)
    for key in ['brasileirao_a', 'brasileirao_b']:
        camp = getattr(comp, key, None)
        kdata = comp_data.get(key, {})
        if camp and kdata:
            _restaurar_campeonato(camp, kdata)

    # Restaurar brasileirão C (pode ser Campeonato ou CampeonatoComGrupos)
    bc_data = comp_data.get("brasileirao_c", {})
    if comp.brasileirao_c and bc_data:
        from managers.competition_manager import CampeonatoComGrupos
        if isinstance(comp.brasileirao_c, CampeonatoComGrupos):
            _restaurar_ccg(comp.brasileirao_c, bc_data)
        else:
            _restaurar_campeonato(comp.brasileirao_c, bc_data)

    def _restaurar_ccg(ccg, data):
        """Restaura um CampeonatoComGrupos (Brasileirão D, Libertadores, etc.)."""
        if not ccg or not data:
            return
        ccg.encerrado = data.get("enc", False)
        ccg._em_mata_mata = data.get("mm", False)
        camp_nome = data.get("camp")
        ccg.campeao = _find_time(camp_nome) if camp_nome else None

        # Rebuild group composition from saved team names to match exact arrangement
        grupos_times_nomes = data.get("grupos_times", [])
        if grupos_times_nomes:
            from managers.competition_manager import Campeonato
            ccg.grupos = []
            for g_nomes in grupos_times_nomes:
                g_times = [t for nome in g_nomes if (t := _find_time(nome))]
                camp = Campeonato(f"Grupo", g_times, turno_e_returno=ccg._turno_e_returno_grupos)
                ccg.grupos.append(camp)

        for i, grupo_data in enumerate(data.get("grupos", [])):
            if i < len(ccg.grupos):
                _restaurar_campeonato(ccg.grupos[i], grupo_data)
        if data.get("mk") and ccg.mata_mata:
            _restaurar_copa(ccg.mata_mata, data["mk"])

    # Restaurar Brasileirão D (CampeonatoComGrupos)
    bd_data = comp_data.get("brasileirao_d", {})
    if comp.brasileirao_d and bd_data:
        _restaurar_ccg(comp.brasileirao_d, bd_data)

    # Restaurar Copa do Brasil
    if comp.copa_brasil and comp_data.get("copa_brasil"):
        _restaurar_copa(comp.copa_brasil, comp_data["copa_brasil"])

    # Restaurar Libertadores e Sul-Americana (CampeonatoComGrupos)
    for key in ['libertadores', 'sul_americana']:
        ccg = getattr(comp, key, None)
        kdata = comp_data.get(key, {})
        if ccg and kdata:
            _restaurar_ccg(ccg, kdata)

    # Restaurar estaduais
    for uf, est_data in comp_data.get("estaduais", {}).items():
        est = comp.estaduais.get(uf)
        if not est or not est_data:
            continue
        est.encerrado = est_data.get("enc", False)
        est._em_mata_mata = est_data.get("mm", False)
        camp_nome = est_data.get("camp")
        est.campeao = _find_time(camp_nome) if camp_nome else None

        # Restaurar fase de grupos (GruposEstadual, GruposIntergrupais ou Campeonato)
        if est_data.get("fg_intergrupos") and est.fase_grupos:
            from managers.competition_manager import GruposIntergrupais
            if isinstance(est.fase_grupos, GruposIntergrupais):
                ig_data = est_data["fg_intergrupos"]
                # Rebuild group assignments
                fg_times_nomes = ig_data.get("grupos_times", [])
                if fg_times_nomes:
                    est.fase_grupos.grupos_times = []
                    for g_nomes in fg_times_nomes:
                        g_times = [t for nome in g_nomes if (t := _find_time(nome))]
                        est.fase_grupos.grupos_times.append(g_times)
                # Restore stats
                for tid_str, s in ig_data.get("stats", {}).items():
                    est.fase_grupos._stats[int(tid_str)] = s
                # Restore fixtures and results
                est.fase_grupos.jogos = ig_data.get("jogos", [])
                est.fase_grupos.rodada_atual = ig_data.get("rodada", 0)
                est.fase_grupos.encerrado = ig_data.get("enc", False)
                saved_res = ig_data.get("resultados", [])
                est.fase_grupos.resultados = []
                for rod in saved_res:
                    est.fase_grupos.resultados.append(
                        [_dict_to_resultado(r) for r in rod]
                    )
        elif est_data.get("fg_grupos") and est.fase_grupos:
            from managers.competition_manager import GruposEstadual, Campeonato as _Camp
            if isinstance(est.fase_grupos, GruposEstadual):
                # Rebuild groups from saved team names
                fg_times_nomes = est_data.get("fg_grupos_times", [])
                if fg_times_nomes:
                    est.fase_grupos.grupos = []
                    for g_nomes in fg_times_nomes:
                        g_times = [t for nome in g_nomes if (t := _find_time(nome))]
                        camp_g = _Camp(f"Grupo", g_times,
                                       turno_e_returno=est.fase_grupos._turno_e_returno)
                        est.fase_grupos.grupos.append(camp_g)
                for i, grupo_data in enumerate(est_data["fg_grupos"]):
                    if i < len(est.fase_grupos.grupos):
                        _restaurar_campeonato(est.fase_grupos.grupos[i], grupo_data)
                est.fase_grupos.encerrado = all(g.encerrado for g in est.fase_grupos.grupos)
                est.fase_grupos.rodada_atual = max(
                    (g.rodada_atual for g in est.fase_grupos.grupos), default=0
                )
        elif est_data.get("fg") and est.fase_grupos:
            _restaurar_campeonato(est.fase_grupos, est_data["fg"])

        if est_data.get("sf") and est.semifinal:
            _restaurar_copa(est.semifinal, est_data["sf"])
        elif est_data.get("sf") and est._em_mata_mata:
            # Semifinal needs to be created from classificados
            from managers.competition_manager import Copa
            clas_nomes = est_data["sf"].get("clas", [[]])
            top_times = []
            if est.fase_grupos:
                top_times = est.fase_grupos.classificacao()[:4]
            if top_times and len(top_times) >= 2:
                est.semifinal = Copa(f"{est.nome} - Mata-Mata", top_times)
                _restaurar_copa(est.semifinal, est_data["sf"])

    # Restaurar ligas europeias
    for pais, divs_data in comp_data.get("ligas_europeias", {}).items():
        pais_ligas = comp.ligas_europeias.get(pais, {})
        for div_str, liga_data in divs_data.items():
            camp = pais_ligas.get(int(div_str))
            if camp and liga_data:
                _restaurar_campeonato(camp, liga_data)

    for key in ["champions_league", "europa_league", "copa_mundo", "eurocopa", "copa_america"]:
        ccg = getattr(comp, key, None)
        kdata = comp_data.get(key, {})
        if ccg and kdata:
            _restaurar_ccg(ccg, kdata)

    # Copa do Nordeste / Copa Verde
    for key in ['copa_nordeste', 'copa_verde']:
        ccg = getattr(comp, key, None)
        kdata = comp_data.get(key, {})
        if ccg and kdata:
            _restaurar_ccg(ccg, kdata)


def _serializar_fantasy(fm: Any) -> Dict[str, Any]:
    """Serializa o estado completo da liga fantasy."""
    liga = getattr(fm, "liga", None)
    if not liga:
        return {}
    return {
        "nome": liga.nome,
        "rodada_atual": liga.rodada_atual,
        "times": [
            {
                "id": tf.id,
                "nome": tf.nome,
                "dono": tf.dono,
                "saldo": tf.saldo,
                "pontos_total": tf.pontos_total,
                "pontos_rodada": tf.pontos_rodada,
                "historico_rodadas": list(tf.historico_rodadas),
                "escalacao": [
                    {
                        "jogador_id": esc.jogador_id,
                        "jogador_nome": esc.jogador_nome,
                        "time_real": esc.time_real,
                        "posicao": esc.posicao,
                        "pontos": esc.pontos,
                        "capitao": esc.capitao,
                    }
                    for esc in tf.escalacao
                ],
            }
            for tf in liga.times
        ],
    }


def _desserializar_fantasy(fm: Any, data: Dict[str, Any]) -> None:
    """Restaura o estado da liga fantasy."""
    liga = LigaFantasy(
        nome=data.get("nome", "Liga Brasfoot"),
        rodada_atual=data.get("rodada_atual", 0),
        times=[],
    )
    for tf_data in data.get("times", []):
        tf = TimeFantasy(
            id=tf_data.get("id", 0),
            nome=tf_data.get("nome", ""),
            dono=tf_data.get("dono", "cpu"),
            saldo=tf_data.get("saldo", 100),
            pontos_total=tf_data.get("pontos_total", 0.0),
            pontos_rodada=tf_data.get("pontos_rodada", 0.0),
            historico_rodadas=list(tf_data.get("historico_rodadas", [])),
            escalacao=[
                EscalacaoFantasy(
                    jogador_id=esc.get("jogador_id", 0),
                    jogador_nome=esc.get("jogador_nome", ""),
                    time_real=esc.get("time_real", ""),
                    posicao=esc.get("posicao", ""),
                    pontos=esc.get("pontos", 0.0),
                    capitao=esc.get("capitao", False),
                )
                for esc in tf_data.get("escalacao", [])
            ],
        )
        liga.times.append(tf)
    fm.liga = liga


def _oferta_to_dict(oferta: OfertaTransferencia) -> Dict[str, Any]:
    return {
        "id": oferta.id,
        "jogador_id": oferta.jogador_id,
        "jogador_nome": oferta.jogador_nome,
        "time_origem": oferta.time_origem,
        "time_destino": oferta.time_destino,
        "valor": oferta.valor,
        "salario_oferecido": oferta.salario_oferecido,
        "tipo": oferta.tipo.name,
        "status": oferta.status.name,
        "jogador_troca_id": oferta.jogador_troca_id,
    }


def _dict_to_oferta(data: Dict[str, Any]) -> OfertaTransferencia:
    return OfertaTransferencia(
        id=data.get("id", 0),
        jogador_id=data.get("jogador_id", 0),
        jogador_nome=data.get("jogador_nome", ""),
        time_origem=data.get("time_origem", ""),
        time_destino=data.get("time_destino", ""),
        valor=data.get("valor", 0),
        salario_oferecido=data.get("salario_oferecido", 0),
        tipo=enum_val(TipoOferta, data.get("tipo", "COMPRA")),
        status=enum_val(StatusOferta, data.get("status", "PENDENTE")),
        jogador_troca_id=data.get("jogador_troca_id", 0),
    )


def _serializar_mercado(mercado: Any) -> Dict[str, Any]:
    return {
        "id_counter": getattr(mercado, "_id_counter", 0),
        "jogadores_livres": [_jogador_to_dict(j) for j in getattr(mercado, "jogadores_livres", [])],
        "ofertas_pendentes": [_oferta_to_dict(o) for o in getattr(mercado, "ofertas_pendentes", [])],
        "ofertas_historico": [_oferta_to_dict(o) for o in getattr(mercado, "ofertas_historico", [])],
    }


def _desserializar_mercado(mercado: Any, data: Dict[str, Any]) -> None:
    mercado._id_counter = data.get("id_counter", 0)
    mercado.jogadores_livres = [_dict_to_jogador(jd) for jd in data.get("jogadores_livres", [])]
    mercado.ofertas_pendentes = [_dict_to_oferta(od) for od in data.get("ofertas_pendentes", [])]
    mercado.ofertas_historico = [_dict_to_oferta(od) for od in data.get("ofertas_historico", [])]
    mercado.noticias = []


# ══════════════════════════════════════════════════════════════
#  SERIALIZAÇÃO / DESSERIALIZAÇÃO DO JOGO COMPLETO
# ══════════════════════════════════════════════════════════════

def serializar_jogo(gm: Any) -> bytes:
    """Serializa GameManager para JSON em bytes.

    O *gm* é do tipo ``managers.game_manager.GameManager`` (import
    evitado para não criar dependência circular). O retorno é ``bytes``
    para escrita direta em arquivo e compatibilidade com ``orjson``.
    """
    # Serializar estado das competições
    comp_state = _serializar_competicoes(gm.competicoes)

    # Serializar artilharia em memória
    artilharia_mem = {}
    for jid, entry in getattr(gm, 'artilharia_memoria', {}).items():
        artilharia_mem[str(jid)] = entry

    # Serializar times europeus {pais: {div: [Time]}}
    eu_ser = {}
    for pais, divs in getattr(gm, 'times_europeus', {}).items():
        eu_ser[pais] = {}
        for div_num, times_list in divs.items():
            eu_ser[pais][str(div_num)] = [_time_to_dict(t, slim=True) for t in times_list]

    # Helper: slim para times AI, full para time do jogador
    _pn = gm.time_jogador.nome if gm.time_jogador else ""
    def _td(t: Time) -> dict:
        return _time_to_dict(t, slim=(t.nome != _pn))

    dados: Dict[str, Any] = {
        "versao": 9,
        "temporada": gm.temporada,
        "semana": gm.semana,
        "time_jogador_nome": _pn,
        "times_serie_a": [_td(t) for t in gm.times_serie_a],
        "times_serie_b": [_td(t) for t in gm.times_serie_b],
        "times_serie_c": [_td(t) for t in gm.times_serie_c],
        "times_serie_d": [_td(t) for t in gm.times_serie_d],
        "times_sem_divisao": [_td(t) for t in gm.times_sem_divisao],
        "times_europeus": eu_ser,
        "competicoes": comp_state,
        "mercado": _serializar_mercado(gm.mercado) if hasattr(gm, 'mercado') else {},
        "artilharia_memoria": artilharia_mem,
        "noticias": [
            {"titulo": n.titulo, "texto": n.texto, "cat": n.categoria.name,
             "rodada": n.rodada}
            for n in getattr(gm, "noticias", [])
        ],
        "lib_qualificados": [t.nome for t in getattr(gm, '_lib_qualificados', [])],
        "inbox": gm.inbox.to_save_dict() if hasattr(gm, 'inbox') else {},
        "music": gm.music.to_save_dict() if hasattr(gm, 'music') else {},
        "fantasy": _serializar_fantasy(gm.fantasy) if hasattr(gm, 'fantasy') else {},
        "coletiva": gm.coletiva.to_save_dict() if hasattr(gm, 'coletiva') else {},
        "conquistas": gm.conquistas.to_save_dict() if hasattr(gm, 'conquistas') else {},
        "premiacoes": gm.premiacoes.to_save_dict() if hasattr(gm, 'premiacoes') else {},
        "recordes": gm.recordes.to_save_dict() if hasattr(gm, 'recordes') else {},
        "auto_save": getattr(gm, 'auto_save_ativo', True),
        "tutorial_visto": getattr(gm, 'tutorial_visto', False),
        "comp_selecoes": getattr(gm, '_comp_selecoes', False),
        # Sistemas avançados (v9+)
        "promessas": gm.promessas_engine.to_save_dict() if hasattr(gm, 'promessas_engine') else {},
        "vestiario": gm.vestiario_engine.to_save_dict() if hasattr(gm, 'vestiario_engine') else {},
        "quimica": gm.quimica_engine.to_save_dict() if hasattr(gm, 'quimica_engine') else {},
        "carreira": gm.carreira_engine.to_save_dict() if hasattr(gm, 'carreira_engine') else {},
        "adaptacao": gm.adaptacao_engine.to_save_dict() if hasattr(gm, 'adaptacao_engine') else {},
        "agentes": gm.agentes_engine.to_save_dict() if hasattr(gm, 'agentes_engine') else {},
        "objetivos": gm.objetivos_engine.to_save_dict() if hasattr(gm, 'objetivos_engine') else {},
        # Novos engines (v10+)
        "ffp": gm.ffp_engine.to_save_dict() if hasattr(gm, 'ffp_engine') else {},
        "rankings": gm.rankings_engine.to_save_dict() if hasattr(gm, 'rankings_engine') else {},
        "hall_of_fame": gm.hall_of_fame.to_save_dict() if hasattr(gm, 'hall_of_fame') else {},
        # Estado de desemprego
        "desempregado": getattr(gm, '_desempregado', False),
        "semanas_desempregado": getattr(gm, '_semanas_desempregado', 0),
        "ofertas_emprego": getattr(gm, '_ofertas_emprego', []),
    }
    if _HAS_ORJSON:
        return _json_fast.dumps(dados)
    return json.dumps(dados, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def desserializar_jogo(gm: Any, json_data) -> None:
    """Restaura o estado do GameManager a partir de JSON (str ou bytes)."""
    if _HAS_ORJSON:
        dados = _json_fast.loads(json_data)
    else:
        if isinstance(json_data, bytes):
            json_data = json_data.decode("utf-8")
        dados = json.loads(json_data)

    gm.temporada = dados.get("temporada", 2026)
    gm.semana = dados.get("semana", 1)
    gm._comp_selecoes = dados.get("comp_selecoes", False)

    gm.times_serie_a = [_dict_to_time(td) for td in dados.get("times_serie_a", [])]
    gm.times_serie_b = [_dict_to_time(td) for td in dados.get("times_serie_b", [])]
    gm.times_serie_c = [_dict_to_time(td) for td in dados.get("times_serie_c", [])]
    gm.times_serie_d = [_dict_to_time(td) for td in dados.get("times_serie_d", [])]
    gm.times_sem_divisao = [_dict_to_time(td) for td in dados.get("times_sem_divisao", [])]

    # Restaurar times europeus
    gm.times_europeus = {}
    for pais, divs in dados.get("times_europeus", {}).items():
        gm.times_europeus[pais] = {}
        for div_str, times_data in divs.items():
            gm.times_europeus[pais][int(div_str)] = [_dict_to_time(td) for td in times_data]

    # Restaurar referência ao time do jogador
    nome_jogador = dados.get("time_jogador_nome", "")
    gm.time_jogador = None
    for t in gm.todos_times():
        if t.nome == nome_jogador:
            gm.time_jogador = t
            t.eh_jogador = True
            break

    # Reconstruir notícias
    from core.models import Noticia
    from core.enums import CategoriaNoticia
    gm.noticias = []
    for nd in dados.get("noticias", []):
        gm.noticias.append(Noticia(
            titulo=nd.get("titulo", ""),
            texto=nd.get("texto", ""),
            categoria=enum_val(CategoriaNoticia, nd.get("cat", "GERAL")),
            rodada=nd.get("rodada", 0),
        ))

    # Restaurar artilharia em memória
    gm.artilharia_memoria = {}
    for jid_str, entry in dados.get("artilharia_memoria", {}).items():
        gm.artilharia_memoria[int(jid_str)] = entry

    if hasattr(gm, 'mercado'):
        mercado_data = dados.get("mercado")
        if mercado_data:
            _desserializar_mercado(gm.mercado, mercado_data)
        elif not getattr(gm.mercado, "jogadores_livres", None):
            max_id = max((j.id for t in gm.todos_times() for j in t.jogadores), default=0) + 1
            gm.mercado.gerar_jogadores_livres(50, max_id)

    # Restaurar qualificados da Libertadores
    gm._lib_qualificados = []
    _time_map = {t.nome: t for t in gm.todos_times()}
    for nome in dados.get("lib_qualificados", []):
        t = _time_map.get(nome)
        if t:
            gm._lib_qualificados.append(t)

    # Restaurar competições preservando progresso
    comp_data = dados.get("competicoes")
    if comp_data and dados.get("versao", 1) >= 4:
        _desserializar_competicoes(gm, comp_data)
    elif comp_data and dados.get("versao", 1) >= 3:
        # Versão 3/4: compatibilidade — recriar e restaurar
        # Versão 3: compatibilidade — recriar e avançar (aproximado)
        _desserializar_competicoes(gm, comp_data)
    else:
        gm._iniciar_temporada()

    # Restaurar inbox (v6+)
    inbox_data = dados.get("inbox")
    if inbox_data and hasattr(gm, 'inbox'):
        try:
            gm.inbox.from_save_dict(inbox_data)
        except Exception:
            pass  # inbox vazia OK em saves antigos

    # Restaurar novos subsistemas (v7+)
    if hasattr(gm, 'music') and dados.get("music"):
        try:
            gm.music.from_save_dict(dados["music"])
        except Exception:
            pass
    if hasattr(gm, 'fantasy'):
        try:
            fantasy_data = dados.get("fantasy")
            if fantasy_data:
                _desserializar_fantasy(gm.fantasy, fantasy_data)
            elif not getattr(gm.fantasy.liga, "times", None):
                gm.fantasy.criar_liga(gm.times_serie_a + gm.times_serie_b)
        except Exception:
            pass
    if hasattr(gm, 'coletiva') and dados.get("coletiva"):
        try:
            gm.coletiva.from_save_dict(dados["coletiva"])
        except Exception:
            pass
    if hasattr(gm, 'conquistas') and dados.get("conquistas"):
        try:
            gm.conquistas.from_save_dict(dados["conquistas"])
        except Exception:
            pass
    if hasattr(gm, 'premiacoes') and dados.get("premiacoes"):
        try:
            gm.premiacoes.from_save_dict(dados["premiacoes"])
        except Exception:
            pass
    if hasattr(gm, 'recordes') and dados.get("recordes"):
        try:
            gm.recordes.from_save_dict(dados["recordes"])
        except Exception:
            pass
    gm.auto_save_ativo = dados.get("auto_save", True)
    gm.tutorial_visto = dados.get("tutorial_visto", False)

    # Restaurar sistemas avançados (v9+)
    _restore = [
        ("promessas_engine", "promessas"),
        ("vestiario_engine", "vestiario"),
        ("quimica_engine", "quimica"),
        ("carreira_engine", "carreira"),
        ("adaptacao_engine", "adaptacao"),
        ("agentes_engine", "agentes"),
        ("objetivos_engine", "objetivos"),
    ]
    for attr, key in _restore:
        d = dados.get(key)
        if d and hasattr(gm, attr):
            try:
                getattr(gm, attr).from_save_dict(d)
            except Exception:
                pass

    # Restaurar estado de desemprego
    gm._desempregado = dados.get("desempregado", False)
    gm._semanas_desempregado = dados.get("semanas_desempregado", 0)
    gm._ofertas_emprego = dados.get("ofertas_emprego", [])

    # Restaurar novos engines (v10+)
    _restore_v10 = [
        ("ffp_engine", "ffp"),
        ("rankings_engine", "rankings"),
        ("hall_of_fame", "hall_of_fame"),
    ]
    for attr, key in _restore_v10:
        d = dados.get(key)
        if d and hasattr(gm, attr):
            try:
                getattr(gm, attr).from_save_dict(d)
            except Exception:
                pass
    # Se ranking vazio após load, inicializar
    if hasattr(gm, 'rankings_engine') and not gm.rankings_engine._pontos:
        gm.rankings_engine.inicializar(gm.todos_times())
