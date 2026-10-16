#!/usr/bin/env python3
"""Gera as configurações das execuções do cenário evento_termico_v2.

Cada execução recebe seus próprios JSONs de dispositivos, gateways e agendamento, a
tabela de fases e o papel de cada sensor. As variações sorteadas (com semente fixa)
atacam os problemas encontrados na v1: carga inicial e consumo diferentes por sensor,
número e posição dos sensores afetados, intensidade do evento, duração das fases,
momento das falhas, perturbações benignas no estado normal e uma execução sem desastre.
"""

import argparse
import csv
import json
import math
import random
import shutil
import uuid
from pathlib import Path

PASTA = Path(__file__).resolve().parent
SCENARIO_ID = "evento_termico_v2"
NAMESPACE = uuid.UUID("6f1c2d0e-7a51-4c4b-9a36-2b8f0e5d3c10")

# Centros dos dois grupos (os mesmos da v1, próximos à coordenada de Uberlândia do manual).
CENTROS = {"gw01": (-18.9186, -48.2772), "gw02": (-18.9246, -48.2732)}
RAIO_GRAUS = 0.005  # cerca de 550 m

# Perfis de atraso da v1 (s); na v2 são multiplicados pela intensidade do sensor.
ATRASO = {
    "normal": [(90, 0.02, 0.12), (10, 0.12, 0.50)],
    "pre_desastre": [(80, 0.10, 0.60), (20, 0.60, 1.50)],
    "desastre": [(75, 0.80, 1.80), (25, 2.00, 4.00)],
    "pos_desastre": [(70, 0.15, 0.60), (30, 0.60, 1.40)],
}


def perfis(fase, escala=1.0):
    return [{"probability": p, "min": round(lo * escala, 3), "max": round(hi * escala, 3)} for p, lo, hi in ATRASO[fase]]


def multiplo(rng, minimo, maximo, passo=30):
    return rng.choice(range(minimo, maximo + 1, passo))


def evento_fase(fase, i, transicao_s):
    """Parâmetros de uma fase para um sensor afetado com intensidade i (1 = valores da v1)."""
    if fase == "pre_desastre":
        temp, drop, idle, tx = (22 + 4 * i, 32 + 8 * i), 8 * i, 0.2 * i, 0.06 * i
    elif fase == "desastre":
        # Descarga em repouso menor que na v1 (8 p.p./min) para que cargas iniciais baixas não se esgotem sem planejamento.
        temp, drop, idle, tx = (26 + 8 * i, 36 + 16 * i), min(60.0, 35 * i), 4 * i, 0.1 * i
    else:
        temp, drop, idle, tx = (20 + 5 * i, 31 + 8 * i), 10 * i, 0.5, 0.04
    return {
        "event_name": fase, "event_type": "permanent",
        "temperature_range": [round(temp[0], 1), round(temp[1], 1)], "pressure_range": [1000.0, 1020.0],
        "battery_transmit_discharge": round(tx, 3), "battery_idle_discharge": round(idle, 3),
        "drop_percentage": round(drop, 1), "delay_profiles": perfis(fase, i),
        "transition_duration_s": transicao_s,
    }


def transitorio(nome, duracao_s, transicao_s=0, retorno_s=0, **campos):
    return {"event_name": nome, "event_type": "transient", "delay_profiles": [], **campos,
            "transition_duration_s": transicao_s, "transient_event_duration_s": duracao_s,
            "transient_event_return_s": retorno_s}


def duracao_evento(evento):
    return sum(evento.get(k, 0) for k in ("transition_duration_s", "transient_event_duration_s", "transient_event_return_s"))


def agendar_benignos(rng, dispositivos, inicio, fim, n_congestionamentos, n_aquecimentos, ocupado):
    """Perturbações benignas: rede congestionada sem calor, ou calor local sem falha de rede. O rótulo continua normal."""
    agenda = []
    pedidos = [("congestionamento_benigno", n_congestionamentos), ("aquecimento_local_benigno", n_aquecimentos)]
    for nome, quantidade in pedidos:
        for _ in range(quantidade):
            for _tentativa in range(50):
                disp = rng.choice(dispositivos)
                if nome == "congestionamento_benigno":
                    evento = transitorio(nome, rng.randint(40, 80), drop_percentage=round(rng.uniform(30, 60), 1),
                                         delay_profiles=[{"probability": 70, "min": 0.3, "max": 1.0},
                                                         {"probability": 30, "min": 1.0, "max": 2.5}])
                else:
                    base = round(rng.uniform(29, 33), 1)
                    evento = transitorio(nome, rng.randint(40, 80), transicao_s=10, retorno_s=10,
                                         temperature_range=[base, round(base + rng.uniform(8, 12), 1)])
                ultimo_inicio = fim - duracao_evento(evento) - 20
                if ultimo_inicio <= inicio + 30:
                    break
                t = rng.randint(inicio + 30, ultimo_inicio)
                janela = (t, t + duracao_evento(evento))
                if all(janela[1] + 10 < a or janela[0] > b + 10 for a, b in ocupado.get(disp, [])):
                    ocupado.setdefault(disp, []).append(janela)
                    agenda.append((t, disp, evento))
                    break
    return agenda


