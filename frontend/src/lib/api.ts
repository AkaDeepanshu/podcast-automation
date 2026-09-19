import axios from "axios";
import type {
  FocusArea,
  JobCreatePayload,
  JobCreated,
  JobDetail,
  JobSummary,
  RunNextResult,
  TopicItem,
} from "./types";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000",
});

export type DialogueLine = {
  speaker: string;
  text: string;
  emotion?: string;
  segment?: number;
};

export type RetryResult = {
  job_id: string;
  from_stage: string;
  task_id: string;
  status: string;
};

export async function listJobs(): Promise<JobSummary[]> {
  const { data } = await api.get<JobSummary[]>("/api/jobs");
  return data;
}

export async function getJob(jobId: string): Promise<JobDetail> {
  const { data } = await api.get<JobDetail>(`/api/jobs/${jobId}`);
  return data;
}

export async function createJob(payload: JobCreatePayload): Promise<JobCreated> {
  const { data } = await api.post<JobCreated>("/api/jobs", payload);
  return data;
}

export async function deleteJob(jobId: string): Promise<void> {
  await api.delete(`/api/jobs/${jobId}`);
}

export async function retryJob(
  jobId: string,
  fromStage: string,
): Promise<RetryResult> {
  const { data } = await api.post<RetryResult>(
    `/api/jobs/${jobId}/retry`,
    null,
    { params: { from_stage: fromStage } },
  );
  return data;
}

export async function getScript(jobId: string): Promise<DialogueLine[]> {
  const { data } = await api.get<DialogueLine[]>(`/api/jobs/${jobId}/script`);
  return data;
}

export type AppConfigResponse = {
  config: Record<string, unknown>;
  speakers: Record<
    string,
    {
      name: string;
      gender?: string;
      voice_id: string;
      persona?: string;
    }
  >;
};

export async function getAppConfig(): Promise<AppConfigResponse> {
  const { data } = await api.get<AppConfigResponse>("/api/config");
  return data;
}

export async function saveAppConfig(
  payload: AppConfigResponse,
): Promise<{ status: string }> {
  const { data } = await api.put<{ status: string }>("/api/config", payload);
  return data;
}

export async function uploadAsset(
  name: "speaker_a" | "speaker_b" | "logo",
  file: File,
): Promise<{ name: string; path: string; bytes: number }> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<{ name: string; path: string; bytes: number }>(
    `/api/assets/${name}`,
    form,
  );
  return data;
}

export function assetUrl(name: "speaker_a" | "speaker_b" | "logo"): string {
  return `${api.defaults.baseURL}/api/assets/${name}`;
}

export function audioUrl(jobId: string): string {
  return `${api.defaults.baseURL}/api/jobs/${jobId}/audio`;
}

export function videoUrl(jobId: string): string {
  return `${api.defaults.baseURL}/api/jobs/${jobId}/video`;
}

export function wsLogsUrl(jobId: string): string {
  const base = (api.defaults.baseURL || "http://127.0.0.1:8000").replace(
    /^http/,
    "ws",
  );
  return `${base}/ws/jobs/${jobId}/logs`;
}

export async function listTopics(status?: string): Promise<TopicItem[]> {
  const { data } = await api.get<TopicItem[]>("/api/topics", {
    params: status ? { status } : undefined,
  });
  return data;
}

export async function createTopic(payload: {
  title: string;
  focus_area_id?: number | null;
  priority?: number;
  status?: "draft" | "approved";
}): Promise<TopicItem> {
  const { data } = await api.post<TopicItem>("/api/topics", payload);
  return data;
}

export async function updateTopic(
  id: number,
  payload: Partial<{ title: string; priority: number; status: string; focus_area_id: number | null }>,
): Promise<TopicItem> {
  const { data } = await api.patch<TopicItem>(`/api/topics/${id}`, payload);
  return data;
}

export async function deleteTopic(id: number): Promise<void> {
  await api.delete(`/api/topics/${id}`);
}

export async function approveTopic(id: number): Promise<TopicItem> {
  const { data } = await api.post<TopicItem>(`/api/topics/${id}/approve`);
  return data;
}

export async function runNextTopic(): Promise<RunNextResult> {
  const { data } = await api.post<RunNextResult>("/api/queue/run-next");
  return data;
}

export async function listFocusAreas(): Promise<FocusArea[]> {
  const { data } = await api.get<FocusArea[]>("/api/focus-areas");
  return data;
}

export async function createFocusArea(name: string): Promise<FocusArea> {
  const { data } = await api.post<FocusArea>("/api/focus-areas", {
    name,
    enabled: true,
  });
  return data;
}

export async function deleteFocusArea(id: number): Promise<void> {
  await api.delete(`/api/focus-areas/${id}`);
}

export default api;
