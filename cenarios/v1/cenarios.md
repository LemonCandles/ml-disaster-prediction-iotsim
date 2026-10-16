
Este documento define os cenários usados para gerar dados sintéticos com o IoTEventSim: os quatro estados do
ambiente, os parâmetros de cada um, a topologia simulada, as falhas injetadas e a forma de rotular as observações.
As configurações correspondentes estão em `configuracoes/`, a tabela quantitativa em `tabela_parametros.csv` e as
regras completas de rotulagem em `../rotulacao.md`.

As quatro classes adotadas são `normal`, `pre_desastre`, `desastre` e `pos_desastre`. Uma execução percorre todas
elas, representando a evolução do incidente e a continuidade do consumo energético. A definição das classes é
temporal e contextual: um erro de rede isolado não transforma automaticamente uma consulta em desastre.

A interpretação operacional dos parâmetros foi conferida diretamente no código do simulador
(`iot-sim-main/src/iot_sim/`), que é a referência para esta versão. A estrutura dos JSONs e os comandos seguem o
`referencias/Manual_IoTEventSim.pdf`, especialmente as seções 6, 10 e 13.

# Fenômeno e limites da representação

O cenário é um **evento térmico sintético com degradação da infraestrutura IoT**, identificador
`evento_termico_v1`. Ele representa, de forma simplificada, o aquecimento do ambiente monitorado durante um
incidente semelhante a um incêndio: as faixas de temperatura aumentam, a comunicação se degrada, o consumo
energético cresce e parte dos dispositivos deixa de responder. Após o período crítico, há recuperação da comunicação
e redução do aquecimento, com perdas permanentes de disponibilidade em alguns nós.

A escolha aproveita os componentes já implementados no simulador — temperatura, pressão, rede e bateria — e começa
por um cenário simples e documentado. Os valores são hipóteses de configuração, **sem calibração física** ou
validação meteorológica. Não representam limiares oficiais de incêndio nem critérios de alerta da Defesa Civil. O
simulador não modela combustão, propagação do fogo, chuva, vento, umidade, fumaça ou danos estruturais.

A pressão permanece entre 1000 e 1020 em todas as fases, como variável auxiliar sem relação programada com o
incidente. A anotação em hPa segue a convenção dos exemplos; o simulador trabalha com números sem validar unidades.
As temperaturas em °C também são uma convenção desta especificação.

Nesta versão, sensor e infraestrutura são alterados pelo mesmo roteiro de eventos. Portanto, uma associação
aprendida por um modelo refletirá inicialmente esse roteiro. Demonstrar utilidade em dados reais exigirá calibração e
avaliação adicionais. A superioridade dos atributos de rede e bateria é uma hipótese a investigar.

# Topologia experimental

São usados 10 dispositivos, organizados em dois grupos de cinco, com um gateway por grupo. Os dispositivos são
servidores CoAP; os gateways consultam suas URIs e publicam no broker MQTT. Essa montagem fornece uma instância local
de borda, agregação e publicação, sem modelagem adicional de atrasos ou recursos de uma nuvem remota.

| Elemento | Configuração |
|:--|:--|
| Host de execução | 127.0.0.1 |
| Gateway 1 | `gw01`, dispositivos nas portas UDP 7101–7105 |
| Gateway 2 | `gw02`, dispositivos nas portas UDP 7201–7205 |
| Recurso CoAP | `/device/data` |
| Intervalo solicitado de consulta | 5000 ms por dispositivo |
| Broker | `localhost:1883` |
| Tópicos MQTT | `/tcc/gw01/` e `/tcc/gw02/` |
| Duração | 1200 s, com 300 s por fase |
| Carga inicial | 94–100%, fixa por dispositivo |
| Localização | Dois agrupamentos ilustrativos próximos da coordenada de Uberlândia usada no manual |

As coordenadas são fixas e não controlam a propagação dos eventos; a seleção dos dispositivos afetados é explícita
no agendamento. Os UUIDs são distintos, o que permite relacionar configurações e registros. Cada arquivo em
`configuracoes/dispositivos/` informa o UUID, a porta, as coordenadas e os parâmetros iniciais do sensor.

Cada grupo contém os seguintes papéis:

