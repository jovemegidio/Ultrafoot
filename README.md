<p align="center">
  <img src="Logo%20-%20UF26%20III.png" alt="Ultrafoot 26" width="180">
</p>

<h1 align="center">Ultrafoot 26</h1>
<p align="center">
  <strong>Ultimate Football Manager Experience</strong><br>
  <em>Jogo completo de gerenciamento de futebol — desktop, offline, 100% gratuito</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white" alt="Python 3.13">
  <img src="https://img.shields.io/badge/Frontend-HTML/CSS/JS-orange?logo=html5&logoColor=white" alt="Frontend">
  <img src="https://img.shields.io/badge/3D_Engine-Three.js_r128-black?logo=threedotjs&logoColor=white" alt="Three.js">
  <img src="https://img.shields.io/badge/Desktop-pywebview-green?logo=windows&logoColor=white" alt="pywebview">
  <img src="https://img.shields.io/badge/License-Proprietary-red" alt="License">
</p>

---

## Sobre o Projeto

O **Ultrafoot 26** é um jogo de gerenciamento de futebol (Football Manager) desenvolvido inteiramente por **um único desenvolvedor**. O projeto demonstra competência em:

- **Arquitetura full-stack** — Backend Python + Frontend SPA em HTML/JS
- **Motor de partidas** com 30+ fatores de simulação, sistema tático completo e visualização 3D WebGL
- **Engenharia de sistemas** — 15+ engines independentes orquestrados (transferências, finanças, FFP, treinamento, IA, scouting, etc.)
- **Persistência offline** — Save system com integridade HMAC, backup automático e validação
- **Experiência desktop nativa** — PyInstaller + pywebview EdgeChromium, splash screen, resolução dinâmica

> 🎮 **40+ ligas nacionais** · **2000+ clubes reais** · **27 campeonatos estaduais brasileiros** · **Motor 3D WebGL**

---

## Stack Técnica

| Camada | Tecnologia | Detalhes |
|--------|-----------|----------|
| **Backend** | Python 3.13 | API síncrona exposta via pywebview bridge |
| **Frontend** | HTML5 / CSS3 / JavaScript | SPA monolítica (~12.500 linhas), Canvas 2D, SVG |
| **Motor 3D** | Three.js r128 | WebGL com PCFSoftShadowMap, ACES Filmic, 6 luzes, câmeras dinâmicas |
| **Desktop** | pywebview 5.x (EdgeChromium) | Janela nativa Windows, bridge Python ↔ JS |
| **Bundling** | PyInstaller 6.19 | Executável standalone ~5.2 MB + assets |
| **Serialização** | orjson | JSON de alta performance para saves e API |
| **Imagens** | Pillow 10.x | Geração dinâmica de avatares (Newgen) |
| **Discord** | pypresence 4.3 | Rich Presence integrado |
| **Instalador** | Inno Setup 6 | Instalador Windows profissional |

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    Desktop App (pywebview)                │
│  ┌──────────────┐    ┌─────────────────────────────────┐ │
│  │  Frontend SPA │◄──►│        Python Backend           │ │
│  │  (index.html) │    │                                 │ │
│  │               │    │  ┌─── GameManager ───────────┐  │ │
│  │  • Dashboard  │    │  │  • Match Engine            │  │ │
│  │  • Táticas    │    │  │  • Transfer Engine         │  │ │
│  │  • Mercado    │    │  │  • Finance Engine          │  │ │
│  │  • Match 3D   │    │  │  • Training Engine         │  │ │
│  │  • Stats/Gfx  │    │  │  • Scout Service           │  │ │
│  │               │    │  │  • AI Service              │  │ │
│  │  Three.js ◄───┼────┼──┤  • FFP Engine              │  │ │
│  │  Canvas 2D    │    │  │  • Inbox Engine            │  │ │
│  │  SVG Charts   │    │  │  • License Service         │  │ │
│  └──────────────┘    │  │  • 15+ more engines...      │  │ │
│                       │  └────────────────────────────┘  │ │
│                       │  ┌─── Persistence ────────────┐  │ │
│                       │  │  JSON saves + HMAC integrity│  │ │
│                       │  │  Auto-backup system         │  │ │
│                       │  └────────────────────────────┘  │ │
│                       └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Funcionalidades Principais

