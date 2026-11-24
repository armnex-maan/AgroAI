"""Mean maximum plant height of non-stressed, well-managed crops, from FAO Irrigation and Drainage Paper 56
(Allen et al. 1998), Table 12, column "Maximum Crop Height (h) (m)". Used only by the Visual Farm Planner.
Crops missing from the table have no value: the planner shows them with a neutral height and says so."""

SOURCE = {"id": "fao56_t12", "title": "FAO (1998) – Crop evapotranspiration, Irrigation and Drainage Paper 56, "
                                      "Table 12 (altezza massima media della coltura)", "year": 1998,
          "url": "https://www.fao.org/4/x0490e/x0490e0b.htm"}

# (min, max) in metres, as printed in Table 12; the row used is noted when the name differs
HEIGHT_M: dict[str, tuple[float, float]] = {
    "tomato": (0.6, 0.6), "potato": (0.6, 0.6), "eggplant": (0.8, 0.8),
    "pepper": (0.7, 0.7),                     # Sweet Peppers (bell)
    "zucchini": (0.3, 0.3),                   # Squash, Zucchini
    "cucumber": (0.3, 0.3), "melon": (0.4, 0.4),  # Sweet Melons
    "watermelon": (0.4, 0.4), "pumpkin": (0.4, 0.4),  # Pumpkin, Winter Squash
    "strawberry": (0.2, 0.2), "cabbage": (0.4, 0.4), "lettuce": (0.3, 0.3), "spinach": (0.3, 0.3),
    "celery": (0.6, 0.6), "carrot": (0.3, 0.3), "radish": (0.3, 0.3),
    "turnip": (0.6, 0.6),                     # Turnip (and Rutabaga)
    "onion": (0.4, 0.4),                      # Onions - dry
    "garlic": (0.3, 0.3), "asparagus": (0.2, 0.8),
    "bean": (0.4, 0.4),                       # Beans, dry and Pulses
    "green_bean": (0.4, 0.4),                 # Beans, green
    "pea": (0.5, 0.5), "faba": (0.8, 0.8), "chickpea": (0.4, 0.4), "soybean": (0.5, 1.0),
    "alfalfa": (0.7, 0.7),                    # Alfalfa Hay
    "wheat": (1.0, 1.0),                      # Winter Wheat
    "barley": (1.0, 1.0),
    "maize": (2.0, 2.0),                      # Maize, Field (grain)
    "sorghum": (1.0, 2.0),                    # Sorghum - grain
    "sunflower": (2.0, 2.0), "rapeseed": (0.6, 0.6), "sugar_beet": (0.5, 0.5),
}


def height(crop: str) -> list[float] | None:
    h = HEIGHT_M.get(crop)
    return list(h) if h else None


# fruit trees and vines (Table 12, "n. Fruit Trees" and "l. Grapes and Berries"), for orchards and vineyards
TREE_HEIGHT_M: dict[str, tuple[float, float]] = {
    "apple": (4, 4), "pear": (4, 4), "cherry": (4, 4),               # Apples, Cherries, Pears
    "peach": (3, 3), "apricot": (3, 3), "plum": (3, 3),              # Apricots, Peaches, Stone Fruit
    "olive": (3, 5), "walnut": (4, 5), "almond": (5, 5), "kiwi": (3, 3),
    "citrus": (2, 4),                                                # Citrus, 20-70% canopy
    "grape_wine": (1.5, 2), "grape_table": (2, 2),
}
TREE_NAMES = {"apple": "Melo", "pear": "Pero", "cherry": "Ciliegio", "peach": "Pesco", "apricot": "Albicocco", "plum": "Susino",
              "olive": "Olivo", "walnut": "Noce", "almond": "Mandorlo", "kiwi": "Actinidia (kiwi)", "citrus": "Agrumi",
              "grape_wine": "Vite da vino", "grape_table": "Vite da tavola"}
