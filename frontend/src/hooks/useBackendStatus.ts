/**
 * useBackendStatus — polls the backend health endpoint and reports
 * whether the server is reachable.
 *
 * Strategy:
 *  - Optimistic default (isOnline = true) so the main UI renders
 *    immediately on first load without a blocking spinner.
 *  - Checks on mount; auto-retries every 30 s while offline.
 *  - Re-checks immediately when the browser reports it is "online"
 *    again (e.g. after a laptop lid-open / network reconnect).
 */

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API_BASE_URL, IS_NGROK_TUNNEL } from '../api/client';

const HEALTH_URL = `${API_BASE_URL}/api/health`;
const HEALTH_TIMEOUT_MS = 5_000;
const OFFLINE_RETRY_INTERVAL_MS = 30_000;
const MAX_OFFLINE_RETRIES = 3;

interface BackendStatus {
  /** True when the last health check succeeded (optimistic default). */
  isOnline: boolean;
  /** True during an in-flight health check. */
  isChecking: boolean;
  /** Trigger an immediate re-check (e.g., when user clicks "Retry"). */
  retry: () => void;
}

export function useBackendStatus(): BackendStatus {
  const [isOnline, setIsOnline] = useState(true);   // optimistic
  const [isChecking, setIsChecking] = useState(false);
  const [offlineRetryCount, setOfflineRetryCount] = useState(0);

  const check = useCallback(async () => {
    setIsChecking(true);
    try {
      await axios.get(HEALTH_URL, {
        timeout: HEALTH_TIMEOUT_MS,
        headers: IS_NGROK_TUNNEL ? { 'ngrok-skip-browser-warning': 'true' } : {},
      });
      setIsOnline(true);
      setOfflineRetryCount(0);  // reset on successful reconnection
    } catch {
      setIsOnline(false);
      setOfflineRetryCount((c) => c + 1);
    } finally {
      setIsChecking(false);
    }
  }, []);

  // Check on mount.
  useEffect(() => {
    check();
  }, [check]);

  // Re-check the moment the browser detects connectivity.
  useEffect(() => {
    window.addEventListener('online', check);
    return () => window.removeEventListener('online', check);
  }, [check]);

  // Auto-retry while offline, up to MAX_OFFLINE_RETRIES times.
  useEffect(() => {
    if (isOnline || offlineRetryCount >= MAX_OFFLINE_RETRIES) return;
    const id = setInterval(check, OFFLINE_RETRY_INTERVAL_MS);
    return () => clearInterval(id);
  }, [isOnline, offlineRetryCount, check]);

  // When the user manually retries, reset the counter so they get
  // another full round of automatic retries if needed.
  const retry = useCallback(() => {
    setOfflineRetryCount(0);
    check();
  }, [check]);

  return { isOnline, isChecking, retry };
}
