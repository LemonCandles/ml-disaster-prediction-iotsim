---
title: "Cenários de desastre no IoTEventSim — versão 2"
subtitle: "Cenário evento_termico_v2: variações entre execuções e justificativa das mudanças"
author: "Cassio Lima Silva"
date: "15 de outubro de 2026"
---

# Objetivo

A versão 2 (`evento_termico_v2`) refina o cenário da versão 1 (`cenarios/v1/cenarios.md`) a partir do que os
primeiros modelos revelaram. O fenômeno, as quatro classes e a forma de rotular continuam os mesmos; o que muda é que
o cenário deixa de ser **uma única execução fixa** e passa a ser um **conjunto de execuções diferentes entre si**,
geradas por `gerar_cenarios.py` com semente fixa. Cada execução tem seus próprios JSONs em
`configuracoes/execucao_XX/`.

# Diagnóstico da versão 1

A análise da v1 (`modelos/02_modelos_iniciais.ipynb`) respondeu às perguntas de revisão do cenário:

| Pergunta | O que a v1 mostrou |
|:--|:--|
| Há exemplos suficientes em cada classe? | Sim para uma primeira análise: 21% a 28% por classe (2.062 linhas). Mas todas vêm de um único ciclo. |
| Os rótulos fazem sentido? | Sim: as fases seguem o cronograma confirmado nos registros, e as falhas aparecem onde foram programadas. |
| O cenário é fácil ou artificial demais? | Artificial em três pontos: tempos fixos, papéis idênticos e fixos nos dois grupos, e sensor e rede sempre degradados juntos. |
| Os modelos aprendem algo relevante ou uma regra trivial? | Em boa parte, uma regra trivial: **só a bateria** dá F1 macro 0,71 (completo: 0,80). |
| É preciso variar os parâmetros? | Sim: com uma execução não há como medir generalização. |

**O efeito relógio.** Todos os sensores começam com carga entre 94% e 100%, e a carga só diminui. Em um ciclo de
tempos fixos, o nível de bateria indica quanto tempo se passou e, portanto, a fase. Os sensores de controle, cujas
leituras são normais o tempo todo, foram classificados corretamente em 74% das consultas do pré-desastre e 67% das do
desastre — o que só a bateria explica. Esse atalho não existiria em uma rede real, em que cada sensor tem uma carga
diferente.

# O que muda e por quê

| Problema na v1 | Mudança na v2 |
|:--|:--|
| Uma única execução; não há como testar em execuções novas | 8 execuções completas, cada uma com sua semente: 7 com desastre e 1 sem desastre |
| Carga inicial quase igual (94–100%) e consumo idêntico: bateria vira relógio | Carga inicial sorteada por sensor entre 60% e 100%; taxas de consumo normais variam ±50% |
| Tempos fixos (300 s por fase): tempo e carga alinhados entre execuções | Duração de cada fase sorteada (normal 240–360 s, pré 210–330 s, desastre 240–360 s, pós 240–360 s) e transições variáveis |
| Papéis fixos e espelhados (`d01` sempre perde energia, `d05` sempre é controle) | Papéis sorteados: os sensores afetados são os mais próximos de um epicentro sorteado; falhas atribuídas com probabilidade |
| 10 sensores sempre | 4 a 6 sensores por gateway (8 a 12 por execução) |
| Intensidade única | Intensidade do evento por execução entre 0,7 e 1,3 da v1, com variação de ±15% entre sensores |
| Falhas sempre aos 690 s | Momento das falhas sorteado dentro do desastre; duração da falha de rede entre 40 e 90 s |
| Sensor e rede sempre degradados juntos | Perturbações benignas no estado normal: congestionamento de rede sem calor e aquecimento local sem falha de rede, rotulados `normal` |
| Toda execução contém desastre | Uma execução inteira sem desastre (só `normal`, com perturbações benignas), para medir alarmes falsos |