| Dispositivo | Papel | Durante o desastre | Pós-desastre |
|:--|:--|:--|:--|
| d01 | Falha energética permanente | Recebe consumo acelerado; esgota a bateria | Continua indisponível |
| d02 | Falha de rede transitória | Perda configurada em 100% por 60 s | Retoma a comunicação e recebe a recuperação |
| d03 e d04 | Degradação | Temperatura, rede e consumo degradados | Recuperação parcial |
| d05 | Controle | Mantém os parâmetros normais | Mantém os parâmetros normais |

Assim, oito nós acompanham o incidente e dois são controles. A presença de controles evita que toda observação de
uma fase global tenha obrigatoriamente valores críticos. Os mesmos papéis nos dois grupos simplificam a verificação;
não constituem diversidade suficiente para avaliar generalização entre tipos de desastre.

# Descrição dos quatro cenários

## Normal

O intervalo inicial estabelece a referência de funcionamento. Todos os dispositivos começam com carga adequada,
temperatura entre 20 e 32 °C, baixa probabilidade de descarte e pequenos atrasos. Uma perda isolada ainda pode
acontecer, pois `drop_percentage` vale 1%. As taxas de consumo são pequenas e a disponibilidade esperada é alta.

O JSON de cada dispositivo representa esse estado inicial; não é necessário enviar um evento para defini-lo. Para uma
execução de controle sem desastre, iniciam-se dispositivos e gateways sem o agendamento. Nesse controle, todas as
consultas válidas recebem `normal`; o cronograma do ciclo completo não deve ser aplicado a uma execução que não
recebeu o incidente.

## Pré-desastre

Aos 300 s, os oito nós afetados recebem `pre_desastre`. Durante 180 s, os limites da distribuição de temperatura, a
probabilidade de descarte e as taxas de descarga caminham linearmente do estado normal para os novos valores. O alvo
é temperatura entre 26 e 40 °C, descarte de 8% e consumo maior que o normal.

O aumento é gradual nos parâmetros da distribuição, não necessariamente em cada leitura: um novo valor uniforme é
sorteado a cada resposta. No código atual, os perfis de atraso mudam de uma vez a partir de 50% da transição,
aproximadamente aos 390 s; a latência não aumenta continuamente durante toda a transição. Entre 480 e 600 s, os nós
permanecem no alvo do pré-desastre.

## Desastre

Aos 600 s, os oito nós afetados recebem `desastre`. A transição dura 30 s e termina aproximadamente aos 630 s. O
alvo é temperatura entre 34 e 52 °C, descarte de 35%, atrasos entre 0,8 e 4 s e consumo energético mais elevado.

Aos 690 s, são acrescentadas duas falhas por grupo: `d01` recebe uma taxa de descarga em repouso suficiente para
zerar a bateria no próximo ciclo de consumo, e `d02` recebe um evento transitório de perda em 100% por 60 s. Os
demais nós afetados continuam sob degradação, e os controles preservam as condições iniciais.

O objetivo é representar alterações intensas nos sensores, deterioração da rede, consumo acelerado e
disponibilidade parcial. A ocorrência de falhas não cria uma quinta classe; elas são manifestações do estado
`desastre`.

## Pós-desastre

Aos 900 s, os seis nós afetados que podem continuar funcionando recebem `pos_desastre`. A transição de recuperação
dura 120 s e termina aproximadamente aos 1020 s. O alvo é temperatura entre 25 e 39 °C, descarte de 10% e atrasos
menores que os do período crítico, mas superiores aos valores normais.

A descarga desacelera, sem recompor a carga perdida. Os dois nós com esgotamento energético permanecem
indisponíveis e não recebem POST de recuperação. Os dois nós com falha de rede transitória retornam ao perfil de
desastre aproximadamente aos 750 s e recebem a recuperação parcial aos 900 s.

A fase pós-desastre representa um ambiente em recuperação, não a restauração integral da infraestrutura. O histórico
da execução distingue o pós-desastre do pré-desastre, mesmo quando leituras individuais se sobrepõem.

# Tabelas de parâmetros

As tabelas descrevem os alvos dos nós afetados. Durante as transições, os valores são interpolados a partir do estado
vigente, conforme a implementação. Os nós de controle mantêm o alvo normal em todo o ciclo, e as falhas especiais
sobrescrevem somente os parâmetros informados em seus eventos.

