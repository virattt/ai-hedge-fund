const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';

export interface AlertItem {
  id: number;
  rule_type: string;
  ticker: string;
  title: string;
  message: string;
  payload: Record<string, unknown> | null;
  severity: string;
  sent_to_telegram: boolean;
  telegram_error: string | null;
  is_read: boolean;
  created_at: string;
}

export interface AlertListResponse {
  alerts: AlertItem[];
  unread_count: number;
  total: number;
}

export interface ScanResponse {
  candidates_evaluated: number;
  alerts_created: number;
  alerts: AlertItem[];
}

export interface AlertSettingsResponse {
  telegram_bot_token: string;
  telegram_chat_id: string;
  telegram_enabled: boolean;
  scan_interval_hours: number;
  squeeze_min_short_pct: number;
  squeeze_min_days_to_cover: number;
  squeeze_require_insider_buy: boolean;
  csuite_min_value: number;
}

export interface AlertSettingsRequest {
  telegram_bot_token?: string;
  telegram_chat_id?: string;
  telegram_enabled?: boolean;
  scan_interval_hours?: number;
  squeeze_min_short_pct?: number;
  squeeze_min_days_to_cover?: number;
  squeeze_require_insider_buy?: boolean;
  csuite_min_value?: number;
}

export interface TelegramTestResponse {
  success: boolean;
  error: string | null;
}

class AlertService {
  private baseUrl = `${API_BASE_URL}/alerts`;

  async list(limit = 50, offset = 0, unreadOnly = false): Promise<AlertListResponse> {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (unreadOnly) params.set('unread_only', 'true');
    const r = await fetch(`${this.baseUrl}/?${params.toString()}`);
    if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || `Failed to list alerts: ${r.statusText}`);
    return r.json();
  }

  async markRead(id: number): Promise<void> {
    const r = await fetch(`${this.baseUrl}/${id}/read`, { method: 'POST' });
    if (!r.ok) throw new Error(`Failed to mark read: ${r.statusText}`);
  }

  async markAllRead(): Promise<void> {
    const r = await fetch(`${this.baseUrl}/read-all`, { method: 'POST' });
    if (!r.ok) throw new Error(`Failed to mark all read: ${r.statusText}`);
  }

  async scanNow(): Promise<ScanResponse> {
    const r = await fetch(`${this.baseUrl}/scan`, { method: 'POST' });
    if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || `Scan failed: ${r.statusText}`);
    return r.json();
  }

  async getSettings(): Promise<AlertSettingsResponse> {
    const r = await fetch(`${this.baseUrl}/settings`);
    if (!r.ok) throw new Error(`Failed to load settings: ${r.statusText}`);
    return r.json();
  }

  async updateSettings(req: AlertSettingsRequest): Promise<AlertSettingsResponse> {
    const r = await fetch(`${this.baseUrl}/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!r.ok) throw new Error(`Failed to update settings: ${r.statusText}`);
    return r.json();
  }

  async testTelegram(): Promise<TelegramTestResponse> {
    const r = await fetch(`${this.baseUrl}/test-telegram`, { method: 'POST' });
    if (!r.ok) throw new Error(`Test failed: ${r.statusText}`);
    return r.json();
  }
}

export const alertService = new AlertService();
