#!/usr/bin/env python3
"""Organiza os registros brutos de coletas do IoTEventSim em um CSV rotulado.

A coleta é feita com as ferramentas do simulador (iot-sim-batch, iot-gw e ev-man; ver
dataset/README.md). Este script não executa simulação: para cada execução, lê os CSVs
dos gateways, a origem temporal (t0) e os logs, trata as limitações conhecidas da
exportação do gateway, atribui os rótulos pela tabela de fases da execução e confere
se o roteiro foi cumprido. Várias execuções são reunidas em um único dataset.

Uso:
    python dataset/organizar_dados.py v1        # cenarios/v1 + dataset/v1/coleta -> dataset/v1
    python dataset/organizar_dados.py v2        # cada cenarios/v2/configuracoes/execucao_XX -> dataset/v2
    python dataset/organizar_dados.py --execucao CONFIG COLETA [--execucao ...] --cenario ID --saida PASTA
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DROP_WINDOW = 12  # tentativas usadas na taxa empírica de falhas
JANELA_BATERIA_S = 60  # distância mínima entre leituras usadas na taxa de descarga
TIMEOUT_GW_S = 15  # timeout de cada consulta no iot-gw
FIELDS = [
    "timestamp", "run_id", "device_id", "gateway_id", "latitude", "longitude",
    "temperature", "pressure", "battery", "battery_rate_pp_min", "latency_ms", "drop_rate", "drop_window_n",
    "available", "error", "event_type", "event_name", "device_role", "scenario_id", "label",
    "elapsed_s", "sent_time_ns", "receipt_time_ns", "message_id", "em_transicao", "cruzou_fase",
]
# Código de erro gravado pelo iot-gw: 0 = resposta válida, 1 = sem resposta (timeout ou 5.03),
# 2 = consulta pulada porque a anterior ainda estava pendente.
ERROS_GW = {"1": "sem_resposta", "2": "consulta_pulada"}
VERSOES = {
    "v1": {"cenario": "evento_termico_v1", "configs": [REPO / "cenarios/v1/configuracoes"],
           "coletas": [REPO / "dataset/v1/coleta"], "saida": REPO / "dataset/v1"},
    "v2": {"cenario": "evento_termico_v2", "configs": sorted((REPO / "cenarios/v2/configuracoes").glob("execucao_*")),
           "coletas": None, "saida": REPO / "dataset/v2"},
}


def relativo(path):
    """Caminho relativo ao repositório quando possível (para registros portáveis)."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ler_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def carregar_fases(config):
    """Tabela de fases da execução: config/fases.csv ou, na v1, a tabela de parâmetros da pasta acima."""
    caminho = config / "fases.csv"
    if not caminho.exists():
        caminho = config.parent / "tabela_parametros.csv"
    with caminho.open(encoding="utf-8", newline="") as stream:
        fases = list(csv.DictReader(stream))
    for fase in fases:
        for chave in ("inicio_s", "fim_s_exclusivo", "transicao_s"):
            fase[chave] = float(fase[chave])
    if fases[0]["inicio_s"] != 0:
        raise ValueError(f"{caminho}: a primeira fase deve começar em 0.")
    for anterior, atual in zip(fases, fases[1:]):
        if atual["inicio_s"] != anterior["fim_s_exclusivo"]:
            raise ValueError(f"{caminho}: fases com lacunas ou sobreposições.")
    return caminho, fases


def fase_em(tempo_s, fases):
    for fase in fases:
        if fase["inicio_s"] <= tempo_s < fase["fim_s_exclusivo"]:
            return fase
    return None


