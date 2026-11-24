"""Common label set for the public plant-disease datasets used to train AGROAI's image model.

Each dataset class is mapped to one unified class "crop/condition", with an Italian name and, when it
exists, the matching cause in causes.py (used as extra evidence by the differential diagnosis).
"""
from __future__ import annotations

# unified class -> (Italian name, cause id in causes.py or None, organ)
CLASSES: dict[str, tuple[str, str | None, str]] = {
    "apple/healthy": ("Melo – foglia sana", "healthy", "leaf"),
    "apple/scab": ("Melo – ticchiolatura", "fungal_leaf_spot", "leaf"),
    "apple/black_rot": ("Melo – marciume nero", "fungal_leaf_spot", "leaf"),
    "apple/rust": ("Melo – ruggine", "rust", "leaf"),
    "apple/fruit_healthy": ("Mela – frutto sano", "healthy", "fruit"),
    "apple/fruit_diseased": ("Mela – frutto malato", None, "fruit"),
    "blueberry/healthy": ("Mirtillo – foglia sana", "healthy", "leaf"),
    "cherry/healthy": ("Ciliegio – foglia sana", "healthy", "leaf"),
    "cherry/powdery_mildew": ("Ciliegio – oidio", "powdery_mildew", "leaf"),
    "citrus/leaf_healthy": ("Agrumi – foglia sana", "healthy", "leaf"),
    "citrus/canker": ("Agrumi – cancro batterico", "fungal_leaf_spot", "leaf"),
    "citrus/greening": ("Agrumi – greening (HLB)", None, "leaf"),
    "citrus/fruit_healthy": ("Agrumi – frutto sano", "healthy", "fruit"),
    "citrus/fruit_diseased": ("Agrumi – frutto malato", None, "fruit"),
    "corn/healthy": ("Mais – foglia sana", "healthy", "leaf"),
    "corn/gray_leaf_spot": ("Mais – cercosporiosi", "fungal_leaf_spot", "leaf"),
    "corn/rust": ("Mais – ruggine", "rust", "leaf"),
    "corn/leaf_blight": ("Mais – elmintosporiosi", "fungal_leaf_spot", "leaf"),
    "grape/healthy": ("Vite – foglia sana", "healthy", "leaf"),
    "grape/black_rot": ("Vite – marciume nero", "fungal_leaf_spot", "leaf"),
    "grape/esca": ("Vite – mal dell'esca", None, "leaf"),
    "grape/leaf_blight": ("Vite – macchie fogliari (Isariopsis)", "fungal_leaf_spot", "leaf"),
    "peach/healthy": ("Pesco – foglia sana", "healthy", "leaf"),
    "peach/bacterial_spot": ("Pesco – maculatura batterica", "fungal_leaf_spot", "leaf"),
    "pepper/healthy": ("Peperone – foglia sana", "healthy", "leaf"),
    "pepper/bacterial_spot": ("Peperone – maculatura batterica", "fungal_leaf_spot", "leaf"),
    "potato/healthy": ("Patata – foglia sana", "healthy", "leaf"),
    "potato/early_blight": ("Patata – alternariosi", "early_blight", "leaf"),
    "potato/late_blight": ("Patata – peronospora", "late_blight", "leaf"),
    "raspberry/healthy": ("Lampone – foglia sana", "healthy", "leaf"),
    "soybean/healthy": ("Soia – foglia sana", "healthy", "leaf"),
    "squash/powdery_mildew": ("Zucca/zucchina – oidio", "powdery_mildew", "leaf"),
    "strawberry/healthy": ("Fragola – foglia sana", "healthy", "leaf"),
    "strawberry/leaf_scorch": ("Fragola – maculatura (leaf scorch)", "fungal_leaf_spot", "leaf"),
    "tomato/healthy": ("Pomodoro – foglia sana", "healthy", "leaf"),
    "tomato/bacterial_spot": ("Pomodoro – maculatura batterica", "fungal_leaf_spot", "leaf"),
    "tomato/early_blight": ("Pomodoro – alternariosi", "early_blight", "leaf"),
    "tomato/late_blight": ("Pomodoro – peronospora", "late_blight", "leaf"),
    "tomato/leaf_mold": ("Pomodoro – cladosporiosi", "fungal_leaf_spot", "leaf"),
    "tomato/septoria": ("Pomodoro – septoriosi", "fungal_leaf_spot", "leaf"),
    "tomato/spider_mites": ("Pomodoro – ragnetto rosso", "sucking_insects", "leaf"),
    "tomato/target_spot": ("Pomodoro – maculatura (target spot)", "fungal_leaf_spot", "leaf"),
    "tomato/yellow_leaf_curl": ("Pomodoro – virus dell'accartocciamento giallo (TYLCV)", "viral_disease", "leaf"),
    "tomato/mosaic": ("Pomodoro – virus del mosaico", "viral_disease", "leaf"),
    # --- added with Liu 2025 tomato greenhouse dataset (crops of single plant parts)
    "tomato/grey_mould_fruit": ("Pomodoro – muffa grigia sul frutto", "grey_mould", "fruit"),
    "tomato/grey_mould_leaf": ("Pomodoro – muffa grigia sulla foglia", "grey_mould", "leaf"),
    "tomato/viral": ("Pomodoro – virosi (TYLCV / ToCV)", "viral_disease", "leaf"),
    "tomato/bacterial_wilt": ("Pomodoro – avvizzimento batterico", "bacterial_wilt", "leaf"),
    # --- citrus fruits and leaves (CC BY 4.0)
    "citrus/black_spot": ("Agrumi – macchia nera (foglia)", "fungal_leaf_spot", "leaf"),
    "citrus/melanose": ("Agrumi – melanosi (foglia)", "fungal_leaf_spot", "leaf"),
    "citrus/scab": ("Agrumi – scabbia (foglia)", "fungal_leaf_spot", "leaf"),
    "citrus/fruit_black_spot": ("Agrumi – macchia nera del frutto", None, "fruit"),
    "citrus/fruit_canker": ("Agrumi – cancro batterico del frutto", None, "fruit"),
    "citrus/fruit_greening": ("Agrumi – greening del frutto", None, "fruit"),
    "citrus/fruit_scab": ("Agrumi – scabbia del frutto", None, "fruit"),
    "citrus/fruit_melanose": ("Agrumi – melanosi del frutto", None, "fruit"),
    # --- brassica vegetables (CC BY 4.0)
    "broccoli/healthy": ("Broccolo – foglia sana", "healthy", "leaf"),
    "broccoli/alternaria": ("Broccolo – alternariosi", "fungal_leaf_spot", "leaf"),
    "broccoli/black_rot": ("Broccolo – marciume nero (Xanthomonas)", "fungal_leaf_spot", "leaf"),
    "cabbage/healthy": ("Cavolo – foglia sana", "healthy", "leaf"),
    "cabbage/alternaria": ("Cavolo – alternariosi", "fungal_leaf_spot", "leaf"),
    "cabbage/cabbage_white": ("Cavolo – danni di cavolaia (bruchi)", "chewing_insects", "leaf"),
    "cabbage/grey_mould": ("Cavolo – muffa grigia", "grey_mould", "leaf"),
    "cabbage/tip_burn": ("Cavolo – necrosi marginale (tip burn)", None, "leaf"),
    "cauliflower/healthy": ("Cavolfiore – foglia sana", "healthy", "leaf"),
    "cauliflower/alternaria": ("Cavolfiore – alternariosi", "fungal_leaf_spot", "leaf"),
    "cauliflower/curd_alternaria": ("Cavolfiore – alternariosi del corimbo", None, "fruit"),
    "cauliflower/soft_rot": ("Cavolfiore – marciume molle batterico", None, "fruit"),
    "cauliflower/virus": ("Cavolfiore – virosi", "viral_disease", "leaf"),
    "turnip/healthy": ("Rapa – foglia sana", "healthy", "leaf"),
    "turnip/alternaria": ("Rapa – alternariosi", "fungal_leaf_spot", "leaf"),
    "turnip/black_rot": ("Rapa – marciume nero (Xanthomonas)", "fungal_leaf_spot", "leaf"),
    # --- healthy and rotten fruits (tomato ripeness crops, fresh/rotten fruits, DiaMOS pear), CC BY 4.0
    "tomato/fruit_healthy": ("Pomodoro – frutto sano", "healthy", "fruit"),
    "tomato/fruit_rotten": ("Pomodoro – frutto marcio", None, "fruit"),
    "apple/fruit_rotten": ("Mela – frutto marcio", None, "fruit"),
    "grape/fruit_healthy": ("Uva – frutto sano", "healthy", "fruit"),
    "grape/fruit_rotten": ("Uva – frutto marcio", None, "fruit"),
    "citrus/fruit_rotten": ("Agrumi – frutto marcio", None, "fruit"),
    "strawberry/fruit_healthy": ("Fragola – frutto sano", "healthy", "fruit"),
    "strawberry/fruit_rotten": ("Fragola – frutto marcio", None, "fruit"),
    "pomegranate/fruit_healthy": ("Melograno – frutto sano", "healthy", "fruit"),
    "pomegranate/fruit_rotten": ("Melograno – frutto marcio", None, "fruit"),
    "banana/fruit_healthy": ("Banana – frutto sano", "healthy", "fruit"),
    "banana/fruit_rotten": ("Banana – frutto marcio", None, "fruit"),
    "guava/fruit_healthy": ("Guava – frutto sano", "healthy", "fruit"),
    "guava/fruit_rotten": ("Guava – frutto marcio", None, "fruit"),
    "jujube/fruit_healthy": ("Giuggiolo – frutto sano", "healthy", "fruit"),
    "jujube/fruit_rotten": ("Giuggiolo – frutto marcio", None, "fruit"),
    "pear/fruit_healthy": ("Pera – frutto sano", "healthy", "fruit"),
    "pear/healthy": ("Pero – foglia sana", "healthy", "leaf"),
    "pear/leaf_spot": ("Pero – septoriosi (macchie fogliari)", "fungal_leaf_spot", "leaf"),
    "pear/leaf_curl": ("Pero – foglie accartocciate", None, "leaf"),
    "pear/slug_damage": ("Pero – danni di lumache", "chewing_insects", "leaf"),
}

