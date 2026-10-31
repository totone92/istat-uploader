"""L'istanza unica: la logica con un sistema finto, il mutex vero su Windows."""
from __future__ import annotations

import sys
import uuid

import pytest

from uploader_turismatica import finestra, istanza


class Finto:
    def __init__(self, *, preso: bool, finestra_dopo: int = 0, rotto: bool = False) -> None:
        self.preso, self.finestra_dopo, self.rotto = preso, finestra_dopo, rotto
        self.tentativi = 0

    def mutex_gia_preso(self, nome: str) -> bool:
        if self.rotto:
            raise OSError("Windows non risponde")
        return self.preso

    def porta_davanti(self, inizio_titolo: str) -> bool:
        self.tentativi += 1
        return self.tentativi > self.finestra_dopo


def test_il_primo_avvio_parte_e_non_cerca_finestre() -> None:
    s = Finto(preso=False)
    assert not istanza.gia_aperto("m", "T", s)
    assert s.tentativi == 0


def test_il_secondo_avvio_porta_davanti_e_si_chiude() -> None:
    s = Finto(preso=True)
    assert istanza.gia_aperto("m", "T", s)
    assert s.tentativi == 1


def test_il_secondo_avvio_aspetta_la_finestra_del_primo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(istanza, "_PAUSA_S", 0.0)
    s = Finto(preso=True, finestra_dopo=3)
    assert istanza.gia_aperto("m", "T", s)
    assert s.tentativi == 4


def test_senza_finestra_si_chiude_lo_stesso(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(istanza, "ATTESA_FINESTRA_S", 0.0)
    assert istanza.gia_aperto("m", "T", Finto(preso=True, finestra_dopo=99))


def test_se_windows_non_risponde_si_parte_lo_stesso() -> None:
    assert not istanza.gia_aperto("m", "T", Finto(preso=True, rotto=True))


def test_il_secondo_avvio_non_crea_la_finestra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(finestra.istanza, "gia_aperto", lambda *_a: True)

    def mai() -> None:
        raise AssertionError("il secondo avvio non deve arrivare fin qui")

    monkeypatch.setattr(finestra.registro, "configura", mai)
    assert finestra.avvia() == 0


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="il mutex c'è solo su Windows")
def test_il_mutex_vero() -> None:
    w = istanza._Windows()
    nome = f"Local\\ProvaIstanza{uuid.uuid4().hex}"
    assert not w.mutex_gia_preso(nome)
    assert w.mutex_gia_preso(nome)
    assert not w.porta_davanti(f"Nessuna finestra {uuid.uuid4().hex}")
