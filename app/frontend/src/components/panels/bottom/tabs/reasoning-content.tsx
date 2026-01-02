import { Copy } from 'lucide-react';
import { useState } from 'react';
import { isJsonString } from './output-tab-utils';

// Component to render reasoning content with JSON formatting and copy button
export function ReasoningContent({ content }: { content: any }) {
  const [copySuccess, setCopySuccess] = useState(false);
  
  if (!content) return null;
  
  const contentString = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
  const isJson = isJsonString(contentString);
  
  const copyToClipboard = () => {
    navigator.clipboard.writeText(contentString)
      .then(() => {
        setCopySuccess(true);
        setTimeout(() => setCopySuccess(false), 2000);
      })
      .catch(err => {
        console.error('Failed to copy text: ', err);
      });
  };
  
  return (
    <div className="group relative">
      <button 
        onClick={copyToClipboard}
        className="absolute top-1 right-1 z-10 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1 text-xs p-1 rounded hover:bg-accent bg-background text-muted-foreground border border-border"
        title="Copy to clipboard"
      >
        <Copy className="h-3 w-3" />
        <span className="text-xs">{copySuccess ? 'Copied!' : 'Copy'}</span>
      </button>
      
      {isJson ? (
        <div className="text-xs">
          <pre className="whitespace-pre-wrap bg-muted p-2 rounded text-xs leading-relaxed max-h-[150px] overflow-auto">
            {contentString}
          </pre>
        </div>
      ) : (
        <div className="text-sm">
          {contentString.split('\n').map((paragraph, idx) => (
            <p key={idx} className="mb-2 last:mb-0">{paragraph}</p>
          ))}
        </div>
      )}
    </div>
  );
} 