# -*- coding: utf-8 -*-
"""
Modelos de domínio — dataclasses puras, sem lógica de persistência.
Migrado do legacy models.py com melhorias: traits, fantasy hooks, tipagem.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from core.enums import (
    Posicao, PePreferido, StatusMoral, StatusLesao,
    TipoContrato, NivelTreinamento, FormacaoTatica,
    EstiloJogo, VelocidadeJogo, MarcacaoPressao,
    TipoStaff, CategoriaNoticia, TraitJogador,
    StatusOferta, TipoOferta,
    StatusLicenca, TipoConteudoLicenciado, RegiaoLicenca,
    TipoRemetente, PrioridadeMensagem, CategoriaMensagem,
    StatusMensagem, TipoAcaoMensagem,
    ClimaPartida, CategoriaConquista, TipoPremio,
    TipoColetiva, TomResposta, TipoUpgradeEstadio,
    TipoPromessa, StatusPromessa,
    StatusVestiario, TipoEvtVestiario,
    NivelEntrosamento, EstiloClube, TipoAgente, NivelAdaptacao,
    TacticalRole, TacticalDuty,
)
from core.constants import OVERALL_WEIGHTS


# ══════════════════════════════════════════════════════════════
#  ATRIBUTOS
# ══════════════════════════════════════════════════════════════

@dataclass
class AtributosTecnicos:
    passe_curto: int = 50
    passe_longo: int = 50
    cruzamento: int = 50
    finalizacao: int = 50
    chute_longa_dist: int = 50
    cabeceio: int = 50
    drible: int = 50
    controle_bola: int = 50
    falta: int = 50
    penalti: int = 50
    desarme: int = 50
    marcacao: int = 50
    lancamento: int = 50

    def overall(self) -> float:
        vals = [self.passe_curto, self.passe_longo, self.cruzamento,
                self.finalizacao, self.chute_longa_dist, self.cabeceio,
                self.drible, self.controle_bola, self.falta, self.penalti,
                self.desarme, self.marcacao, self.lancamento]
        return sum(vals) / len(vals)


@dataclass
class AtributosFisicos:
    velocidade: int = 50
    aceleracao: int = 50
    resistencia: int = 50
    forca: int = 50
    agilidade: int = 50
    salto: int = 50
    equilibrio: int = 50

    def overall(self) -> float:
        vals = [self.velocidade, self.aceleracao, self.resistencia,
                self.forca, self.agilidade, self.salto, self.equilibrio]
        return sum(vals) / len(vals)


@dataclass
class AtributosMentais:
    visao_jogo: int = 50
    decisao: int = 50
    concentracao: int = 50
    determinacao: int = 50
    lideranca: int = 50
    trabalho_equipe: int = 50
    criatividade: int = 50
    compostura: int = 50
    agressividade: int = 50
    posicionamento: int = 50
    antecipacao: int = 50
    bravura: int = 50

    def overall(self) -> float:
        vals = [self.visao_jogo, self.decisao, self.concentracao,
                self.determinacao, self.lideranca, self.trabalho_equipe,
                self.criatividade, self.compostura, self.agressividade,
                self.posicionamento, self.antecipacao, self.bravura]
        return sum(vals) / len(vals)


@dataclass
class AtributosGoleiro:
    reflexos: int = 50
    posicionamento_gol: int = 50
    jogo_aereo: int = 50
    defesa_1v1: int = 50
    reposicao: int = 50
    jogo_com_pes: int = 50
    punho: int = 50
    elasticidade: int = 50
    comando_area: int = 50

    def overall(self) -> float:
        vals = [self.reflexos, self.posicionamento_gol, self.jogo_aereo,
                self.defesa_1v1, self.reposicao, self.jogo_com_pes,
                self.punho, self.elasticidade, self.comando_area]
        return sum(vals) / len(vals)


# ══════════════════════════════════════════════════════════════
#  JOGADOR
# ══════════════════════════════════════════════════════════════

@dataclass
class Historico:
    temporada: int = 2026
    time: str = ""
    jogos: int = 0
    gols: int = 0
    assistencias: int = 0
    cartoes_amarelos: int = 0
    cartoes_vermelhos: int = 0
    nota_media: float = 6.0


@dataclass
class ContratoJogador:
    tipo: TipoContrato = TipoContrato.PROFISSIONAL
    salario: int = 50_000
    multa_rescisoria: int = 1_000_000
    duracao_meses: int = 24
    meses_restantes: int = 24
    time_origem: str = ""
    clausula_compra: int = 0


@dataclass
class Jogador:
    id: int = 0
    nome: str = ""
    idade: int = 25
    nacionalidade: str = "Brasil"
    foto: str = ""
    posicao: Posicao = Posicao.CA
    posicoes_alternativas: List[Posicao] = field(default_factory=list)
    pe_preferido: PePreferido = PePreferido.DIREITO
    numero_camisa: int = 0
    altura: float = 1.80
    peso: float = 78.0

    # Atributos
    tecnicos: AtributosTecnicos = field(default_factory=AtributosTecnicos)
    fisicos: AtributosFisicos = field(default_factory=AtributosFisicos)
    mentais: AtributosMentais = field(default_factory=AtributosMentais)
    goleiro: AtributosGoleiro = field(default_factory=AtributosGoleiro)

    # Status
    moral: int = 70
    condicao_fisica: int = 100
    status_lesao: StatusLesao = StatusLesao.SAUDAVEL
    dias_lesao: int = 0
    cartao_amarelo_acumulado: int = 0
    suspensao_jogos: int = 0

    # Contrato
    contrato: ContratoJogador = field(default_factory=ContratoJogador)

    # Potencial e desenvolvimento
    potencial: int = 70
    talento_oculto: int = 50

    # Traits (NOVO)
    traits: List[TraitJogador] = field(default_factory=list)

    # Histórico
    historico: List[Historico] = field(default_factory=list)
    historico_temporada: Historico = field(default_factory=Historico)

    # Preferências
    quer_sair: bool = False
    feliz: bool = True
    adaptacao: int = 100

    # ── Propriedades ──────────────────────────────────────────

    @property
    def overall(self) -> int:
        w = OVERALL_WEIGHTS.get(self.posicao.name, OVERALL_WEIGHTS["DEFAULT"])
        return int(
            self.tecnicos.overall() * w[0]
            + self.fisicos.overall() * w[1]
            + self.mentais.overall() * w[2]
            + self.goleiro.overall() * w[3]
        )

    @property
    def valor_mercado(self) -> int:
        base = self.overall * 100_000
        if self.idade < 23:
            base *= 1.5
        elif self.idade < 27:
            base *= 1.2
        elif self.idade > 32:
            base *= 0.5
        elif self.idade > 30:
            base *= 0.7
        if self.potencial > 80:
            base *= 1.3
        return int(base)

    @property
    def status_moral_enum(self) -> StatusMoral:
        if self.moral >= 85:
            return StatusMoral.EXCELENTE
        if self.moral >= 65:
            return StatusMoral.BOM
        if self.moral >= 45:
            return StatusMoral.NORMAL
        if self.moral >= 25:
            return StatusMoral.RUIM
        return StatusMoral.PESSIMO

    def pode_jogar(self) -> bool:
        return (
            self.status_lesao == StatusLesao.SAUDAVEL
            and self.suspensao_jogos == 0
            and self.condicao_fisica >= 20
        )

    def tem_trait(self, trait: TraitJogador) -> bool:
        return trait in self.traits


# ══════════════════════════════════════════════════════════════
#  STAFF
# ══════════════════════════════════════════════════════════════

@dataclass
class StaffMembro:
    id: int = 0
    nome: str = ""
    idade: int = 45
    tipo: TipoStaff = TipoStaff.TREINADOR
    habilidade: int = 50
    salario: int = 30_000
    especializacao: str = ""


# ══════════════════════════════════════════════════════════════
#  ESTÁDIO
# ══════════════════════════════════════════════════════════════

@dataclass
class Estadio:
    nome: str = "Estádio Municipal"
    capacidade: int = 30_000
    nivel_gramado: int = 70
    nivel_estrutura: int = 70
    preco_ingresso: int = 50
    custo_manutencao: int = 200_000
    # Seções do estádio (Brasfoot-style)
    cap_geral: int = 15_000
    cap_arquibancada: int = 8_000
    cap_cadeira: int = 5_000
    cap_camarote: int = 2_000
    preco_geral: int = 30
    preco_arquibancada: int = 50
    preco_cadeira: int = 80
    preco_camarote: int = 150
    # Construction queue: list of {tipo, semanas_restantes, descricao}
    obras_em_andamento: List[Dict] = field(default_factory=list)

    @property
    def receita_jogo_lotado(self) -> int:
        return self.capacidade * self.preco_ingresso

    def publico_estimado(self, fator_atratividade: float) -> int:
        base = int(self.capacidade * fator_atratividade)
        variacao = random.randint(-int(base * 0.1), int(max(1, base * 0.1)))
        return max(1000, min(self.capacidade, base + variacao))


# ══════════════════════════════════════════════════════════════
#  FINANÇAS
# ══════════════════════════════════════════════════════════════

@dataclass
class Financas:
    saldo: int = 5_000_000
    orcamento_salarios: int = 2_000_000
    orcamento_transferencias: int = 10_000_000
    receitas_mes: int = 0
    despesas_mes: int = 0
    historico_mensal: List[Dict] = field(default_factory=list)

    patrocinador_principal: str = "Sem patrocinador"
    receita_patrocinio_mensal: int = 500_000
    contrato_patrocinio_meses: int = 12
    material_esportivo: str = ""
    patrocinador_costas: str = ""
    patrocinador_manga: str = ""

    receita_tv_mensal: int = 300_000

    num_socios: int = 10_000
    mensalidade_socio: int = 50

    @property
    def receita_socios_mensal(self) -> int:
        return self.num_socios * self.mensalidade_socio

    def processar_mes(self, folha_salarial: int, receitas_extras: int = 0,
                      despesas_extras: int = 0) -> Dict:
        receitas = (self.receita_patrocinio_mensal
                    + self.receita_tv_mensal
                    + self.receita_socios_mensal
                    + receitas_extras)
        despesas = folha_salarial + despesas_extras
        self.saldo += receitas - despesas
        self.receitas_mes = receitas
        self.despesas_mes = despesas
        registro = {"receitas": receitas, "despesas": despesas,
                    "saldo": self.saldo, "folha": folha_salarial}
        self.historico_mensal.append(registro)
        return registro


# ══════════════════════════════════════════════════════════════
#  TÁTICA
# ══════════════════════════════════════════════════════════════

@dataclass
class Tatica:
    formacao: FormacaoTatica = FormacaoTatica.F442
    estilo: EstiloJogo = EstiloJogo.EQUILIBRADO
    velocidade: VelocidadeJogo = VelocidadeJogo.NORMAL
    marcacao: MarcacaoPressao = MarcacaoPressao.NORMAL

    linha_alta: bool = False
    contra_ataque: bool = False
    jogo_pelas_laterais: bool = False
    jogo_pelo_centro: bool = False
    bola_longa: bool = False
    toque_curto: bool = True
    pressao_saida_bola: bool = False
    zaga_adiantada: bool = False

    cobrador_falta: Optional[int] = None
    cobrador_penalti: Optional[int] = None
    cobrador_escanteio: Optional[int] = None
    capitao: Optional[int] = None

    # ── Roles táticos por slot (FM-style) ──
    # Mapa: slot_idx (0-10) → {"role": TacticalRole.value, "duty": TacticalDuty.value}
    roles_jogadores: Dict[int, Dict[str, str]] = field(default_factory=dict)

    # ── Estratégias de bola parada (Set Pieces) ──
    escanteio_estilo: str = "areaCentral"   # areaCentral, primeiro_pau, segundo_pau, curto, direto_area
    falta_estilo: str = "direto"            # direto, cruzamento, toque_curto, por_cima
    lateral_longo: bool = False             # arremesso lateral longo
    # Marcação em bola parada defensiva
    defesa_escanteio: str = "zona"          # zona, individual, misto
    num_barreira_falta: int = 3             # jogadores na barreira (2-5)


# ══════════════════════════════════════════════════════════════
#  TREINAMENTO
# ══════════════════════════════════════════════════════════════

@dataclass
class Treinamento:
    foco_tecnico: str = "Geral"
    foco_fisico: str = "Geral"
    foco_tatico: str = "Geral"
    intensidade: NivelTreinamento = NivelTreinamento.NORMAL
    # Ultrafoot-style: primary skill focus
    foco_principal: str = "finalizacao"  # gol, desarme, armacao, finalizacao
    foco_secundario: str = "velocidade"  # velocidade, tecnica, passe
    auto_decidir: bool = True  # let assistant coach decide
    # ── Treino individualizado por jogador ──
    # Mapa: jogador_id → {"foco": str, "intensidade": str, "sessoes": int}
    planos_individuais: Dict[int, Dict[str, str]] = field(default_factory=dict)

    @property
    def risco_lesao(self) -> float:
        from config import TREINO_RISCO
        return TREINO_RISCO.get(self.intensidade.name, 0.03)

    @property
    def fator_evolucao(self) -> float:
        from config import TREINO_FATOR
        return TREINO_FATOR.get(self.intensidade.name, 1.0)


# ══════════════════════════════════════════════════════════════
#  BASE JUVENIL
# ══════════════════════════════════════════════════════════════

@dataclass
class BaseJuvenil:
    nivel: int = 50
    investimento_mensal: int = 100_000
    jogadores: List[Jogador] = field(default_factory=list)
    chance_revelar: float = 0.15


# ══════════════════════════════════════════════════════════════
#  DIRETORIA (Board Objectives)
# ══════════════════════════════════════════════════════════════

@dataclass
class Diretoria:
    """Board expectations and manager satisfaction."""
    meta_principal: str = ""           # e.g. "Top 8", "Acesso", "Título"
    meta_minima: str = ""              # e.g. "Não rebaixar", "Top 12"
    satisfacao: int = 50               # 0-100
    paciencia: int = 50                # 0-100, lower = closer to sacking
    pressao_torcida: int = 50          # 0-100
    demitido: bool = False
    mensagens: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.satisfacao >= 80:
            return "Excelente"
        elif self.satisfacao >= 60:
            return "Boa"
        elif self.satisfacao >= 40:
            return "Regular"
        elif self.satisfacao >= 20:
            return "Ruim"
        return "Crítica"


# ══════════════════════════════════════════════════════════════
#  TIME
# ══════════════════════════════════════════════════════════════

@dataclass
class Time:
    id: int = 0
    nome: str = ""
    nome_curto: str = ""
    cidade: str = ""
    estado: str = ""
    cor_principal: str = ""
    cor_secundaria: str = ""
    divisao: int = 1
    prestigio: int = 70
    torcida_tamanho: int = 1_000_000

    jogadores: List[Jogador] = field(default_factory=list)
    staff: List[StaffMembro] = field(default_factory=list)

    estadio: Estadio = field(default_factory=Estadio)
    financas: Financas = field(default_factory=Financas)
    base_juvenil: BaseJuvenil = field(default_factory=BaseJuvenil)

    tatica: Tatica = field(default_factory=Tatica)
    titulares: List[int] = field(default_factory=list)
    reservas: List[int] = field(default_factory=list)

    treinamento: Treinamento = field(default_factory=Treinamento)
    diretoria: Diretoria = field(default_factory=Diretoria)

    vitorias: int = 0
    empates: int = 0
    derrotas: int = 0
    gols_marcados: int = 0
    gols_sofridos: int = 0
    pontos: int = 0

    eh_jogador: bool = False

    # ── Propriedades ──────────────────────────────────────────

    @property
    def folha_salarial(self) -> int:
        total = sum(j.contrato.salario for j in self.jogadores)
        total += sum(s.salario for s in self.staff)
        return total

    @property
    def saldo_gols(self) -> int:
        return self.gols_marcados - self.gols_sofridos

    @property
    def overall_medio(self) -> int:
        if not self.jogadores:
            return 0
        return int(sum(j.overall for j in self.jogadores) / len(self.jogadores))

    @property
    def forca_time(self) -> int:
        titulares = [j for j in self.jogadores if j.id in self.titulares]
        if not titulares:
            return self.overall_medio
        ovr = sum(j.overall for j in titulares) / len(titulares)
        moral_m = sum(j.moral for j in titulares) / len(titulares)
        cond_m = sum(j.condicao_fisica for j in titulares) / len(titulares)
        return int(ovr * 0.6 + moral_m * 0.1 * 0.99
                   + cond_m * 0.1 * 0.99 + self.prestigio * 0.2)

    def jogador_por_id(self, jid: int) -> Optional[Jogador]:
        for j in self.jogadores:
            if j.id == jid:
                return j
        return None

    def staff_por_tipo(self, tipo: TipoStaff) -> Optional[StaffMembro]:
        for s in self.staff:
            if s.tipo == tipo:
                return s
        return None

    def resetar_temporada(self) -> None:
        self.vitorias = 0
        self.empates = 0
        self.derrotas = 0
        self.gols_marcados = 0
        self.gols_sofridos = 0
        self.pontos = 0
        for j in self.jogadores:
            j.historico_temporada = Historico(time=self.nome)
            j.cartao_amarelo_acumulado = 0
            j.suspensao_jogos = 0


# ══════════════════════════════════════════════════════════════
#  EVENTOS & RESULTADO DE PARTIDA
# ══════════════════════════════════════════════════════════════

@dataclass
class EventoPartida:
    minuto: int = 0
    tipo: str = ""
    jogador_nome: str = ""
    jogador_id: int = 0
    time: str = ""
    detalhe: str = ""


@dataclass
class ResultadoPartida:
    time_casa: str = ""
    time_fora: str = ""
    gols_casa: int = 0
    gols_fora: int = 0
    posse_casa: float = 50.0
    finalizacoes_casa: int = 0
    finalizacoes_fora: int = 0
    finalizacoes_gol_casa: int = 0
    finalizacoes_gol_fora: int = 0
    escanteios_casa: int = 0
    escanteios_fora: int = 0
    faltas_casa: int = 0
    faltas_fora: int = 0
    impedimentos_casa: int = 0
    impedimentos_fora: int = 0
    publico: int = 0
    renda: int = 0
    eventos: List[EventoPartida] = field(default_factory=list)

    # Fantasy hook — preenchido pelo motor
    notas_jogadores: Dict[int, float] = field(default_factory=dict)
    fantasy_pontos: Dict[int, float] = field(default_factory=dict)

    # Condições de jogo
    clima: str = ""
    nivel_gramado: int = 80
    eh_derby: bool = False
    narrador_texto: List[str] = field(default_factory=list)  # narração textual

    # xG / xA / Momentum — preenchido pelo motor
    xg_casa: float = 0.0
    xg_fora: float = 0.0
    xa_casa: float = 0.0
    xa_fora: float = 0.0
    momentum: List[Dict] = field(default_factory=list)

    # Escalações (nomes dos 11 titulares) — preenchido pelo motor
    escalacao_casa: List[str] = field(default_factory=list)
    escalacao_fora: List[str] = field(default_factory=list)

    # Árbitro da partida
    arbitro: str = ""

    @property
    def placar(self) -> str:
        return f"{self.time_casa} {self.gols_casa} x {self.gols_fora} {self.time_fora}"


# ══════════════════════════════════════════════════════════════
#  OFERTA DE TRANSFERÊNCIA
# ══════════════════════════════════════════════════════════════

@dataclass
class OfertaTransferencia:
    id: int = 0
    jogador_id: int = 0
    jogador_nome: str = ""
    time_origem: str = ""
    time_destino: str = ""
    valor: int = 0
    salario_oferecido: int = 0
    tipo: TipoOferta = TipoOferta.COMPRA
    status: StatusOferta = StatusOferta.PENDENTE
    jogador_troca_id: int = 0


# ══════════════════════════════════════════════════════════════
#  NOTÍCIA
# ══════════════════════════════════════════════════════════════

@dataclass
class Noticia:
    titulo: str = ""
    texto: str = ""
    categoria: CategoriaNoticia = CategoriaNoticia.GERAL
    rodada: int = 0


# ══════════════════════════════════════════════════════════════
#  LICENCIAMENTO DE CONTEÚDO
# ══════════════════════════════════════════════════════════════

@dataclass
class LicencaConteudo:
    """Metadados de licenciamento de uma liga, clube ou competição."""
    id: str = ""                            # identificador único (ex: "ING_premier_league")
    tipo: TipoConteudoLicenciado = TipoConteudoLicenciado.LIGA
    nome_oficial: str = ""                  # nome real licenciado
    nome_generico: str = ""                 # nome fallback genérico
    regiao: RegiaoLicenca = RegiaoLicenca.GLOBAL
    pais_codigo: str = ""                   # código do país (ex: "ING", "ESP")
    status: StatusLicenca = StatusLicenca.GENERICO
    data_validade: str = ""                 # YYYY-MM-DD, vazio = sem expiração
    restricoes: List[str] = field(default_factory=list)  # ex: ["sem_escudo", "sem_uniforme"]
    asset_oficial: str = ""                 # caminho do asset oficial
    asset_fallback: str = ""                # caminho do asset genérico/placeholder
    fonte: str = ""                         # fonte de dados (ex: "pack224", "oficial", "mod")
    ativo_build_comercial: bool = False     # se pode incluir em build comercial


@dataclass
class RegistroLicencaLiga:
    """Registro completo de licenciamento de uma liga."""
    id_liga: str = ""                       # ex: "ING_div_1"
    nome_oficial: str = ""                  # ex: "Premier League"
    nome_generico: str = ""                 # ex: "English First Division"
    pais: str = ""
    regiao: RegiaoLicenca = RegiaoLicenca.EUROPA
    status: StatusLicenca = StatusLicenca.GENERICO
    clubes_licenciados: int = 0
    clubes_total: int = 0
    escudo_disponivel: bool = False
    trofeu_disponivel: bool = False
    uniformes_disponiveis: bool = False
    pack_origem: str = ""                   # ex: "base", "pack_europa", "mod_user"


@dataclass
class RegistroLicencaClube:
    """Registro completo de licenciamento de um clube."""
    id_clube: str = ""                      # ex: "manchester_united"
    nome_oficial: str = ""
    nome_generico: str = ""                 # ex: "Manchester Red"
    pais: str = ""
    liga_id: str = ""
    status: StatusLicenca = StatusLicenca.GENERICO
    escudo_oficial: str = ""
    escudo_fallback: str = ""
    uniforme_oficial: bool = False
    uniforme_fallback: bool = True
    jogadores_nomes_reais: bool = False
    estadio_nome_oficial: str = ""
    estadio_nome_generico: str = ""


@dataclass
class RegistroLicencaCompeticao:
    """Registro de licenciamento de uma competição/torneio."""
    id_competicao: str = ""
    nome_oficial: str = ""
    nome_generico: str = ""
    regiao: RegiaoLicenca = RegiaoLicenca.GLOBAL
    status: StatusLicenca = StatusLicenca.GENERICO
    trofeu_oficial: str = ""
    trofeu_fallback: str = ""
    logo_oficial: str = ""
    logo_fallback: str = ""


# ══════════════════════════════════════════════════════════════
#  CENTRAL DE NOTIFICAÇÕES / INBOX DO TÉCNICO
# ══════════════════════════════════════════════════════════════

@dataclass
class AcaoMensagem:
    """Uma ação disponível em resposta a uma mensagem."""
    tipo: TipoAcaoMensagem = TipoAcaoMensagem.ARQUIVAR
    label: str = ""                         # texto exibido no botão
    valor: str = ""                         # dados associados (JSON string)
    tela_destino: str = ""                  # se abrir_tela, qual tela ir


@dataclass
class MensagemInbox:
    """Mensagem na caixa de entrada do técnico."""
    id: int = 0
    rodada: int = 0
    temporada: int = 2026
    remetente_tipo: TipoRemetente = TipoRemetente.SISTEMA
    remetente_nome: str = ""                # nome do remetente (ex: "Carlos Silva" ou "Diretoria")
    remetente_cargo: str = ""               # cargo do remetente (ex: "Presidente", "Capitão")
    categoria: CategoriaMensagem = CategoriaMensagem.NOTICIA_TEMPORADA
    prioridade: PrioridadeMensagem = PrioridadeMensagem.MEDIA
    titulo: str = ""
    texto: str = ""
    status: StatusMensagem = StatusMensagem.NAO_LIDA
    acoes: List[AcaoMensagem] = field(default_factory=list)
    prazo_resposta: int = -1                # rodadas até expirar, -1 = sem prazo
    respondida_com: str = ""                # qual ação foi tomada
    # Impactos potenciais
    impacto_moral: int = 0                  # -20 a +20
    impacto_reputacao: int = 0              # -10 a +10
    impacto_satisfacao_diretoria: int = 0   # -15 a +15
    impacto_financeiro: int = 0             # valor em R$
    # Contexto
    jogador_id: int = 0                     # se relacionado a jogador
    time_nome: str = ""                     # se relacionado a time
    competicao: str = ""                    # se relacionado a competição
    fixada: bool = False
    arquivada: bool = False


# ══════════════════════════════════════════════════════════════
#  CLIMA DE PARTIDA
# ══════════════════════════════════════════════════════════════

@dataclass
class CondicoesPartida:
    """Condições climáticas e estado do gramado para uma partida."""
    clima: ClimaPartida = ClimaPartida.SOL
    temperatura: int = 25           # graus Celsius
    nivel_gramado: int = 80         # 0-100
    vento: int = 0                  # km/h

    @property
    def fator_gramado(self) -> float:
        return max(0.85, self.nivel_gramado / 100)

    @property
    def fator_clima(self) -> float:
        m = {ClimaPartida.SOL: 1.0, ClimaPartida.NUBLADO: 0.98,
             ClimaPartida.CHUVA: 0.93, ClimaPartida.CHUVA_FORTE: 0.87,
             ClimaPartida.NEVE: 0.85, ClimaPartida.CALOR_EXTREMO: 0.90}
        return m.get(self.clima, 1.0)


# ══════════════════════════════════════════════════════════════
#  CONQUISTAS / ACHIEVEMENTS
# ══════════════════════════════════════════════════════════════

@dataclass
class Conquista:
    """Achievement desbloqueável."""
    id: str = ""
    titulo: str = ""
    descricao: str = ""
    icone: str = "🏆"
    categoria: CategoriaConquista = CategoriaConquista.TITULO
    desbloqueada: bool = False
    data_desbloqueio: str = ""      # "temp X, semana Y"
    progresso: int = 0
    meta: int = 1
    oculta: bool = False


# ══════════════════════════════════════════════════════════════
#  PREMIAÇÕES DE FIM DE TEMPORADA
# ══════════════════════════════════════════════════════════════

@dataclass
class PremiacaoTemporada:
    """Prêmio individual ou coletivo de fim de temporada."""
    tipo: TipoPremio = TipoPremio.ARTILHEIRO
    temporada: int = 2026
    jogador_nome: str = ""
    jogador_id: int = 0
    time_nome: str = ""
    competicao: str = ""
    valor: str = ""                 # ex: "25 gols" ou "9.2 nota média"


# ══════════════════════════════════════════════════════════════
#  COLETIVA DE IMPRENSA
# ══════════════════════════════════════════════════════════════

@dataclass
class PerguntaColetiva:
    """Pergunta de um jornalista na coletiva."""
    id: int = 0
    texto: str = ""
    jornalista: str = ""
    veiculo: str = ""
    tom_sugerido: List[TomResposta] = field(default_factory=list)
    contexto: str = ""              # referência a resultado, jogador etc.

@dataclass
class RespostaColetiva:
    """Resposta do técnico."""
    tom: TomResposta = TomResposta.DIPLOMATICO
    texto: str = ""
    impacto_moral_elenco: int = 0
    impacto_torcida: int = 0
    impacto_midia: int = 0
    impacto_diretoria: int = 0

@dataclass
class SessaoColetiva:
    """Sessão de coletiva de imprensa."""
    tipo: TipoColetiva = TipoColetiva.POS_JOGO
    perguntas: List[PerguntaColetiva] = field(default_factory=list)
    respostas: List[RespostaColetiva] = field(default_factory=list)
    concluida: bool = False


# ══════════════════════════════════════════════════════════════
#  RIVALIDADES / DERBIES
# ══════════════════════════════════════════════════════════════

@dataclass
class Rivalidade:
    """Par de times com rivalidade."""
    time_a: str = ""
    time_b: str = ""
    intensidade: int = 80            # 0-100
    nome_classico: str = ""          # ex: "Fla-Flu", "Clássico dos Milhões"


# ══════════════════════════════════════════════════════════════
#  UPGRADE DE ESTÁDIO DETALHADO
# ══════════════════════════════════════════════════════════════

@dataclass
class UpgradeEstadio:
    """Upgrade em andamento no estádio."""
    tipo: TipoUpgradeEstadio = TipoUpgradeEstadio.CAPACIDADE
    custo: int = 0
    semanas_restantes: int = 0
    bonus: int = 0                   # incremento ao concluir


# ══════════════════════════════════════════════════════════════
#  RECORDES DE CARREIRA
# ══════════════════════════════════════════════════════════════

@dataclass
class RecordeCarreira:
    """Recorde individual na carreira do técnico."""
    chave: str = ""                  # id do recorde
    descricao: str = ""
    valor: int = 0
    detalhe: str = ""                # ex: "Temporada 2027, Série A"


# ══════════════════════════════════════════════════════════════
#  PRÉ-TEMPORADA
# ══════════════════════════════════════════════════════════════

@dataclass
class PreTemporada:
    """Estado da pré-temporada."""
    ativa: bool = False
    semanas_total: int = 4
    semanas_restantes: int = 0
    amistosos_jogados: int = 0
    foco_treino: str = "fisico"      # fisico / tatico / tecnico
    bonus_condicao: int = 0


# ══════════════════════════════════════════════════════════════
#  PROMESSAS
# ══════════════════════════════════════════════════════════════

@dataclass
class Promessa:
    """Promessa feita a um jogador, diretoria ou torcida."""
    id: int = 0
    tipo: TipoPromessa = TipoPromessa.TITULAR
    status: StatusPromessa = StatusPromessa.ATIVA
    descricao: str = ""
    jogador_id: int = 0               # se aplicável
    jogador_nome: str = ""
    prazo_semanas: int = 12            # semanas para cumprir
    semanas_restantes: int = 12
    penalidade_moral: int = -15        # impacto se quebrada
    penalidade_reputacao: int = -5
    valor_referencia: int = 0          # ex: salário prometido, valor reforço

    @property
    def expirada(self) -> bool:
        return self.semanas_restantes <= 0 and self.status == StatusPromessa.ATIVA


# ══════════════════════════════════════════════════════════════
#  CARREIRA DO TREINADOR
# ══════════════════════════════════════════════════════════════

@dataclass
class CarreiraTreinador:
    """Histórico e legado do treinador ao longo das temporadas."""
    nome: str = "Treinador"
    reputacao: int = 50                # 0-100
    experiencia: int = 0               # semanas totais
    titulos: List[Dict] = field(default_factory=list)  # [{nome, temporada, time}]
    times_anteriores: List[Dict] = field(default_factory=list)  # [{nome, semanas, motivo_saida}]
    vitorias_total: int = 0
    empates_total: int = 0
    derrotas_total: int = 0
    melhor_posicao: str = ""
    pior_posicao: str = ""
    estilo_preferido: str = "equilibrado"
    especialidade: str = ""            # "formador", "motivador", "tattico", "resultadista"

    @property
    def aproveitamento(self) -> float:
        jogos = self.vitorias_total + self.empates_total + self.derrotas_total
        if jogos == 0:
            return 0.0
        return round((self.vitorias_total * 3 + self.empates_total) / (jogos * 3) * 100, 1)


# ══════════════════════════════════════════════════════════════
#  DINÂMICA DE VESTIÁRIO
# ══════════════════════════════════════════════════════════════

@dataclass
class EventoVestiario:
    """Evento ocorrido no vestiário."""
    tipo: TipoEvtVestiario = TipoEvtVestiario.UNIAO
    descricao: str = ""
    jogadores_envolvidos: List[int] = field(default_factory=list)
    impacto_moral: int = 0
    semana: int = 0

@dataclass
class DynamicaVestiario:
    """Estado do vestiário e dinâmica de grupo."""
    harmonia: int = 70                  # 0-100
    coesao: int = 60                    # 0-100
    lider_id: int = 0                   # capitão/líder emergente
    panelinhas: List[List[int]] = field(default_factory=list)  # grupos de jogadores
    eventos_recentes: List[EventoVestiario] = field(default_factory=list)
    tensoes: List[Dict] = field(default_factory=list)  # [{jogador_a, jogador_b, nivel}]

    @property
    def status(self) -> StatusVestiario:
        if self.harmonia >= 80:
            return StatusVestiario.HARMONIOSO
        if self.harmonia >= 60:
            return StatusVestiario.ESTAVEL
        if self.harmonia >= 40:
            return StatusVestiario.TENSO
        if self.harmonia >= 20:
            return StatusVestiario.CONFLITUOSO
        return StatusVestiario.TOXICO

    @property
    def bonus_moral(self) -> float:
        """Multiplier for team moral based on locker room harmony."""
        return 0.85 + (self.harmonia / 100) * 0.30


# ══════════════════════════════════════════════════════════════
#  QUÍMICA TÁTICA / ENTROSAMENTO
# ══════════════════════════════════════════════════════════════

@dataclass
class QuimicaTatica:
    """Entrosamento do time com a formação e entre jogadores."""
    familiaridade_formacao: int = 50    # 0-100, cresce com uso
    formacao_usada: str = "4-4-2"       # última formação usada
    semanas_mesma_formacao: int = 0
    parcerias: List[Dict] = field(default_factory=list)  # [{j1_id, j2_id, nivel}]
    entrosamento_geral: int = 50        # 0-100

    @property
    def nivel(self) -> NivelEntrosamento:
        e = self.entrosamento_geral
        if e >= 90:
            return NivelEntrosamento.PERFEITO
        if e >= 70:
            return NivelEntrosamento.ALTO
        if e >= 45:
            return NivelEntrosamento.MEDIO
        if e >= 20:
            return NivelEntrosamento.BAIXO
        return NivelEntrosamento.NENHUM

    @property
    def bonus_tatico(self) -> float:
        """Multiplier bonus from tactical chemistry (1.0-1.10)."""
        return 1.0 + (self.entrosamento_geral / 1000)


# ══════════════════════════════════════════════════════════════
#  IDENTIDADE DO CLUBE
# ══════════════════════════════════════════════════════════════

@dataclass
class IdentidadeClube:
    """DNA e identidade histórica do clube."""
    estilo: EstiloClube = EstiloClube.OFENSIVO
    formacao_raiz: str = "4-4-2"
    valoriza_base: bool = False
    rivalidades_historicas: List[str] = field(default_factory=list)
    torcida_exigente: bool = False
    tradicao_copas: bool = False
    tradicao_libertadores: bool = False


# ══════════════════════════════════════════════════════════════
#  PERFIL DE AGENTE (Empresário)
# ══════════════════════════════════════════════════════════════

@dataclass
class PerfilAgente:
    """Perfil do agente/empresário de um jogador."""
    nome: str = ""
    tipo: TipoAgente = TipoAgente.AMIGAVEL
    influencia: int = 50               # 0-100
    comissao_pct: float = 0.10         # percentual que cobra
    dificuldade_negociacao: int = 50   # 0-100
    jogadores_representados: List[int] = field(default_factory=list)

    @property
    def multiplicador_pedido(self) -> float:
        """Quanto o agente infla os pedidos."""
        base = {
            TipoAgente.AMIGAVEL: 1.0,
            TipoAgente.AGRESSIVO: 1.25,
            TipoAgente.LEGALISTA: 1.10,
            TipoAgente.SUPERAGENTE: 1.40,
            TipoAgente.OPORTUNISTA: 1.15,
        }
        return base.get(self.tipo, 1.0)


# ══════════════════════════════════════════════════════════════
#  ADAPTAÇÃO CULTURAL
# ══════════════════════════════════════════════════════════════

@dataclass
class AdaptacaoCultural:
    """Estado de adaptação de um jogador estrangeiro."""
    jogador_id: int = 0
    pais_origem: str = ""
    pais_atual: str = "Brasil"
    nivel: NivelAdaptacao = NivelAdaptacao.EM_ADAPTACAO
    progresso: int = 30                 # 0-100
    semanas_no_pais: int = 0
    fala_idioma: bool = False
    tem_familia: bool = True
    penalidade_overall: int = -5        # penalidade temporária no overall

    @property
    def fator_rendimento(self) -> float:
        """Factor applied to player performance while adapting."""
        if self.progresso >= 90:
            return 1.0
        if self.progresso >= 60:
            return 0.95
        if self.progresso >= 30:
            return 0.90
        return 0.85


# ══════════════════════════════════════════════════════════════
#  ANÁLISE PÓS-JOGO
# ══════════════════════════════════════════════════════════════

@dataclass
class AnalisePartida:
    """Análise tática pós-jogo."""
    xg_casa: float = 0.0
    xg_fora: float = 0.0
    xa_casa: float = 0.0
    xa_fora: float = 0.0
    dominio_posse: str = ""          # "casa" ou "fora"
    setor_dominante_casa: str = ""   # "ataque", "meio", "defesa"
    setor_dominante_fora: str = ""
    pressao_alta_efetiva_casa: bool = False
    pressao_alta_efetiva_fora: bool = False
    momentum_periodos: List[Dict] = field(default_factory=list)  # [{min_ini, min_fim, time, intensidade}]
    recomendacoes: List[str] = field(default_factory=list)
    notas_taticas: List[str] = field(default_factory=list)
    jogador_destaque: str = ""
    jogador_fraco: str = ""


# ══════════════════════════════════════════════════════════════
#  OBJETIVO PESSOAL DO JOGADOR
# ══════════════════════════════════════════════════════════════

@dataclass
class ObjetivoPessoalJogador:
    """Objetivo pessoal de um jogador na temporada."""
    jogador_id: int = 0
    descricao: str = ""               # "Marcar 15 gols", "Ser titular", etc.
    tipo: str = "gols"                # gols, assists, titular, selecao
    meta: int = 10
    progresso: int = 0
    impacto_moral_sucesso: int = 15
    impacto_moral_falha: int = -10