PLANTVILLAGE = {
    "Apple___Apple_scab": "apple/scab", "Apple___Black_rot": "apple/black_rot",
    "Apple___Cedar_apple_rust": "apple/rust", "Apple___healthy": "apple/healthy",
    "Blueberry___healthy": "blueberry/healthy",
    "Cherry_(including_sour)___Powdery_mildew": "cherry/powdery_mildew",
    "Cherry_(including_sour)___healthy": "cherry/healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": "corn/gray_leaf_spot",
    "Corn_(maize)___Common_rust_": "corn/rust", "Corn_(maize)___Northern_Leaf_Blight": "corn/leaf_blight",
    "Corn_(maize)___healthy": "corn/healthy",
    "Grape___Black_rot": "grape/black_rot", "Grape___Esca_(Black_Measles)": "grape/esca",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": "grape/leaf_blight", "Grape___healthy": "grape/healthy",
    "Orange___Haunglongbing_(Citrus_greening)": "citrus/greening",
    "Peach___Bacterial_spot": "peach/bacterial_spot", "Peach___healthy": "peach/healthy",
    "Pepper,_bell___Bacterial_spot": "pepper/bacterial_spot", "Pepper,_bell___healthy": "pepper/healthy",
    "Potato___Early_blight": "potato/early_blight", "Potato___Late_blight": "potato/late_blight",
    "Potato___healthy": "potato/healthy", "Raspberry___healthy": "raspberry/healthy",
    "Soybean___healthy": "soybean/healthy", "Squash___Powdery_mildew": "squash/powdery_mildew",
    "Strawberry___Leaf_scorch": "strawberry/leaf_scorch", "Strawberry___healthy": "strawberry/healthy",
    "Tomato___Bacterial_spot": "tomato/bacterial_spot", "Tomato___Early_blight": "tomato/early_blight",
    "Tomato___Late_blight": "tomato/late_blight", "Tomato___Leaf_Mold": "tomato/leaf_mold",
    "Tomato___Septoria_leaf_spot": "tomato/septoria",
    "Tomato___Spider_mites Two-spotted_spider_mite": "tomato/spider_mites",
    "Tomato___Target_Spot": "tomato/target_spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": "tomato/yellow_leaf_curl",
    "Tomato___Tomato_mosaic_virus": "tomato/mosaic", "Tomato___healthy": "tomato/healthy",
}

