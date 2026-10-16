# Modelos

Análise exploratória, treinamento e avaliação de classificadores das fases `normal`, `pre_desastre`, `desastre` e `pos_desastre`, comparação entre as versões do dataset. Usa `dataset/v1/dataset.csv` e `dataset/v2/dataset.csv` sem alterá-los.

## O que há nesta pasta

| Arquivo ou pasta | Para que serve |
|:--|:--|
| [01_analise_exploratoria.ipynb](01_analise_exploratoria.ipynb) | Análise exploratória da v1: leitura, ausentes, exemplos por classe, séries temporais, distribuições e correlações. |
| [02_modelos_iniciais.ipynb](02_modelos_iniciais.ipynb) | Modelos na v1: pré-processamento, separação treino/teste, treinamento, métricas, matrizes de confusão, curvas ROC e AUC, conjuntos de atributos, importância e análise de erros. |
| [03_comparacao_versoes.ipynb](03_comparacao_versoes.ipynb) | Comparação v1 × v2: tabela das versões, efeito relógio da bateria, avaliação deixando uma execução de fora, alarmes falsos e respostas às perguntas de revisão do cenário. |
| [04_experimentos_finais.ipynb](04_experimentos_finais.ipynb) | Experimentos finais na v2: 7 modelos (incluindo SVM, Gradient Boosting e XGBoost) × 4 conjuntos de atributos × consulta isolada ou com janelas de 60 s, ajuste de hiperparâmetros, tabela comparativa, matrizes de confusão, F1 por classe e análise de erros. |
| [comum.py](comum.py) | Leitura das versões do dataset, grupos de atributos e estilo dos gráficos, usados pelos notebooks. |
| [janelas.py](janelas.py) | Atributos de janela de 60 s por sensor e por gateway, calculados só com resultados já conhecidos no instante de cada decisão. |
| [figuras/](figuras/) | Gráficos gerados pelos notebooks. |
| [resultados/](resultados/) | Tabelas de métricas exportadas pelos notebooks. |
| [requirements.txt](requirements.txt) | Versões das bibliotecas usadas. |

Os notebooks estão salvos já executados, com todas as saídas visíveis.

## Resumo dos resultados

### Versão 1 (notebooks 01 e 02)

Foram usadas 2.060 tentativas, retiradas as duas que cruzaram uma fronteira de fase. Os atributos são somente medições observáveis: `temperature`, `pressure`, `battery`, `latency_ms`, `available` e `drop_rate`. As medições ausentes por falha foram imputadas pela mediana do treino.

O protocolo principal treina com os sensores de um gateway e testa nos do outro, e vice-versa:

| Modelo | Acurácia | F1 macro | AUC macro (ROC) |
|:--|--:|--:|--:|
| Referência (classe majoritária) | 0,28 | 0,11 | 0,50 |
| Árvore de Decisão | 0,79 | 0,78 | 0,91 |
| **Random Forest** | **0,80** | **0,80** | **0,95** |
| Regressão Logística | 0,64 | 0,63 | 0,86 |
| KNN | 0,62 | 0,61 | 0,79 |

As matrizes de confusão dos quatro modelos estão em `figuras/modelos_matrizes_confusao.png` (por gateway) e `figuras/modelos_matrizes_confusao_aleatorio.png` (aleatório). As curvas ROC um-contra-todos estão em `figuras/modelos_roc.png`, e as AUCs por classe em `resultados/auc_roc.csv`.

- Somente com sensores, o F1 macro fica entre 0,34 e 0,42. Com sensores e rede, sobe para até 0,56. Com todos os atributos, chega a 0,80.
- **A bateria sozinha atinge 0,71.** Em uma única execução, ela decresce monotonicamente e funciona como um relógio do ciclo. Por isso, os resultados são otimistas e não mostram generalização. O notebook discute esse efeito e propõe como tratá-lo.
- A divisão aleatória 70/30 deu resultados próximos aos da divisão por gateway (Random Forest 0,79), e a validação cruzada de 5 partes, 0,82 ± 0,01. Nesta execução, compartilhar sensores entre treino e teste inflou pouco o resultado.