### ⚽ Motor de Partidas
- Simulação minuto a minuto com 30+ variáveis (forma, moral, fadiga, química, altitude, clima)
- **Visualização 3D WebGL** com estádio, luzes, jogadores, bola com glow e trilhas de passe
- 5 câmeras: Broadcast, Tática, Lateral, Goleiro, Diretor (rodízio automático)
- xG (Expected Goals), momentum, mapas de passe em tempo real
- Gráficos pós-jogo com Canvas 2D

### 📋 Sistema Tático
- Formações personalizáveis com drag & drop
- Instruções individuais por jogador
- Estilos de jogo (posse, contra-ataque, pressão alta)
- 7 variáveis táticas: velocidade, marcação, linha de defesa, intensidade

### 💰 Gestão Financeira
- Folha salarial mensal/anual com projeções
- Receitas: bilheteria, TV, patrocínio, merchandising
- **Fair Play Financeiro (FFP)** com compliance real
- Renda proporcional à divisão e prestígio

### 🔍 Scouting & Transferências
- Rede de olheiros com 40+ países
- Busca avançada com filtros (posição, idade, força, valor)
- Negociação de contratos (salário, cláusula, duração)
- **Deadline Day** com pressão e ofertas de última hora
- Mercado de jogadores livres

### 🏟️ Sistemas Avançados (exclusivos)
| Sistema | Descrição |
|---------|-----------|
| **Promise Engine** | Sistema de promessas do elenco com consequências |
| **Locker Room Engine** | Dinâmica de vestiário e moral coletiva |
| **Tactical Chemistry** | Entrosamento entre jogadores baseado em partidas |
| **Cultural Adaptation** | Jogadores estrangeiros se adaptam culturalmente |
| **Coach Career** | Carreira do técnico com demissão e ofertas |
| **Club Identity** | Identidade visual dinâmica (cores do time na UI) |
| **Agent Profile** | Agentes com personalidades que afetam negociações |
| **Player Objectives** | Metas pessoais dos jogadores |
| **Deadline Day** | Simulação completa do último dia da janela |
| **Staff Meeting** | Reuniões de comissão técnica |
| **Newgen Avatar** | Geração procedural de fotos (Pillow) |
| **Post-Match Analysis** | Análise detalhada pós-jogo com gráficos |
| **Fantasy Manager** | Liga Fantasy integrada com pontuação |
| **Press Conference** | Coletivas de imprensa com impacto na moral |
| **Hall of Fame** | Hall da Fama, recordes, conquistas, premiações |

### 🌍 Conteúdo
- **40+ ligas nacionais**: Brasil (Séries A–D), Inglaterra, Espanha, Itália, Alemanha, França, Portugal, Argentina, etc.
- **27 campeonatos estaduais** brasileiros (AC a TO)
- **Competições internacionais**: Champions League, Europa League, Libertadores, Sul-Americana, Copa do Brasil
- **2000+ clubes** com escudos, camisas e dados reais
- **Seleções nacionais** com convocações

---

## Estrutura do Código