| Cenário | Temperatura (°C) | Atraso (ms) | Descarte (%) | Bateria | Nós operacionais |
|:--|:--|:--|--:|:--|:--|
| `normal` | 20–32 | 20–500 | 1 | Inicial: 94–100% | 10 |
| `pre_desastre` | 26–40 | 100–1500 | 8 | Carga em redução | 10 |
| `desastre` | 34–52 | 800–4000 | 35 | Dois nós atingem 0% | 8; 6 na interrupção |
| `pos_desastre` | 25–39 | 150–1400 | 10 | Residual; dois em 0% | 8 |

O atraso e o descarte são valores configurados. "Nós operacionais" descreve condições de energia e conectividade
programadas, não uma garantia de resposta a todas as consultas. Os números do desastre valem após a aplicação das
falhas: oito nós após o esgotamento e seis durante a interrupção transitória da rede. As faixas de temperatura se
sobrepõem — 26–32 °C entre normal e pré-desastre, 34–40 °C entre pré-desastre e desastre, e grande sobreposição entre
pré e pós-desastre. Uma temperatura isolada não define todas as classes.

| Alvo | Descarga em repouso (p.p./min) | Custo por GET ou POST (p.p.) | Transição (s) |
|:--|--:|--:|--:|
| Normal | 0,02 | 0,01 | 0 |
| Pré-desastre | 0,20 | 0,06 | 180 |
| Desastre | 8,00 | 0,20 | 30 |
| Pós-desastre | 0,50 | 0,04 | 120 |

P.p. significa pontos percentuais da carga. A carga inicial é configurada apenas no `DeviceConfig`; os eventos
modificam as taxas de consumo, mas não definem `battery_charge`.

| Alvo | Perfil 1: peso; intervalo (s) | Perfil 2: peso; intervalo (s) | Média teórica do atraso (ms) |
|:--|:--|:--|--:|
| Normal | 90%; 0,02–0,12 | 10%; 0,12–0,50 | 94,0 |
| Pré-desastre | 80%; 0,10–0,60 | 20%; 0,60–1,50 | 490,0 |
| Desastre | 75%; 0,80–1,80 | 25%; 2,00–4,00 | 1725,0 |
| Pós-desastre | 70%; 0,15–0,60 | 30%; 0,60–1,40 | 562,5 |

Em cada resposta, o simulador escolhe um perfil pelos pesos e sorteia um atraso uniforme dentro dele. A média é
calculada por soma(peso / 100 × (min + max) / 2) e descreve apenas o atraso artificial configurado, não uma latência
medida. As mesmas informações, com unidades explícitas e os perfis completos, constam em `tabela_parametros.csv`.

# Falhas transitórias e permanentes

| Evento | Nós | Início (s) | Parâmetro alterado | Duração / retorno |
|:--|:--|--:|:--|:--|
| Rede transitória | d02 de ambos os grupos | 690 | Descarte de GET em 100% | 60 s; retorna aos parâmetros de desastre |
| Energia permanente | d01 de ambos os grupos | 690 | Descarga em repouso de 120 p.p./min | Zera no próximo consumo em repouso, em até ~60 s; sem retorno |

Os eventos de falha têm transição zero. `delay_profiles: []` significa preservar o perfil atual, não eliminar o
atraso. Os demais parâmetros permanecem como no estado de desastre.

A falha energética usa descarga acelerada para comprimir a demonstração em minutos. Como o simulador desconta o
consumo em repouso a cada 60 s desde o início do servidor, a bateria não zera necessariamente no instante do POST; o
tempo exato depende do alinhamento desse temporizador. Depois do esgotamento, o simulador recusa GET e POST com
`5.03 Service Unavailable`. A falha é permanente dentro da execução e não representa dano físico validado; reiniciar o
processo inicia uma nova execução com a carga inicial do JSON.

A falha transitória de rede continua recebendo POST, pois o descarte é aplicado ao GET. Seu retorno restaura os
parâmetros do evento anterior, sem recuperar a carga consumida. O agendamento evita novos eventos nesse nó até depois
da falha e do retorno.