PLANTDOC = {
    "Apple Scab Leaf": "apple/scab", "Apple leaf": "apple/healthy", "Apple rust leaf": "apple/rust",
    "Bell_pepper leaf": "pepper/healthy", "Bell_pepper leaf spot": "pepper/bacterial_spot",
    "Blueberry leaf": "blueberry/healthy", "Cherry leaf": "cherry/healthy",
    "Corn Gray leaf spot": "corn/gray_leaf_spot", "Corn leaf blight": "corn/leaf_blight", "Corn rust leaf": "corn/rust",
    "Peach leaf": "peach/healthy", "Potato leaf early blight": "potato/early_blight",
    "Potato leaf late blight": "potato/late_blight", "Raspberry leaf": "raspberry/healthy",
    "Soyabean leaf": "soybean/healthy", "Squash Powdery mildew leaf": "squash/powdery_mildew",
    "Strawberry leaf": "strawberry/healthy", "Tomato Early blight leaf": "tomato/early_blight",
    "Tomato Septoria leaf spot": "tomato/septoria", "Tomato leaf": "tomato/healthy",
    "Tomato leaf bacterial spot": "tomato/bacterial_spot", "Tomato leaf late blight": "tomato/late_blight",
    "Tomato leaf mosaic virus": "tomato/mosaic", "Tomato leaf yellow virus": "tomato/yellow_leaf_curl",
    "Tomato mold leaf": "tomato/leaf_mold", "Tomato two spotted spider mites leaf": "tomato/spider_mites",
    "grape leaf": "grape/healthy", "grape leaf black rot": "grape/black_rot",
}

