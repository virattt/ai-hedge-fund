// app/next-frontend/components/agents/agent-card.tsx
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'; // Assuming you'll add Avatar from ShadCN
import { ArrowRight } from 'lucide-react';

export interface Agent {
  id: string;
  name: string;
  description: string;
  avatarUrl?: string; // Optional: for agent image
  philosophy?: string; // Optional: more detailed philosophy
}

interface AgentCardProps {
  agent: Agent;
}

export default function AgentCard({ agent }: AgentCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center space-x-4">
        <Avatar>
          {/* Placeholder for actual image if agent.avatarUrl is provided */}
          {agent.avatarUrl ? <AvatarImage src={agent.avatarUrl} alt={agent.name} /> : null}
          <AvatarFallback>{agent.name.substring(0, 2).toUpperCase()}</AvatarFallback>
        </Avatar>
        <div>
          <CardTitle>{agent.name}</CardTitle>
          <CardDescription>{agent.description}</CardDescription>
        </div>
      </CardHeader>
      {agent.philosophy && (
        <CardContent>
          <p className="text-sm text-muted-foreground">{agent.philosophy}</p>
        </CardContent>
      )}
      <CardFooter>
        <Button asChild variant="secondary" className="w-full">
          <Link href={`/agents/${agent.id}`}>
            Interact with {agent.name} <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}