# Cronograma

O tempo t = 0 é o início do coordenador de eventos (`ev-man`), depois que dispositivos e gateways estão prontos. Os
`time_ms` do agendamento são relativos a esse instante. Os intervalos são fechados no início e abertos no fim.

| Intervalo (s) | Fase global | Ação principal |
|:--|:--|:--|
| [0, 300) | `normal` | Referência sem eventos |
| [300, 480) | `pre_desastre` | Transição de entrada em 8 nós |
| [480, 600) | `pre_desastre` | Permanência no alvo |
| [600, 630) | `desastre` | Transição crítica em 8 nós |
| [630, 690) | `desastre` | Degradação estabelecida |
| [690, 750) | `desastre` | Falha transitória de rede e início do esgotamento |
| [750, 900) | `desastre` | Rede de d02 retorna ao perfil crítico; d01 sem energia |
| [900, 1020) | `pos_desastre` | Recuperação gradual em 6 nós |
| [1020, 1200) | `pos_desastre` | Recuperação parcial estabelecida |

O agendamento completo (`configuracoes/agendamentos/ciclo_completo.json`) contém 26 POSTs: 8 de pré-desastre, 8 de
desastre, 4 de falhas especiais e 6 de recuperação. Os instantes são planejados; o recebimento CoAP e o temporizador
energético introduzem pequenas diferenças. Uma execução só é considerada consistente depois de confirmar a aceitação
dos eventos e observar os comportamentos previstos. O coordenador termina após enviar os eventos de 900 s, mas a
coleta deve continuar até 1200 s.

# Rotulagem

O alvo é a **fase global do ambiente**, determinada pelo cronograma confirmado: cada consulta enviada em [0, 300)
recebe `normal`; em [300, 600), `pre_desastre`; em [600, 900), `desastre`; e em [900, 1200), `pos_desastre`.

O rótulo é atribuído pelo tempo de envio da consulta, relativo à origem registrada da execução:
`elapsed_s = (sent_time - t0_ns) / 10^9`, com `sent_time` em nanossegundos Unix, como no CSV do gateway. O campo
`timestamp` da resposta não é usado: em registros com erro, o gateway repete o de uma resposta anterior.

As transições pertencem à fase que está começando e são indicadas pela coluna auxiliar `em_transicao`. Um nó de
controle em funcionamento normal durante a fase crítica recebe `desastre`, pois a classificação identifica o estado
do ambiente, não o defeito individual do sensor. O papel do nó fica apenas nos metadados de auditoria. Como um
controle isolado pode não conter informação sobre a fase global, recomenda-se investigar também atributos agregados
por grupo ou janelas de observações.

Uma falha de comunicação não muda o rótulo temporal: é registrada como indisponibilidade daquela consulta, com
sensores e bateria ausentes. Consultas cuja resposta atravessa uma fronteira de fase são marcadas com `cruzou_fase`
e ficam fora do conjunto supervisionado principal. Falhas no envio de eventos ou ausência da origem temporal
invalidam a associação entre cronograma e execução. Os detalhes, exemplos de fronteira e cuidados com o CSV estão em
`../rotulacao.md`.

# Detecção e predição

Classificar uma consulta nas quatro fases é uma tarefa de **identificação do estado atual**; não demonstra, por si
só, antecipação de desastres. Uma extensão possível é um alvo de antecipação: dadas somente observações até o
instante t, prever se o ambiente estará em desastre após um horizonte de 60 s. Nesse caso, a janela de atributos
termina em t, o alvo é obtido do cronograma em t + 60, e amostras sem horizonte futuro observável são removidas.

`scenario_id`, horários absolutos e relativos, nomes dos eventos, identificadores e marcas de transição não entram nas
variáveis de treinamento, pois revelam o roteiro. Também não entram as taxas configuradas de perda e consumo: o modelo
deve receber medições disponíveis na coleta, não os parâmetros usados para construir o rótulo.

Para avaliar generalização, recomenda-se separar execuções completas entre treino e teste. Uma divisão aleatória de
linhas de um único ciclo mistura observações da mesma trajetória. Será necessário repetir o experimento com novas
inicializações e depois variar duração, intensidade, momento dos eventos e quantidade de nós afetados.