O que **não** muda: o simulador e seus modelos, o intervalo de consulta de 5 s com *timeout* de 15 s, a forma de
coleta com os comandos do manual, as quatro classes, a regra de rotulagem pelo tempo de envio (`cenarios/rotulacao.md`)
e a pressão entre 1000 e 1020 hPa, mantida como atributo sem relação com o evento.

# Parâmetros em função da intensidade

Cada sensor afetado recebe uma intensidade *i* = (intensidade da execução) × U(0,85; 1,15). Com *i* = 1, os alvos de
temperatura, descarte e atraso são os da v1:

| Fase | Temperatura (°C) | Descarte (%) | Atraso | Descarga em repouso (p.p./min) | Custo por GET (p.p.) |
|:--|:--|:--|:--|:--|:--|
| `normal` | 19–21 a 31–33 (por sensor) | 1 | perfis da v1 | 0,02 × U(0,5; 1,5) | 0,01 × U(0,5; 1,5) |
| `pre_desastre` | 22 + 4*i* a 32 + 8*i* | 8*i* | perfis da v1 × *i* | 0,2*i* | 0,06*i* |
| `desastre` | 26 + 8*i* a 36 + 16*i* | 35*i* (máx. 60) | perfis da v1 × *i* | 4*i* | 0,1*i* |
| `pos_desastre` | 20 + 5*i* a 31 + 8*i* | 10*i* | perfis da v1 × *i* | 0,5 | 0,04 |

A descarga no desastre foi reduzida (v1: 8 p.p./min e 0,2 p.p. por GET) porque as cargas iniciais agora podem ser
baixas: com os valores da v1, sensores começando em 60% se esgotariam sem planejamento. As falhas especiais seguem a
v1: a falha energética usa descarga de 120 p.p./min e não tem retorno; a falha de rede é transitória, com descarte de
100%.

# Papéis e epicentro

Em cada execução, um epicentro é sorteado entre os dois grupos (±0,006° em torno do ponto médio). Em cada gateway,
de 2 até *n* − 1 sensores mais próximos do epicentro são afetados, e os demais são controles — sempre há ao menos um
controle por grupo. Entre os afetados de cada gateway, um sofre falha energética com probabilidade 0,5 e outro sofre
falha de rede com probabilidade 0,6; os restantes passam por degradação. Toda execução com desastre tem pelo menos uma
falha. O papel de cada sensor fica em `papeis.json`, usado apenas na auditoria (coluna `device_role` do dataset).

# Perturbações benignas

Durante o estado normal, cada execução com desastre recebe, com probabilidade 0,7, um ou dois congestionamentos de
rede (descarte de 30–60% e atrasos de 0,3–2,5 s por 40–80 s, sem mudar a temperatura) e, com probabilidade 0,6, um
aquecimento local (faixa de temperatura que começa entre 29 e 33 °C e termina 8 a 12 °C acima, por 40–80 s, sem mudar a rede). A execução sem desastre
recebe dois ou três congestionamentos e um ou dois aquecimentos ao longo de 1200 s. Esses eventos não mudam o rótulo:
o ambiente continua `normal`. Eles existem para que uma falha de rede isolada ou uma leitura quente isolada não sejam,
por si sós, sinal de desastre.

# Execuções geradas

| Exec. | Sensores | Int. | Normal | Pré | Des. | Pós | Contr. | Degr. | Energia | Rede | Benig. |
|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 01 | 4 + 6 | 1,24 | 360 | 300 | 360 | 300 | 2 | 7 | 0 | 1 | 3 |
| 02 | 5 + 5 | 0,88 | 270 | 300 | 330 | 360 | 5 | 3 | 1 | 1 | 2 |
| 03 | 4 + 4 | 0,92 | 240 | 270 | 330 | 270 | 3 | 3 | 2 | 0 | 3 |
| 04 | 6 + 5 | 0,76 | 300 | 330 | 330 | 270 | 5 | 4 | 1 | 1 | 0 |
| 05 | 5 + 5 | 1,29 | 270 | 300 | 360 | 330 | 3 | 4 | 1 | 2 | 2 |
| 06 | 6 + 6 | 0,75 | 270 | 270 | 300 | 270 | 6 | 3 | 1 | 2 | 1 |
| 07 | 6 + 5 | 1,08 | 330 | 210 | 330 | 300 | 3 | 6 | 1 | 1 | 1 |
| 08 | 5 + 6 | — | 1200 | — | — | — | 11 | 0 | 0 | 0 | 3 |

