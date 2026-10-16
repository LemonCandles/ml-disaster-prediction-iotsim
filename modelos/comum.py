"""Definições compartilhadas pelos notebooks de análise e modelagem.

Centraliza a leitura das versões do dataset (dataset/v1, dataset/v2), os grupos de atributos
e o estilo dos gráficos, para que os notebooks usem exatamente as mesmas regras.
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

PASTA = Path(__file__).resolve().parent
REPO = PASTA.parent
DATASETS = REPO / "dataset"
FIGURAS = PASTA / "figuras"
RESULTADOS = PASTA / "resultados"

# Ordem cronológica das fases; usada em tabelas, gráficos e matrizes de confusão.
CLASSES = ["normal", "pre_desastre", "desastre", "pos_desastre"]
NOMES_CLASSES = {
    "normal": "Normal",
    "pre_desastre": "Pré-desastre",
    "desastre": "Desastre",
    "pos_desastre": "Pós-desastre",
}
# Fases da v1 (fixas); na v2 cada execução tem sua própria tabela em cenarios/v2/configuracoes/.
FASES = [(0, 300, "normal"), (300, 600, "pre_desastre"), (600, 900, "desastre"), (900, 1200, "pos_desastre")]

# Papéis dos sensores (coluna device_role, só para auditoria).
PAPEIS = {
    "falha_energetica": "Falha energética",
    "falha_rede": "Falha de rede",
    "degradacao": "Degradação",
    "controle": "Controle",
}
ORDEM_PAPEIS = list(PAPEIS.values())

# Atributos observáveis permitidos por cenarios/rotulacao.md (sem tempo, eventos ou identificadores).
SENSORES = ["temperature", "pressure"]
BATERIA = ["battery"]
REDE = ["latency_ms", "available", "drop_rate"]
CONJUNTOS = {
    "Sensores": SENSORES,
    "Sensores + bateria": SENSORES + BATERIA,
    "Sensores + rede": SENSORES + REDE,
    "Sensores + rede + bateria": SENSORES + REDE + BATERIA,
}
# Alternativa ao nível de bateria: taxa de descarga observada nos últimos 60 s ou mais.
TAXA_BATERIA = ["battery_rate_pp_min"]

# Paleta categórica de referência (validada para daltonismo nos quatro primeiros slots adjacentes).
SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_SEC = "#52514e"
GRADE = "#e4e3df"
CATEGORICA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
COR_CLASSE = dict(zip(CLASSES, CATEGORICA))
COR_PAPEL = dict(zip(ORDEM_PAPEIS, CATEGORICA))
SEQUENCIAL = "Blues"


def carregar_dados(versao="v1", incluir_cruzamentos=False):
    """Lê dataset/<versao>/dataset.csv preservando ausências e acrescenta o papel legível do sensor.

    Por padrão remove as respostas com ``cruzou_fase = 1``, como pede a rotulação.
    """
    dados = pd.read_csv(DATASETS / versao / "dataset.csv", dtype={"sent_time_ns": "Int64", "receipt_time_ns": "Int64"})
    dados["timestamp"] = pd.to_datetime(dados["timestamp"], utc=True)
    dados["label"] = pd.Categorical(dados["label"], categories=CLASSES, ordered=True)
    dados["papel"] = dados["device_role"].map(PAPEIS)
    if not incluir_cruzamentos:
        dados = dados[dados["cruzou_fase"] == 0].reset_index(drop=True)
    return dados


def aplicar_estilo():
    """Estilo discreto: grade recessiva, linhas finas e texto em tons neutros."""
    mpl.rcParams.update({
        "figure.facecolor": SUPERFICIE,
        "axes.facecolor": SUPERFICIE,
        "savefig.facecolor": SUPERFICIE,
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.labelcolor": TEXTO_SEC,
        "axes.edgecolor": GRADE,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRADE,
        "grid.linewidth": 0.6,
        "xtick.color": TEXTO_SEC,
        "ytick.color": TEXTO_SEC,
        "text.color": TEXTO,
        "lines.linewidth": 1.5,
        "legend.frameon": False,
    })


def sombrear_fases(ax, rotular=True):
    """Marca as quatro fases no eixo x (tempo relativo em segundos)."""
    for inicio, fim, classe in FASES:
        if classe in ("pre_desastre", "pos_desastre"):
            ax.axvspan(inicio, fim, color="#f1f0ec", zorder=0, lw=0)
        if inicio:
            ax.axvline(inicio, color="#b8b7b1", lw=0.8, zorder=1)
        if rotular:
            ax.text((inicio + fim) / 2, 1.01, NOMES_CLASSES[classe], transform=ax.get_xaxis_transform(),
                    ha="center", va="bottom", fontsize=8.5, color=TEXTO_SEC)
    ax.set_xlim(0, 1215)


def salvar(fig, nome):
    FIGURAS.mkdir(exist_ok=True)
    fig.savefig(FIGURAS / nome)
