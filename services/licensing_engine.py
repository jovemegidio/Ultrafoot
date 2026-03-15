# -*- coding: utf-8 -*-
"""
Licensing Engine — Gerencia licenciamento de ligas, clubes e competições.

Responsabilidades:
- Carregar e manter registro de licenças por liga/clube/competição
- Resolver nomes oficiais vs genéricos conforme status de licença
- Resolver assets oficiais vs fallback/placeholder
- Validar conformidade para builds comerciais
- Suportar packs, mods e expansões
- Separar conteúdo BR (já presente) de conteúdo internacional
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional

from core.enums import (
    StatusLicenca, TipoConteudoLicenciado, RegiaoLicenca,
)
from core.models import (
    LicencaConteudo, RegistroLicencaLiga,
    RegistroLicencaClube, RegistroLicencaCompeticao,
)
from utils.logger import get_logger

log = get_logger(__name__)


# ══════════════════════════════════════════════════════════════
#  MAPAS PADRÃO DE REGIÕES
# ══════════════════════════════════════════════════════════════

_PAIS_REGIAO: Dict[str, RegiaoLicenca] = {
    "BRA": RegiaoLicenca.BRASIL,
    "ARG": RegiaoLicenca.AMERICA_SUL, "BOL": RegiaoLicenca.AMERICA_SUL,
    "CHI": RegiaoLicenca.AMERICA_SUL, "COL": RegiaoLicenca.AMERICA_SUL,
    "EQU": RegiaoLicenca.AMERICA_SUL, "PAR": RegiaoLicenca.AMERICA_SUL,
    "PER": RegiaoLicenca.AMERICA_SUL, "URU": RegiaoLicenca.AMERICA_SUL,
    "VEN": RegiaoLicenca.AMERICA_SUL,
    "ING": RegiaoLicenca.EUROPA, "ESP": RegiaoLicenca.EUROPA,
    "ITA": RegiaoLicenca.EUROPA, "ALE": RegiaoLicenca.EUROPA,
    "FRA": RegiaoLicenca.EUROPA, "POR": RegiaoLicenca.EUROPA,
    "HOL": RegiaoLicenca.EUROPA, "BEL": RegiaoLicenca.EUROPA,
    "TUR": RegiaoLicenca.EUROPA, "RUS": RegiaoLicenca.EUROPA,
    "ESC": RegiaoLicenca.EUROPA, "SUI": RegiaoLicenca.EUROPA,
    "AUT": RegiaoLicenca.EUROPA, "GRE": RegiaoLicenca.EUROPA,
    "CRO": RegiaoLicenca.EUROPA, "SER": RegiaoLicenca.EUROPA,
    "DIN": RegiaoLicenca.EUROPA, "NOR": RegiaoLicenca.EUROPA,
    "SUE": RegiaoLicenca.EUROPA, "UCR": RegiaoLicenca.EUROPA,
    "MEX": RegiaoLicenca.AMERICA_NORTE, "EUA": RegiaoLicenca.AMERICA_NORTE,
    "CAT": RegiaoLicenca.AMERICA_NORTE,
    "JAP": RegiaoLicenca.ASIA, "CHN": RegiaoLicenca.ASIA,
    "ARS": RegiaoLicenca.ASIA, "EMI": RegiaoLicenca.ASIA,
    "AFS": RegiaoLicenca.AFRICA, "EGI": RegiaoLicenca.AFRICA,
    "MAR": RegiaoLicenca.AFRICA, "AFG": RegiaoLicenca.ASIA,
    "AUS": RegiaoLicenca.OCEANIA,
}


class LicensingEngine:
    """Motor de licenciamento de conteúdo do jogo."""

    def __init__(self, data_dir: str = ""):
        if not data_dir:
            if getattr(sys, 'frozen', False):
                data_dir = os.path.join(sys._MEIPASS, "data")
            else:
                data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        self._data_dir = data_dir
        self._licensing_dir = os.path.join(data_dir, "licensing")

        # Registros em memória
        self._ligas: Dict[str, RegistroLicencaLiga] = {}
        self._clubes: Dict[str, RegistroLicencaClube] = {}
        self._competicoes: Dict[str, RegistroLicencaCompeticao] = {}
        self._conteudos: Dict[str, LicencaConteudo] = {}

        # Modo comercial — quando True, bloqueia conteúdo não licenciado
        self.modo_comercial: bool = False

        self._carregar_registros()

    # ══════════════════════════════════════════════════════════
    #  CARREGAMENTO
    # ══════════════════════════════════════════════════════════

    def _carregar_registros(self) -> None:
        """Carrega registros de licenciamento do disco ou gera padrões."""
        lic_file = os.path.join(self._licensing_dir, "registry.json")
        if os.path.exists(lic_file):
            try:
                with open(lic_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._carregar_de_dict(data)
                log.info("Licenciamento carregado: %d ligas, %d clubes, %d competições",
                         len(self._ligas), len(self._clubes), len(self._competicoes))
                return
            except Exception as e:
                log.warning("Erro ao carregar registry.json: %s", e)

        # Gerar registros padrão a partir da estrutura de dados existente
        self._gerar_registros_padrao()

    def _carregar_de_dict(self, data: dict) -> None:
        for lid, ld in data.get("ligas", {}).items():
            self._ligas[lid] = RegistroLicencaLiga(
                id_liga=lid,
                nome_oficial=ld.get("nome_oficial", ""),
                nome_generico=ld.get("nome_generico", ""),
                pais=ld.get("pais", ""),
                regiao=RegiaoLicenca(ld.get("regiao", "global")),
                status=StatusLicenca(ld.get("status", "generico")),
                clubes_licenciados=ld.get("clubes_licenciados", 0),
                clubes_total=ld.get("clubes_total", 0),
                escudo_disponivel=ld.get("escudo_disponivel", False),
                trofeu_disponivel=ld.get("trofeu_disponivel", False),
                uniformes_disponiveis=ld.get("uniformes_disponiveis", False),
                pack_origem=ld.get("pack_origem", "base"),
            )
        for cid, cd in data.get("clubes", {}).items():
            self._clubes[cid] = RegistroLicencaClube(
                id_clube=cid,
                nome_oficial=cd.get("nome_oficial", ""),
                nome_generico=cd.get("nome_generico", ""),
                pais=cd.get("pais", ""),
                liga_id=cd.get("liga_id", ""),
                status=StatusLicenca(cd.get("status", "generico")),
                escudo_oficial=cd.get("escudo_oficial", ""),
                escudo_fallback=cd.get("escudo_fallback", ""),
                uniforme_oficial=cd.get("uniforme_oficial", False),
                uniforme_fallback=cd.get("uniforme_fallback", True),
                jogadores_nomes_reais=cd.get("jogadores_nomes_reais", False),
                estadio_nome_oficial=cd.get("estadio_nome_oficial", ""),
                estadio_nome_generico=cd.get("estadio_nome_generico", ""),
            )
        for cpid, cpd in data.get("competicoes", {}).items():
            self._competicoes[cpid] = RegistroLicencaCompeticao(
                id_competicao=cpid,
                nome_oficial=cpd.get("nome_oficial", ""),
                nome_generico=cpd.get("nome_generico", ""),
                regiao=RegiaoLicenca(cpd.get("regiao", "global")),
                status=StatusLicenca(cpd.get("status", "generico")),
                trofeu_oficial=cpd.get("trofeu_oficial", ""),
                trofeu_fallback=cpd.get("trofeu_fallback", ""),
                logo_oficial=cpd.get("logo_oficial", ""),
                logo_fallback=cpd.get("logo_fallback", ""),
            )

    def _gerar_registros_padrao(self) -> None:
        """Gera registros padrão: BR = oficial, internacional = genérico."""
        # Competições brasileiras — consideradas oficiais no jogo
        comps_br = [
            ("brasileirao_a", "Brasileirão Série A", "Campeonato Brasileiro Primeira Divisão"),
            ("brasileirao_b", "Brasileirão Série B", "Campeonato Brasileiro Segunda Divisão"),
            ("brasileirao_c", "Brasileirão Série C", "Campeonato Brasileiro Terceira Divisão"),
            ("brasileirao_d", "Brasileirão Série D", "Campeonato Brasileiro Quarta Divisão"),
            ("copa_brasil", "Copa do Brasil", "Copa Nacional"),
            ("libertadores", "Copa Libertadores", "Copa Continental América do Sul"),
            ("sulamericana", "Copa Sul-Americana", "Copa Continental Secundária"),
        ]
        for cid, nome_oficial, nome_generico in comps_br:
            self._competicoes[cid] = RegistroLicencaCompeticao(
                id_competicao=cid,
                nome_oficial=nome_oficial,
                nome_generico=nome_generico,
                regiao=RegiaoLicenca.BRASIL if "brasil" in cid else RegiaoLicenca.AMERICA_SUL,
                status=StatusLicenca.OFICIAL,
            )

        # Competições europeias — genéricas por padrão
        comps_eu = [
            ("champions_league", "UEFA Champions League", "Liga dos Campeões da Europa"),
            ("europa_league", "UEFA Europa League", "Copa Europeia"),
        ]
        for cid, nome_oficial, nome_generico in comps_eu:
            self._competicoes[cid] = RegistroLicencaCompeticao(
                id_competicao=cid,
                nome_oficial=nome_oficial,
                nome_generico=nome_generico,
                regiao=RegiaoLicenca.EUROPA,
                status=StatusLicenca.GENERICO,
            )

        # Ligas — carregar de seeds se disponível
        self._gerar_ligas_de_seeds()

        log.info("Registros padrão gerados: %d ligas, %d clubes, %d competições",
                 len(self._ligas), len(self._clubes), len(self._competicoes))

    def _gerar_ligas_de_seeds(self) -> None:
        """Gera registros de ligas a partir dos seeds existentes."""
        # BR — séries
        series_br = [
            ("BRA_serie_a", "Brasileirão Série A", "Campeonato Brasileiro Div 1", "BRA"),
            ("BRA_serie_b", "Brasileirão Série B", "Campeonato Brasileiro Div 2", "BRA"),
            ("BRA_serie_c", "Brasileirão Série C", "Campeonato Brasileiro Div 3", "BRA"),
            ("BRA_serie_d", "Brasileirão Série D", "Campeonato Brasileiro Div 4", "BRA"),
        ]
        for lid, nome, gen, pais in series_br:
            self._ligas[lid] = RegistroLicencaLiga(
                id_liga=lid, nome_oficial=nome, nome_generico=gen,
                pais=pais, regiao=RegiaoLicenca.BRASIL,
                status=StatusLicenca.OFICIAL,
                escudo_disponivel=True, trofeu_disponivel=True,
                uniformes_disponiveis=True, pack_origem="base",
            )

        # Internacionais — de teams_eu.json
        eu_path = os.path.join(self._data_dir, "seeds", "teams_eu.json")
        if os.path.exists(eu_path):
            try:
                with open(eu_path, "r", encoding="utf-8") as f:
                    eu_data = json.load(f)
                for cc, country in eu_data.items():
                    pais_nome = country.get("pais_nome", cc)
                    regiao = _PAIS_REGIAO.get(cc, RegiaoLicenca.GLOBAL)
                    ligas = country.get("ligas", [])
                    divisoes = country.get("divisoes", {})
                    for div_key, teams in divisoes.items():
                        div_num = int(div_key.replace("div_", ""))
                        liga_nome = ligas[div_num - 1]["nome"] if div_num <= len(ligas) else f"Div {div_num}"
                        lid = f"{cc}_div_{div_num}"
                        self._ligas[lid] = RegistroLicencaLiga(
                            id_liga=lid,
                            nome_oficial=liga_nome,
                            nome_generico=f"{pais_nome} - Divisão {div_num}",
                            pais=cc,
                            regiao=regiao,
                            status=StatusLicenca.GENERICO,
                            clubes_total=len(teams),
                            pack_origem="pack224" if len(eu_data) > 20 else "base",
                        )
                        # Gerar registros de clubes
                        for t in teams:
                            cid = t.get("file_key", t["nome"].lower().replace(" ", "_"))
                            self._clubes[cid] = RegistroLicencaClube(
                                id_clube=cid,
                                nome_oficial=t["nome"],
                                nome_generico=t["nome"],  # mesmo nome pois já são genéricos
                                pais=cc,
                                liga_id=lid,
                                status=StatusLicenca.GENERICO,
                            )
            except Exception as e:
                log.warning("Erro ao gerar ligas de seeds EU: %s", e)

        # BR clubes de teams_br.json
        br_path = os.path.join(self._data_dir, "seeds", "teams_br.json")
        if os.path.exists(br_path):
            try:
                with open(br_path, "r", encoding="utf-8") as f:
                    br_data = json.load(f)
                div_map = {"serie_a": "BRA_serie_a", "serie_b": "BRA_serie_b",
                           "serie_c": "BRA_serie_c", "serie_d": "BRA_serie_d"}
                for cat, liga_id in div_map.items():
                    for t in br_data.get(cat, []):
                        cid = t.get("file_key", t["nome"].lower().replace(" ", "_"))
                        self._clubes[cid] = RegistroLicencaClube(
                            id_clube=cid,
                            nome_oficial=t["nome"],
                            nome_generico=t["nome"],
                            pais="BRA",
                            liga_id=liga_id,
                            status=StatusLicenca.OFICIAL,
                            jogadores_nomes_reais=True,
                        )
            except Exception as e:
                log.warning("Erro ao gerar clubes BR: %s", e)

    # ══════════════════════════════════════════════════════════
    #  RESOLUÇÃO DE NOMES
    # ══════════════════════════════════════════════════════════

    def resolver_nome_liga(self, liga_id: str) -> str:
        """Retorna nome oficial ou genérico conforme licença e modo."""
        reg = self._ligas.get(liga_id)
        if not reg:
            return liga_id
        if self.modo_comercial and reg.status in (
            StatusLicenca.GENERICO, StatusLicenca.BLOQUEADO
        ):
            return reg.nome_generico or reg.nome_oficial
        return reg.nome_oficial or reg.nome_generico

    def resolver_nome_clube(self, clube_id: str) -> str:
        reg = self._clubes.get(clube_id)
        if not reg:
            return clube_id
        if self.modo_comercial and reg.status in (
            StatusLicenca.GENERICO, StatusLicenca.BLOQUEADO
        ):
            return reg.nome_generico or reg.nome_oficial
        return reg.nome_oficial or reg.nome_generico

    def resolver_nome_competicao(self, comp_id: str) -> str:
        reg = self._competicoes.get(comp_id)
        if not reg:
            return comp_id
        if self.modo_comercial and reg.status in (
            StatusLicenca.GENERICO, StatusLicenca.BLOQUEADO
        ):
            return reg.nome_generico or reg.nome_oficial
        return reg.nome_oficial or reg.nome_generico

    def resolver_asset_clube(self, clube_id: str, tipo: str = "escudo") -> str:
        """Retorna caminho do asset oficial ou fallback."""
        reg = self._clubes.get(clube_id)
        if not reg:
            return ""
        if tipo == "escudo":
            if reg.escudo_oficial and not self.modo_comercial:
                return reg.escudo_oficial
            return reg.escudo_fallback
        return ""

    # ══════════════════════════════════════════════════════════
    #  CONSULTAS
    # ══════════════════════════════════════════════════════════

    def ligas_por_regiao(self, regiao: RegiaoLicenca) -> List[RegistroLicencaLiga]:
        return [l for l in self._ligas.values() if l.regiao == regiao]

    def ligas_por_pais(self, pais: str) -> List[RegistroLicencaLiga]:
        return [l for l in self._ligas.values() if l.pais == pais]

    def clubes_por_liga(self, liga_id: str) -> List[RegistroLicencaClube]:
        return [c for c in self._clubes.values() if c.liga_id == liga_id]

    def status_licenca_liga(self, liga_id: str) -> StatusLicenca:
        reg = self._ligas.get(liga_id)
        return reg.status if reg else StatusLicenca.GENERICO

    def status_licenca_clube(self, clube_id: str) -> StatusLicenca:
        reg = self._clubes.get(clube_id)
        return reg.status if reg else StatusLicenca.GENERICO

    # ══════════════════════════════════════════════════════════
    #  COMPLIANCE — Validação para Build Comercial
    # ══════════════════════════════════════════════════════════

    def relatorio_compliance(self) -> Dict:
        """Gera relatório de conformidade legal para build comercial."""
        total_ligas = len(self._ligas)
        total_clubes = len(self._clubes)
        total_comps = len(self._competicoes)

        ligas_oficiais = sum(1 for l in self._ligas.values()
                            if l.status == StatusLicenca.OFICIAL)
        ligas_licenciadas = sum(1 for l in self._ligas.values()
                                if l.status == StatusLicenca.LICENCIADO)
        ligas_genericas = sum(1 for l in self._ligas.values()
                              if l.status == StatusLicenca.GENERICO)
        ligas_bloqueadas = sum(1 for l in self._ligas.values()
                               if l.status == StatusLicenca.BLOQUEADO)

        clubes_oficiais = sum(1 for c in self._clubes.values()
                              if c.status == StatusLicenca.OFICIAL)
        clubes_genericos = sum(1 for c in self._clubes.values()
                               if c.status == StatusLicenca.GENERICO)

        problemas = []
        for lid, l in self._ligas.items():
            if l.status == StatusLicenca.BLOQUEADO:
                problemas.append(f"Liga bloqueada: {l.nome_oficial} ({lid})")
        for cid, c in self._clubes.items():
            if c.status == StatusLicenca.BLOQUEADO:
                problemas.append(f"Clube bloqueado: {c.nome_oficial} ({cid})")

        return {
            "total_ligas": total_ligas,
            "total_clubes": total_clubes,
            "total_competicoes": total_comps,
            "ligas_oficiais": ligas_oficiais,
            "ligas_licenciadas": ligas_licenciadas,
            "ligas_genericas": ligas_genericas,
            "ligas_bloqueadas": ligas_bloqueadas,
            "clubes_oficiais": clubes_oficiais,
            "clubes_genericos": clubes_genericos,
            "problemas": problemas,
            "aprovado_build_comercial": ligas_bloqueadas == 0 and len(problemas) == 0,
            "regioes": {
                r.value: len(self.ligas_por_regiao(r))
                for r in RegiaoLicenca
                if self.ligas_por_regiao(r)
            },
        }

    def atualizar_status_liga(self, liga_id: str, novo_status: StatusLicenca) -> bool:
        """Atualiza status de licença de uma liga."""
        reg = self._ligas.get(liga_id)
        if not reg:
            return False
        reg.status = novo_status
        return True

    def atualizar_status_clube(self, clube_id: str, novo_status: StatusLicenca) -> bool:
        reg = self._clubes.get(clube_id)
        if not reg:
            return False
        reg.status = novo_status
        return True

    # ══════════════════════════════════════════════════════════
    #  EXPORT / SAVE
    # ══════════════════════════════════════════════════════════

    def salvar_registro(self) -> None:
        """Persiste o registro de licenciamento no disco."""
        os.makedirs(self._licensing_dir, exist_ok=True)
        data = {
            "ligas": {},
            "clubes": {},
            "competicoes": {},
        }
        for lid, l in self._ligas.items():
            data["ligas"][lid] = {
                "nome_oficial": l.nome_oficial,
                "nome_generico": l.nome_generico,
                "pais": l.pais,
                "regiao": l.regiao.value,
                "status": l.status.value,
                "clubes_licenciados": l.clubes_licenciados,
                "clubes_total": l.clubes_total,
                "escudo_disponivel": l.escudo_disponivel,
                "trofeu_disponivel": l.trofeu_disponivel,
                "uniformes_disponiveis": l.uniformes_disponiveis,
                "pack_origem": l.pack_origem,
            }
        for cid, c in self._clubes.items():
            data["clubes"][cid] = {
                "nome_oficial": c.nome_oficial,
                "nome_generico": c.nome_generico,
                "pais": c.pais,
                "liga_id": c.liga_id,
                "status": c.status.value,
                "escudo_oficial": c.escudo_oficial,
                "escudo_fallback": c.escudo_fallback,
                "uniforme_oficial": c.uniforme_oficial,
                "uniforme_fallback": c.uniforme_fallback,
                "jogadores_nomes_reais": c.jogadores_nomes_reais,
                "estadio_nome_oficial": c.estadio_nome_oficial,
                "estadio_nome_generico": c.estadio_nome_generico,
            }
        for cpid, cp in self._competicoes.items():
            data["competicoes"][cpid] = {
                "nome_oficial": cp.nome_oficial,
                "nome_generico": cp.nome_generico,
                "regiao": cp.regiao.value,
                "status": cp.status.value,
                "trofeu_oficial": cp.trofeu_oficial,
                "trofeu_fallback": cp.trofeu_fallback,
                "logo_oficial": cp.logo_oficial,
                "logo_fallback": cp.logo_fallback,
            }
        reg_path = os.path.join(self._licensing_dir, "registry.json")
        with open(reg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info("Registro de licenciamento salvo em %s", reg_path)

    # ══════════════════════════════════════════════════════════
    #  SERIALIZAÇÃO PARA API
    # ══════════════════════════════════════════════════════════

    def to_api_dict(self) -> Dict:
        """Retorna dados completos para o frontend."""
        resultado = {
            "modo_comercial": self.modo_comercial,
            "ligas": [],
            "clubes": [],
            "competicoes": [],
            "compliance": self.relatorio_compliance(),
        }
        for lid, l in self._ligas.items():
            resultado["ligas"].append({
                "id": lid,
                "nome_oficial": l.nome_oficial,
                "nome_generico": l.nome_generico,
                "nome_exibicao": self.resolver_nome_liga(lid),
                "pais": l.pais,
                "regiao": l.regiao.value,
                "status": l.status.value,
                "clubes_total": l.clubes_total,
                "clubes_licenciados": l.clubes_licenciados,
                "escudo_disponivel": l.escudo_disponivel,
                "trofeu_disponivel": l.trofeu_disponivel,
                "uniformes_disponiveis": l.uniformes_disponiveis,
                "pack_origem": l.pack_origem,
            })
        for cid, c in self._clubes.items():
            resultado["clubes"].append({
                "id": cid,
                "nome_oficial": c.nome_oficial,
                "nome_generico": c.nome_generico,
                "nome_exibicao": self.resolver_nome_clube(cid),
                "pais": c.pais,
                "liga_id": c.liga_id,
                "status": c.status.value,
            })
        for cpid, cp in self._competicoes.items():
            resultado["competicoes"].append({
                "id": cpid,
                "nome_oficial": cp.nome_oficial,
                "nome_generico": cp.nome_generico,
                "nome_exibicao": self.resolver_nome_competicao(cpid),
                "regiao": cp.regiao.value,
                "status": cp.status.value,
            })
        return resultado
