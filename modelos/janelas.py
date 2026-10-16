"""Atributos de janela temporal por sensor e por gateway.

Cada consulta é decidida no instante em que seu resultado fica conhecido: na chegada da resposta, se ela foi
válida, ou ao fim do timeout de 15 s, se falhou (um limite conservador, porque uma resposta 5.03 chega antes).
Os atributos de janela resumem apenas as consultas cujo resultado já era conhecido nesse instante, nos 60 s
anteriores — do mesmo sensor e de todos os sensores do mesmo gateway. Nenhuma informação posterior à decisão é usada.
"""

import pandas as pd

JANELA = "60s"
TIMEOUT_S = 15

# Atributos de janela, separados pelos mesmos grupos usados nas comparações.
JANELA_SENSORES = ["temp_media_60s", "gw_temp_media_60s", "gw_temp_max_60s"]
JANELA_REDE = ["latencia_media_60s", "disponibilidade_60s", "gw_latencia_mediana_60s", "gw_falhas_60s"]
JANELA_BATERIA = ["gw_taxa_bateria_media_60s"]


def instante_decisao(dados):
    """Instante (ns) em que o resultado da consulta fica conhecido."""
    limite = dados["sent_time_ns"].astype("int64") + TIMEOUT_S * 1_000_000_000
    return dados["receipt_time_ns"].astype("Float64").fillna(limite.astype("Float64")).astype("int64")


def _rolar(grupo, calculos):
    """Aplica as agregações em janela de 60 s (intervalo (t - 60 s, t]) na ordem do instante de decisão."""
    ordenado = grupo.sort_values("decisao")
    serie = ordenado.set_index(pd.to_datetime(ordenado["decisao"]))
    janela = serie.rolling(JANELA, closed="right")
    valores = {nome: getattr(janela[coluna], funcao)().to_numpy() for nome, (coluna, funcao) in calculos.items()}
    return pd.DataFrame(valores, index=ordenado.index)


def adicionar_atributos_janela(dados):
    """Devolve uma cópia de ``dados`` com os atributos de janela por sensor e por gateway."""
    dados = dados.copy()
    dados["decisao"] = instante_decisao(dados)
    dados["falha"] = 1.0 - dados["available"]

    por_sensor = {"temp_media_60s": ("temperature", "mean"), "latencia_media_60s": ("latency_ms", "mean"),
                  "disponibilidade_60s": ("available", "mean")}
    por_gateway = {"gw_temp_media_60s": ("temperature", "mean"), "gw_temp_max_60s": ("temperature", "max"),
                   "gw_latencia_mediana_60s": ("latency_ms", "median"), "gw_falhas_60s": ("falha", "mean"),
                   "gw_taxa_bateria_media_60s": ("battery_rate_pp_min", "mean")}
    sensor = pd.concat(_rolar(g, por_sensor) for _, g in dados.groupby(["run_id", "device_id"], sort=False))
    gateway = pd.concat(_rolar(g, por_gateway) for _, g in dados.groupby(["run_id", "gateway_id"], sort=False))
    return pd.concat([dados.drop(columns=["decisao", "falha"]), sensor, gateway], axis=1)
