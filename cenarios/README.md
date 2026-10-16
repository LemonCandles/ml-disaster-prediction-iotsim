# Cenários de desastre

Definição dos cenários simulados no IoTEventSim: os estados `normal`, `pre_desastre`, `desastre` e `pos_desastre`, seus parâmetros, as configurações JSON do simulador e as regras para rotular as observações. Há duas versões: a v1 é uma única execução fixa; a v2 é um conjunto de execuções que variam entre si, criado para corrigir os problemas encontrados na v1.

## O que há nesta pasta

| Arquivo ou pasta | Para que serve |
|:--|:--|
| [rotulacao.md](rotulacao.md) | Regras para atribuir os rótulos, exemplos de fronteira e prevenção de vazamento. Valem para as duas versões. |
| [v1/cenarios.md](v1/cenarios.md) | Versão 1: fenômeno simulado, topologia, os quatro estados, parâmetros, falhas, cronograma e rotulagem. |
| [v1/tabela_parametros.csv](v1/tabela_parametros.csv) | Parâmetros e intervalos de tempo de cada estado na v1. |
| [v1/configuracoes/](v1/configuracoes/) | JSONs da execução da v1: 10 sensores, 2 gateways, eventos, agendamento e papéis. |
| [v2/cenarios.md](v2/cenarios.md) | Versão 2: diagnóstico da v1, justificativa de cada mudança, variações e as execuções geradas. |
| [v2/gerar_cenarios.py](v2/gerar_cenarios.py) | Gera as configurações das execuções da v2 a partir de uma semente. |
| [v2/configuracoes/](v2/configuracoes/) | Uma pasta por execução (`execucao_01` a `execucao_08`) e o `resumo.json` com os parâmetros sorteados. |

## As duas versões

| | Versão 1 (`evento_termico_v1`) | Versão 2 (`evento_termico_v2`) |
|:--|:--|:--|
| Execuções | 1 | 8 (7 com desastre, 1 sem desastre) |
| Sensores | 10 (5 por gateway) | 8 a 12 (4 a 6 por gateway) |
| Carga inicial | 94–100% | 60–100%, sorteada por sensor |
| Duração das fases | 300 s cada | 210–360 s, sorteada por fase e execução |
| Papéis | Fixos e iguais nos dois grupos | Sorteados: afetados pela proximidade de um epicentro |
| Intensidade | Única | 0,7 a 1,3 da v1, com variação entre sensores |
| Perturbações benignas | Nenhuma | Congestionamentos de rede e aquecimentos locais no estado normal |

A justificativa de cada mudança está em [v2/cenarios.md](v2/cenarios.md). Em resumo, a v1 permitia que os modelos acertassem a fase só pelo nível de bateria (o *efeito relógio*) e não permitia testar em execuções novas.

## Configurações do simulador

Cada pasta de configuração (`v1/configuracoes/` e cada `v2/configuracoes/execucao_XX/`) tem a mesma estrutura:

| Arquivo ou pasta | Para que serve |
|:--|:--|
| `dispositivos/` | Um JSON por sensor, no estado normal inicial. |
| `gateways/gw01.json` e `gw02.json` | Lista de sensores que cada gateway consulta. |
| `agendamentos/` | Instante em que cada sensor recebe cada evento. |
| `papeis.json` | Papel de cada sensor: controle, degradação, falha energética ou falha de rede. |
| `fases.csv` (v2) | Início, fim e transição de cada fase da execução. Na v1, essa informação está em `v1/tabela_parametros.csv`. |

A v1 também guarda em `v1/configuracoes/eventos/` uma cópia de cada evento em arquivo próprio; o agendamento contém os mesmos eventos.

## Fases e rótulos

O rótulo é a fase global do ambiente no instante de envio da consulta, obtida da tabela de fases da execução — não de limiares sobre as leituras. Um sensor de controle com leituras normais durante o desastre recebe `desastre`. Na v1, as fases duram 300 s cada (0–300, 300–600, 600–900 e 900–1200 s); na v2, cada execução tem seus próprios limites. Os detalhes estão em [rotulacao.md](rotulacao.md).

Os valores são parâmetros de um evento térmico sintético, sem calibração física. Os JSONs são validados pelos modelos do simulador (`DeviceConfig` e `EventConfig`).

## Como usar

Para gerar de novo as configurações da v2 (a mesma semente produz os mesmos arquivos):

```bash
python3 cenarios/v2/gerar_cenarios.py              # 8 execuções, semente 20261015
python3 cenarios/v2/gerar_cenarios.py --help       # outras sementes, quantidades e portas
```

A execução dos cenários e a coleta seguem os comandos do `referencias/Manual_IoTEventSim.pdf`; os detalhes estão em [../dataset/README.md](../dataset/README.md).