# Restrições do simulador

As configurações respeitam os modelos `DeviceConfig` e `EventConfig`. Os pontos abaixo exigem atenção ao executar e
organizar os dados:

1. **Unidades:** `delay_profiles.min/max` estão em segundos; `time_ms` e o intervalo do gateway, em milissegundos.
   `drop_percentage` usa a escala 0–100. A descarga em repouso é em p.p. por minuto; o custo de transmissão, em p.p.
   por operação processada.
2. **Perda e consulta:** o descarte simulado espera 20 s, e o gateway tem timeout de 15 s. Retransmissões CoAP e
   timeouts fazem a taxa de consultas malsucedidas diferir da probabilidade de descarte configurada.
3. **Frequência efetiva:** os 5000 ms são um intervalo solicitado. O gateway espera a resposta ou o timeout de cada
   dispositivo antes de seguir; não há garantia de uma linha por nó a cada 5 s durante a degradação.
4. **CSV e ausências:** o gateway usa `;` como delimitador. Após uma resposta prévia, erros são gravados com
   `error > 0`, `receipt_time = -1` e sensores e bateria em zero; esses zeros não são medições. Antes da primeira
   resposta bem-sucedida, uma tentativa com erro não gera linha, mas o `message_id` sequencial permite detectar essa
   perda. O CSV não distingue timeout de `5.03`; essa distinção aparece apenas na saída do gateway.
5. **Origem temporal:** o `ev-man` não grava um `t0_ns`. A coleta o registra com `date +%s%N` imediatamente antes de
   iniciar o coordenador e guarda a saída do `ev-man` com a aceitação dos POSTs.
6. **Dois gateways:** os CSVs usam o horário com resolução de segundos no nome. Os gateways devem ser iniciados com
   pelo menos 2 s de separação para não escreverem no mesmo arquivo.
7. **Carga e sementes:** não há campo de semente aleatória nem de recarga nos JSONs. Usar os mesmos JSONs não torna
   leituras e perdas idênticas entre execuções.

A latência de uma resposta válida é `(receipt_time - sent_time) / 10^6` ms. A ausência de resposta é censura por
timeout ou erro, não uma latência. Uma taxa empírica de falhas deve ser calculada sobre tentativas efetivamente
registradas, e não sobre uma grade de consultas fictícias.

# Critérios de aceite

A configuração deve atender aos seguintes critérios antes da geração de dados:

- Todos os arquivos de dispositivos e eventos são aceitos pelos modelos do simulador; portas e UUIDs são únicos;
  perfis de atraso têm pesos que somam 100.
- As listas dos gateways e os destinos dos eventos correspondem exatamente aos dispositivos definidos.
- Os controles não recebem eventos; os nós com falha energética não recebem recuperação; os eventos transitórios
  terminam antes de outro POST destinado ao mesmo nó.
- Os intervalos de rotulagem cobrem os 1200 s sem sobreposição nem lacunas.
- Em cada execução, os eventos são confirmados nos registros e os efeitos especiais são observados antes de aceitar os
  dados (verificações feitas por `dataset/organizar_dados.py`).

Os parâmetros têm sobreposição entre classes e mantêm controles, mas ainda podem produzir uma classificação fácil, o
que deve ser verificado pelos modelos. Refinamentos possíveis incluem execuções normais com perturbações benignas,
variação de intensidade e duração, mudança dos nós afetados e trajetórias em que rede e sensor não sejam degradados em
associação perfeita. A versão 2 (`../v2/cenarios.md`) implementa esses refinamentos.

# Fontes

- `referencias/TCC_v4.pdf`, seções 1.4 e 3.1: objetivos do estudo e comparação entre sensores e atributos de infraestrutura.
- `referencias/Manual_IoTEventSim.pdf`, seções 6, 10 e 13: estrutura dos JSONs, operação dos gateways e agendamento de eventos.
- Código do simulador em `iot-sim-main/src/iot_sim/`: `model.py`, `sensor.py`, `network.py`, `battery.py`, `sim.py`,
  `batch.py`, `gw.py` e `evman.py`.

As faixas e taxas deste documento foram propostas para esta versão experimental; não foram extraídas do artigo do
IoTEventSim.
