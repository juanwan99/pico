import { act, renderHook, waitFor } from '@testing-library/react';
import {
  deleteMyModelEndpoint,
  getMyModelEndpoint,
  putMyModelEndpoint,
  testMyModelEndpoint,
} from '~/data-provider/pico/api';
import useMyModelEndpoint from '../useMyModelEndpoint';

jest.mock('~/data-provider/pico/api', () => ({
  deleteMyModelEndpoint: jest.fn(),
  getMyModelEndpoint: jest.fn(),
  putMyModelEndpoint: jest.fn(),
  testMyModelEndpoint: jest.fn(),
}));

const mockedGet = jest.mocked(getMyModelEndpoint);
const mockedPut = jest.mocked(putMyModelEndpoint);
const mockedDelete = jest.mocked(deleteMyModelEndpoint);
const mockedTest = jest.mocked(testMyModelEndpoint);

const EMPTY = {
  configured: false,
  enabled: false,
  base_url: '',
  model: '',
  masked_key: '',
  updated_at: null,
};

describe('useMyModelEndpoint (pico#1331「我的接口」)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedGet.mockResolvedValue(EMPTY);
  });

  it('loads the saved endpoint on mount', async () => {
    mockedGet.mockResolvedValue({
      configured: true,
      enabled: true,
      base_url: 'https://api.example.com/v1',
      model: 'gpt-4o-mini',
      masked_key: 'sk-…abcd',
      updated_at: '2026-10-17T00:00:00Z',
    });
    const { result } = renderHook(() => useMyModelEndpoint());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data.configured).toBe(true);
    expect(result.current.data.masked_key).toBe('sk-…abcd');
  });

  it('save() PUTs the form and stores the masked reply, never the raw key', async () => {
    mockedPut.mockResolvedValue({
      configured: true,
      enabled: true,
      base_url: 'https://api.example.com/v1',
      model: 'gpt-4o-mini',
      masked_key: 'sk-…wxyz',
      updated_at: '2026-10-17T00:01:00Z',
    });
    const { result } = renderHook(() => useMyModelEndpoint());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let ok = false;
    await act(async () => {
      ok = await result.current.save({
        base_url: 'https://api.example.com/v1',
        model: 'gpt-4o-mini',
        api_key: 'sk-raw-secret-wxyz',
        enabled: true,
      });
    });

    expect(ok).toBe(true);
    expect(mockedPut).toHaveBeenCalledWith({
      base_url: 'https://api.example.com/v1',
      model: 'gpt-4o-mini',
      api_key: 'sk-raw-secret-wxyz',
      enabled: true,
    });
    expect(result.current.data.masked_key).toBe('sk-…wxyz');
    // The dialog never holds the full key after a save — only what the
    // server echoes back (sk-…last4).
    expect(JSON.stringify(result.current.data)).not.toContain('sk-raw-secret-wxyz');
  });

  it('save() surfaces a teacher-safe error and keeps the previous data', async () => {
    mockedPut.mockRejectedValue(new Error('服务器还没配好密钥保险箱，暂时不能保存，请告诉管理员'));
    const { result } = renderHook(() => useMyModelEndpoint());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let ok = true;
    await act(async () => {
      ok = await result.current.save({
        base_url: 'https://api.example.com/v1',
        model: 'gpt-4o-mini',
        api_key: 'sk-raw',
        enabled: true,
      });
    });

    expect(ok).toBe(false);
    expect(result.current.error).toBe('服务器还没配好密钥保险箱，暂时不能保存，请告诉管理员');
    expect(result.current.data.configured).toBe(false);
  });

  it('test() reports ok + model + latency on success', async () => {
    mockedTest.mockResolvedValue({ ok: true, model: 'gpt-4o-mini', latency_ms: 420 });
    const { result } = renderHook(() => useMyModelEndpoint());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.test({
        base_url: 'https://api.example.com/v1',
        model: 'gpt-4o-mini',
        api_key: 'sk-raw',
      });
    });

    expect(result.current.testing).toBe(false);
    expect(result.current.testResult).toEqual({
      ok: true,
      model: 'gpt-4o-mini',
      latency_ms: 420,
    });
  });

  it('test() reports a short reason on failure, never a raw vendor error', async () => {
    mockedTest.mockResolvedValue({ ok: false, reason: '密钥不对，请检查密钥是否填错或已过期' });
    const { result } = renderHook(() => useMyModelEndpoint());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.test({ api_key: 'sk-raw' });
    });

    expect(result.current.testResult).toEqual({
      ok: false,
      reason: '密钥不对，请检查密钥是否填错或已过期',
    });
  });

  it('remove() clears the row back to the unconfigured state', async () => {
    mockedGet.mockResolvedValue({
      configured: true,
      enabled: true,
      base_url: 'https://api.example.com/v1',
      model: 'gpt-4o-mini',
      masked_key: 'sk-…abcd',
      updated_at: '2026-10-17T00:00:00Z',
    });
    mockedDelete.mockResolvedValue({ ok: true });
    const { result } = renderHook(() => useMyModelEndpoint());
    await waitFor(() => expect(result.current.data.configured).toBe(true));

    let ok = false;
    await act(async () => {
      ok = await result.current.remove();
    });

    expect(ok).toBe(true);
    expect(result.current.data).toEqual(EMPTY);
  });
});