def carregar_topologia(config):
    """Associa cada URI ao arquivo do dispositivo, à configuração, ao gateway e ao papel."""
    papeis = ler_json(config / "papeis.json")
    dispositivos = {}
    for path in sorted((config / "dispositivos").glob("*.json")):
        cfg = ler_json(path)
        uri = f'coap://{cfg["server_host"]}:{cfg["server_port"]}/{"/".join(cfg["resource_path"])}'
        dispositivos[uri] = {"device_id": path.stem, "uuid": cfg["uuid"], "coordinate": cfg["coordinate"],
                             "temperature_range": cfg["temperature_range"], "papel": papeis[path.stem]}
    for path in sorted((config / "gateways").glob("*.json")):
        for uri in ler_json(path)["devices"]:
            if "gateway_id" in dispositivos[uri]:
                raise ValueError(f"{uri} aparece em dois gateways.")
            dispositivos[uri]["gateway_id"] = path.stem
    return dispositivos


def carregar_agendamento(config):
    """Eventos planejados por URI, com o intervalo em que cada um vale (em s desde t0)."""
    caminhos = sorted((config / "agendamentos").glob("*.json"))
    if len(caminhos) != 1:
        raise ValueError(f"{config}/agendamentos deve conter exatamente um agendamento.")
    itens = sorted(ler_json(caminhos[0]), key=lambda i: i["time_ms"])
    por_uri = defaultdict(list)
    for item in itens:
        evento = item["event"]
        inicio = item["time_ms"] / 1000
        fim = float("inf")
        if evento.get("event_type") == "transient":
            fim = inicio + sum(evento.get(k, 0) for k in
                               ("transition_duration_s", "transient_event_duration_s", "transient_event_return_s"))
        por_uri[item["device"]].append((inicio, fim, evento["event_name"], evento.get("event_type", "permanent")))
    return caminhos[0], itens, por_uri


def evento_vigente(eventos, tempo_s):
    """Último evento agendado já enviado ao sensor; um transitório expira e devolve o anterior."""
    vigente = ("Normal", "none")
    for inicio, fim, nome, tipo in eventos:
        if inicio <= tempo_s < fim:
            vigente = (nome, tipo)
    return vigente


def ler_t0(coleta):
    texto = (coleta / "t0_ns.txt").read_text(encoding="utf-8").strip()
    if not texto.isdigit():
        raise ValueError("t0_ns.txt deve conter apenas o instante Unix em nanossegundos.")
    return int(texto)


def ler_evman(coleta):
    """Respostas do ev-man: 'Sent event to <uri>: <código>' e as mensagens de falha de envio.

    Outras linhas (por exemplo, avisos internos do aiocoap ao descartar conexões) são contadas
    à parte, pois não indicam falha de um POST.
    """
    aceitos, falhas, outras = Counter(), [], Counter()
    for linha in (coleta / "evman.log").read_text(encoding="utf-8", errors="replace").splitlines():
        linha = linha.strip()
        m = re.match(r"Sent event to (\S+): (.+)$", linha)
        if m and m.group(2).startswith("2.01"):
            aceitos[m.group(1)] += 1
        elif m or linha.startswith(("Timeout sending event", "Failed to send event", "Fatal error")):
            falhas.append(linha)
        elif linha:
            outras[linha] += 1
    return aceitos, falhas, outras


def ler_batch(coleta, t0_ns):
    """Instantes (s desde t0) em que os sensores registraram eventos, e quantos esgotamentos de bateria houve."""
    recebidos, esgotamentos = [], 0
    instante = None
    padrao_hora = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) ")
    for linha in (coleta / "batch.log").read_text(encoding="utf-8", errors="replace").splitlines():
        m = padrao_hora.match(linha)
        if m:
            local = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S,%f").astimezone()
            instante = local.timestamp() - t0_ns / 1e9
        m = re.search(r"Received Event Mode Trigger: event_name='([^']+)'", linha)
        if m and instante is not None:
            recebidos.append((instante, m.group(1)))
        if "🔋 Battery fully discharged." in linha:  # mensagem do modelo de bateria, uma por esgotamento
            esgotamentos += 1
    return recebidos, esgotamentos


