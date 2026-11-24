// Italian labels and number/date formatting shared by all pages.

export const num = (v: number | null | undefined, digits = 1) =>
  v == null || Number.isNaN(v) ? "—" : v.toLocaleString("it-IT", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const pct = (v: number | null | undefined, digits = 0) => (v == null ? "—" : `${num(v * 100, digits)}%`);

export const dateTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("it-IT", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

export const time = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" }) : "—";

export const ago = (iso: string | null | undefined) => {
  if (!iso) return "mai";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "adesso";
  if (s < 3600) return `${Math.round(s / 60)} min fa`;
  if (s < 86400) return `${Math.round(s / 3600)} ore fa`;
  return `${Math.round(s / 86400)} giorni fa`;
};

export const greeting = () => {
  const h = new Date().getHours();
  return h < 13 ? "Buongiorno" : h < 18 ? "Buon pomeriggio" : "Buonasera";
};

export const SOURCE: Record<string, string> = {
  simulation: "Demo", device: "Sensore", manual: "Manuale", forecast: "Previsione",
};
export const SOURCE_HELP: Record<string, string> = {
  simulation: "Dato di prova generato dal simulatore, non misurato nel campo",
  device: "Misurato da un sensore reale nel campo",
  manual: "Inserito o caricato a mano",
  forecast: "Previsione o stima meteo",
};

export const SEVERITY: Record<string, string> = { high: "Alta", medium: "Media", low: "Bassa", info: "Info" };
export const STATUS: Record<string, string> = { online: "Collegato", offline: "Spento", stale: "Non risponde" };

export const SENSOR: Record<string, { label: string; unit: string; icon: string }> = {
  soil_moisture: { label: "Umidità del terreno", unit: "%", icon: "drop" },
  soil_temperature: { label: "Temperatura del terreno", unit: "°C", icon: "thermo" },
  air_temperature: { label: "Temperatura dell'aria", unit: "°C", icon: "thermo" },
  air_humidity: { label: "Umidità dell'aria", unit: "%", icon: "drop" },
  soil_ph: { label: "pH del terreno", unit: "", icon: "flaskph" },
  soil_ec: { label: "Salinità del terreno (EC)", unit: "mS/cm", icon: "flaskph" },
  rainfall: { label: "Pioggia", unit: "mm", icon: "drop" },
  light_intensity: { label: "Luce", unit: "", icon: "sun" },
  wind_speed: { label: "Vento", unit: "m/s", icon: "wave" },
  wind_direction: { label: "Direzione del vento", unit: "°", icon: "wave" },
  leaf_wetness: { label: "Bagnatura fogliare", unit: "", icon: "drop" },
  nitrogen: { label: "Azoto", unit: "", icon: "leaf" },
  phosphorus: { label: "Fosforo", unit: "", icon: "leaf" },
  potassium: { label: "Potassio", unit: "", icon: "leaf" },
  battery_voltage: { label: "Batteria", unit: "V", icon: "sun" },
  irrigation_water: { label: "Acqua irrigata", unit: "L", icon: "drop" },
  irrigation_time: { label: "Tempo di irrigazione", unit: "min", icon: "drop" },
};
export const sensorLabel = (t: string) => SENSOR[t]?.label ?? t;

export const SEASON: Record<string, string> = { summer: "estiva", winter: "autunno-vernina", perennial: "perenne" };

export const TEXTURE: Record<string, string> = {
  sand: "sabbioso", "loamy sand": "sabbioso-franco", "sandy loam": "franco-sabbioso", loam: "franco (medio impasto)",
  "silt loam": "franco-limoso", silt: "limoso", "sandy clay loam": "franco-sabbioso-argilloso",
  "clay loam": "franco-argilloso", "silty clay loam": "franco-limoso-argilloso", "sandy clay": "argilloso-sabbioso",
  "silty clay": "argilloso-limoso", clay: "argilloso",
};

export const SUIT_CLASS: Record<string, string> = {
  S1: "Molto adatta", S2: "Adatta", S3: "Poco adatta", N: "Non adatta",
};

export const LIKELIHOOD: Record<string, string> = { high: "Probabile", medium: "Possibile", low: "Poco probabile" };
export const URGENCY: Record<string, string> = { high: "Urgente", medium: "Entro pochi giorni", low: "Non urgente", none: "" };
export const VERDICT: Record<string, string> = { probable: "Probabile", possible: "Possibile", unknown: "Non riconosciuto", other_sound: "Nessun animale" };

export const SOUND_GROUP: Record<string, string> = {
  bird: "Uccelli", poultry_waterfowl: "Pollame / anatre", insect: "Insetti", amphibian: "Rane", rodent: "Roditori",
  dog_canid: "Cani / volpi", cat_feline: "Gatti", livestock: "Bestiame", wild_animal: "Animali (generico)",
  water_irrigation: "Acqua / irrigazione", wind_vegetation: "Vento / foglie", machinery_vehicle: "Macchine / motori",
  human: "Persone", silence: "Silenzio", other: "Altro", none: "—", unavailable: "Non disponibile",
};

export const TIP_CATEGORY: Record<string, string> = {
  water: "Acqua", fertilizer: "Concimi", soil: "Terreno", energy: "Gasolio e lavoro", pest: "Parassiti",
};
export const IMPACT: Record<string, string> = { high: "Risparmio alto", medium: "Risparmio medio", low: "Risparmio piccolo" };
export const LEGAL: Record<string, string> = {
  allowed: "Consentito", allowed_with_conditions: "Consentito con regole", prohibited: "Vietato", check_local: "Da verificare",
};
