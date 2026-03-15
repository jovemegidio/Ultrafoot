# -*- coding: utf-8 -*-
"""
Enumerações de domínio do Ultrafoot.
Consolidado a partir do legacy models.py com adições para fantasy e traits.
"""
from __future__ import annotations
from enum import Enum


# ── Posições ──────────────────────────────────────────────────

class Posicao(Enum):
    GOL = "Goleiro"
    ZAG = "Zagueiro"
    LD = "Lateral Direito"
    LE = "Lateral Esquerdo"
    VOL = "Volante"
    MC = "Meia Central"
    ME = "Meia Esquerda"
    MD = "Meia Direita"
    MEI = "Meia Atacante"
    PD = "Ponta Direita"
    PE = "Ponta Esquerda"
    CA = "Centroavante"
    SA = "Segundo Atacante"


# ── Pé preferido ──────────────────────────────────────────────

class PePreferido(Enum):
    DIREITO = "Direito"
    ESQUERDO = "Esquerdo"
    AMBIDESTRO = "Ambidestro"


# ── Status / moral ────────────────────────────────────────────

class StatusMoral(Enum):
    EXCELENTE = "Excelente"
    BOM = "Bom"
    NORMAL = "Normal"
    RUIM = "Ruim"
    PESSIMO = "Péssimo"


class StatusLesao(Enum):
    SAUDAVEL = "Saudável"
    LEVE = "Lesão Leve"
    MEDIA = "Lesão Média"
    GRAVE = "Lesão Grave"


# ── Contrato ──────────────────────────────────────────────────

class TipoContrato(Enum):
    PROFISSIONAL = "Profissional"
    EMPRESTIMO = "Empréstimo"
    JUVENIL = "Juvenil"


# ── Treinamento ───────────────────────────────────────────────

class NivelTreinamento(Enum):
    LEVE = "Leve"
    NORMAL = "Normal"
    INTENSO = "Intenso"
    MUITO_INTENSO = "Muito Intenso"


# ── Tática ────────────────────────────────────────────────────

class FormacaoTatica(Enum):
    # ── Clássicas ──
    F442 = "4-4-2"
    F433 = "4-3-3"
    F451 = "4-5-1"
    F352 = "3-5-2"
    F343 = "3-4-3"
    F4231 = "4-2-3-1"
    F4141 = "4-1-4-1"
    F532 = "5-3-2"
    F4321 = "4-3-2-1"
    F4222 = "4-2-2-2"
    # ── Modernas ──
    F4132 = "4-1-3-2"
    F4411 = "4-4-1-1"
    F4312 = "4-3-1-2"
    F3412 = "3-4-1-2"
    F3421 = "3-4-2-1"
    F541 = "5-4-1"
    F5212 = "5-2-1-2"
    F4213 = "4-2-1-3"
    F4240 = "4-2-4-0"
    F3241 = "3-2-4-1"
    F3511 = "3-5-1-1"
    F4123 = "4-1-2-3"
    # ── Variantes Atacantes ──
    F4330 = "4-3-3 (Falso 9)"
    F433D = "4-3-3 (Defensivo)"
    F4231A = "4-2-3-1 (Ataque Largo)"
    F442D = "4-4-2 (Diamante)"
    # ── Ultra-Ofensivas/Defensivas ──
    F3331 = "3-3-3-1"
    F424 = "4-2-4"
    F631 = "6-3-1"
    F5311 = "5-3-1-1"
    F4150 = "4-1-5-0"
    F3142 = "3-1-4-2"


# ── Roles Táticos (FM-style) ─────────────────────────────────

class TacticalDuty(Enum):
    DEFEND = "Defender"
    SUPPORT = "Apoiar"
    ATTACK = "Atacar"


