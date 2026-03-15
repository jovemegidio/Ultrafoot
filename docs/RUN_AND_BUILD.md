# Ultrafoot - execucao e build

## Como iniciar o jogo

Desenvolvimento:

```powershell
.\.venv\Scripts\python.exe .\desktop_app.py
```

Executavel ja gerado:

```powershell
.\release_build\Ultrafoot\Ultrafoot.exe
```

## Modelo de dados offline

- O jogo base nao precisa de banco externo.
- Os dados principais vem de `data/seeds/*.json`.
- Ajustes curados de estadio/patrocinio ficam em `data/seeds/team_metadata_overrides.json`.
- Os saves ficam em `saves/`.
- Cada save agora usa checksum local, metadata e backups rotativos em `saves/_backups/`.
- O arquivo `brasfoot.db` nao e requisito do fluxo principal.

## Musica offline e streamer-safe

- As faixas podem continuar em `music/`.
- O player so aparece com carreira/save ativo e entra em autoplay ao iniciar ou carregar a carreira.
- Opcionalmente, o jogo tambem aceita manifesto em `data/assets/music/manifest.json` ou `music/manifest.json`.
- O manifesto suporta metadados como `titulo`, `artista`, `contextos`, `streamer_safe` e `licenca`.
- Sem manifesto, o jogo faz fallback para scan local e toca apenas em contexto de menu/general.

## Licenca offline e builds comerciais

- O status local da licenca fica em `license_status.json` ao lado do executavel.
- O modo atual suporta `demo`, `trial` offline e ativacao por serial local.
- O bridge desktop expoe `get_license_status` e `activate_license` para a UI.

## Auditoria de assets

- A tela de licensing agora agrega o registro de assets empacotados.
- O registry verifica escudos, camisas, trilhas, mapeamentos quebrados e faltas criticas de compliance.
- O objetivo e permitir build comercial estrito com fallback visual quando um asset licenciado estiver ausente.

## Build do executavel

Sincronizar branding e gerar build:

```powershell
.\.venv\Scripts\python.exe .\scripts\sync_branding_assets.py
.\.venv\Scripts\python.exe .\build_exe.py
```

## Instalador Windows

1. Gere o executavel com `build_exe.py`.
2. Abra `build/installer/Ultrafoot.iss` no Inno Setup.
3. Compile o instalador.

O executavel, o instalador e os atalhos usam o icone derivado de `Icone.png`.
