import pytest

from reglas_venezuela import normalizar, tipo_vehiculo


@pytest.mark.parametrize("leido, esperado", [
    ("AB123CD", "AB123CD"),     # formato vigente, leído bien
    ("ab-123 cd", "AB123CD"),   # minúsculas, guiones y espacios
    ("A8I23CD", "AB123CD"),     # 8 en posición de letra, I en posición de número
    ("AB1Z3CO", "AB123CO"),     # Z en posición de número
    ("ABC12D", "ABC12D"),       # formato anterior
    ("ABC123", "ABC123"),       # formato más antiguo
    ("AX7V56D", "AX7V56D"),     # moto: foto real de una placa de Aragua
    ("AX7V5GD", "AX7V56D"),     # moto: G en posición de número
    ("AB1C23D", "AB1C23D"),  # moto, otro ejemplo
    ("AB1C2ZD", "AB1C22D"),     # moto: Z en posición de número
])
def test_corrige_por_posicion(leido, esperado):
    assert normalizar(leido) == esperado


@pytest.mark.parametrize("leido", [
    "5AU5341",   # placa extranjera de 7 caracteres: necesitaría 4 cambios
    "AB1",       # muy corta
    "QNA4B79",
    "CRACK339",  # texto de la pantalla, no es placa
    "",
    None,
    "AB12",
])
def test_descarta_lo_que_no_es_placa_venezolana(leido):
    assert normalizar(leido) is None


def test_carro_y_moto_de_7_caracteres_no_se_confunden():
    assert normalizar("AB123CD") == "AB123CD"   # carro
    assert normalizar("AB1C23D") == "AB1C23D"   # moto
    assert normalizar("A81C23D") == "AB1C23D"   # moto con una B leída como 8


@pytest.mark.parametrize("placa, tipo", [
    ("AB123CD", "Carro"),
    ("ABC12D", "Carro"),
    ("ABC123", "Carro"),
    ("AX7V56D", "Moto"),
    ("ax-7v 56d", "Moto"),
    ("5AU5341", "Otro"),
    ("", "Otro"),
    (None, "Otro"),
])
def test_tipo_de_vehiculo(placa, tipo):
    assert tipo_vehiculo(placa) == tipo