class TacticalRole(Enum):
    """60+ roles táticos com nome PT-BR e posições compatíveis."""
    # ── Goleiro ──
    GOLEIRO = "Goleiro"
    GOLEIRO_LIBERO = "Goleiro-Líbero"
    # ── Zagueiros ──
    ZAGUEIRO_CENTRAL = "Zagueiro Central"
    BEQUE_JOGADOR = "Beque-Jogador"
    LIBERO = "Líbero"
    ZAGUEIRO_COBERTURA = "Zagueiro Cobertura"
    # ── Laterais / Alas ──
    LATERAL_DEFENSIVO = "Lateral Defensivo"
    LATERAL_OFENSIVO = "Lateral Ofensivo"
    ALA = "Ala"
    ALA_INVERTIDO = "Ala Invertido"
    ALA_COMPLETO = "Ala Completo"
    # ── Volantes ──
    VOLANTE = "Volante"
    VOLANTE_DEFENSOR = "Volante Destruidor"
    MEIO_CAMPO_DEFENSIVO = "Meio-Campo Defensivo"
    REGISTA_ROLE = "Regista"
    ANCORA = "Âncora"
    HALF_BACK = "Half-Back"
    # ── Meias ──
    MEIA_CENTRAL = "Meia Central"
    MEIA_OFENSIVO = "Meia Ofensivo"
    MEIA_ATACANTE = "Meia-Atacante"
    BOX_TO_BOX_ROLE = "Box-to-Box"
    CARRILERO = "Carrilero"
    MEZZALA = "Mezzala"
    ORGANIZADOR = "Organizador"
    # ── Pontas / Extremos ──
    PONTA = "Ponta"
    PONTA_INVERTIDO = "Ponta Invertido"
    MEIA_PONTA = "Meia-Ponta"
    PONTA_POR_DENTRO = "Ponta por Dentro"
    # ── Atacantes ──
    CENTROAVANTE = "Centroavante"
    FALSO_9 = "Falso 9"
    ATACANTE_AVANCADO = "Atacante Avançado"
    ATACANTE_COMPLETO = "Atacante Completo"
    POACHER = "Matador de Área"
    TARGET_MAN = "Pivô"
    TREQUARTISTA = "Trequartista"
    SEGUNDA_REFERENCIA = "Segundo Atacante"
    PONTA_DE_LANCA = "Ponta-de-Lança"
    RAUMDEUTER = "Raumdeuter"
    ENGANCHE = "Enganche"
    # ── Especiais ──
    SHADOW_STRIKER = "Atacante Sombra"
    WIDE_TARGET = "Pivô Aberto"
    PRESSING_FORWARD = "Atacante Pressionador"
    INVERTED_FORWARD = "Atacante Invertido"
    WING_BACK_ROLE = "Wing-Back"
    SWEEPER_KEEPER = "Goleiro Varredura"


class EstiloJogo(Enum):
    MUITO_DEFENSIVO = "Muito Defensivo"
    DEFENSIVO = "Defensivo"
    EQUILIBRADO = "Equilibrado"
    OFENSIVO = "Ofensivo"
    MUITO_OFENSIVO = "Muito Ofensivo"


class VelocidadeJogo(Enum):
    LENTO = "Lento"
    NORMAL = "Normal"
    RAPIDO = "Rápido"


class MarcacaoPressao(Enum):
    RECUADA = "Recuada"
    NORMAL = "Normal"
    ALTA = "Pressão Alta"


# ── Staff ─────────────────────────────────────────────────────

class TipoStaff(Enum):
    TREINADOR = "Treinador"
    AUXILIAR = "Auxiliar Técnico"
    PREPARADOR = "Preparador Físico"
    TREINADOR_GOL = "Treinador de Goleiros"
    SCOUT = "Olheiro"
    MEDICO = "Médico"
    DIRETOR = "Diretor de Futebol"


# ── Notícias ──────────────────────────────────────────────────

class CategoriaNoticia(Enum):
    TRANSFERENCIA = "transferencia"
    RESULTADO = "resultado"
    LESAO = "lesao"
    GERAL = "geral"
    FINANCAS = "financas"
    FANTASY = "fantasy"


# ══════════════════════════════════════════════════════════════
#  NOVOS — traits, estilo de jogo individual, status de oferta
# ══════════════════════════════════════════════════════════════

