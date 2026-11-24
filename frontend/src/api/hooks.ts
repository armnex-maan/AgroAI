import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import {
  Assessment, Alert, Device, LatestZoneTelemetry, Reading, Scenario,
  Farm, Field, Zone, Recording, Detection, Label, Waveform, Engines, MLModelInfo, LabelSummary,
  Identification, Spectrum, SiteAssessment,
} from "./types";

export const useHealth = () =>
  useQuery({ queryKey: ["health"], queryFn: () => api.get<any>("/health"), retry: false });
export const useLatest = () =>
  useQuery({ queryKey: ["latest"], queryFn: () => api.get<LatestZoneTelemetry[]>("/api/v1/telemetry/latest") });
export const useDevices = () =>
  useQuery({ queryKey: ["devices"], queryFn: () => api.get<Device[]>("/api/v1/devices") });
export const useHistory = (sensorId: string | undefined, limit = 200) =>
  useQuery({
    queryKey: ["history", sensorId, limit],
    queryFn: () => api.get<Reading[]>(`/api/v1/telemetry/history?sensor_id=${sensorId}&limit=${limit}`),
    enabled: !!sensorId,
  });
export const useScenarios = () =>
  useQuery({ queryKey: ["scenarios"], queryFn: () => api.get<Scenario[]>("/api/v1/simulation/scenarios") });
export const useAlerts = () =>
  useQuery({ queryKey: ["alerts"], queryFn: () => api.get<Alert[]>("/api/v1/alerts") });
export const useAssessment = (zoneId?: string) =>
  useQuery({
    queryKey: ["assessment", zoneId],
    queryFn: () => api.get<Assessment>(`/api/v1/intelligence/assessment${zoneId ? `?zone_id=${zoneId}` : ""}`),
    refetchInterval: 30000,
  });
export const useFarms = () => useQuery({ queryKey: ["farms"], queryFn: () => api.get<Farm[]>("/api/v1/farms") });
export const useFields = (farmId?: string) =>
  useQuery({
    queryKey: ["fields", farmId],
    queryFn: () => api.get<Field[]>(`/api/v1/fields${farmId ? `?farm_id=${farmId}` : ""}`),
  });
export const useZones = (fieldId?: string) =>
  useQuery({
    queryKey: ["zones", fieldId],
    queryFn: () => api.get<Zone[]>(`/api/v1/zones${fieldId ? `?field_id=${fieldId}` : ""}`),
  });

export const useActivateScenario = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.post<Scenario[]>("/api/v1/simulation/scenarios/activate", { name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenarios"] }),
  });
};

export const useAckAlert = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<Alert>(`/api/v1/alerts/${id}/ack`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
};

// ---------- acoustic ----------
const still = { refetchInterval: false as const };
export const useEngines = () =>
  useQuery({ queryKey: ["engines"], queryFn: () => api.get<Engines>("/api/v1/audio/engines"), ...still, staleTime: 60000 });
export const useRecordings = () =>
  useQuery({ queryKey: ["recordings"], queryFn: () => api.get<Recording[]>("/api/v1/audio/recordings"), refetchInterval: 15000 });
export const useDetections = (id?: string) =>
  useQuery({ queryKey: ["detections", id], queryFn: () => api.get<Detection[]>(`/api/v1/audio/recordings/${id}/detections`), enabled: !!id, ...still });
export const useWaveform = (id?: string) =>
  useQuery({ queryKey: ["waveform", id], queryFn: () => api.get<Waveform>(`/api/v1/audio/recordings/${id}/waveform`), enabled: !!id, ...still, staleTime: Infinity });
export const useSpectrum = (id?: string) =>
  useQuery({ queryKey: ["spectrum", id], queryFn: () => api.get<Spectrum>(`/api/v1/audio/recordings/${id}/spectrum`), enabled: !!id, ...still, staleTime: Infinity });
export const useLabels = (id?: string) =>
  useQuery({ queryKey: ["labels", id], queryFn: () => api.get<Label[]>(`/api/v1/audio/recordings/${id}/labels`), enabled: !!id, ...still });
export const useLabelSummary = () =>
  useQuery({ queryKey: ["label-summary"], queryFn: () => api.get<LabelSummary>("/api/v1/audio/labels/summary"), ...still });
export const useModels = () =>
  useQuery({ queryKey: ["models"], queryFn: () => api.get<MLModelInfo[]>("/api/v1/ml/models"), ...still });
export const useProfiles = () =>
  useQuery({ queryKey: ["profiles"], queryFn: () => api.get<{ name: string; description: string }[]>("/api/v1/audio/sample-profiles"), ...still, staleTime: Infinity });

export const useAnalyze = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<{ identification: Identification; detections: Detection[] }>(`/api/v1/audio/recordings/${id}/analyze`),
    onSuccess: (_d, id) => {
      qc.invalidateQueries({ queryKey: ["detections", id] });
      qc.invalidateQueries({ queryKey: ["recordings"] });
    },
  });
};

// ---------- agronomy ----------
export const useSiteAssessment = () =>
  useMutation({
    mutationFn: (body: { lat: number; lon: number; country_code?: string; farm_id?: string; ph?: number; texture?: string }) =>
      api.post<SiteAssessment>("/api/v1/agronomy/assess", body),
  });
