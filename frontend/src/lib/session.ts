// Session boundary: auth is an httpOnly cookie the backend owns; the frontend's one
// duty is wiping the react-query cache so one account's data never renders for the next.
import { queryClient } from "./queryClient";
import { apiPost } from "./api";

// Frontend-only flag: resets on a full page reload so the user must sign in again.
let sessionStarted = false;

export function hasSessionStarted(): boolean {
  return sessionStarted;
}

// Call after every successful login/signup.
export function beginSession(): void {
  queryClient.clear();
  sessionStarted = true;
}

// Call from every sign-out control; the hard redirect resets all in-memory state.
export async function endSession(redirectTo: string = "/login"): Promise<void> {
  // A retry key must never survive an explicit sign-out on this tab.
  try {
    for (let i = sessionStorage.length - 1; i >= 0; i -= 1) {
      const key = sessionStorage.key(i);
      if (key?.startsWith("oro:load-intake-idempotency:")) sessionStorage.removeItem(key);
    }
  } catch {
    // Storage can be unavailable in restricted browser contexts.
  }
  try {
    await apiPost("/auth/logout");
  } finally {
    queryClient.clear();
    sessionStarted = false;
    window.location.assign(redirectTo);
  }
}
