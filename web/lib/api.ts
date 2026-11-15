export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

function detailMessage(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    const parts = detail.map((d) =>
      typeof d === "string" ? d : typeof d?.msg === "string" ? d.msg : null,
    );
    const text = parts.filter(Boolean).join(" ");
    return text || null;
  }
  return null;
}

async function parse<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T;
  let message = `Request failed (${res.status}).`;
  try {
    const body = await res.json();
    message = detailMessage(body?.detail) ?? message;
  } catch {
    if (res.status === 502 || res.status === 504 || res.status === 500) {
      message =
        "The server did not finish this request. Live NASA analysis can take about a minute — try again, or open the UK model / a demo field.";
    }
  }
  throw new ApiError(message, res.status);
}

export async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  return parse<T>(await fetch(path, { signal }));
}

export async function postJSON<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return parse<T>(
    await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    }),
  );
}

export const isAbort = (err: unknown) => err instanceof DOMException && err.name === "AbortError";
