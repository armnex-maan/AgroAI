"""Species gate: Perch names the species, YAMNet must confirm an animal of that group."""
from app.ml.audio import species

LOCAL = {
    "Turdus merula": {"common_name": "Merlo", "group": "bird", "observations": 900},
    "Canis familiaris": {"common_name": "Cane", "group": "mammal"},
    "Canis aureus": {"common_name": "Sciacallo dorato", "group": "mammal"},
    "Felis catus": {"common_name": "Gatto domestico", "group": "mammal"},
    "Gryllus campestris": {"common_name": "Grillo campestre", "group": "insect"},
    "Talpa europaea": {"common_name": "Talpa europea", "group": "mammal"},
}


def _perch(*names, insect=0.0):
    return {"available": True, "group_evidence": {"insect": insect, "amphibian": 0.0},
            "species": [{"scientific_name": n, "score": 0.97, "start_s": 0.0, "end_s": 5.0} for n in names]}


def _yam(**groups):
    return {"available": True, "groups": [{"group": g, "score": s} for g, s in groups.items()]}


def test_machine_noise_never_becomes_an_animal():
    ok, rej, gate = species.candidates(_perch("Turdus merula"), _yam(machinery_vehicle=0.95, bird=0.1), LOCAL, 0.5, 0.2)
    assert ok == [] and rej and gate["noise"] == 0.95


def test_bird_confirmed_by_yamnet_is_probable_with_italian_name():
    ok, _, _ = species.candidates(_perch("Turdus merula"), _yam(bird=0.9), LOCAL, 0.5, 0.2)
    assert ok[0]["label"] == "Merlo (Turdus merula)" and ok[0]["level"] == "probable"


def test_species_of_wrong_group_is_rejected():
    ok, rej, _ = species.candidates(_perch("Turdus merula"), _yam(dog_canid=0.9), LOCAL, 0.5, 0.2)
    assert all(c["scientific_name"] != "Turdus merula" for c in ok)


def test_clear_cat_sound_rejects_jackal_but_keeps_cat():
    ok, rej, _ = species.candidates(_perch("Canis aureus", "Felis catus"), _yam(cat_feline=0.98), LOCAL, 0.5, 0.2)
    assert [c["scientific_name"] for c in ok] == ["Felis catus"]
    assert any("Sciacallo" in r["label"] for r in rej)


def test_cricket_confirmed_by_perch_cricket_class():
    ok, _, _ = species.candidates(_perch("Gryllus campestris", insect=0.3), _yam(wild_animal=0.8), LOCAL, 0.5, 0.2)
    assert ok and ok[0]["scientific_name"] == "Gryllus campestris"


def test_mole_is_never_more_than_possible():
    ok, _, _ = species.candidates(_perch("Talpa europaea"), _yam(rodent=0.9, wild_animal=0.9), LOCAL, 0.5, 0.2)
    assert ok and ok[0]["level"] == "possible" and "pochissime registrazioni" in ok[0]["evidence"]


def test_without_yamnet_species_are_capped_at_possible():
    ok, _, _ = species.candidates(_perch("Turdus merula"), None, LOCAL, 0.5, 0.2)
    assert ok and all(c["level"] == "possible" for c in ok)


def test_car_horn_is_machinery_not_goose():
    from app.ml.audio.yamnet import group_for
    assert group_for("Vehicle horn, car horn, honking")[0] == "machinery_vehicle"
    assert group_for("Honk")[0] == "poultry_waterfowl"
    assert group_for("Livestock, farm animals, working animals")[0] == "farm_animal"
