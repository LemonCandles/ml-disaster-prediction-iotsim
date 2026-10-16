# Dataset

Datasets rotulados gerados pela execução dos cenários de `cenarios/` no IoTEventSim. A coleta usa as ferramentas do próprio simulador, como no `referencias/Manual_IoTEventSim.pdf` — sensores em lote, gateways e coordenador de eventos —, e um script organiza os registros brutos em um CSV pronto para análise. Há duas versões, correspondentes às duas versões dos cenários.

## O que há nesta pasta

| Arquivo ou pasta | Para que serve |
|:--|:--|
| [v1/dataset.csv](v1/dataset.csv) | Versão 1: uma execução do cenário `evento_termico_v1` (2.062 linhas). |
| [v2/dataset.csv](v2/dataset.csv) | Versão 2: oito execuções do cenário `evento_termico_v2` (17.812 linhas). |
| `v1/execucao.json`, `v2/execucao.json` | Registro da organização: origem temporal, eventos confirmados, verificações, contagens e hashes dos arquivos usados, por execução. |
| `v1/coleta/`, `v2/coleta/execucao_XX/` | Registros brutos de cada execução, gerados pelos comandos do simulador. |
| [dicionario_dados.md](dicionario_dados.md) | Define as 26 colunas (iguais nas duas versões), unidades, tipos e valores ausentes. |
| [coletar_execucao.sh](coletar_execucao.sh) | Roda os comandos do manual para uma execução: sensores, gateways, registro de t0 e `ev-man`. |
| [organizar_dados.py](organizar_dados.py) | Lê os registros brutos, trata as limitações do CSV do gateway, atribui os rótulos e confere cada execução. |

Cada pasta de coleta contém:

| Arquivo | Gerado por | Conteúdo |
|:--|:--|:--|
| `logs/gw-*.csv` | `iot-gw` (um por gateway) | Cada consulta: tempos de envio e recebimento, medições e código de erro. |
| `t0_ns.txt` | `date +%s%N` | Instante Unix, em nanossegundos, imediatamente antes de iniciar o `ev-man`: a origem da rotulagem. |
| `evman.log` | `ev-man` | Resposta a cada evento enviado (`2.01 Created`). |
| `batch.log` | `iot-sim-batch` | Horário em que cada sensor recebeu um evento e esgotamentos de bateria. |
| `gw01.log`, `gw02.log` | `iot-gw` | Tipo de cada falha (timeout ou `5.03`), sem horário. |

## Comparação entre as versões

| | Versão 1 | Versão 2 |
|:--|--:|--:|
| Execuções (com desastre / sem desastre) | 1 / 0 | 7 / 1 |
| Sensores por execução | 10 | 8–12 |
| Duração do ciclo (s) | 1200 | 1110–1320 |
| Carga na primeira leitura (%) | 94–100 | 60–100 |
| Papéis (controle / degradação / falha energética / falha de rede) | 2 / 4 / 2 / 2 | 38 / 30 / 7 / 8 |
| Perturbações benignas | 0 | 15 |
| Tentativas | 2.062 | 17.812 |
| `normal` | 586 (28,4%) | 6.649 (37,3%) |
| `pre_desastre` | 539 (26,1%) | 3.755 (21,1%) |
| `desastre` | 436 (21,1%) | 3.681 (20,7%) |
| `pos_desastre` | 501 (24,3%) | 3.727 (20,9%) |
| Disponibilidade geral | 82,3% | 89,8% |
| Disponibilidade no desastre | 63,8% | 77,0% |
| Respostas que cruzaram fronteira de fase | 2 | 16 |
| F1 macro, só nível de bateria (Random Forest) | 0,71 | 0,34 |
| F1 macro, melhor conjunto de atributos (Random Forest) | 0,80 | 0,55 |

As duas últimas linhas vêm de `modelos/03_comparacao_versoes.ipynb`. Na v1, a avaliação treina em um gateway e testa no outro, dentro da única execução. Na v2, treina em sete execuções e testa na oitava. A queda mostra que a v1 permitia um atalho — o nível de bateria indicava o tempo decorrido — que a v2 removeu. As razões de cada mudança estão em `cenarios/v2/cenarios.md`.

Todas as execuções das duas versões terminaram com `status = concluida`. Na v2, todos os 158 eventos (de 3 a 28 por execução) foram aceitos e registrados pelos sensores no máximo 0,37 s depois do agendado.

## Como coletar

O broker MQTT deve estar ativo (`sudo service mosquitto start`, seção 5 do manual), e o simulador instalado em `iot-sim-main/.venv`.

Na v1, cada comando foi aberto em um terminal, a partir da pasta de coleta vazia:

```bash
# Terminal 1 — sensores
cd dataset/v1/coleta
../../../iot-sim-main/.venv/bin/iot-sim-batch --config-dir ../../../cenarios/v1/configuracoes/dispositivos --log-level INFO 2>&1 | tee batch.log

# Terminais 2 e 3 — um gateway por grupo, com pelo menos 2 s entre eles
cd dataset/v1/coleta
PYTHONUNBUFFERED=1 ../../../iot-sim-main/.venv/bin/iot-gw -i 5000 -d ../../../cenarios/v1/configuracoes/gateways/gw01.json -b localhost:1883 -t /tcc/gw01/ | tee gw01.log
#   (o mesmo com gw02.json e gw02.log)

# Terminal 4 — instante zero e eventos, pelo menos 1 minuto depois dos gateways
cd dataset/v1/coleta
date +%s%N > t0_ns.txt; PYTHONUNBUFFERED=1 ../../../iot-sim-main/.venv/bin/ev-man ../../../cenarios/v1/configuracoes/agendamentos/ciclo_completo.json | tee evman.log
```

Esperar pelo menos 1 minuto entre iniciar os gateways e iniciar o `ev-man` (ver *Tentativas iniciais não gravadas*, abaixo). Manter sensores e gateways ativos até o fim da última fase. Depois, encerrar os gateways com **Ctrl+C** (o CSV é completado no encerramento) e, em seguida, os sensores.

**Várias execuções.** Para a v2, que tem oito execuções, `coletar_execucao.sh` abre exatamente esses comandos para uma execução, espera 60 s de aquecimento (variável `AQUECIMENTO_S`), registra t0 e envia Ctrl+C a cada componente quando a última fase termina (mais 20 s). Cada execução da v2 usa portas próprias, então várias podem rodar ao mesmo tempo:

```bash
for c in cenarios/v2/configuracoes/execucao_*; do
  dataset/coletar_execucao.sh "$c" "dataset/v2/coleta/$(basename "$c")" &
  sleep 5   # espaça o início das execuções
done
wait
```

Cada execução leva a duração do seu ciclo (18 a 22 minutos na v2). Para uma nova coleta, usar pastas vazias: o script recusa uma pasta que já tenha arquivos.

## Como organizar

```bash
python3 dataset/organizar_dados.py v1   # -> dataset/v1/dataset.csv e execucao.json
python3 dataset/organizar_dados.py v2   # -> dataset/v2/dataset.csv e execucao.json
# Outras coletas: --execucao CONFIG COLETA (repetível) --cenario ID --saida PASTA
```

O script usa apenas a biblioteca padrão do Python. Para cada execução:

1. **Une os CSVs dos gateways** e identifica sensor, gateway e papel pelas configurações da execução.
2. **Trata as limitações do CSV do gateway.** Em uma falha, o gateway grava temperatura, pressão e bateria iguais a zero e repete o horário da última resposta; esses valores viram ausências. A latência é `receipt_time - sent_time`, apenas para respostas válidas.
3. **Atribui o rótulo** pelo tempo de envio relativo a `t0` e pela tabela de fases da execução (`cenarios/rotulacao.md`). Marca `em_transicao` e `cruzou_fase` e separa as consultas anteriores a `t0` e posteriores à última fase.
4. **Calcula atributos de janela observáveis:**
   - `drop_rate`: fração de falhas nas últimas 12 tentativas do sensor;
   - `battery_rate_pp_min`: descarga desde a leitura válida feita pelo menos 60 s antes.
5. **Confere a execução.** Uma execução só é aceita com `status = concluida`. As verificações são:
   - todos os POSTs com `2.01 Created`;
   - eventos registrados pelos sensores no máximo 1 s depois do agendado;
   - ciclo completo coberto e todas as classes esperadas presentes;
   - nenhuma tentativa perdida dentro do ciclo (explicado abaixo);
   - sensores com falha energética sem respostas a partir de 70 s depois da falha;
   - sensores com falha de rede sem respostas durante a falha e com respostas depois;
   - controles com temperatura normal (fora dos aquecimentos benignos) e disponibilidade de pelo menos 85%.


Duas observações sobre os registros:

- **Tentativas iniciais não gravadas.** O `iot-gw` só começa a gravar um sensor no CSV depois da primeira resposta válida; uma falha anterior não gera linha. Como o estado normal tem 1% de perda, cada sensor tem 1% de chance de perder a primeira consulta — com 83 sensores na v2, cerca de um caso por coleta.
  - *Como é detectado.* O gateway numera todas as tentativas (`message_id`), inclusive as não gravadas, e imprime cada falha, na ordem, em `gw01.log`/`gw02.log`. Se a primeira linha de um sensor tem `message_id` m, o script confere na saída do gateway que as m − 1 falhas anteriores foram timeouts. Cada timeout ocupa 15 s, então a última tentativa perdida foi enviada pelo menos 15 s antes da primeira linha gravada. A verificação só aprova a execução se essas tentativas ficaram antes de `t0`.
  - *O que aconteceu na v2.* Duas tentativas não foram gravadas: `gw01-d01` na execução 04 e `gw02-d04` na execução 08. As duas foram timeouts enviados 13,8 s e 9,2 s antes de `t0`, fora do ciclo; o dataset não perdeu nenhuma tentativa. Os detalhes estão em `check_details.initial_attempts_not_logged` de `v2/execucao.json`.
  - *Como evitar.* A coleta da v2 esperou 17 s entre os gateways e o `ev-man`; o `coletar_execucao.sh` espera 60 s: para uma tentativa ser perdida dentro do ciclo, seriam necessários pelo menos quatro timeouts seguidos no mesmo sensor (chance da ordem de 1 em 100 milhões).