def ler_falhas_gateways(coleta):
    """Falhas impressas pelos gateways: total por tipo e, por URI, a sequência de tipos em ordem cronológica.

    A saída não tem horário, mas cada tentativa malsucedida gera exatamente uma linha, na ordem em que ocorreu.
    """
    tipos, por_uri = Counter(), defaultdict(list)
    padroes = [("timeout", r"Timeout requesting (\S+)"), ("5.03", r"503 Service Unavailable.* for (\S+)"),
               ("4.04", r"404 Not Found for (\S+)"), ("erro", r"Error requesting (\S+?):")]
    for path in sorted(coleta.glob("gw*.log")):
        for linha in path.read_text(encoding="utf-8", errors="replace").splitlines():
            for tipo, padrao in padroes:
                m = re.search(padrao, linha)
                if m:
                    tipos[tipo] += 1
                    por_uri[m.group(1)].append(tipo)
                    break
    return tipos, por_uri


def ler_csvs_gateways(coleta, topologia):
    arquivos = sorted((coleta / "logs").glob("gw-*.csv"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum logs/gw-*.csv em {coleta}.")
    linhas = []
    for path in arquivos:
        with path.open(encoding="utf-8", newline="") as stream:
            linhas_arquivo = list(csv.DictReader(stream, delimiter=";"))
        gateways = {topologia[l["uri"]]["gateway_id"] for l in linhas_arquivo}
        if len(gateways) != 1:
            raise ValueError(f"{path.name} mistura dispositivos de gateways diferentes: {gateways}")
        linhas += linhas_arquivo
    return arquivos, linhas


def taxa_bateria(historico, enviado_ns, carga):
    """Descarga observada (p.p./min) desde a última leitura válida feita pelo menos 60 s antes."""
    anterior = None
    for t_ns, valor in reversed(historico):
        if enviado_ns - t_ns >= JANELA_BATERIA_S * 1e9:
            anterior = (t_ns, valor)
            break
    if anterior is None:
        return ""
    return (anterior[1] - carga) / ((enviado_ns - anterior[0]) / 60e9)


def organizar_execucao(config, coleta, cenario):
    caminho_fases, fases = carregar_fases(config)
    topologia = carregar_topologia(config)
    caminho_agenda, agendamento, eventos_por_uri = carregar_agendamento(config)
    t0_ns = ler_t0(coleta)
    nome = config.name if config.name.startswith("execucao") else "execucao"
    run_id = f"{nome}-{t0_ns}"
    arquivos_gw, brutas = ler_csvs_gateways(coleta, topologia)
    aceitos, falhas_evman, outras_evman = ler_evman(coleta)
    recebidos, esgotamentos = ler_batch(coleta, t0_ns)
    falhas_gw, falhas_por_uri = ler_falhas_gateways(coleta)

    # Ordena por sensor e número da tentativa para calcular as taxas em janela.
    brutas.sort(key=lambda l: (topologia[l["uri"]]["device_id"], int(l["message_id"])))
    historico = defaultdict(lambda: deque(maxlen=DROP_WINDOW))
    cargas = defaultdict(list)
    primeira_mensagem = {}
    linhas, fora = [], Counter()
    for bruta in brutas:
        uri = bruta["uri"]
        disp = topologia[uri]
        if bruta["uuid"] != disp["uuid"]:
            raise ValueError(f"UUID inesperado para {uri}.")
        primeira_mensagem.setdefault(disp["device_id"], (int(bruta["message_id"]), (int(bruta["sent_time"]) - t0_ns) / 1e9))
        enviado_ns = int(bruta["sent_time"])
        recebido_ns = int(bruta["receipt_time"])
        valida = bruta["error"] == "0" and recebido_ns > 0
        historico[uri].append(0 if valida else 1)
        taxa = ""
        if valida:
            taxa = taxa_bateria(cargas[uri], enviado_ns, float(bruta["battery"]))
            cargas[uri].append((enviado_ns, float(bruta["battery"])))
        elapsed = (enviado_ns - t0_ns) / 1e9
        fase = fase_em(elapsed, fases)
        if fase is None:
            fora["antes_de_t0" if elapsed < 0 else "depois_do_fim"] += 1
            continue

        nome_evento, tipo_evento = evento_vigente(eventos_por_uri[uri], elapsed)
        linha = {campo: "" for campo in FIELDS}
        linha.update(
            timestamp=datetime.fromtimestamp(enviado_ns / 1e9, timezone.utc).isoformat(),
            run_id=run_id, device_id=disp["device_id"], gateway_id=disp["gateway_id"],
            latitude=disp["coordinate"]["latitude"], longitude=disp["coordinate"]["longitude"],
            drop_rate=sum(historico[uri]) / len(historico[uri]), drop_window_n=len(historico[uri]),
            available=int(valida), error="" if valida else ERROS_GW.get(bruta["error"], "sem_resposta"),
            event_type=tipo_evento, event_name=nome_evento, device_role=disp["papel"], scenario_id=cenario,
            label=fase["rotulo"], elapsed_s=elapsed, sent_time_ns=enviado_ns,
            receipt_time_ns=recebido_ns if recebido_ns > 0 else "", message_id=int(bruta["message_id"]),
            em_transicao=int(elapsed < fase["inicio_s"] + fase["transicao_s"]), cruzou_fase=0,
        )
        if valida:
            # Só respostas válidas trazem medições; em falhas o gateway grava zeros, que viram ausência.
            linha.update(temperature=float(bruta["temperature"]), pressure=float(bruta["pressure"]),
                         battery=float(bruta["battery"]), battery_rate_pp_min=taxa,
                         latency_ms=(recebido_ns - enviado_ns) / 1e6)
            fase_recebimento = fase_em((recebido_ns - t0_ns) / 1e9, fases)
            linha["cruzou_fase"] = int(fase_recebimento is None or fase_recebimento["rotulo"] != fase["rotulo"])
        linhas.append(linha)

    checks, detalhes = conferir(linhas, topologia, agendamento, fases, aceitos, falhas_evman, recebidos,
                                primeira_mensagem, fora, falhas_por_uri)
    planejados = sum(1 for d in topologia.values() if d["papel"] == "falha_energetica")
    resumo = {}
    for fase in fases:
        sel = [l for l in linhas if l["label"] == fase["rotulo"]]
        med = [l for l in sel if l["available"]]
        resumo[fase["rotulo"]] = {
            "rows": len(sel), "available": len(med), "unavailable": len(sel) - len(med),
            "crossed_phase": sum(l["cruzou_fase"] for l in sel),
            "in_transition": sum(l["em_transicao"] for l in sel),
            "mean_temperature_c": sum(l["temperature"] for l in med) / len(med) if med else None,
            "mean_latency_ms": sum(l["latency_ms"] for l in med) / len(med) if med else None,
        }
    fontes = [*arquivos_gw, *(coleta / n for n in ("t0_ns.txt", "evman.log", "batch.log")),
              *sorted(coleta.glob("gw*.log")), *sorted(config.rglob("*.json")), caminho_fases]
    registro = {
        "run_id": run_id, "config": relativo(config), "coleta": relativo(coleta),
        "status": "concluida" if all(checks.values()) else "requer_revisao",
        "t0_ns": t0_ns, "start_utc": datetime.fromtimestamp(t0_ns / 1e9, timezone.utc).isoformat(),
        "duration_s": fases[-1]["fim_s_exclusivo"], "phases": {f["rotulo"]: [f["inicio_s"], f["fim_s_exclusivo"]] for f in fases},
        "devices": len(topologia), "roles": dict(Counter(d["papel"] for d in topologia.values())),
        "row_count": len(linhas), "excluded_rows": dict(fora),
        "events_accepted": sum(aceitos.values()), "events_expected": len(agendamento),
        "event_send_failures": falhas_evman, "other_evman_messages": dict(outras_evman),
        "events_logged_by_devices": dict(Counter(n for _, n in recebidos)),
        "battery_depletions_logged": esgotamentos, "battery_depletions_planned": planejados,
        "gateway_failures_by_type": dict(falhas_gw),
        "checks": checks, "check_details": detalhes, "summary_by_class": resumo,
        "sources_sha256": {relativo(p): sha256(p) for p in fontes},
    }
    return linhas, registro


def conferir(linhas, topologia, agendamento, fases, aceitos, falhas_evman, recebidos, primeira_mensagem, fora,
             falhas_por_uri):
    """Verificações do roteiro pedidas em cenarios/rotulacao.md, a partir dos papéis e do agendamento."""
    por_disp = defaultdict(list)
    for l in linhas:
        por_disp[l["device_id"]].append(l)
    uri_de = {d["device_id"]: uri for uri, d in topologia.items()}
    eventos_de = defaultdict(list)
    for item in agendamento:
        eventos_de[item["device"]].append(item)
    fim = fases[-1]["fim_s_exclusivo"]

    esperados = Counter(item["device"] for item in agendamento)
    nomes_esperados = Counter(item["event"]["event_name"] for item in agendamento)
    atraso = [min((abs(t - item["time_ms"] / 1000) for t, n in recebidos if n == item["event"]["event_name"]),
                  default=float("inf")) for item in agendamento]
    detalhes = {"max_event_receipt_offset_s": max(atraso) if atraso else None}

    energia, rede, controles = [], [], []
    for disp, papel in ((d["device_id"], d["papel"]) for d in topologia.values()):
        linhas_d = por_disp[disp]
        itens = eventos_de[uri_de[disp]]
        if papel == "falha_energetica":
            t = next(i["time_ms"] / 1000 for i in itens if i["event"]["event_name"] == "falha_energetica_permanente")
            energia.append(any(l["available"] for l in linhas_d if l["elapsed_s"] < t)
                           and not any(l["available"] for l in linhas_d if l["elapsed_s"] > t + 70))
        elif papel == "falha_rede":
            item = next(i for i in itens if i["event"]["event_name"] == "falha_rede_transitoria")
            t, dur = item["time_ms"] / 1000, item["event"]["transient_event_duration_s"]
            rede.append(not any(l["available"] for l in linhas_d if t + 5 <= l["elapsed_s"] < t + dur)
                        and any(l["available"] for l in linhas_d if t + dur + 5 <= l["elapsed_s"] < fim))
        elif papel == "controle":
            aquecimento = [(i["time_ms"] / 1000, i["time_ms"] / 1000 + sum(i["event"].get(k, 0) for k in (
                "transition_duration_s", "transient_event_duration_s", "transient_event_return_s")) + 10)
                for i in itens if i["event"]["event_name"] == "aquecimento_local_benigno"]
            faixa = topologia[uri_de[disp]]["temperature_range"]
            normais = all(faixa[0] <= l["temperature"] <= faixa[1] for l in linhas_d
                          if l["available"] and not any(a <= l["elapsed_s"] < b for a, b in aquecimento))
            controles.append(normais and sum(l["available"] for l in linhas_d) / len(linhas_d) >= 0.85)
    detalhes.update(energy_failure_devices=len(energia), network_failure_devices=len(rede), control_devices=len(controles))
    # O gateway só grava um sensor a partir da primeira resposta válida. Se a primeira linha gravada tem
    # message_id m, as m - 1 tentativas anteriores falharam; a saída do gateway mostra o tipo de cada falha, na
    # ordem. Se todas foram timeouts, cada uma ocupou 15 s, e a última foi enviada até 15 s antes da primeira
    # linha gravada: fica fora do ciclo quando essa linha foi enviada menos de 15 s depois de t0.
    perdidas, dentro_do_ciclo = {}, []
    for d, (m, t) in primeira_mensagem.items():
        if m == 1:
            continue
        anteriores = falhas_por_uri.get(uri_de[d], [])[:m - 1]
        so_timeouts = len(anteriores) == m - 1 and all(tipo == "timeout" for tipo in anteriores)
        perdidas[d] = {"tentativas_nao_gravadas": m - 1, "tipos_na_saida_do_gateway": anteriores,
                       "primeira_linha_elapsed_s": round(t, 3), "ultima_perdida_ate_s": round(t - TIMEOUT_GW_S, 3)}
        dentro_do_ciclo.append(not (so_timeouts and t < TIMEOUT_GW_S))
    detalhes["initial_attempts_not_logged"] = perdidas

    checks = {
        "eventos_aceitos_2_01": aceitos == esperados and not falhas_evman,
        "eventos_registrados_pelos_sensores": Counter(n for _, n in recebidos) == nomes_esperados,
        "eventos_recebidos_em_ate_1s": all(a < 1 for a in atraso),
        "coleta_cobre_todo_o_ciclo": fora["depois_do_fim"] > 0 and min(l["elapsed_s"] for l in linhas) < 5,
        "classes_esperadas": {l["label"] for l in linhas} == {f["rotulo"] for f in fases},
        "todos_os_dispositivos": set(por_disp) == set(uri_de),
        "nenhuma_tentativa_perdida_no_ciclo": all(d in primeira_mensagem for d in uri_de) and not any(dentro_do_ciclo),
        "falha_energetica_permanente": all(energia),
        "falha_rede_transitoria": all(rede),
        "controles_normais": all(controles),
    }
    return checks, detalhes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("versao", nargs="?", choices=sorted(VERSOES), help="Versão com caminhos padrão")
    parser.add_argument("--execucao", nargs=2, action="append", type=Path, metavar=("CONFIG", "COLETA"),
                        help="Pasta de configuração e pasta de coleta de uma execução (repetível)")
    parser.add_argument("--cenario", help="Identificador do cenário (scenario_id)")
    parser.add_argument("--saida", type=Path, help="Pasta onde gravar dataset.csv e execucao.json")
    args = parser.parse_args()

    if args.versao:
        padrao = VERSOES[args.versao]
        configs = padrao["configs"]
        coletas = padrao["coletas"] or [REPO / "dataset" / args.versao / "coleta" / c.name for c in configs]
        pares, cenario, saida = list(zip(configs, coletas)), padrao["cenario"], padrao["saida"]
    elif args.execucao and args.cenario and args.saida:
        pares, cenario, saida = [(c.resolve(), k.resolve()) for c, k in args.execucao], args.cenario, args.saida.resolve()
    else:
        parser.error("informe uma versão (v1 ou v2) ou --execucao, --cenario e --saida")

    linhas, registros = [], []
    for config, coleta in pares:
        linhas_exec, registro = organizar_execucao(config, coleta, cenario)
        linhas += linhas_exec
        registros.append(registro)
        print(f"{registro['run_id']}: {registro['status']}, {registro['row_count']} linhas"
              + "".join(f"; FALHOU {k}" for k, v in registro["checks"].items() if not v))

    linhas.sort(key=lambda l: (l["run_id"], l["sent_time_ns"], l["device_id"]))
    saida.mkdir(parents=True, exist_ok=True)
    caminho_csv = saida / "dataset.csv"
    with caminho_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(linhas)
    contagem = Counter(l["label"] for l in linhas)
    total = {
        "status": "concluida" if all(r["status"] == "concluida" for r in registros) else "requer_revisao",
        "scenario_id": cenario,
        "metodo": "iot-sim-batch + iot-gw (-i 5000, MQTT) + ev-man, conforme Manual_IoTEventSim.pdf; "
                  "t0 registrado imediatamente antes do ev-man",
        "drop_window_attempts": DROP_WINDOW, "battery_rate_min_gap_s": JANELA_BATERIA_S,
        "runs": len(registros), "row_count": len(linhas), "rows_by_class": dict(contagem),
        "dataset_sha256": sha256(caminho_csv), "organizer_sha256": sha256(Path(__file__)),
        "python_version": sys.version.split()[0], "executions": registros,
    }
    (saida / "execucao.json").write_text(json.dumps(total, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{total['status']}: {len(registros)} execução(ões), {len(linhas)} linhas -> {relativo(caminho_csv)}")
    return 0 if total["status"] == "concluida" else 1


if __name__ == "__main__":
    raise SystemExit(main())
