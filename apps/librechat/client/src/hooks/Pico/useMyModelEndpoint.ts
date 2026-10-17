import { useCallback, useEffect, useState } from 'react';
import {
  deleteMyModelEndpoint,
  getMyModelEndpoint,
  putMyModelEndpoint,
  testMyModelEndpoint,
  type PicoModelEndpoint,
  type PicoModelEndpointTestResult,
} from '~/data-provider/pico/api';

const EMPTY_ENDPOINT: PicoModelEndpoint = {
  configured: false,
  enabled: false,
  base_url: '',
  model: '',
  masked_key: '',
  updated_at: null,
};

export type MyModelEndpointSaveInput = {
  base_url: string;
  model: string;
  api_key: string;
  enabled: boolean;
};

export type MyModelEndpointState = {
  data: PicoModelEndpoint;
  loading: boolean;
  saving: boolean;
  testing: boolean;
  deleting: boolean;
  error: string | null;
  testResult: PicoModelEndpointTestResult | null;
  refresh: () => Promise<void>;
  save: (input: MyModelEndpointSaveInput) => Promise<boolean>;
  remove: () => Promise<boolean>;
  test: (input: Partial<MyModelEndpointSaveInput>) => Promise<void>;
};

/** pico#1331「我的接口」: load/save/test/delete the teacher's own endpoint.
 *
 * `picoFetch` already turns a failed response into a teacher-safe message
 * (see data-provider/pico/api.ts), so errors caught here are shown as-is.
 */
export default function useMyModelEndpoint(): MyModelEndpointState {
  const [data, setData] = useState<PicoModelEndpoint>(EMPTY_ENDPOINT);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<PicoModelEndpointTestResult | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getMyModelEndpoint();
      setData(res);
    } catch (err) {
      setError((err as Error)?.message || null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const save = useCallback(async (input: MyModelEndpointSaveInput) => {
    setSaving(true);
    setError(null);
    try {
      const res = await putMyModelEndpoint(input);
      setData(res);
      return true;
    } catch (err) {
      setError((err as Error)?.message || null);
      return false;
    } finally {
      setSaving(false);
    }
  }, []);

  const remove = useCallback(async () => {
    setDeleting(true);
    setError(null);
    try {
      await deleteMyModelEndpoint();
      setData(EMPTY_ENDPOINT);
      setTestResult(null);
      return true;
    } catch (err) {
      setError((err as Error)?.message || null);
      return false;
    } finally {
      setDeleting(false);
    }
  }, []);

  const test = useCallback(async (input: Partial<MyModelEndpointSaveInput>) => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testMyModelEndpoint(input);
      setTestResult(res);
    } catch (err) {
      setTestResult({ ok: false, reason: (err as Error)?.message || undefined });
    } finally {
      setTesting(false);
    }
  }, []);

  return { data, loading, saving, testing, deleting, error, testResult, refresh, save, remove, test };
}
