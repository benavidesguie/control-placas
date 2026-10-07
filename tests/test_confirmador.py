from motor import Confirmador, distancia


def lectura(placa, conf=0.9):
    return {"placa": placa, "conf_ocr": conf, "conf_deteccion": 0.8, "caja": (0, 0, 10, 10)}


def test_distancia():
    assert distancia("JXU24D", "JXU24D") == 0
    assert distancia("JXU24D", "JXU241") == 1
    assert distancia("AB123CD", "AB123C") == 1
    assert distancia("AB123CD", "XY987ZW") == 7


def test_un_carro_con_lecturas_parecidas_se_registra_una_vez():
    c = Confirmador(cierre_s=1.5)
    eventos = []
    for t, placa in enumerate(["JXU24D", "JXU241", "JXU24D", "JXU240", "JXU24D"]):
        eventos += c.agregar([lectura(placa)], t * 0.25)
    eventos += c.agregar([], 10)  # el carro ya no se ve
    assert [e["placa"] for e in eventos] == ["JXU24D"]
    assert eventos[0]["lecturas"] == 5


def test_dos_carros_distintos_son_dos_eventos():
    c = Confirmador()
    c.agregar([lectura("AB123CD"), lectura("XY987ZW")], 0)
    c.agregar([lectura("AB123CD"), lectura("XY987ZW")], 0.5)
    eventos = c.agregar([], 5)
    assert sorted(e["placa"] for e in eventos) == ["AB123CD", "XY987ZW"]


def test_una_sola_lectura_de_baja_confianza_no_se_registra():
    c = Confirmador()
    c.agregar([lectura("AB123CD", 0.7)], 0)
    assert c.agregar([], 5) == []


def test_una_sola_lectura_muy_confiable_si_se_registra():
    c = Confirmador()
    c.agregar([lectura("AB123CD", 0.95)], 0)
    assert [e["placa"] for e in c.agregar([], 5)] == ["AB123CD"]


def test_no_repite_la_misma_placa_dentro_de_la_espera():
    c = Confirmador(espera_s=60)
    for t0 in (0, 20):  # el mismo carro pasa dos veces en 20 s
        c.agregar([lectura("AB123CD")], t0)
        c.agregar([lectura("AB123CD")], t0 + 0.5)
    eventos = c.agregar([], 30)
    assert len(eventos) == 1


def test_terminar_cierra_los_carros_a_la_vista():
    c = Confirmador()
    c.agregar([lectura("AB123CD")], 0)
    c.agregar([lectura("AB123CD")], 0.5)
    assert [e["placa"] for e in c.terminar(1)] == ["AB123CD"]
