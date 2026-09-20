import axios from "axios";
import type {
  AutomationSettings,
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

export async function getAutomation(): Promise<AutomationSettings> {
  const { data } = await api.get<AutomationSettings>("/api/automation");
  return data;
}

export async function saveAutomation(
  payload: Partial<AutomationSettings>,
): Promise<AutomationSettings> {
  const { data } = await api.put<AutomationSettings>("/api/automation", payload);
  return data;
}

export async function startAutomation(): Promise<AutomationSettings> {
  const { data } = await api.post<AutomationSettings>("/api/automation/start");
  return data;
}

export async function stopAutomation(): Promise<AutomationSettings> {
  const { data } = await api.post<AutomationSettings>("/api/automation/stop");
  return data;
}

export async function runAutomationNow(): Promise<RunNextResult> {
  const { data } = await api.post<RunNextResult>("/api/automation/run-now");
  return data;
}

export type NotificationStatus = {
  telegram_configured: boolean;
};

export async function getNotificationStatus(): Promise<NotificationStatus> {
  const { data } = await api.get<NotificationStatus>("/api/notifications/status");
  return data;
}

export async function testNotification(): Promise<{ status: string; event: string }> {
  const { data } = await api.post<{ status: string; event: string }>(
    "/api/notifications/test",
  );
  return data;
}

export type DiscoveryResult = {
  status: string;
  created: Array<{
    id?: number;
    title: string;
    focus_area?: string;
    status?: string;
  }>;
  inserted_status?: string | null;
  detail?: string | null;
  task_id?: string | null;
};

export async function runDiscovery(perArea = 3): Promise<DiscoveryResult> {
  const { data } = await api.post<DiscoveryResult>("/api/discovery/run", {
    per_area: perArea,
    async_run: false,
  });
  return data;
}

export default api;
