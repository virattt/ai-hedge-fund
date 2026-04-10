const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Website {
  id: number;
  url: string;
  name: string;
  scrape_status: string;
  scrape_interval_minutes?: number | null;
  is_active: boolean;
  max_depth: number;
  max_pages: number;
  include_external: boolean;
  last_scraped_at?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface ScrapeResult {
  id: number;
  website_id: number;
  scraped_at: string;
  content_length: number;
  content_preview: string;
  status: string;
  error_message?: string | null;
  page_url?: string | null;
  depth: number;
  scrape_run_id?: string | null;
  parent_result_id?: number | null;
}

export interface ScrapeResultDetail extends ScrapeResult {
  content: string;
}

export interface WebsiteCreateRequest {
  url: string;
  name: string;
  scrape_interval_minutes?: number | null;
  max_depth?: number;
  max_pages?: number;
  include_external?: boolean;
}

export interface WebsiteUpdateRequest {
  name?: string;
  scrape_interval_minutes?: number | null;
  is_active?: boolean;
  max_depth?: number;
  max_pages?: number;
  include_external?: boolean;
}

export interface ScrapeRun {
  scrape_run_id: string;
  website_id: number;
  scraped_at: string;
  total_pages: number;
  success_count: number;
  error_count: number;
}

class ScrapingService {
  private baseUrl = `${API_BASE_URL}/scraping`;

  async getWebsites(): Promise<Website[]> {
    const response = await fetch(`${this.baseUrl}/websites`);
    if (!response.ok) {
      throw new Error(`Failed to fetch websites: ${response.statusText}`);
    }
    return response.json();
  }

  async getWebsite(id: number): Promise<Website> {
    const response = await fetch(`${this.baseUrl}/websites/${id}`);
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Website not found');
      }
      throw new Error(`Failed to fetch website: ${response.statusText}`);
    }
    return response.json();
  }

  async createWebsite(request: WebsiteCreateRequest): Promise<Website> {
    const response = await fetch(`${this.baseUrl}/websites`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const detail = body?.detail;
      if (Array.isArray(detail)) {
        throw new Error(detail.map((e: { msg: string }) => e.msg).join('; '));
      }
      throw new Error(detail || `Failed to create website: ${response.statusText}`);
    }
    return response.json();
  }

  async updateWebsite(id: number, request: WebsiteUpdateRequest): Promise<Website> {
    const response = await fetch(`${this.baseUrl}/websites/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Website not found');
      }
      throw new Error(`Failed to update website: ${response.statusText}`);
    }
    return response.json();
  }

  async deleteWebsite(id: number): Promise<void> {
    const response = await fetch(`${this.baseUrl}/websites/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Website not found');
      }
      throw new Error(`Failed to delete website: ${response.statusText}`);
    }
  }

  async triggerScrape(id: number): Promise<{ message: string; website_id: number }> {
    const response = await fetch(`${this.baseUrl}/websites/${id}/scrape`, {
      method: 'POST',
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Website not found');
      }
      if (response.status === 409) {
        throw new Error('Scrape already in progress');
      }
      throw new Error(`Failed to trigger scrape: ${response.statusText}`);
    }
    return response.json();
  }

  async getResults(id: number, limit = 20): Promise<ScrapeResult[]> {
    const response = await fetch(`${this.baseUrl}/websites/${id}/results?limit=${limit}`);
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Website not found');
      }
      throw new Error(`Failed to fetch results: ${response.statusText}`);
    }
    return response.json();
  }

  async getResultDetail(resultId: number): Promise<ScrapeResultDetail> {
    const response = await fetch(`${this.baseUrl}/results/${resultId}`);
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Result not found');
      }
      throw new Error(`Failed to fetch result detail: ${response.statusText}`);
    }
    return response.json();
  }

  async getRuns(websiteId: number, limit = 20): Promise<ScrapeRun[]> {
    const response = await fetch(`${this.baseUrl}/websites/${websiteId}/runs?limit=${limit}`);
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Website not found');
      }
      throw new Error(`Failed to fetch runs: ${response.statusText}`);
    }
    return response.json();
  }

  async getRunResults(runId: string): Promise<ScrapeResult[]> {
    const response = await fetch(`${this.baseUrl}/runs/${runId}/results`);
    if (!response.ok) {
      throw new Error(`Failed to fetch run results: ${response.statusText}`);
    }
    return response.json();
  }
}

export const scrapingService = new ScrapingService();
