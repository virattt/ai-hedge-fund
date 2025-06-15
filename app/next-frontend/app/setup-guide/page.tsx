// app/next-frontend/app/setup-guide/page.tsx
"use client"; // May use client components for interactivity if added later (e.g. copy buttons for code)

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, ExternalLink, CheckCircle, FileText, Settings, HelpCircle } from 'lucide-react';

// Simple CodeBlock component for now, can be enhanced later
const CodeBlock = ({ children }: { children: React.ReactNode }) => (
  <pre className="bg-muted p-4 rounded-md overflow-x-auto text-sm my-4">{children}</pre>
);

export default function SetupGuidePage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Self-Hosting Setup Guide</h1>
        <p className="text-muted-foreground mt-2">
          Follow these steps to get the Financial Analysis Platform running on your own infrastructure.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><FileText className="mr-2 h-5 w-5" />Introduction</CardTitle>
          <CardDescription>Welcome to the setup guide for self-hosting the platform.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p>This guide will walk you through the necessary steps to configure and deploy the application. Self-hosting gives you full control over your data and the operational environment.</p>
          <Alert>
            <CheckCircle className="h-4 w-4" />
            <AlertTitle>Goal</AlertTitle>
            <AlertDescription>
              By the end of this guide, you will have a fully functional, self-hosted instance of the platform, including the backend services and the frontend UI.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><Settings className="mr-2 h-5 w-5" />Prerequisites</CardTitle>
          <CardDescription>Software and tools you need before starting.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ul className="list-disc list-inside space-y-2">
            <li><strong>Docker and Docker Compose:</strong> For containerizing and running the application. Visit <a href="https://www.docker.com/get-started" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Docker's website <ExternalLink className="inline h-4 w-4" /></a> for installation instructions.</li>
            <li><strong>Git:</strong> For cloning the repository.</li>
            <li><strong>Node.js and npm/pnpm:</strong> For managing frontend dependencies if you plan to modify the frontend. (pnpm is used in this project's frontend)</li>
            <li><strong>Python:</strong> For backend development or customization.</li>
            <li><strong>API Keys (Optional but Recommended):</strong> Some features (e.g., fetching real-time stock data, advanced LLM models) might require API keys from third-party providers. These will be configured via environment variables.</li>
          </ul>
          <Alert variant="destructive">
            <Terminal className="h-4 w-4" />
            <AlertTitle>Command Line Familiarity</AlertTitle>
            <AlertDescription>
              Basic knowledge of using the command line/terminal will be necessary for running commands.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Cloning the Repository</CardTitle>
        </CardHeader>
        <CardContent>
          <p>First, clone the repository to your local machine:</p>
          <CodeBlock>{`git clone https://github.com/your-username/your-repository-name.git # Replace with actual repo URL
cd your-repository-name`}</CodeBlock>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Backend Setup</CardTitle>
          <CardDescription>Configuring the Python backend services.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p>The backend is responsible for data processing, interacting with financial APIs, and serving data to the frontend.</p>
          <ol className="list-decimal list-inside space-y-2">
            <li><strong>Environment Variables:</strong>
              <p>Navigate to the \`app/backend\` directory (or root, depending on where \`.env.example\` is). Copy the \`.env.example\` file to \`.env\`:</p>
              <CodeBlock>cp .env.example .env</CodeBlock>
              <p>Edit the \`.env\` file and fill in any necessary API keys or configuration values. Refer to comments within the file for guidance.</p>
              <CodeBlock>{`# Example .env content from .env.example
SOME_API_KEY=your_api_key_here
DATABASE_URL=your_database_url_here # If applicable
# Other backend settings...`}</CodeBlock>
            </li>
            <li><strong>Dependencies:</strong> (Usually handled by Docker, but for local dev:)
              <p>If running locally without Docker, ensure Python dependencies are installed (e.g., using Poetry):</p>
              <CodeBlock>{`cd src # or wherever pyproject.toml for backend is
poetry install`}</CodeBlock>
            </li>
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Frontend Setup</CardTitle>
          <CardDescription>Configuring the Next.js frontend.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p>The frontend provides the user interface for interacting with the platform.</p>
           <ol className="list-decimal list-inside space-y-2">
            <li><strong>Environment Variables (Frontend):</strong>
              <p>Navigate to the \`app/next-frontend\` directory. If there's an \`.env.example\` specific to the frontend, copy it to \`.env.local\`:</p>
              <CodeBlock>{`cd app/next-frontend
cp .env.example .env.local # If it exists`}</CodeBlock>
              <p>Edit \`.env.local\` for any frontend-specific settings, like the backend API URL if it's not running on the default localhost port configured in Docker Compose.</p>
              <CodeBlock>{`# Example .env.local content
NEXT_PUBLIC_API_URL=http://localhost:8000/api # Adjust if your backend runs elsewhere`}</CodeBlock>
            </li>
            <li><strong>Dependencies:</strong> (Usually handled by Docker, but for local dev:)
              <p>If running locally without Docker, install frontend dependencies:</p>
              <CodeBlock>{`cd app/next-frontend
pnpm install`}</CodeBlock>
            </li>
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><Terminal className="mr-2 h-5 w-5" />Docker Deployment</CardTitle>
          <CardDescription>Running the application using Docker Compose for a streamlined setup.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p>Docker is the recommended way to run the application as it handles all dependencies and configurations for both backend and frontend.</p>
          <ol className="list-decimal list-inside space-y-2">
            <li><strong>Ensure Docker is running.</strong></li>
            <li><strong>Build and Run Containers:</strong>
              <p>From the root directory of the project (where \`docker-compose.yml\` is located):</p>
              <CodeBlock>docker-compose up --build</CodeBlock>
              <p>This command will build the images for the backend and frontend services and then start them. The \`--build\` flag ensures images are rebuilt if there are changes.</p>
            </li>
            <li><strong>Accessing the Application:</strong>
              <p>Once the containers are running, you should be able to access the frontend in your web browser (typically at <a href="http://localhost:3000" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">http://localhost:3000 <ExternalLink className="inline h-4 w-4" /></a>) and the backend API (typically at <a href="http://localhost:8000/api/health" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">http://localhost:8000/api/health <ExternalLink className="inline h-4 w-4" /></a> or similar, check \`docker-compose.yml\` for port mappings).</p>
            </li>
            <li><strong>Stopping the Application:</strong>
              <p>To stop the containers, press \`Ctrl+C\` in the terminal where \`docker-compose up\` is running, or run:</p>
              <CodeBlock>docker-compose down</CodeBlock>
            </li>
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><HelpCircle className="mr-2 h-5 w-5" />Troubleshooting</CardTitle>
          <CardDescription>Common issues and how to resolve them.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ul className="list-disc list-inside space-y-2">
            <li><strong>Port Conflicts:</strong> If another service is using ports 3000 or 8000 (or whatever is configured), Docker Compose will fail to start. Stop the conflicting service or change the ports in \`docker-compose.yml\`.</li>
            <li><strong>API Key Issues:</strong> If features are not working as expected, double-check your API keys in the \`.env\` files.</li>
            <li><strong>Docker Build Failures:</strong> Check the error messages during \`docker-compose up --build\`. It might be due to network issues, missing files, or syntax errors in Dockerfiles.</li>
            <li><strong>Frontend can't connect to Backend:</strong> Ensure \`NEXT_PUBLIC_API_URL\` in \`app/next-frontend/.env.local\` (if used) points to the correct backend address accessible from the frontend container or your host machine if running frontend locally. When using Docker Compose, services can usually reach each other by their service name (e.g., \`http://backend:8000\`).</li>
          </ul>
          <p>For further assistance, please check the project's README or open an issue on the GitHub repository.</p>
        </CardContent>
      </Card>
    </div>
  );
}
