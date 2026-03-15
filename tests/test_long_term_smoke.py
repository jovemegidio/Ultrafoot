import json
import sys
import time
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
        "ligas": ["BRA", "ARG", "BOL", "VEN", "COL", "ING", "ESP", "ITA", "FRA"],
        "tecnico_nome": "Smoke Tester",
        "temporada_inicio": 2026,
        "competicoes_selecoes": True,
        "tacas_internacionais": True,
    }
    result = json.loads(api.novo_jogo_config(json.dumps(cfg)))
    _assert(result.get("ok"), "novo_jogo_config falhou")

    # Ligas internacionais basicas
    info = json.loads(api.get_european_leagues_info())
    keys = {item["key"] for item in info["ligas"]}
    _assert("liga_ARG_1" in keys, "Argentina div 1 ausente")
    _assert("liga_BOL_1" in keys, "Bolivia div 1 ausente")
    _assert("liga_VEN_1" in keys, "Venezuela div 1 ausente")
    _assert("liga_ING_1" in keys, "Inglaterra div 1 ausente")

    # Agente livre
    mercado = json.loads(api.get_mercado())
    _assert(mercado["livres"], "sem agentes livres")
    livre_id = mercado["livres"][0]["id"]
    livre_res = json.loads(api.contratar_livre(livre_id))
    _assert(livre_res.get("ok"), f"contratar_livre falhou: {livre_res}")

    # Compra de jogador
    busca_times = json.loads(api.buscar_mercado(tab="times"))
    compra_ok = False
    for jogador in sorted(busca_times.get("times", []), key=lambda item: item.get("valor", 0))[:12]:
        res = json.loads(api.fazer_oferta(jogador["id"], max(int(jogador.get("valor", 0)), 1)))
        if res.get("ok"):
            compra_ok = True
            break
    _assert(compra_ok, "nenhuma compra de jogador foi aceita no smoke")

    # Emprestimo
    busca_times = json.loads(api.buscar_mercado(tab="times"))
    emprestimo_ok = False
    for jogador in sorted(busca_times.get("times", []), key=lambda item: item.get("overall", 0), reverse=True)[:12]:
        res = json.loads(api.fazer_oferta_emprestimo(jogador["id"]))
        if res.get("ok"):
            emprestimo_ok = True
            break
    _assert(emprestimo_ok, "nenhum emprestimo foi aceito no smoke")

    # Demissao e novo clube
    demissao = json.loads(api.pedir_demissao())
    _assert(demissao.get("ok"), "pedir_demissao falhou")
    ofertas = demissao.get("ofertas", [])
    tentativas = 0
    while not ofertas and tentativas < 8:
        api._gm.avancar_semana()
        ofertas = list(api._gm._ofertas_emprego)
        tentativas += 1
    _assert(ofertas, "nenhuma oferta de tecnico apareceu apos demissao")
    aceita = json.loads(api.aceitar_oferta_tecnico(ofertas[0]["nome"]))
    _assert(aceita.get("ok"), f"aceitar_oferta_tecnico falhou: {aceita}")

    gm = api._gm
    serie_a_inicial = {t.nome for t in gm.times_serie_a}
    seen_wc = gm.competicoes.copa_mundo is not None
    seen_euro = gm.competicoes.eurocopa is not None
    seen_copa_america = gm.competicoes.copa_america is not None

    t0 = time.time()
    while gm.temporada < 2032:
        gm.avancar_semana()
        seen_wc = seen_wc or (gm.competicoes.copa_mundo is not None)
        seen_euro = seen_euro or (gm.competicoes.eurocopa is not None)
        seen_copa_america = seen_copa_america or (gm.competicoes.copa_america is not None)

        _assert(len(gm.times_serie_a) == 20, "Serie A perdeu integridade")
        _assert(len(gm.times_serie_b) == 20, "Serie B perdeu integridade")
        _assert(len(gm.times_serie_c) == 20, "Serie C perdeu integridade")
        _assert(len(gm.times_serie_d) >= 64, "Serie D ficou pequena demais")

    serie_a_final = {t.nome for t in gm.times_serie_a}
    _assert(seen_wc, "Copa do Mundo nao apareceu ate 2032")
    _assert(seen_euro, "Eurocopa nao apareceu ate 2032")
    _assert(seen_copa_america, "Copa America nao apareceu ate 2032")
    _assert(serie_a_inicial != serie_a_final, "Promocao/rebaixamento nao alterou a Serie A")

    print("[OK] test_long_term_smoke PASSED")
    print("Temporada final:", gm.temporada, "semana:", gm.semana)
    print("Selecoes vistas:", {"wc": seen_wc, "euro": seen_euro, "copa_america": seen_copa_america})
    print("Serie A alterada:", len(serie_a_inicial.symmetric_difference(serie_a_final)))
    print("Tempo total:", round(time.time() - t0, 2), "s")


if __name__ == "__main__":
    main()
