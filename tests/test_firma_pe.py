from __future__ import annotations

import struct

from scripts.firma_pe import firma_interni, inutile, stato_firma, togli_inutili


def _pe(dimensione_certificati: int, magic: int = 0x20B) -> bytes:
    dati = bytearray(512)
    dati[:2] = b"MZ"
    struct.pack_into("<I", dati, 60, 128)
    dati[128:132] = b"PE\0\0"
    struct.pack_into("<H", dati, 152, magic)
    voce = 152 + (96 if magic == 0x10B else 112) + 4 * 8
    struct.pack_into("<I", dati, voce + 4, dimensione_certificati)
    return bytes(dati)


def test_riconosce_la_firma_a_64_e_32_bit():
    assert stato_firma(_pe(4096)) is True
    assert stato_firma(_pe(0)) is False
    assert stato_firma(_pe(4096, magic=0x10B)) is True
    assert stato_firma(_pe(0, magic=0x10B)) is False


def test_un_file_che_non_e_un_pe_non_si_firma():
    assert stato_firma(b"#!/bin/sh\n" * 20) is None
    assert stato_firma(b"MZ") is None


def test_toglie_solo_i_binari_che_non_partono_mai():
    assert not inutile("webview\\lib\\runtimes\\win-arm64\\native\\WebView2Loader.dll")
    assert inutile("clr_loader/ffi/dlls/x86/ClrLoader.dll")
    assert inutile("webview\\lib\\WebBrowserInterop.x86.dll")
    assert inutile("selenium/webdriver/common/linux/selenium-manager")
    assert not inutile("webview\\lib\\runtimes\\win-x64\\native\\WebView2Loader.dll")
    assert not inutile("clr_loader\\ffi\\dlls\\amd64\\ClrLoader.dll")
    assert not inutile("selenium\\webdriver\\common\\windows\\selenium-manager.exe")
    voci = [("a/dlls/x86/x.dll", "s", "BINARY"), ("b.dll", "s", "BINARY")]
    assert togli_inutili(voci) == [("b.dll", "s", "BINARY")]


def test_senza_firma_pronta_le_voci_restano_quelle(monkeypatch, tmp_path):
    monkeypatch.delenv("FIRMA_PRONTA", raising=False)
    voci = [("b.dll", str(tmp_path / "non-esiste.dll"), "BINARY")]
    assert firma_interni(voci, tmp_path) == voci