class TraitJogador(Enum):
    """Características especiais que afetam a simulação (30+)."""
    # ── Ofensivos ──
    CLUTCH = "Decisivo"               # melhor em momentos-chave
    ARTILHEIRO = "Artilheiro"         # bônus finalização
    ASSISTENTE = "Garçom"             # bônus passes decisivos
    DRIBLE_MAGICO = "Drible Mágico"   # bônus drible
    CAMISA_10 = "Camisa 10"           # bônus criatividade
    RAINHA = "Rainha"                 # bom no jogo aéreo
    VELOCISTA = "Velocista"           # bônus velocidade em contra-ataque
    FINALIZADOR_FRIO = "Sangue Frio"  # alta conversão em 1v1 com goleiro
    VOLEIO = "Voleio"                 # bônus em finalizações acrobáticas
    CHUTE_LONGE = "Canhão"            # bônus chute de longa distância
    OPORTUNISTA = "Oportunista"       # bônus em rebotes e sobras
    DRIBLADOR_SERIAL = "Finta"        # mantém posse ao driblar sob pressão
    # ── Criativos / Meio ──
    LANCA_BOLA = "Lançador"           # bônus passe longo / lançamento
    REGISTA = "Regista"               # dita o ritmo do jogo (passes + visão)
    BOX_TO_BOX = "Box-to-Box"         # contribui ataque e defesa (±stamina)
    MEIA_PAREDE = "Parede"            # bônus em trocas curtas rápidas
    # ── Defensivos ──
    MURALHA = "Muralha"               # bônus defesa
    CARRASCO = "Carrasco"             # desarmes fortes, risco de falta
    LEITURA_JOGO = "Leitura de Jogo"  # antecipação + interceptação
    ZAGUEIRO_LIDER = "Líder de Zaga"  # organiza linha defensiva
    # ── Goleiro ──
    PEGADOR_PENALTI = "Pegador"       # bônus em pênaltis (goleiro)
    GOLEIRO_LINHA = "Goleiro-Líbero"  # sai bem da área, joga com pés
    MILAGREIRO = "Milagreiro"         # defesas impossíveis esporádicas
    # ── Mentais / Personalidade ──
    LIDERANCA_NATO = "Líder Nato"     # bônus moral para colegas
    MOTOR = "Motor"                   # recupera condição mais rápido
    PROFISSIONAL = "Profissional"     # nunca perde moral por bench
    JOGADOR_GRANDE_JOGO = "Big Game"  # melhor em jogos decisivos/finais
    MENTALMENTE_FORTE = "Mentalidade" # resiste a pressão (compostura+)
    PROVOCADOR = "Provocador"         # irrita adversários, risco cartão
    # ── Negativos ──
    PANELEIRO = "Paneleiro"           # moral baixa contamina elenco
    VIDRACEIRO = "Vidraça"            # lesiona com facilidade
    INCONSISTENTE = "Irregular"       # notas oscilam muito
    LENTO_ADAPTACAO = "Difícil Adaptação"  # demora a se adaptar a novos times


class StatusOferta(Enum):
    PENDENTE = "pendente"
    ACEITA = "aceita"
    RECUSADA = "recusada"
    CANCELADA = "cancelada"


class TipoOferta(Enum):
    COMPRA = "compra"
    EMPRESTIMO = "emprestimo"
    TROCA = "troca"


# ── Licenciamento ─────────────────────────────────────────────

class StatusLicenca(Enum):
    """Status de licenciamento de uma liga, clube ou competição."""
    OFICIAL = "oficial"              # Totalmente licenciado
    LICENCIADO = "licenciado"        # Licenciado por terceiro
    GENERICO = "generico"            # Usa nomes/assets genéricos
    PLACEHOLDER = "placeholder"      # Placeholder premium automático
    MOD_USUARIO = "mod_usuario"      # Conteúdo instalado por mod
    BLOQUEADO = "bloqueado"          # Bloqueado para build comercial


class TipoConteudoLicenciado(Enum):
    """Tipo de conteúdo que requer licenciamento."""
    LIGA = "liga"
    CLUBE = "clube"
    COMPETICAO = "competicao"
    JOGADOR_IMAGEM = "jogador_imagem"
    ESTADIO_IMAGEM = "estadio_imagem"
    PATROCINADOR = "patrocinador"
    TROFEU = "trofeu"
    UNIFORME = "uniforme"