```
├── desktop_app.py          # API bridge (pywebview → Python) — 3800+ lines
├── server.py               # Servidor HTTP alternativo (modo standalone)
├── config.py               # Constantes globais, paths, versão
├── index.html              # Frontend SPA completo — 12500+ lines
├── build_exe.py            # Script de build PyInstaller automatizado
├── core/
│   ├── models.py           # Modelos de domínio (Jogador, Time, Partida, etc.)
│   ├── enums.py            # Enumerações (Posição, Formação, etc.)
│   ├── constants.py        # Constantes do jogo
│   └── exceptions.py       # Exceções customizadas
├── engine/
│   ├── match_engine.py     # Motor de simulação de partidas
│   ├── transfer_engine.py  # Motor de transferências e negociações
│   ├── training_engine.py  # Motor de treinamento e evolução
│   └── ...                 # 10+ engines especializados
├── managers/
│   ├── game_manager.py     # Orquestrador principal — 1700+ lines
│   └── competition_manager.py  # Calendário e tabelas
├── services/
│   ├── license_service.py  # Ativação offline com HMAC
│   ├── scout_service.py    # Rede de olheiros
│   ├── ai_service.py       # IA dos times adversários
│   ├── ffp_engine.py       # Fair Play Financeiro
│   ├── inbox_engine.py     # Sistema de mensagens in-game
│   ├── music_manager.py    # Player de música integrado
│   ├── discord_rpc.py      # Discord Rich Presence
│   └── ...                 # 8+ serviços
├── save_system/            # Persistência JSON + integridade HMAC
├── fantasy/                # Fantasy League engine
├── utils/                  # Logging, helpers
├── data/seeds/             # Dados estáticos (ligas, times, jogadores)
├── teams/                  # Escudos e camisas (PNG)
├── sons/                   # Efeitos sonoros (WAV)
├── music/                  # Trilha sonora
├── trofeus/                # Ícones de troféus
├── selecoes/               # Dados de seleções
├── conf_estadual/          # Configurações dos 27 estaduais
├── conf_ligas_nacionais/   # Configurações das 40+ ligas
└── web/
    └── landing/            # Landing page do jogo
```

---

## Destaques Técnicos

### Motor 3D (Three.js)
```javascript
// Estádio completo com iluminação de 6 pontos
_init() {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    // 4 spotlights simulando floodlights + ambient + directional + fill
}

// 5 câmeras com transição suave
setCameraView(view) {
    // broadcast | tactical | sideline | behind-goal | director
}
```

### Motor de Partida (Python)
```python
# 30+ fatores de simulação por minuto
def simular_minuto(self, minuto: int) -> List[Evento]:
    fator_casa = self._calcular_vantagem_casa()
    moral = self._moral_coletiva(time)
    fadiga = self._calcular_fadiga(jogador, minuto)
    quimica = self._quimica_tatica(time)
    # xG, momentum, clima, altitude, lesões...
```

### Integridade de Saves
```python
# HMAC-SHA256 para proteção contra adulteração
def _compute_hmac(self, state: Dict) -> str:
    payload = "|".join(f"{k}={state[k]}" for k in sorted(state))
    return hmac.new(_HMAC_KEY, payload.encode(), hashlib.sha256).hexdigest()
```

---

## Como Executar (Desenvolvimento)

```bash
# 1. Clonar o repositório
git clone https://github.com/jovemegidio/Ultrafoot.git
cd Ultrafoot

# 2. Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate        # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Executar em modo desenvolvimento
python desktop_app.py

# 5. Build do executável
python build_exe.py
```

---

## Screenshots

<p align="center">
  <em>Dashboard do jogo com tema dinâmico baseado nas cores do clube</em>
</p>

---

## Métricas do Projeto

| Métrica | Valor |
|---------|-------|
| Linhas de código (Python) | ~25.000+ |
| Linhas de código (HTML/JS/CSS) | ~12.500+ |
| Engines independentes | 15+ |
| Ligas jogáveis | 40+ |
| Clubes com dados reais | 2.000+ |
| Estaduais brasileiros | 27 |
| Variáveis de simulação | 30+ |
| Tempo de desenvolvimento | Solo dev |

---

## Autor

**Egídio** — [@jovemegidio](https://github.com/jovemegidio)

Desenvolvido inteiramente por um único programador como projeto de portfólio, demonstrando:
- Arquitetura de software em larga escala
- Gerenciamento de estado complexo
- Engines de simulação com múltiplas variáveis
- UI/UX moderna com 3D WebGL
- Build automation e distribuição desktop

---

<p align="center">
  <img src="Logo%20-%20UF26%20III.png" alt="Ultrafoot 26" width="80"><br>
  <strong>Ultrafoot 26</strong> — Ultimate Football Manager Experience<br>
  <em>© 2026 Egídio. Todos os direitos reservados.</em>
</p>
