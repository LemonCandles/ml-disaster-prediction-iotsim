#!/usr/bin/env bash
# Executa uma coleta com os comandos do manual (referencias/Manual_IoTEventSim.pdf), sem substituir nenhuma ferramenta:
# sensores em lote (iot-sim-batch), um iot-gw por arquivo de gateway e o ev-man com o agendamento.
# Equivale a abrir um terminal para cada comando; o script só os inicia na ordem certa, registra t0
# e os encerra com Ctrl+C (SIGINT) quando a última fase termina.
#
# Uso: dataset/coletar_execucao.sh CONFIG COLETA
#   CONFIG  pasta com dispositivos/, gateways/, agendamentos/ e fases.csv (ou ../tabela_parametros.csv)
#   COLETA  pasta nova onde ficam os registros brutos
# O broker MQTT precisa estar ativo em localhost:1883 (sudo service mosquitto start).
# AQUECIMENTO_S (padrão 60) é a espera entre os gateways e o ev-man; ver dataset/README.md.

set -euo pipefail
set -m  # cada comando em seu próprio grupo de processos, para receber Ctrl+C como em um terminal

[[ $# -eq 2 ]] || { echo "Uso: $0 CONFIG COLETA" >&2; exit 2; }
REPO=$(cd "$(dirname "$0")/.." && pwd)
BIN="$REPO/iot-sim-main/.venv/bin"
CONFIG=$(realpath "$1")
COLETA=$(realpath -m "$2")

FASES="$CONFIG/fases.csv"
[[ -f $FASES ]] || FASES="$CONFIG/../tabela_parametros.csv"
DURACAO=$(awk -F, 'NR > 1 { fim = $3 } END { printf "%d", fim }' "$FASES")
AGENDA=$(ls "$CONFIG"/agendamentos/*.json)

if [[ -d $COLETA && -n $(ls -A "$COLETA") ]]; then
  echo "A pasta $COLETA já contém arquivos; use uma pasta nova." >&2; exit 1
fi
(exec 3<>/dev/tcp/127.0.0.1/1883) 2>/dev/null || { echo "Broker MQTT inativo em localhost:1883." >&2; exit 1; }
mkdir -p "$COLETA"
cd "$COLETA"
export PYTHONUNBUFFERED=1
NOME=$(basename "$CONFIG")

# Terminal 1 — sensores
"$BIN/iot-sim-batch" --config-dir "$CONFIG/dispositivos" --log-level INFO > batch.log 2>&1 &
SENSORES=$!
sleep 3

# Terminais 2 e 3 — um gateway por grupo, com 2 s de separação (o nome do CSV usa o segundo atual)
GATEWAYS=()
for gw in "$CONFIG"/gateways/*.json; do
  g=$(basename "$gw" .json)
  "$BIN/iot-gw" -i 5000 -d "$gw" -b localhost:1883 -t "/tcc/$NOME/$g/" > "$g.log" 2>&1 &
  GATEWAYS+=($!)
  sleep 2
done
# Aquecimento: o gateway só grava um sensor depois da primeira resposta válida. Com 1% de perda no estado
# normal, a primeira consulta pode terminar em timeout (15 s) e não ser gravada; esperando 60 s, uma perda
# dentro do ciclo exigiria quatro timeouts seguidos no mesmo sensor.
sleep "${AQUECIMENTO_S:-60}"

# Terminal 4 — instante zero e coordenador de eventos
date +%s%N > t0_ns.txt
"$BIN/ev-man" "$AGENDA" > evman.log 2>&1 &
T0=$(cat t0_ns.txt)
echo "[$NOME] t0 registrado; coleta de ${DURACAO} s em $COLETA"

# Mantém sensores e gateways até 20 s depois do fim da última fase.
while (( ($(date +%s%N) - T0) / 1000000000 < DURACAO + 20 )); do sleep 5; done

# Ctrl+C nos gateways (completa os CSVs) e depois nos sensores.
kill -INT "${GATEWAYS[@]}"
wait "${GATEWAYS[@]}" 2>/dev/null || true
kill -INT "$SENSORES"
wait "$SENSORES" 2>/dev/null || true
wait 2>/dev/null || true
echo "[$NOME] coleta encerrada"
