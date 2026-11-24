export type Source = "simulation" | "device" | "manual" | "forecast";
export type Severity = "info" | "low" | "medium" | "high";

export interface SensorSpec {
  id?: string;
  type: string;
  unit: string;
  min_value?: number | null;
  max_value?: number | null;
  enabled: boolean;
}

export interface Device {
  id: string;
  name: string;
  farm_id: string | null;
  zone_id: string | null;
  hardware_type: string;
  firmware: string | null;
  source: Source;
  status: string;
  last_seen: string | null;
  provisioned: boolean;
  ip_address: string | null;
  sensors: SensorSpec[];
}

export interface Recording {
  id: string; zone_id: string | null; device_id: string | null;
  ts: string; duration_s: number; sample_rate: number; source: Source; status: string;
  notes: string | null; verdict: string | null; summary: string | null;
}
export interface Detection {
  id: string; model: string; model_version: string | null; category: string;
  confidence: number; signal_quality: number; evidence: any; ts: string;
}
export interface Label {
  id: string; recording_id: string; label: string;
  start_s: number; end_s: number | null; labeler: string; notes: string | null;
}
export interface Waveform { duration_s: number; sample_rate: number; min_max: number[]; }
export interface Spectrum { freqs: number[]; db: number[]; }
export interface Candidate {
  label: string; group: string; source: string; score: number;
  level: "probable" | "possible"; evidence: string; verification: string;
  scientific_name?: string; common_name?: string | null; taxon_group?: string; taxon_group_it?: string;
}
export interface Identification {
  verdict: "probable" | "possible" | "unknown" | "other_sound"; summary: string;
  main_sound?: { group: string; label: string; score: number; level?: string } | null;
  deterrents_triggered?: { device_id: string; reason: string }[]; candidates: Candidate[];
  rejected?: { label: string; score: number; group: string; reason: string }[];
  species_model?: { available?: boolean; local_filter?: boolean; local_species?: number | null; excluded_not_local?: number };
  context: { group: string; description: string; score: number; best_class: string }[];
  thresholds: { probable: number; possible: number; note: string };
  engines: Record<string, boolean>;
}
export interface Engines {
  perch?: { available: boolean; enabled: boolean; species?: number; error?: string | null };
  yamnet: { available: boolean; enabled: boolean; error?: string | null; classes?: number; license?: string };
  birdnet: { available: boolean; enabled: boolean; error?: string | null; license: string };
  farm_model: { active: boolean; version: number | null; labels: string[] };
  underground_experimental: { available: boolean; note: string };
  thresholds: Record<string, number>;
}
export interface MLModelInfo {
  id: string; kind: string; version: number; status: string; feature_version: string;
  labels: string[]; class_counts: Record<string, number>; n_samples: number; metrics: any;
  created_at: string; notes: string | null;
}
export interface LabelSummary {
  labels: { label: string; count: number; simulated: number; recordings: number }[];
  min_per_class_train: number; min_per_class_activate: number;
}

export interface CropResult {
  key: string; name: string; season: string;
  score_irrigated: number; class_irrigated: string;
  score_rainfed: number; class_rainfed: string;
  irrigation_need_mm: number; fao_water_range_mm: number[];
  limiting_factor: string | null;
  factors: { factor: string; value: string; requirement: string; score: number; note?: string | null }[];
  legume: boolean; family: string; notes: string;
}
export interface SourceRef { title: string; url: string; }
export interface Tip {
  id: string; category: string; impact: string; title: string; why: string; action: string; sources: SourceRef[];
}
export interface RiceSystem {
  id: string; name: string; what: string; benefits: string[]; requirements: string[];
  legal: { status: string; note: string }; sources: SourceRef[];
}
export interface SiteAssessment {
  location: { lat: number; lon: number; country: string | null };
  generated_at: string;
  climate: {
    source: string; period: string; years: number; hemisphere: string;
    annual: { t_mean: number; precip_mm: number; et0_mm: number; mean_annual_min_c: number; frost_free_days: number };
    monthly: { month: number; t_mean: number | null; precip_mm: number; et0_mm: number }[];
    seasons: Record<string, { months: number[]; t_mean: number; precip_mm: number; et0_mm: number }>;
    gdd: Record<string, number>;
  };
  soil: {
    ph: number | null; ph_source: string | null; texture: string | null; texture_source: string | null;
    soc_g_kg: number | null; properties: Record<string, { value: number; unit: string }>; source: string | null;
  };
  crops: CropResult[];
  cost_tips: Tip[];
  rice: {
    country: string | null; in_eu: boolean; rice_suitability: CropResult | null;
    systems: RiceSystem[]; water_saving: { title: string; text: string; sources: SourceRef[] }[]; disclaimer: string;
  };
  warnings: string[];
  method: Record<string, string>;
  sources: SourceRef[];
}

export interface SensorValue {
  value: number;
  unit: string;
  quality: number;
}

export interface LatestZoneTelemetry {
  device_id: string;
  zone_id: string | null;
  source: Source;
  status: string;
  last_seen: string | null;
  values: Record<string, SensorValue>;
}

export interface Reading {
  ts: string;
  sensor_id: string;
  sensor_type: string;
  value: number;
  unit: string;
  quality: number;
  source: Source;
}

export interface Scenario {
  name: string;
  title: string;
  description: string;
  active: boolean;
}

export interface Alert {
  id: string;
  zone_id: string | null;
  ts: string;
  category: string;
  severity: Severity;
  message: string;
  data: any;
  acknowledged: boolean;
  prediction_id: string | null;
}

export interface Prediction {
  id: string;
  zone_id: string | null;
  ts: string;
  kind: string;
  severity: Severity;
  summary: string;
  supporting: any[];
  confidence: number;
  model: string;
  explanation: string | null;
}

export interface Assessment {
  zone_id: string | null;
  status: string;
  findings: string[];
  recommendations: string[];
  narrative: string | null;
  predictions: Prediction[];
  alerts: Alert[];
  sources: string[];
  generated_at: string;
}

export interface Farm {
  id: string; name: string; owner: string;
  latitude: number | null; longitude: number | null; timezone: string;
}
export interface Field {
  id: string; farm_id: string; name: string;
  area_ha: number | null; soil_type: string | null; polygon: any;
}
export interface Zone {
  id: string; field_id: string; name: string; polygon: any;
}
