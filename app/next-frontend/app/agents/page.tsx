// app/next-frontend/app/agents/page.tsx
import AgentCard, { Agent } from '@/components/agents/agent-card'; // Ensure Agent type is exported and imported

const mockAgents: Agent[] = [
  { id: 'warren-buffett', name: 'Warren Buffett', description: 'Value Investing Oracle', philosophy: 'Focuses on long-term value, moats, and understanding businesses deeply.' },
  { id: 'peter-lynch', name: 'Peter Lynch', description: 'Growth at a Reasonable Price', philosophy: 'Invest in what you know, look for GARP opportunities.' },
  { id: 'cathie-wood', name: 'Cathie Wood', description: 'Disruptive Innovation Investor', philosophy: 'Identifies and invests in breakthrough technologies and innovation platforms.' },
  { id: 'michael-burry', name: 'Michael Burry', description: 'Contrarian Value Investor', philosophy: 'Known for his deep research into unconventional and often overlooked opportunities.' },
  // Add more mock agents as needed
];

export default function AgentsPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight">Financial Agents</h1>
        <p className="text-muted-foreground mt-2">
          Select an agent to get specialized financial insights and advice based on their unique investment philosophy.
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {mockAgents.map((agent) => (
          <AgentCard key={agent.id} agent={agent} />
        ))}
      </div>
    </div>
  );
}
