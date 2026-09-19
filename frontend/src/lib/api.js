import axios from "axios";

/** Axios client for the FastAPI backend. Step 4. */
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
});

export default api;
