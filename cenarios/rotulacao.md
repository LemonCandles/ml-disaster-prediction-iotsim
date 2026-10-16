# Rotulagem dos cenários

O alvo principal identifica a **fase global do ambiente** em cada execução dos cenários `evento_termico_v1` e `evento_termico_v2`. Os rótulos vêm do roteiro de eventos confirmado, não de limiares aplicados às temperaturas, baterias ou erros. Isso permite avaliar se as observações disponíveis explicam a fase sem usar uma regra que já defina a resposta.

## Regras temporais

| Tempo relativo de envio | Rótulo planejado | Interpretação |
|:--|:--|:--|
| `0 <= t < 300` | `normal` | Referência anterior ao incidente |
| `300 <= t < 600` | `pre_desastre` | Entrada gradual e permanência em degradação inicial |
| `600 <= t < 900` | `desastre` | Período crítico, incluindo falhas |
| `900 <= t < 1200` | `pos_desastre` | Recuperação parcial |

A tabela acima é a da v1 (`v1/tabela_parametros.csv`). Na v2, cada execução tem sua própria tabela em `v2/configuracoes/execucao_XX/fases.csv`, com a mesma estrutura; a execução sem desastre tem apenas a fase `normal`. As regras abaixo valem para ambas, trocando 300, 600, 900 e 1200 s pelos limites da execução. Os exemplos de fronteira usam os limites da v1.

O tempo zero é registrado no início do coordenador de eventos. Se o gateway usa `sent_time` em nanossegundos Unix e o registro da execução contém `t0_ns`, calcula-se:

```text
elapsed_s = (sent_time - t0_ns) / 1_000_000_000
```

O `ev-man` não registra essa origem automaticamente. Por isso, a coleta grava `t0_ns` com `date +%s%N` imediatamente antes de iniciar o `ev-man` (ver [../dataset/README.md](../dataset/README.md)), e a organização confere esse instante com o horário em que os sensores registraram os eventos. A reprodução inicial usa processos na mesma máquina; em uma execução distribuída, também seria necessário verificar a sincronização dos relógios.

O campo `timestamp` da resposta não é a origem da rotulagem: em uma falha, o gateway pode reutilizar o timestamp de uma resposta anterior. Um evento `transient` ou `permanent` descreve o mecanismo de alteração, não a classe. O `status` expõe o nome do evento e só deve servir à auditoria.

## Exemplos de fronteira

| `elapsed_s` | `label_planejado` | `em_transicao` |
|--:|:--|:--|
| 0 | `normal` | falso |
| 299,999 | `normal` | falso |
| 300 | `pre_desastre` | verdadeiro |
| 479,999 | `pre_desastre` | verdadeiro |
| 480 | `pre_desastre` | falso |
| 600 | `desastre` | verdadeiro |
| 630 | `desastre` | falso |
| 690 | `desastre` | falso |
| 900 | `pos_desastre` | verdadeiro |
| 1020 | `pos_desastre` | falso |
| 1200 | Fora do intervalo; não atribuir rótulo | — |

`em_transicao` marca a transição da fase global. Os controles não mudam de parâmetros, mas recebem a mesma marca temporal de auditoria. No caso de consultas válidas cujo recebimento ocorre em outra fase, definir `cruzou_fase = true`. Para a primeira avaliação, excluir essas consultas do conjunto supervisionado principal e preservar os registros brutos. Não calcular fase de recebimento quando `receipt_time = -1`.

Esses tempos são planejados. Se um POST chegar atrasado, a transição física começa no recebimento. Uma execução com atrasos relevantes, rejeição de eventos ou ausência de confirmação deve ser revisada antes da rotulagem definitiva. A primeira versão recomenda repetir a execução quando o roteiro não for cumprido, mantendo os logs da tentativa descartada.

## Fase global, dispositivo e disponibilidade

Um sensor de controle pode reportar 24 °C e bateria alta durante o desastre. Seu rótulo principal ainda é `desastre`: o ambiente está na fase crítica, mesmo que aquele sensor não esteja diretamente afetado. O campo `device_role` explica essa situação na auditoria. Não se promete distinguir a fase global a partir de toda leitura isolada; agregações de dispositivos e histórico temporal podem ser necessárias.

`available` é uma variável observada por tentativa, independente da classe. Será 1 quando a consulta produzir uma resposta válida e 0 quando não houver resposta utilizável no timeout ou ocorrer erro. Falha energética permanente e perda transitória durante o desastre compartilham o mesmo rótulo principal.

