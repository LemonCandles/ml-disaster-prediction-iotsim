# Dicionário de dados

As duas versões do dataset (`v1/dataset.csv` e `v2/dataset.csv`) têm as mesmas colunas. Cada linha representa **uma tentativa de consulta CoAP feita por um gateway (`iot-gw`) a um sensor**, incluindo consultas malsucedidas. As linhas vêm dos CSVs dos gateways, organizados por `organizar_dados.py`. O CSV usa UTF-8, vírgula como separador e ponto decimal. Campos vazios representam dados não obtidos; não são valores zero.

| Coluna | Tipo ao importar | Unidade / valores | Significado |
|:--|:--|:--|:--|
| `timestamp` | texto ou data UTC | ISO 8601 | Instante de envio da consulta, em UTC. |
| `run_id` | texto | `execucao-<t0_ns>` (v1) ou `execucao_XX-<t0_ns>` (v2) | Identificador da execução: nome da configuração e origem temporal registrada antes do `ev-man`. Separa execuções entre treino e teste. |
| `device_id` | texto | `gw01-d01`, `gw02-d06`… | Nome do arquivo de configuração do sensor. Na v2, o mesmo nome em execuções diferentes é outro sensor. |
| `gateway_id` | texto | `gw01` ou `gw02` | Grupo de coleta definido pelas listas de gateways da configuração (`gateways/`). |
| `latitude` | decimal | graus | Coordenada ilustrativa da configuração do sensor. Continua preenchida em falhas; não é uma localização medida na resposta. |
| `longitude` | decimal | graus | Coordenada ilustrativa da configuração do sensor. |
| `temperature` | decimal, aceita ausentes | °C | Leitura retornada pelo simulador em uma resposta válida. |
| `pressure` | decimal, aceita ausentes | hPa, convenção do cenário | Leitura de pressão retornada pelo simulador. A faixa não foi calibrada à localização ilustrativa. |
| `battery` | decimal, aceita ausentes | 0 a 100% | Carga informada na resposta válida. Não é preenchida com zero apenas porque houve falha. |
| `battery_rate_pp_min` | decimal, aceita ausentes | p.p./min | Descarga observada: diferença entre a carga da resposta válida mais recente feita pelo menos 60 s antes e a carga atual, dividida pelo intervalo. Ausente em falhas e no primeiro minuto de cada sensor. Mede o consumo recente sem depender da carga inicial. |
| `latency_ms` | decimal, aceita ausentes | ms | `receipt_time_ns - sent_time_ns` de uma resposta com medições, ambos gravados pelo gateway no relógio do sistema. Inclui a comunicação CoAP e eventuais retransmissões; não é o atraso configurado no JSON. |
| `drop_rate` | decimal | proporção de 0 a 1 | Fração de consultas sem medições válidas nas últimas até 12 tentativas deste sensor, incluindo a tentativa da linha. Conta também as tentativas anteriores a `t0` que o gateway registrou, por serem observações já disponíveis. Inclui timeouts e respostas `5.03`; não é uma medição da perda de pacotes no enlace. |
| `drop_window_n` | inteiro | 1 a 12 | Quantidade efetiva de tentativas usada no denominador de `drop_rate`. |
| `available` | inteiro | 0 ou 1 | 1 quando o gateway registrou resposta válida (`error = 0` e `receipt_time` preenchido); 0 nos demais casos. |
| `error` | texto, aceita vazio | vazio, `sem_resposta`, `consulta_pulada` | Resultado da tentativa segundo o gateway: `sem_resposta` (código 1) reúne timeout e `5.03 Service Unavailable` (bateria esgotada), que o CSV do gateway não distingue; `consulta_pulada` (código 2) indica que a consulta anterior ainda estava pendente. Vazio quando a consulta foi válida. A contagem por tipo de falha fica em `execucao.json`, a partir de `gw01.log` e `gw02.log`. |
| `event_type` | texto | `none`, `permanent`, `transient` | Tipo do último evento agendado para o sensor até o envio, segundo o agendamento da execução (`agendamentos/`) e a confirmação dos POSTs. `none` indica o estado inicial. Metadado de auditoria. |
| `event_name` | texto | nome do evento vigente | Nome desse evento (`Normal` antes do primeiro). Um evento transitório volta ao anterior ao fim de sua duração. Inclui o período de transição gradual. Metadado de auditoria. |
| `device_role` | texto | `controle`, `degradacao`, `falha_energetica`, `falha_rede` | Papel do sensor no roteiro (`papeis.json`). Metadado de auditoria; não usar no treinamento. |
| `scenario_id` | texto | `evento_termico_v1` ou `evento_termico_v2` | Identificador do cenário definido em `cenarios/`. |
| `label` | texto | `normal`, `pre_desastre`, `desastre`, `pos_desastre` | Fase global no instante de envio da consulta, segundo a tabela de fases da execução (`fases.csv` ou, na v1, `tabela_parametros.csv`). |
| `elapsed_s` | decimal | s | `(sent_time_ns - t0_ns) / 10⁹`: tempo relativo de envio desde a origem gravada imediatamente antes do `ev-man`. |
| `sent_time_ns` | inteiro de 64 bits | nanossegundos Unix | Instante de envio no relógio civil. Preserva a precisão que a representação ISO de `timestamp` não conserva. |
| `receipt_time_ns` | inteiro de 64 bits, aceita ausentes | nanossegundos Unix | Instante de recebimento de uma resposta válida, gravado pelo gateway. Vazio quando não houve resposta válida (o gateway grava `-1`). |
| `message_id` | inteiro | a partir de 1 | Número sequencial da tentativa no gateway, por sensor. Conta inclusive tentativas anteriores a `t0` e permite verificar se alguma tentativa deixou de ser gravada. |
| `em_transicao` | inteiro | 0 ou 1 | Marca a transição da fase global, com a duração definida na tabela de fases (na v1: pré-desastre até 480 s, desastre até 630 s e pós-desastre até 1020 s). Os controles recebem a mesma marca temporal. |
| `cruzou_fase` | inteiro | 0 ou 1 | 1 quando uma resposta com medições foi validada em outra fase ou depois do fim da última fase (1200 s na v1). Esses registros devem ser excluídos da primeira avaliação supervisionada. |

