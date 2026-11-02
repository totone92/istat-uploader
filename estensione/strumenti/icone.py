"""Le icone dell'estensione, dal logo dell'uploader: quadrato azzurro e tre barre."""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

ACCENTO = (0x1F, 0x6F, 0xEB)
BIANCO = (0xFF, 0xFF, 0xFF)
BARRE = ((10, 11, 21), (16, 15, 21), (22, 12, 21))


def _dentro_arrotondato(x: float, y: float) -> bool:
    d = max(abs(x - 16) - 6, 0) ** 2 + max(abs(y - 16) - 6, 0) ** 2
    return d <= 8 ** 2


def _su_barra(x: float, y: float) -> bool:
    return any(
        (x - cx) ** 2 + (y - max(y1, min(y, y2))) ** 2 <= 1.5 ** 2
        for cx, y1, y2 in BARRE
    )


def icona(lato: int) -> bytes:
    passi = 4
    righe = bytearray()
    for r in range(lato):
        righe.append(0)
        for c in range(lato):
            somma = [0, 0, 0]
            opaco = 0
            for i in range(passi):
                for j in range(passi):
                    x = (c + (i + .5) / passi) * 32 / lato
                    y = (r + (j + .5) / passi) * 32 / lato
                    if not _dentro_arrotondato(x, y):
                        continue
                    opaco += 1
                    colore = BIANCO if _su_barra(x, y) else ACCENTO
                    for k in range(3):
                        somma[k] += colore[k]
            if opaco:
                righe += bytes(s // opaco for s in somma)
            else:
                righe += bytes(3)
            righe.append(opaco * 255 // passi ** 2)

    def pezzo(tipo: bytes, dati: bytes) -> bytes:
        corpo = tipo + dati
        return struct.pack(">I", len(dati)) + corpo + struct.pack(">I", zlib.crc32(corpo))

    testa = struct.pack(">IIBBBBB", lato, lato, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + pezzo(b"IHDR", testa)
            + pezzo(b"IDAT", zlib.compress(bytes(righe), 9)) + pezzo(b"IEND", b""))


if __name__ == "__main__":
    cartella = Path(sys.argv[1])
    for lato in (16, 48, 128):
        (cartella / f"icona-{lato}.png").write_bytes(icona(lato))