A cópia atual do gateway grava zeros em sensores e bateria depois de erros, reaproveitando uma resposta anterior. Na organização do dataset, linhas com `error > 0` devem ter essas medições tratadas como ausentes, e não como temperatura de 0 °C ou bateria efetivamente zerada. `receipt_time = -1` também é ausência. Apenas uma resposta válida ou evidência separada dos logs pode confirmar carga real de 0%.

Antes da primeira resposta bem-sucedida, algumas tentativas com erro não são gravadas pelo gateway. Não se pode estimar disponibilidade corretamente ignorando essas tentativas. Como o gateway numera todas as tentativas (`message_id`), inclusive as não gravadas, e imprime o tipo de cada falha na ordem em que ocorre, a organização do dataset verifica se alguma tentativa não gravada pode ter ocorrido depois de `t0`. Iniciar os gateways pelo menos 1 minuto antes de `t0` torna essa perda praticamente impossível (ver `dataset/README.md`). A cadência de 5 s não autoriza fabricar amostras: timeouts tornam a frequência efetiva irregular.

## Metadados e rótulo definitivo

Conservar para auditoria `run_id`, `scenario_id`, dispositivo, gateway, papel do dispositivo, parâmetros, origem temporal, tempo relativo, fase, marca de transição e evidência de aceitação dos eventos. O `run_id` identifica uma inicialização completa e deve mudar quando dispositivos forem reiniciados.

Aplicar a tabela temporal para obter **`label_planejado`**. Esse campo passa a **`label`** somente depois de verificar:

1. A origem temporal foi registrada e corresponde ao agendamento executado.
2. Os POSTs necessários foram aceitos com resposta CoAP de sucesso; a mensagem de envio deve ser examinada junto ao código retornado. Um POST apenas tentado não confirma a alteração.
3. As falhas de rede e energia tiveram os efeitos previstos, e a execução continuou até o fim do pós-desastre.
4. As consultas pertencem à execução correta; aquecimento anterior a `t0` e registros depois do fim da última fase foram separados.

O registro temporal não confirma sozinho a aplicação dos eventos: os logs do coordenador e dos dispositivos também são necessários.

Na execução sem desastre da v2 (`execucao_08`), não há mudança de fase: o `fases.csv` tem só a fase `normal`, e todas as consultas do ciclo recebem esse rótulo, inclusive durante as perturbações benignas.

## Atributos e prevenção de vazamento

Os conjuntos de atributos comparados nos modelos seguem a proposta do TCC:

- sensores: temperatura e pressão;
- sensores e bateria: adicionar carga observada e, quando possível, variação histórica;
- sensores e rede: adicionar latência medida, disponibilidade e taxa empírica de falhas em janela;
- combinação completa: reunir os atributos anteriores.

Excluir do treinamento o rótulo e os metadados que revelam o roteiro: `scenario_id`, `run_id`, fase, tempo relativo, horários absolutos, `event_name`, `event_type`, `status`, marca de transição, número da mensagem e identificadores. Também excluir coordenadas e papel do dispositivo: na v1 são fixos e associados aos nós escolhidos para falhar; na v2, os papéis decorrem da distância ao epicentro, e as coordenadas os revelariam.

Os valores configurados de `drop_percentage` e das taxas de bateria são informações de geração, não medições observadas. Não devem entrar no treinamento. A taxa empírica de falhas é outra variável: deve usar somente tentativas disponíveis até o instante da previsão, sobre uma janela previamente definida.

Separar execuções completas entre treino e teste. Ajustar imputação, normalização e outros transformadores somente no treino. Uma única execução serve para verificar a geração, mas não demonstra generalização.

## Detecção atual e antecipação futura

O esquema de quatro classes identifica o estado atual. Para uma tarefa posterior de antecipação, propõe-se horizonte de 60 s e alvo binário `desastre_em_60s`: 1 quando `label(t + 60) == desastre`, 0 nos demais casos com futuro observável. Esse alvo não é sinônimo de “início de desastre nos próximos 60 s”: também será 1 para parte das consultas já dentro da fase crítica.

Se a pergunta for especificamente prever **o início**, será necessário definir outro alvo: 1 quando o início do desastre ocorrer em `(t, t + 60]`, usando somente amostras anteriores ao desastre. Distinguir as duas tarefas evita apresentar reconhecimento de um evento já ativo como alerta antecipado.

Em ambas as tarefas, atributos de janelas devem conter somente observações disponíveis até `t`, incluindo o instante de recebimento. Remover amostras cujo alvo esteja depois do fim da execução. Dados e horizontes futuros de uma mesma janela não podem atravessar a divisão treino/teste.