Sensores: gw01 + gw02. Int.: intensidade. Durações das fases em segundos. Contr., Degr., Energia e Rede: quantidade de
sensores de controle, com degradação, com falha energética e com falha de rede. Benig.: perturbações benignas. O resumo completo, com transições e epicentros, está em `configuracoes/resumo.json`.

# Arquivos de cada execução

| Dentro de `configuracoes/execucao_XX/` | Conteúdo |
|:--|:--|
| `dispositivos/` | Um JSON por sensor, com porta própria (as execuções podem rodar ao mesmo tempo). |
| `gateways/gw01.json`, `gw02.json` | Sensores consultados por cada gateway. |
| `agendamentos/ciclo.json` | Todos os eventos da execução, com o instante de envio. |
| `fases.csv` | Início, fim e transição de cada fase: a tabela usada na rotulagem desta execução. |
| `papeis.json` | Papel de cada sensor (controle, degradação, falha energética, falha de rede). |

# Rotulagem e uso

As regras de `cenarios/rotulacao.md` continuam valendo, com a tabela de fases de cada execução no lugar dos limites
fixos de 300, 600 e 900 s. A coluna `device_role` e as demais informações de roteiro continuam fora do treinamento.

Com várias execuções, a avaliação dos modelos deve separar **execuções inteiras** entre treino e teste, por exemplo,
deixando uma execução de fora por vez. A taxa de descarga observada (`battery_rate_pp_min`) é uma alternativa ao nível
absoluto da bateria: mede o consumo recente, que depende da fase, sem depender da carga inicial.

# Efeito das mudanças

As oito execuções foram coletadas e organizadas em `dataset/v2/` (17.812 linhas), e todas passaram nas verificações
do roteiro. A comparação com a v1 está em `modelos/03_comparacao_versoes.ipynb`. Com o Random Forest, testado em uma
execução que não viu:

| Atributos | v1 (mesma execução) | v2 (execução nova) |
|:--|--:|--:|
| Apenas nível de bateria | 0,71 | 0,34 |
| Sensores + rede + nível de bateria | 0,80 | 0,50 |
| Sensores + rede + taxa de bateria | 0,73 | 0,55 |
| Sensores | 0,42 | 0,33 |

O atalho do nível de bateria desapareceu: sozinho, ele cai de 0,71 para 0,34, próximo do acaso (0,25). O desempenho restante vem de
sinais ligados ao fenômeno — rede, taxa de descarga e temperatura. A v2 também expôs um limite da classificação por
consulta: os controles, que não mudam com a fase, somam 43% das consultas das fases críticas e são quase sempre
classificados como `normal`. Nos sensores afetados, o F1 macro é 0,78. Isso indica que a próxima melhoria está na
unidade de decisão (janelas de tempo e agregação por gateway), e não em novas variações do cenário. Essa mudança foi
feita em `modelos/04_experimentos_finais.ipynb`: com janelas de 60 s do sensor e do gateway, o Random Forest chega a
0,82 na mesma avaliação.

# Limites

O cenário continua sintético e sem calibração física: as variações tornam o problema menos previsível, mas não o
aproximam de dados reais. As perturbações benignas e o epicentro são hipóteses de modelagem. Oito execuções ainda são
poucas para estimativas precisas de desempenho; o gerador permite produzir mais com outras sementes.