## Valores ausentes e zeros

Quando `available = 0`, `temperature`, `pressure`, `battery` e `latency_ms` ficam vazios. Nessas tentativas, o CSV original do gateway grava temperatura, pressão e bateria iguais a zero e repete o `timestamp` da última resposta válida; a organização descarta esses valores, que não são medições. Não se reaproveitam valores ou horários de respostas antigas. As informações de identidade, localização configurada, rótulo e resultado da tentativa permanecem disponíveis.

`battery = 0` só pode aparecer como medição quando uma resposta válida informar esse valor. Uma resposta `5.03` não permite inventar uma leitura de bateria: o campo fica vazio. O esgotamento é confirmado separadamente pelas respostas `5.03` registradas em `gw01.log`/`gw02.log` e pela verificação `falha_energetica_permanente` de `execucao.json`.

Não há preenchimento de lacunas, interpolação ou imputação no dataset inicial. Também não foram criadas linhas para intervalos em que nenhuma tentativa ocorreu. O intervalo solicitado é de 5 s, mas a consulta seguinte espera a tentativa anterior terminar. Timeouts de 15 s reduzem a quantidade de consultas durante degradação.

## Importação para análise

Para trabalhar em Python, mantendo os tempos em nanossegundos como inteiros e as ausências como ausências:

```python
import pandas as pd

dados = pd.read_csv(
    "dataset/v2/dataset.csv",
    dtype={"sent_time_ns": "Int64", "receipt_time_ns": "Int64"},
)
dados["timestamp"] = pd.to_datetime(dados["timestamp"], utc=True)
```

Os inteiros em nanossegundos excedem a precisão numérica do Excel. Se o CSV for aberto em uma planilha, importar essas duas colunas como texto para preservar os dígitos. O arquivo original mantém os inteiros exatos.

## Uso em aprendizado de máquina

`label` é o alvo. Os candidatos a atributos são `temperature`, `pressure`, `battery`, `battery_rate_pp_min`, `latency_ms`, `available` e `drop_rate`. `drop_window_n` informa o suporte da taxa e pode ser usado no tratamento de janelas iniciais. A taxa da linha só fica conhecida após concluir essa tentativa; para antecipação, respeitar o instante em que cada resposta ficou disponível.

Identificadores, coordenadas, horários, tempo relativo, eventos, papéis, códigos e marcas de transição são destinados à auditoria. Não usá-los para fornecer o roteiro ao classificador. Em particular, `event_name` e `event_type` são informações internas do simulador e não fazem parte das medições disponíveis para uma implantação real.

As regras de rotulagem estão em `cenarios/rotulacao.md`, e os limites da análise no README desta pasta. Para avaliar generalização, separar execuções inteiras (`run_id`) entre treino e teste; a v1 tem uma única execução e não permite essa avaliação.
