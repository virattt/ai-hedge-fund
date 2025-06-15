// app/next-frontend/app/agents/[agentId]/page.tsx
"use client"; // Added "use client" because of React.useState and event handlers

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input'; // Assuming you'll add Input from ShadCN
import { Textarea } from '@/components/ui/textarea'; // Assuming you'll add Textarea from ShadCN
import { Paperclip, Send } from 'lucide-react';
import React from 'react'; // Added import for React

// Mock data - in a real app, this would come from an API or a shared data source
const mockAgentsData: { [key: string]: { name: string; description: string; philosophy: string; avatarUrl?: string } } = {
  'warren-buffett': { name: 'Warren Buffett', description: 'Value Investing Oracle', philosophy: 'Focuses on long-term value, moats, and understanding businesses deeply.', avatarUrl: '/avatars/buffett.png' },
  'peter-lynch': { name: 'Peter Lynch', description: 'Growth at a Reasonable Price', philosophy: 'Invest in what you know, look for GARP opportunities.', avatarUrl: '/avatars/lynch.png' },
  'cathie-wood': { name: 'Cathie Wood', description: 'Disruptive Innovation Investor', philosophy: 'Identifies and invests in breakthrough technologies and innovation platforms.', avatarUrl: '/avatars/wood.png' },
  'michael-burry': { name: 'Michael Burry', description: 'Contrarian Value Investor', philosophy: 'Known for his deep research into unconventional and often overlooked opportunities.' },
};

interface AgentInteractionPageProps {
  params: { agentId: string };
}

export default function AgentInteractionPage({ params }: AgentInteractionPageProps) {
  const agent = mockAgentsData[params.agentId];

  if (!agent) {
    return <div>Agent not found.</div>;
  }

  // Mock chat messages state - will be replaced with actual state management
  const [messages, setMessages] = React.useState([
    { id: 1, sender: 'agent', text: `Hello! I am ${agent.name}. How can I assist you today based on my philosophy: "${agent.philosophy}"?` },
  ]);
  const [inputText, setInputText] = React.useState('');

  const handleSendMessage = () => {
    if (inputText.trim() === '') return;
    // Add user message
    const newMessages = [...messages, { id: Date.now(), sender: 'user', text: inputText }];
    // Mock agent response
    newMessages.push({ id: Date.now() + 1, sender: 'agent', text: `Thinking about "${inputText}"...` });
    setMessages(newMessages);
    setInputText('');
    // In a real app, you would call an API here to get the agent's response
  };


  return (
    <div className="flex flex-col h-[calc(100vh-10rem)]"> {/* Adjust height as needed */}
      <div className="mb-6 flex items-center space-x-4">
        <Avatar className="h-16 w-16">
          {agent.avatarUrl && <AvatarImage src={agent.avatarUrl} alt={agent.name} />}
          <AvatarFallback className="text-2xl">{agent.name.substring(0, 2).toUpperCase()}</AvatarFallback>
        </Avatar>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Chat with {agent.name}</h1>
          <p className="text-muted-foreground">{agent.description}</p>
        </div>
      </div>

      <div className="flex-grow overflow-y-auto space-y-4 p-4 border rounded-md bg-muted/50">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${msg.sender === 'user' ? 'bg-primary text-primary-foreground' : 'bg-background border'}`}>
              {msg.text}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center space-x-2">
        <Textarea
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder={`Ask ${agent.name} a question...`}
          className="flex-grow resize-none"
          rows={1}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSendMessage();
            }
          }}
        />
        <Button variant="ghost" size="icon" disabled> {/* Placeholder for attachment */}
          <Paperclip className="h-5 w-5" />
          <span className="sr-only">Attach file</span>
        </Button>
        <Button onClick={handleSendMessage} disabled={!inputText.trim()}>
          Send <Send className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// Add generateStaticParams for Next.js to know which agentId pages to pre-render at build time
export async function generateStaticParams() {
  return Object.keys(mockAgentsData).map((agentId) => ({
    agentId,
  }));
}
