"""Corrige y valida lecturas con los formatos de placas venezolanas.

Formatos que se aceptan:
  AB123CD  carro, formato vigente (2 letras, 3 números, 2 letras)
  ABC12D   carro, formato anterior
  ABC123   carro, formato más antiguo
  AB1C23D  moto, formato vigente (confirmado con la foto de una moto de Aragua: AX7V56D)
Otros formatos de moto (más antiguos) faltan por confirmar con fotos reales.

El OCR confunde letras y números parecidos (O/0, I/1, B/8...). Como cada
posición del formato es siempre letra o siempre número, se corrige por
posición (máximo 2 cambios) y se descarta lo que no cumple ningún formato.
"""
import re

A_LETRA = {"0": "O", "1": "I", "2": "Z", "4": "A", "5": "S", "6": "G", "7": "T", "8": "B"}
A_NUMERO = {"O": "0", "D": "0", "Q": "0", "U": "0", "I": "1", "L": "1", "J": "1", "Z": "2",
            "A": "4", "S": "5", "G": "6", "T": "7", "B": "8"}

MAX_CORRECCIONES = 2  # más cambios que esto ya no es una placa venezolana mal leída

# L = letra, N = número
FORMATOS = {7: ["LLNNNLL", "LLNLNNL"], 6: ["LLLNNL", "LLLNNN"]}


def _aplicar(t, patron):
    out = []
    for c, p in zip(t, patron):
        c = A_LETRA.get(c, c) if p == "L" else A_NUMERO.get(c, c)
        if (p == "L") != c.isalpha():
            return None
        out.append(c)
    r = "".join(out)
    if sum(a != b for a, b in zip(r, t)) > MAX_CORRECCIONES:
        return None
    return r


def normalizar(texto):
    """Devuelve la placa corregida, o None si no puede ser una placa venezolana."""
    t = re.sub(r"[^A-Z0-9]", "", (texto or "").upper())
    patrones = FORMATOS.get(len(t), [])
    if len(t) == 6:
        # El último carácter distingue ABC12D de ABC123: se respeta lo leído
        patrones = [p for p in patrones if (p[-1] == "L") == t[-1].isalpha()]
    # Si cabe en más de un formato (carro y moto de 7 caracteres), gana el que necesita menos cambios
    candidatos = [r for r in (_aplicar(t, p) for p in patrones) if r]
    if not candidatos:
        return None
    return min(candidatos, key=lambda r: sum(a != b for a, b in zip(r, t)))