MULTIFRUIT = {
    "Citrus CanckerLeaf": "citrus/canker", "Citrus Healthy Leaf": "citrus/leaf_healthy",
    "Citrus Fruit disease": "citrus/fruit_diseased", "Citrus Healthy Fruit": "citrus/fruit_healthy",
    "Disease Apple Fruit": "apple/fruit_diseased", "Healthy Apple Fruit": "apple/fruit_healthy",
}

DATASETS = {
    "tomato_ripe": {"name": "Unified Tomato Ripeness (Karkooti 2026)", "licence": "CC BY 4.0",
                    "url": "https://huggingface.co/datasets/ParsaVictor/tomato-ripeness-detection",
                    "citation": "Karkooti (2026), da 6 dataset Roboflow CC BY 4.0",
                    "kind": "pomodori sani (vari gradi di maturazione) e marci"},
    "fresh_rotten": {"name": "Fresh and Rotten Fruits (Sultana et al. 2022)", "licence": "CC BY 4.0",
                     "url": "https://huggingface.co/datasets/Project-AgML/fresh_rotten_fruit_classification",
                     "citation": "Sultana et al. (2022), Data in Brief 44:108552", "kind": "8 frutti sani e marci"},
    "diamos": {"name": "DiaMOS Plant – pero (Fenu & Malloci 2021)", "licence": "CC BY 4.0",
               "url": "https://doi.org/10.5281/zenodo.5557313", "citation": "Fenu & Malloci (2021), Agronomy 11:2107",
               "kind": "pere sane (fasi di crescita) e foglie di pero, Sardegna"},
    "tomato_liu": {"name": "Tomato Disease (Liu 2025)", "licence": "CC BY 4.0",
                   "url": "https://huggingface.co/datasets/Project-AgML/tomato_disease_detection",
                   "citation": "Liu (2025), Data in Brief 63:112032, doi:10.1016/j.dib.2025.112032",
                   "kind": "foto reali in serra, ritagli di frutti, foglie e fusti"},
    "citrus_fl": {"name": "Citrus Fruits and Leaves", "licence": "CC BY 4.0",
                  "url": "https://huggingface.co/datasets/Project-AgML/citrus_fruit_leaf_disease_classification",
                  "citation": "Rauf et al. (2019), Data in Brief 26:104340", "kind": "foto di frutti e foglie di agrumi"},
    "veg_leaf": {"name": "Comprehensive Vegetable Leaf Disease", "licence": "CC BY 4.0",
                 "url": "https://huggingface.co/datasets/InriaXagriscienceFM/comprehensive_vegetable_leaf_disease_men_classification",
                 "citation": "Ikteshad et al. (2025), Mendeley Data, doi:10.17632/rh8c5tgg5k.1",
                 "kind": "foto reali di foglie di broccolo, cavolo, cavolfiore, rapa"},
    "plantdoc": {"name": "PlantDoc", "licence": "CC BY 4.0", "url": "https://github.com/pratikkayal/PlantDoc-Dataset",
                 "citation": "Singh et al. (2020), PlantDoc: A Dataset for Visual Plant Disease Detection, CoDS-COMAD",
                 "kind": "foto reali (internet, campo)"},
    "plantvillage": {"name": "PlantVillage", "licence": "CC BY-SA 3.0",
                     "url": "https://github.com/spMohanty/PlantVillage-Dataset",
                     "citation": "Mohanty, Hughes & Salathé (2016), Frontiers in Plant Science 7:1419",
                     "kind": "foto di laboratorio (sfondo uniforme)"},
    "multifruit6d": {"name": "MultiFruit-6D (ABCGMP)", "licence": "CC BY 4.0",
                     "url": "https://data.mendeley.com/datasets/fhbvmpcyy2/4",
                     "citation": "Nain, Jain & Jain, Mendeley Data (MNIT Jaipur)",
                     "kind": "foto reali di frutti e foglie"},
}


