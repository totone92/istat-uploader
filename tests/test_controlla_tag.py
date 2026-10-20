"""Il controllo tag ↔ versione che decide se nasce una Release."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import uploader_turismatica
from scripts.controlla_tag import INIT, controlla, versione_app


def test_legge_la_versione_dal_testo_e_combacia_con_quella_del_pacchetto() -> None:
    assert versione_app() == uploader_turismatica.__version__


def test_tag_giusto_passa_tag_sbagliato_dice_i_due_valori_esatti() -> None:
    assert controlla("v1.1.0", "1.1.0") is None
    errore = controlla("v1.1.1", "1.1.0")
    assert errore is not None
    assert "'v1.1.1'" in errore and "'1.1.0'" in errore


def test_da_riga_di_comando_esce_con_zero_sul_tag_dell_app() -> None:
    script = Path(INIT).parent.parent / "scripts" / "controlla_tag.py"
    tag = f"v{uploader_turismatica.__version__}"
    # UTF-8 anche dal lato del figlio: su Windows l'uscita di default è cp1252.
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    giusto = subprocess.run([sys.executable, str(script), tag], capture_output=True,
                            text=True, encoding="utf-8", env=env)
    assert giusto.returncode == 0, giusto.stderr
    sbagliato = subprocess.run([sys.executable, str(script), "v0.0.0"], capture_output=True,
                               text=True, encoding="utf-8", env=env)
    assert sbagliato.returncode == 1
    assert "'v0.0.0'" in sbagliato.stderr
