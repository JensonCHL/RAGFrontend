// User ID Management Utility
// Generates and persists a unique user ID per browser for multi-user support

const USER_ID_KEY = "rag_user_id";

export function getUserId(): string {
  if (typeof window === "undefined") {
    return "";
  }

  // Check if user ID already exists in localStorage
  let userId = localStorage.getItem(USER_ID_KEY);

  if (!userId) {
    // Generate a new unique user ID
    userId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem(USER_ID_KEY, userId);
  }

  return userId;
}

export function clearUserId(): void {
  localStorage.removeItem(USER_ID_KEY);
}