CROP_ALIASES = {
    "tomato": ["pomodor", "tomato"], "apple": ["mela", "melo", "apple"], "citrus": ["agrum", "arancia", "arancio",
    "limone", "mandarin", "clementin", "citrus", "orange"], "grape": ["vite", "uva", "grape"],
    "potato": ["patata", "potato"], "pepper": ["peperon", "pepper"], "corn": ["mais", "granturco", "corn", "maize"],
    "peach": ["pesc", "peach"], "cherry": ["cilieg", "cherry"], "strawberry": ["fragol", "strawberry"],
    "squash": ["zucc", "squash"], "blueberry": ["mirtill", "blueberry"], "raspberry": ["lampon", "raspberry"],
    "soybean": ["soia", "soy"],
    "cauliflower": ["cavolfior", "cauliflower"], "broccoli": ["broccol", "cima di rapa", "cime di rapa"],
    "cabbage": ["cavolo", "verza", "cappuccio", "cabbage"], "turnip": ["rapa", "turnip"],
    "pear": ["pera", "pero", "pere", "pear"], "pomegranate": ["melagran", "melogran", "pomegranate"],
    "banana": ["banan"], "guava": ["guava", "guaiava"], "jujube": ["giuggiol", "jujube"],
}


def crop_of(label: str) -> str:
    return label.split("/", 1)[0]


def crop_key(name: str | None) -> str | None:
    """Italian or English crop name -> dataset crop key ("Pomodoro San Marzano" -> "tomato")."""
    if not name:
        return None
    n = name.lower()
    # longest matching word wins: "melograno" contains "melo" but is a pomegranate
    hits = [(len(w), k) for k, words in CROP_ALIASES.items() for w in words if w in n]
    return max(hits)[1] if hits else None
