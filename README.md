# ml-disaster-prediction-iotsim

Repositório do TCC: Modelagem preditiva de desastres naturais integrando algoritmos de aprendizado de máquina e simulações de IoT (IoTSim)

O trabalho usa o simulador IoTEventSim para criar cenários de desastre em uma rede IoT, gerar datasets rotulados a partir das simulações e avaliar classificadores na identificação das fases `normal`, `pre_desastre`, `desastre` e `pos_desastre`.

## Estrutura

| Pasta ou arquivo | Para que serve |
|:--|:--|
| [cenarios/](cenarios/) | Definição dos cenários (versões v1 e v2): estados, parâmetros, configurações JSON do simulador e regras de rotulagem. |
| [dataset/](dataset/) | Coleta com o IoTEventSim, registros brutos, script de organização, datasets rotulados (v1 e v2) e dicionário de dados. |
| [modelos/](modelos/) | Análise exploratória, modelos de classificação, comparação entre versões, experimentos finais, figuras e tabelas. |
| [reproduzir.sh](reproduzir.sh) | Reproduz o trabalho por etapas (ver *Como reproduzir*). |
| `iot-sim-main/` | Cópia local do simulador ([paulo-coelho/iot-sim](https://github.com/paulo-coelho/iot-sim)); não versionada aqui, ver *Requisitos*. |
| [referencias/](referencias/) | Manual do simulador e versão atual da monografia (`TCC_v4.pdf`). |

Cada pasta tem um README com o conteúdo, os principais resultados e os comandos daquela parte.

## Fluxo

1. **Cenários** — `cenarios/v1/` e `cenarios/v2/` descrevem os sensores, gateways e eventos de cada execução; `cenarios/rotulacao.md` define os rótulos.
2. **Dataset** — o simulador é executado com os comandos do manual, e `dataset/organizar_dados.py` transforma os registros dos gateways em `dataset/v1/dataset.csv` e `dataset/v2/dataset.csv`.
3. **Modelos** — os notebooks em `modelos/` leem os datasets, treinam os classificadores, comparam as versões e geram as figuras e tabelas dos resultados.

## Requisitos

| Para | É preciso |
|:--|:--|
| Gerar cenários e organizar os dados | Python 3.12 ou mais recente (só a biblioteca padrão) |
| Coletar dados | O IoTEventSim no commit `87015b6` (21/07/2026), com Python 3.12 e [uv](https://docs.astral.sh/uv/); o broker Mosquitto em `localhost:1883` |
| Executar os notebooks | Python 3.12 ou mais recente e `uv`; as versões das bibliotecas estão em `modelos/requirements.txt` |

O simulador tem repositório Git próprio e não faz parte deste. Todas as coletas usaram o commit `87015b644e5dc868efe7b8aa7fe48c98a9172291`, sem alterações locais; `./reproduzir.sh simulador` clona e instala exatamente essa versão.

## Como reproduzir

Os datasets e os registros brutos das coletas estão versionados. Assim, as análises podem ser reproduzidas sem executar o simulador:

```bash
./reproduzir.sh tudo        # organiza os dados, executa os quatro notebooks (cerca de 50 min)
```

Para reproduzir também a geração dos dados, as etapas são, em ordem:

```bash
./reproduzir.sh simulador   # clona o IoTEventSim na versão usada e instala seu ambiente
./reproduzir.sh cenarios    # gera as configurações da v2 (mesma semente, mesmos arquivos)
sudo service mosquitto start
./reproduzir.sh coleta-v2   # oito coletas em paralelo, cerca de 25 min
./reproduzir.sh organizar   # registros brutos -> dataset/v1 e dataset/v2
./reproduzir.sh modelos     # ambiente de modelagem e os quatro notebooks
```

A coleta recusa pastas que já tenham registros: para coletar de novo, mova ou apague `dataset/v2/coleta/` antes. Uma nova coleta gera medições diferentes, porque o simulador sorteia leituras, perdas e atrasos sem semente fixa; o processo e as verificações são os mesmos. A coleta da v1, feita à mão, terminal por terminal, está descrita em `dataset/README.md`.

O que se reproduz de forma exata:

- **Configurações da v2:** a mesma semente gera os mesmos arquivos.
- **Datasets:** organizar os mesmos registros brutos gera os mesmos CSVs (os hashes estão em `dataset/*/execucao.json`).
- **Resultados dos notebooks:** as sementes são fixas, então os notebooks reproduzem as mesmas métricas.

## Conteúdo exigido pelo plano

| Item do plano | Onde está |
|:--|:--|
| Arquivos de configuração dos cenários | `cenarios/v1/configuracoes/`, `cenarios/v2/configuracoes/` e o gerador `cenarios/v2/gerar_cenarios.py` |
| Scripts de execução | `dataset/coletar_execucao.sh` (comandos do manual para uma execução) e `reproduzir.sh` |
| Scripts de coleta | `dataset/coletar_execucao.sh`; os comandos manuais estão em `dataset/README.md` |
| Scripts de pré-processamento | `dataset/organizar_dados.py` (limpeza, rotulagem e conferência) e `modelos/janelas.py` (atributos de janela) |
| Notebooks de análise | `modelos/01_analise_exploratoria.ipynb`, `modelos/03_comparacao_versoes.ipynb` |
| Notebooks de aprendizado de máquina | `modelos/02_modelos_iniciais.ipynb`, `modelos/04_experimentos_finais.ipynb` |
| Datasets ou instruções para gerá-los | `dataset/v1/`, `dataset/v2/` (datasets e registros brutos) e as instruções acima |
| README explicando como reproduzir | Este arquivo e os READMEs de cada pasta |