def gerar_execucao(numero, semente, com_desastre, escala_tempo, base_porta):
    rng = random.Random(semente)
    nome = f"execucao_{numero:02d}"

    # Topologia: 4 a 6 sensores por gateway, posições sorteadas em torno de cada centro.
    dispositivos, gateways = {}, {}
    for g_idx, (gw, (lat0, lon0)) in enumerate(CENTROS.items()):
        n = rng.randint(4, 6)
        gateways[gw] = []
        for i in range(1, n + 1):
            disp_id = f"{gw}-d{i:02d}"
            ang, r = rng.uniform(0, 2 * math.pi), RAIO_GRAUS * math.sqrt(rng.random())
            porta = base_porta + 100 * numero + 50 * g_idx + i
            dispositivos[disp_id] = {
                "uuid": str(uuid.uuid5(NAMESPACE, f"{SCENARIO_ID}/{nome}/{disp_id}")),
                "server_host": "127.0.0.1", "server_port": porta, "resource_path": ["device", "data"],
                "coordinate": {"latitude": round(lat0 + r * math.sin(ang), 6), "longitude": round(lon0 + r * math.cos(ang), 6)},
                "battery_charge": round(rng.uniform(60, 100), 2),
                "temperature_range": [round(rng.uniform(19, 21), 1), round(rng.uniform(31, 33), 1)],
                "pressure_range": [1000.0, 1020.0],
                "battery_transmit_discharge": round(0.01 * rng.uniform(0.5, 1.5), 4),
                "battery_idle_discharge": round(0.02 * rng.uniform(0.5, 1.5), 4),
                "drop_percentage": 1.0, "delay_profiles": perfis("normal"),
            }
            gateways[gw].append(disp_id)

    def t(segundos):
        return int(round(segundos * escala_tempo))

    agenda, ocupado = [], {}
    papeis = {d: "controle" for d in dispositivos}
    resumo = {"execucao": nome, "semente": semente, "com_desastre": com_desastre,
              "sensores": len(dispositivos), "sensores_por_gateway": {g: len(v) for g, v in gateways.items()}}

    if not com_desastre:
        fases = [("normal", 0, t(1200), 0)]
        agenda += agendar_benignos(rng, list(dispositivos), 0, t(1200), rng.randint(2, 3), rng.randint(1, 2), ocupado)
        resumo.update(intensidade=None, duracoes_s={"normal": t(1200)})
    else:
        dur = {"normal": t(multiplo(rng, 240, 360)), "pre_desastre": t(multiplo(rng, 210, 330)),
               "desastre": t(multiplo(rng, 240, 360)), "pos_desastre": t(multiplo(rng, 240, 360))}
        trans = {"pre_desastre": int(dur["pre_desastre"] * rng.uniform(0.4, 0.7)),
                 "desastre": t(rng.randint(20, 45)), "pos_desastre": t(rng.randint(60, 150))}
        trans["pos_desastre"] = min(trans["pos_desastre"], dur["pos_desastre"] - t(30))
        fases, inicio = [], 0
        for fase in ("normal", "pre_desastre", "desastre", "pos_desastre"):
            fases.append((fase, inicio, inicio + dur[fase], trans.get(fase, 0)))
            inicio += dur[fase]
        ini = {f: i for f, i, _, _ in fases}
        fim = {f: e for f, _, e, _ in fases}

        # Sensores afetados: os mais próximos de um epicentro sorteado entre os grupos.
        intensidade = round(rng.uniform(0.7, 1.3), 3)
        lat_e = (CENTROS["gw01"][0] + CENTROS["gw02"][0]) / 2 + rng.uniform(-0.006, 0.006)
        lon_e = (CENTROS["gw01"][1] + CENTROS["gw02"][1]) / 2 + rng.uniform(-0.006, 0.006)
        intensidades = {}
        for gw, membros in gateways.items():
            ordem = sorted(membros, key=lambda d: math.dist(
                (dispositivos[d]["coordinate"]["latitude"], dispositivos[d]["coordinate"]["longitude"]), (lat_e, lon_e)))
            afetados = ordem[:rng.randint(2, len(membros) - 1)]
            for d in afetados:
                papeis[d] = "degradacao"
                intensidades[d] = round(intensidade * rng.uniform(0.85, 1.15), 3)
            livres = afetados[:]
            rng.shuffle(livres)
            if rng.random() < 0.5:
                papeis[livres.pop()] = "falha_energetica"
            if rng.random() < 0.6 and livres:
                papeis[livres.pop()] = "falha_rede"
        if not any(p in ("falha_energetica", "falha_rede") for p in papeis.values()):
            papeis[rng.choice(list(intensidades))] = rng.choice(["falha_energetica", "falha_rede"])

        for d, i in intensidades.items():
            agenda.append((ini["pre_desastre"], d, evento_fase("pre_desastre", i, trans["pre_desastre"])))
            agenda.append((ini["desastre"], d, evento_fase("desastre", i, trans["desastre"])))
            if papeis[d] == "falha_energetica":
                momento = ini["desastre"] + t(rng.randint(45, 150))
                agenda.append((momento, d, {"event_name": "falha_energetica_permanente", "event_type": "permanent",
                                            "battery_idle_discharge": 120.0, "delay_profiles": [],
                                            "transition_duration_s": 0}))
            else:
                if papeis[d] == "falha_rede":
                    duracao = t(rng.randint(40, 90))
                    momento = ini["desastre"] + t(rng.randint(45, 90))
                    momento = min(momento, fim["desastre"] - duracao - t(20))
                    agenda.append((momento, d, transitorio("falha_rede_transitoria", duracao, drop_percentage=100.0)))
                agenda.append((ini["pos_desastre"], d, evento_fase("pos_desastre", i, trans["pos_desastre"])))

        agenda += agendar_benignos(rng, list(dispositivos), 0, ini["pre_desastre"],
                                   int(rng.random() < 0.7) * rng.randint(1, 2), int(rng.random() < 0.6), ocupado)
        resumo.update(intensidade=intensidade, duracoes_s=dur, transicoes_s=trans,
                      epicentro={"latitude": round(lat_e, 6), "longitude": round(lon_e, 6)})

    contagem = {p: sum(1 for v in papeis.values() if v == p) for p in ("controle", "degradacao", "falha_energetica", "falha_rede")}
    resumo.update(papeis=contagem, eventos=len(agenda),
                  eventos_benignos=sum(1 for _, _, e in agenda if e["event_name"].endswith("_benigno")),
                  duracao_total_s=fases[-1][2])
    uris = {d: f'coap://127.0.0.1:{c["server_port"]}/device/data' for d, c in dispositivos.items()}
    return nome, dispositivos, gateways, uris, sorted(agenda, key=lambda a: (a[0], a[1])), fases, papeis, resumo


