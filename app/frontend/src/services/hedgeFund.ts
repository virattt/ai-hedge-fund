import { HedgeFundRequest, AgentInfo, TradingDecision, PortfolioSnapshot } from '../types/hedgeFund';

const API_BASE_URL = 'http://localhost:8000';

export class HedgeFundService {
    static async getAgents(): Promise<AgentInfo[]> {
        const response = await fetch(`${API_BASE_URL}/hedge-fund/agents`);
        if (!response.ok) {
            throw new Error('Failed to fetch agents');
        }
        return response.json();
    }

    static async runHedgeFund(
        request: HedgeFundRequest,
        onProgress: (event: any) => void,
        onComplete: (data: any) => void,
        onError: (error: string) => void
    ): Promise<void> {
        const response = await fetch(`${API_BASE_URL}/hedge-fund/run`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            throw new Error('Failed to start hedge fund run');
        }

        const reader = response.body?.getReader();
        if (!reader) {
            throw new Error('Failed to get response reader');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.trim()) continue;

                const [eventLine, dataLine] = line.split('\n');
                const eventType = eventLine.replace('event: ', '');
                const data = JSON.parse(dataLine.replace('data: ', ''));

                switch (eventType) {
                    case 'startevent':
                        // Handle start event if needed
                        break;
                    case 'progressupdateevent':
                        onProgress(data);
                        break;
                    case 'completeevent':
                        onComplete(data.data);
                        break;
                    case 'errorevent':
                        onError(data.message);
                        break;
                }
            }
        }
    }
} 