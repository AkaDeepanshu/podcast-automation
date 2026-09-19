import axios from "axios";
import type { JobCreatePayload, JobCreated, JobDetail, JobSummary } from "./types";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000",
});

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

export function audioUrl(jobId: string): string {
  return `${api.defaults.baseURL}/api/jobs/${jobId}/audio`;
}

export function videoUrl(jobId: string): string {
  return `${api.defaults.baseURL}/api/jobs/${jobId}/video`;
}

export function wsLogsUrl(jobId: string): string {
  const base = (api.defaults.baseURL || "http://127.0.0.1:8000").replace(/^http/, "ws");
  return `${base}/ws/jobs/${jobId}/logs`;
}

export default api;