def gravar(destino, nome, dispositivos, gateways, uris, agenda, fases, papeis):
    pasta = destino / nome
    if pasta.exists():
        shutil.rmtree(pasta)
    for sub in ("dispositivos", "gateways", "agendamentos"):
        (pasta / sub).mkdir(parents=True)
    for d, cfg in dispositivos.items():
        (pasta / "dispositivos" / f"{d}.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    for gw, membros in gateways.items():
        (pasta / "gateways" / f"{gw}.json").write_text(json.dumps({"devices": [uris[d] for d in membros]}, indent=2) + "\n",
                                                       encoding="utf-8")
    itens = [{"time_ms": int(t * 1000), "device": uris[d], "event": e} for t, d, e in agenda]
    (pasta / "agendamentos" / "ciclo.json").write_text(json.dumps(itens, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (pasta / "fases.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["rotulo", "inicio_s", "fim_s_exclusivo", "transicao_s"])
        writer.writerows(fases)
    (pasta / "papeis.json").write_text(json.dumps(papeis, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execucoes", type=int, default=8, help="Número total de execuções")
    parser.add_argument("--sem-desastre", type=int, default=1, help="Quantas das últimas execuções ficam sem desastre")
    parser.add_argument("--semente", type=int, default=20261015)
    parser.add_argument("--escala-tempo", type=float, default=1.0, help="Multiplica as durações (use < 1 só para testes)")
    parser.add_argument("--porta-base", type=int, default=9000)
    parser.add_argument("--saida", type=Path, default=PASTA / "configuracoes")
    args = parser.parse_args()

    resumos = []
    for numero in range(1, args.execucoes + 1):
        com_desastre = numero <= args.execucoes - args.sem_desastre
        nome, *dados, resumo = gerar_execucao(numero, args.semente + numero, com_desastre, args.escala_tempo, args.porta_base)
        gravar(args.saida, nome, *dados)
        resumos.append(resumo)
        print(f"{nome}: {resumo['sensores']} sensores, papéis {resumo['papeis']}, "
              f"{resumo['eventos']} eventos ({resumo['eventos_benignos']} benignos), {resumo['duracao_total_s']} s")
    (args.saida / "resumo.json").write_text(json.dumps({"scenario_id": SCENARIO_ID, "semente_base": args.semente,
                                                        "escala_tempo": args.escala_tempo, "execucoes": resumos},
                                                       indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
