/**
 * src/features/settings/useServerSettings.ts
 *
 * State and actions behind the server-address setting. No UI.
 * Wraps serverConfig.ts (storage + validation) and api.ts (connection test).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { testServerConnection } from "../../lib/api";
import {
  DEFAULT_SERVER_URL,
  clearServerUrl,
  getSavedServerUrl,
  normalizeServerUrl,
  saveServerUrl,
} from "../../lib/serverConfig";

export type ConnectionTestState =
  | { status: "idle" }
  | { status: "testing" }
  | { status: "ok"; url: string; version: string | null }
  | { status: "failed"; reason: string };

export interface UseServerSettingsReturn {
  /** True until the saved address has been read from the device. */
  loading: boolean;

  /** Text field value. Editing it clears the test result and any save error. */
  input: string;
  setInput: (text: string) => void;

  /** Fallback used when nothing is saved. */
  defaultUrl: string;
  savedUrl: string | null;
  /** The address API requests currently use. */
  effectiveUrl: string;

  /** Normalized form of `input`; null when empty or invalid. */
  normalizedInput: string | null;
  /** Why `input` is invalid; null when empty or valid. */
  validationError: string | null;
  /** `input` is valid and differs from the saved address. */
  isDirty: boolean;

  test: ConnectionTestState;
  /** Tests the normalized input. Does nothing when the input is not valid. */
  testConnection: () => Promise<void>;

  saving: boolean;
  saveError: string | null;
  /** Validates, persists, and applies the input. Resolves true on success. */
  save: () => Promise<boolean>;
  /** Removes the saved address (falls back to the default). Resolves true on success. */
  reset: () => Promise<boolean>;
}

export function useServerSettings(): UseServerSettingsReturn {
  const [loading, setLoading] = useState(true);
  const [input, setInputState] = useState("");
  const [savedUrl, setSavedUrl] = useState<string | null>(null);
  const [test, setTest] = useState<ConnectionTestState>({ status: "idle" });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const mounted = useRef(true);
  const touched = useRef(false); // user typed before the saved value finished loading
  const testSeq = useRef(0); // bumped to discard stale test results

  useEffect(() => {
    mounted.current = true;
    getSavedServerUrl().then((url) => {
      if (!mounted.current) return;
      setSavedUrl(url);
      if (!touched.current && url) setInputState(url);
      setLoading(false);
    });
    return () => {
      mounted.current = false;
    };
  }, []);

  const setInput = useCallback((text: string) => {
    touched.current = true;
    testSeq.current += 1;
    setInputState(text);
    setTest({ status: "idle" });
    setSaveError(null);
  }, []);

  const parsed = useMemo(() => (input.trim() ? normalizeServerUrl(input) : null), [input]);
  const normalizedInput = parsed && parsed.ok ? parsed.url : null;
  const validationError = parsed && !parsed.ok ? parsed.reason : null;

  const testConnection = useCallback(async () => {
    if (!normalizedInput) return;
    const seq = ++testSeq.current;
    setTest({ status: "testing" });
    const result = await testServerConnection(normalizedInput);
    if (!mounted.current || seq !== testSeq.current) return;
    setTest(
      result.ok
        ? { status: "ok", url: result.url, version: result.version }
        : { status: "failed", reason: result.reason }
    );
  }, [normalizedInput]);

  const save = useCallback(async (): Promise<boolean> => {
    setSaving(true);
    setSaveError(null);
    const result = await saveServerUrl(input);
    if (!mounted.current) return result.ok;
    setSaving(false);
    if (!result.ok) {
      setSaveError(result.reason);
      return false;
    }
    setSavedUrl(result.url);
    setInputState(result.url);
    return true;
  }, [input]);

  const reset = useCallback(async (): Promise<boolean> => {
    setSaving(true);
    setSaveError(null);
    const ok = await clearServerUrl();
    if (!mounted.current) return ok;
    setSaving(false);
    if (!ok) {
      setSaveError("Could not reset the address on this device. Please try again.");
      return false;
    }
    testSeq.current += 1;
    setSavedUrl(null);
    setInputState("");
    setTest({ status: "idle" });
    return true;
  }, []);

  return {
    loading,
    input,
    setInput,
    defaultUrl: DEFAULT_SERVER_URL,
    savedUrl,
    effectiveUrl: savedUrl ?? DEFAULT_SERVER_URL,
    normalizedInput,
    validationError,
    isDirty: normalizedInput !== null && normalizedInput !== savedUrl,
    test,
    testConnection,
    saving,
    saveError,
    save,
    reset,
  };
}