class RegiaoLicenca(Enum):
    """Região geográfica do conteúdo."""
    BRASIL = "brasil"
    AMERICA_SUL = "america_sul"
    EUROPA = "europa"
    AMERICA_NORTE = "america_norte"
    ASIA = "asia"
    AFRICA = "africa"
    OCEANIA = "oceania"
    GLOBAL = "global"


# ── Central de Notificações / Inbox ───────────────────────────

class TipoRemetente(Enum):
    """Quem envia a mensagem ao técnico."""
    DIRETORIA = "diretoria"
    JOGADOR = "jogador"
    CAPITAO = "capitao"
    STAFF = "staff"
    DEPARTAMENTO_MEDICO = "departamento_medico"
    SCOUT = "scout"
    AGENTE = "agente"
    IMPRENSA = "imprensa"
    TORCIDA = "torcida"
    FEDERACAO = "federacao"
    SISTEMA = "sistema"


class PrioridadeMensagem(Enum):
    """Prioridade da mensagem na inbox."""
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class CategoriaMensagem(Enum):
    """Categoria temática da mensagem."""
    COBRANCA_DIRETORIA = "cobranca_diretoria"
    RISCO_DEMISSAO = "risco_demissao"
    ULTIMATO = "ultimato"
    ELOGIO = "elogio"
    OBJETIVO_TEMPORADA = "objetivo_temporada"
    JOGADOR_RECLAMACAO = "jogador_reclamacao"
    JOGADOR_RENOVACAO = "jogador_renovacao"
    JOGADOR_AUMENTO = "jogador_aumento"
    JOGADOR_TRANSFERENCIA = "jogador_transferencia"
    PROMESSA_NAO_CUMPRIDA = "promessa_nao_cumprida"
    RECOMENDACAO_SCOUT = "recomendacao_scout"
    AVISO_MEDICO = "aviso_medico"
    SUSPENSAO = "suspensao"
    RETORNO_LESAO = "retorno_lesao"
    PROPOSTA_OUTRO_CLUBE = "proposta_outro_clube"
    DEMISSAO_OUTRO_TECNICO = "demissao_outro_tecnico"
    VAGA_EMPREGO = "vaga_emprego"
    NOTICIA_TEMPORADA = "noticia_temporada"
    ENTREVISTA = "entrevista"
    RESULTADO_FINANCEIRO = "resultado_financeiro"
    COBRANCA_TORCIDA = "cobranca_torcida"
    PREMIACAO = "premiacao"
    ALERTA_CALENDARIO = "alerta_calendario"
    PRE_JOGO = "pre_jogo"
    POS_JOGO = "pos_jogo"
    CONFLITO_ELENCO = "conflito_elenco"
    MERCADO_OPORTUNIDADE = "mercado_oportunidade"
    STAFF_RECOMENDACAO = "staff_recomendacao"


class StatusMensagem(Enum):
    """Estado da mensagem."""
    NAO_LIDA = "nao_lida"
    LIDA = "lida"
    RESPONDIDA = "respondida"
    ARQUIVADA = "arquivada"
    EXPIRADA = "expirada"


class TipoAcaoMensagem(Enum):
    """Ações possíveis a partir de uma mensagem."""
    RESPONDER = "responder"
    ACEITAR = "aceitar"
    RECUSAR = "recusar"
    ADIAR = "adiar"
    NEGOCIAR = "negociar"
    PROMETER = "prometer"
    ARQUIVAR = "arquivar"
    ABRIR_TELA = "abrir_tela"


# ── Clima ─────────────────────────────────────────────────────

class ClimaPartida(Enum):
    SOL = "Ensolarado"
    NUBLADO = "Nublado"
    CHUVA = "Chuva"
    CHUVA_FORTE = "Chuva Forte"
    NEVE = "Neve"
    CALOR_EXTREMO = "Calor Extremo"


# ── Achievements ──────────────────────────────────────────────

