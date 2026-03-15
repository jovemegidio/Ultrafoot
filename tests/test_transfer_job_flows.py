# -*- coding: utf-8 -*-
"""Smoke de fluxos básicos de mercado e carreira via API desktop."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop_app import BrasfootAPI


def _assert(ok, msg):
    if not ok:
        raise AssertionError(msg)


def main():
    api = BrasfootAPI()
    cfg = {
        "time": "Flamengo",
        "ligas": ["BRA", "ARG", "ING", "ESP"],
        "tecnico_nome": "Flow Tester",
        "temporada_inicio": 2026,
        "competicoes_selecoes": True,
        "tacas_internacionais": True,
    }
    result = json.loads(api.novo_jogo_config(json.dumps(cfg)))
    _assert(result.get("ok"), "novo_jogo_config falhou")

    gm = api._gm
    gm.auto_save_ativo = False

    mercado = json.loads(api.get_mercado())
    _assert(mercado["mercado_aberto"], "mercado deveria iniciar aberto")
    _assert(mercado["livres"], "sem agentes livres")

    livre_id = mercado["livres"][0]["id"]
    livre_res = json.loads(api.contratar_livre(livre_id))
    _assert(livre_res.get("ok"), f"contratar_livre falhou: {livre_res}")

    busca_times = json.loads(api.buscar_mercado(tab="times"))
    compra_ok = False
    for jogador in sorted(busca_times.get("times", []), key=lambda item: item.get("valor", 0))[:12]:
        res = json.loads(api.fazer_oferta(jogador["id"], max(int(jogador.get("valor", 0)), 1)))
        if res.get("ok"):
            compra_ok = True
            break
    _assert(compra_ok, "nenhuma compra foi aceita")

    busca_times = json.loads(api.buscar_mercado(tab="times"))
    emprestimo_ok = False
    for jogador in sorted(busca_times.get("times", []), key=lambda item: item.get("overall", 0), reverse=True)[:12]:
        res = json.loads(api.fazer_oferta_emprestimo(jogador["id"]))
        if res.get("ok"):
            emprestimo_ok = True
            break
    _assert(emprestimo_ok, "nenhum empréstimo foi aceito")

    demissao = json.loads(api.pedir_demissao())
    _assert(demissao.get("ok"), "pedir_demissao falhou")
    ofertas = demissao.get("ofertas", [])
    tentativas = 0
    while not ofertas and tentativas < 8:
        gm.avancar_semana()
        ofertas = list(gm._ofertas_emprego)
        tentativas += 1
    _assert(ofertas, "nenhuma oferta apareceu após a demissão")

    aceita = json.loads(api.aceitar_oferta_tecnico(ofertas[0]["nome"]))
    _assert(aceita.get("ok"), f"aceitar_oferta_tecnico falhou: {aceita}")
    _assert(gm.time_jogador is not None, "time do jogador não foi reassumido")

    print("[OK] test_transfer_job_flows PASSED")


if __name__ == "__main__":
    main()
