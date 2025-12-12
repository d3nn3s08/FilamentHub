from app.services.printer_data import PrinterData


def test_printer_data_has_ams_units():
    pd = PrinterData()
    assert hasattr(pd, "ams_units")
    assert isinstance(pd.ams_units, list)


def test_to_dict_serializable():
    pd = PrinterData()
    pd.ams_units.append({"ams_id": 0, "trays": []})
    d = pd.to_dict()
    assert "ams_units" in d
    assert isinstance(d["ams_units"], list)


def test_trays_structure_list():
    pd = PrinterData()
    pd.ams_units = [{"trays": [1, 2, 3]}]
    d = pd.to_dict()
    assert isinstance(d["ams_units"][0]["trays"], list)
