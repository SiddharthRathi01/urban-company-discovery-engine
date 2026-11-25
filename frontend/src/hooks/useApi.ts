import { useEffect, useState } from "react";
import { ApiError, get, type Envelope, type Params } from "../api/client";

export interface ApiState<T> {
  data: T | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  meta: Record<string, any>;
  loading: boolean;
  error: ApiError | null;
}

/** Fetch a GET endpoint. Pass path=null to skip. Re-fetches when the path or params change. */
export function useApi<T>(path: string | null, params?: Params): ApiState<T> {
  const key = path ? path + JSON.stringify(params ?? {}) : "";
  const [state, setState] = useState<ApiState<T>>({ data: null, meta: {}, loading: !!path, error: null });
  useEffect(() => {
    if (!path) {
      setState({ data: null, meta: {}, loading: false, error: null });
      return;
    }
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    get<T>(path, params)
      .then((r: Envelope<T>) => alive && setState({ data: r.data, meta: r.meta, loading: false, error: null }))
      .catch((e: unknown) => alive && setState({ data: null, meta: {}, loading: false, error: e instanceof ApiError ? e : new ApiError(0, "error", String(e)) }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}
