"""Log no padrão do ecossistema (2026-11-26): pasta, limpeza de 30 dias e
migração do `~/.argus/argus.log` da 0.10.0. `registro.configurar` não é
chamado aqui porque troca o `sys.stdout` do processo inteiro (o do pytest)."""

import datetime
from pathlib import Path

from argus import registro
from argus.app import migrar_log_antigo


def test_pasta_no_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert registro.pasta_logs("ARGUS") == tmp_path / "Ecossistema" / "ARGUS" / "Logs"


def test_limpeza_apaga_so_logs_do_dia_antigos(tmp_path):
    hoje = datetime.date(2026, 11, 26)
    (tmp_path / "2026-10-01.log").write_text("velho")
    (tmp_path / "2026-11-20.log").write_text("recente")
    (tmp_path / "antigo-argus.log").write_text("migrado")
    assert registro.limpar(tmp_path, hoje=hoje) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-11-20.log", "antigo-argus.log"]


def test_migra_log_antigo_e_mantem_config(tmp_path):
    antiga = tmp_path / "home" / ".argus"
    antiga.mkdir(parents=True)
    (antiga / "argus.log").write_text("linha antiga")
    (antiga / "config.json").write_text("{}")
    nova = tmp_path / "Logs"
    nova.mkdir()
    caminhos = [str(antiga / "argus.log"), str(antiga / "argus.log.1")]
    movidos = migrar_log_antigo(str(nova), caminhos)
    assert [Path(m).name for m in movidos] == ["antigo-argus.log"]
    assert (nova / "antigo-argus.log").read_text() == "linha antiga"
    assert not (antiga / "argus.log").exists() and (antiga / "config.json").exists()
    assert migrar_log_antigo(str(nova), caminhos) == []
