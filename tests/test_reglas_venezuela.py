import pytest

from reglas_venezuela import normalizar


@pytest.mark.parametrize("leido, esperado", [
    ("AB123CD", "AB123CD"),     # formato vigente, leído bien
    ("ab-123 cd", "AB123CD"),   # minúsculas, guiones y espacios
    ("A8I23CD", "AB123CD"),     # 8 en posición de letra, I en posición de número
    ("AB1Z3CO", "AB123CO"),     # Z en posición de número
    ("ABC12D", "ABC12D"),       # formato anterior
    ("ABC123", "ABC123"),       # formato más antiguo
])
def test_corrige_por_posicion(leido, esperado):
    assert normalizar(leido) == esperado


@pytest.mark.parametrize("leido", [
    "5AU5341",   # placa extranjera de 7 caracteres: necesitaría 4 cambios
    "LM1AB2X",
    "QNA4B79",
    "CRACK339",  # texto de la pantalla, no es placa
    "",
    None,
    "AB12",
])
def test_descarta_lo_que_no_es_placa_venezolana(leido):
    assert normalizar(leido) is None