class CategoriaConquista(Enum):
    TITULO = "titulo"
    CARREIRA = "carreira"
    PARTIDA = "partida"
    FINANCEIRO = "financeiro"
    JOGADOR = "jogador"
    ESPECIAL = "especial"


# ── Premiações ────────────────────────────────────────────────

class TipoPremio(Enum):
    BOLA_OURO = "Bola de Ouro"
    ARTILHEIRO = "Artilheiro"
    REVELACAO = "Revelação"
    MELHOR_GOLEIRO = "Melhor Goleiro"
    MELHOR_TECNICO = "Melhor Técnico"
    CRAQUE_CAMPEONATO = "Craque do Campeonato"
    SELECAO_CAMPEONATO = "Seleção do Campeonato"


# ── Coletiva ──────────────────────────────────────────────────

class TipoColetiva(Enum):
    PRE_JOGO = "pre_jogo"
    POS_JOGO = "pos_jogo"
    SEMANAL = "semanal"
    EMERGENCIAL = "emergencial"


class TomResposta(Enum):
    CONFIANTE = "confiante"
    HUMILDE = "humilde"
    AGRESSIVO = "agressivo"
    DIPLOMATICO = "diplomatico"
    EVASIVO = "evasivo"


# ── Estádio Upgrade ──────────────────────────────────────────

class TipoUpgradeEstadio(Enum):
    CAPACIDADE = "capacidade"
    GRAMADO = "gramado"
    ILUMINACAO = "iluminacao"
    VESTIARIO = "vestiario"
    CAMAROTES = "camarotes"
    COBERTURA = "cobertura"
    CENTRO_TREINAMENTO = "centro_treinamento"


# ── Promessas ─────────────────────────────────────────────────

class TipoPromessa(Enum):
    TITULAR = "titular"
    RENOVAR = "renovar"
    COMPRAR_REFORCO = "comprar_reforco"
    VENDER_JOGADOR = "vender_jogador"
    AUMENTO_SALARIAL = "aumento_salarial"
    NAO_VENDER = "nao_vender"
    TITULO = "titulo"
    MELHORAR_ELENCO = "melhorar_elenco"


class StatusPromessa(Enum):
    ATIVA = "ativa"
    CUMPRIDA = "cumprida"
    QUEBRADA = "quebrada"
    EXPIRADA = "expirada"


# ── Vestiário / Dinâmica de Grupo ─────────────────────────────

class StatusVestiario(Enum):
    HARMONIOSO = "harmonioso"
    ESTAVEL = "estavel"
    TENSO = "tenso"
    CONFLITUOSO = "conflituoso"
    TOXICO = "toxico"


class TipoEvtVestiario(Enum):
    CONFLITO = "conflito"
    UNIAO = "uniao"
    LIDERANCA = "lideranca"
    PANELINHA = "panelinha"
    CELEBRACAO = "celebracao"
    CRITICA = "critica"


# ── Entrosamento / Química Tática ─────────────────────────────

class NivelEntrosamento(Enum):
    NENHUM = "nenhum"
    BAIXO = "baixo"
    MEDIO = "medio"
    ALTO = "alto"
    PERFEITO = "perfeito"


# ── Identidade do Clube ───────────────────────────────────────

class EstiloClube(Enum):
    OFENSIVO = "ofensivo"
    DEFENSIVO = "defensivo"
    POSSE_DE_BOLA = "posse_de_bola"
    CONTRA_ATAQUE = "contra_ataque"
    JOGO_DIRETO = "jogo_direto"
    BASE_FORTE = "base_forte"
    COMPRADOR = "comprador"


# ── Perfil de Agente ──────────────────────────────────────────

class TipoAgente(Enum):
    AMIGAVEL = "amigavel"
    AGRESSIVO = "agressivo"
    LEGALISTA = "legalista"
    SUPERAGENTE = "superagente"
    OPORTUNISTA = "oportunista"


# ── Adaptação Cultural ───────────────────────────────────────

class NivelAdaptacao(Enum):
    INADAPTADO = "inadaptado"
    EM_ADAPTACAO = "em_adaptacao"
    ADAPTADO = "adaptado"
    TOTALMENTE_ADAPTADO = "totalmente_adaptado"
