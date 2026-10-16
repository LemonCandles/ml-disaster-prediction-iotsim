#!/usr/bin/env bash
# Reproduz o trabalho por etapas. Cada etapa apenas encadeia os comandos documentados nos READMEs das pastas.
#
# Uso: ./reproduzir.sh ETAPA
#   simulador    clona o IoTEventSim na versão usada e instala seu ambiente (iot-sim-main/.venv)
#   cenarios     gera de novo as configurações da v2 (a mesma semente produz os mesmos arquivos)
#   coleta-v2    executa as oito coletas da v2 em paralelo (cerca de 25 min; requer o Mosquitto ativo)
#   organizar    transforma os registros brutos de dataset/v1 e dataset/v2 nos datasets rotulados
#   modelos      cria o ambiente de modelagem e executa os quatro notebooks (cerca de 50 min)
#   tudo         organizar e modelos (usa as coletas já versionadas)
#
# Os datasets e as coletas brutas estão versionados: para reproduzir as análises, basta "./reproduzir.sh tudo".

set -euo pipefail
cd "$(dirname "$0")"

SIMULADOR_URL="https://github.com/paulo-coelho/iot-sim.git"
SIMULADOR_COMMIT="87015b644e5dc868efe7b8aa7fe48c98a9172291"  # versão usada em todas as coletas

simulador() {
  [[ -d iot-sim-main ]] || git clone "$SIMULADOR_URL" iot-sim-main
  git -C iot-sim-main checkout --quiet "$SIMULADOR_COMMIT"
  (cd iot-sim-main && uv venv --python 3.12 && uv pip install .)
}

cenarios() {
  python3 cenarios/v2/gerar_cenarios.py
}

coleta_v2() {
  (exec 3<>/dev/tcp/127.0.0.1/1883) 2>/dev/null || { echo "Inicie o broker: sudo service mosquitto start" >&2; exit 1; }
  for c in cenarios/v2/configuracoes/execucao_*; do
    dataset/coletar_execucao.sh "$c" "dataset/v2/coleta/$(basename "$c")" &
    sleep 5
  done
  wait
}

organizar() {
  python3 dataset/organizar_dados.py v1
  python3 dataset/organizar_dados.py v2
}

modelos() {
  [[ -x modelos/.venv/bin/python ]] || uv venv modelos/.venv
  uv pip install --quiet --python modelos/.venv/bin/python -r modelos/requirements.txt
  for nb in modelos/0*.ipynb; do
    echo "Executando $nb"
    modelos/.venv/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=7200 "$nb"
  done
}

case "${1:-}" in
  simulador) simulador ;;
  cenarios) cenarios ;;
  coleta-v2) coleta_v2 ;;
  organizar) organizar ;;
  modelos) modelos ;;
  tudo) organizar; modelos ;;
  *) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