### Versão 2 e comparação (notebook 03)

Na v2, os modelos são treinados com sete execuções e testados na oitava, que não viram, e as previsões das oito rodadas são reunidas. Random Forest, F1 macro:

| Atributos | v1 (por gateway) | v2 (uma execução de fora) |
|:--|--:|--:|
| Sensores | 0,42 | 0,33 |
| Sensores + rede | 0,54 | 0,44 |
| Apenas nível de bateria | 0,71 | 0,34 |
| Sensores + rede + nível de bateria | 0,80 | 0,50 |
| Sensores + rede + taxa de bateria | 0,73 | **0,55** |

- **O efeito relógio desapareceu na v2**: o nível de bateria sozinho cai de 0,71 para 0,34, perto do acaso (0,25). A taxa de descarga (`battery_rate_pp_min`) é o substituto útil.
- **Rede e bateria continuam ajudando**: sensores 0,33 → com rede 0,44 → com taxa de bateria 0,55.
- **Os controles limitam a classificação por consulta**: eles somam 43% das consultas das fases críticas e quase sempre são previstos como `normal`. Nos sensores afetados, o F1 macro é 0,78.
- **Alarmes falsos**: na execução sem desastre, 32% das consultas foram classificadas como alguma fase de desastre.
- A divisão aleatória 70/30 da v2 dá 0,65, contra 0,55 com execuções separadas.

### Experimentos finais (notebook 04)

Dataset v2, sempre testando em uma execução que o modelo não viu. Configuração principal: sensores + rede + bateria (taxa de descarga), com janelas de 60 s do sensor e do gateway.

| Modelo | F1 macro | Acurácia | F1 por execução | Alarmes falsos (execução sem desastre) |
|:--|--:|--:|--:|--:|
| **Random Forest** | **0,82** | **0,84** | 0,81 ± 0,04 | 2,0% |
| SVM | 0,81 | 0,83 | 0,80 ± 0,03 | 0,0% |
| Gradient Boosting | 0,79 | 0,82 | 0,79 ± 0,03 | 5,7% |
| XGBoost | 0,79 | 0,81 | 0,79 ± 0,05 | 8,6% |
| Regressão Logística | 0,79 | 0,81 | 0,77 ± 0,04 | 2,1% |
| KNN | 0,77 | 0,80 | 0,77 ± 0,04 | 1,0% |
| Árvore de Decisão | 0,70 | 0,72 | 0,69 ± 0,06 | 19,3% |

Hiperparâmetros padrão; o ajuste por validação cruzada agrupada por execução muda o F1 macro em no máximo 0,01.

- **As janelas são o maior ganho:** +0,20 a +0,30 de F1 macro em todos os modelos (Random Forest: 0,55 → 0,82). Os controles, antes quase sempre previstos como `normal`, passam a acertar de 61% a 83% das fases críticas.
- **Rede e bateria melhoram todos os modelos.** Com janelas, o F1 macro vai de 0,56–0,66 (só sensores) a 0,70–0,82 (conjunto completo).
- **Atributos mais importantes:** temperatura máxima do gateway, taxa de descarga (do gateway e do sensor) e fração de falhas do gateway.
- **Erros restantes:** concentram-se no primeiro minuto de cada fase, porque a janela ainda contém a fase anterior. O pós-desastre é confundido com o desastre (23%), e o pré-desastre com o normal (12%).

## Como reproduzir

Na raiz do repositório:

```bash
uv venv modelos/.venv
uv pip install --python modelos/.venv/bin/python -r modelos/requirements.txt

cd modelos
.venv/bin/jupyter nbconvert --to notebook --execute --inplace 01_analise_exploratoria.ipynb
.venv/bin/jupyter nbconvert --to notebook --execute --inplace 02_modelos_iniciais.ipynb
.venv/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 03_comparacao_versoes.ipynb  # cerca de 4 min
.venv/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=7200 04_experimentos_finais.ipynb  # cerca de 45 min
```

