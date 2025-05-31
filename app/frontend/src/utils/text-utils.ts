/**
 * Splits text into smaller paragraphs for better readability.
 * @param text The text to format
 * @returns An array of formatted paragraphs
 */
export function formatTextIntoParagraphs(text: string): string[] {
  if (!text) return [];
  
  // First split by any existing paragraphs
  const paragraphs = text.split('\n').filter(p => p.trim().length > 0);
  
  const formattedParagraphs: string[] = [];
  
  // Process each paragraph
  paragraphs.forEach(paragraph => {
    // Split into sentences using period, question mark, or exclamation mark followed by space
    // Modified to avoid treating decimal points as sentence endings
    const sentences = paragraph.match(/[^.!?]+(?:\.\d+[^.!?]*|[.!?]+\s*)/g) || [paragraph];
    
    let currentChunk = '';
    let sentenceCount = 0;
    
    // Group every 2-3 sentences
    sentences.forEach(sentence => {
      currentChunk += sentence;
      sentenceCount++;
      
      // After 2-3 sentences, create a new paragraph
      // Only consider it a break point if it's not part of a decimal number
      if (sentenceCount >= 2 && (sentenceCount % 3 === 0 || (sentence.endsWith('. ') && !sentence.match(/\d\.\s*$/)))) {
        formattedParagraphs.push(currentChunk.trim());
        currentChunk = '';
        sentenceCount = 0;
      }
    });
    
    // Add any remaining text
    if (currentChunk.trim()) {
      formattedParagraphs.push(currentChunk.trim());
    }
  });
  
  return formattedParagraphs;
}

/**
 * Checks if a string is valid JSON format
 * @param text The text to check
 * @returns true if the text is valid JSON or valid JS object, false otherwise
 */
export function isJsonString(text: string): boolean {
  if (!text) return false;
  
  // Trim the text to remove any leading/trailing whitespace
  const trimmedText = text.trim();
  
  // Quick initial check - if it doesn't look like JSON at all, return early
  if (
    !(
      (trimmedText.startsWith('{') && trimmedText.endsWith('}')) || 
      (trimmedText.startsWith('[') && trimmedText.endsWith(']'))
    )
  ) {
    return false;
  }
  
  // More sophisticated check for Python json.dumps() output or valid JSON
  // Count the number of keys/properties in the string to validate it looks like JSON
  const bracketMatches = trimmedText.match(/[{}[\]]/g) || [];
  const colonMatches = trimmedText.match(/:/g) || [];
  
  // For objects, we should have colons separating keys and values
  // And balanced brackets (though this is a simple heuristic)
  if (trimmedText.startsWith('{') && (colonMatches.length === 0 || bracketMatches.length % 2 !== 0)) {
    return false;
  }
  
  try {
    // First try standard JSON parsing
    JSON.parse(trimmedText);
    return true;
  } catch (e) {
    // If standard JSON parsing fails, try to handle JavaScript-like objects with NaN/undefined/Infinity
    try {
      // Replace JavaScript-specific values with JSON-compatible ones for validation
      const normalizedText = trimmedText
        .replace(/\bNaN\b/g, 'null')
        .replace(/\bundefined\b/g, 'null')
        .replace(/\bInfinity\b/g, 'null')
        .replace(/\b-Infinity\b/g, 'null');
      
      JSON.parse(normalizedText);
      return true;
    } catch (e2) {
      return false;
    }
  }
}

/**
 * Formats content that could be either JSON or regular text
 * @param content The content to format
 * @returns An object containing the formatted content and whether it's JSON
 */
export function formatContent(content: string): { 
  isJson: boolean; 
  formattedContent: string | string[]; 
} {
  if (!content) {
    return { isJson: false, formattedContent: [] };
  }
  
  if (isJsonString(content)) {
    try {
      // First try standard JSON parsing
      const parsedJson = JSON.parse(content);
      const formattedJson = JSON.stringify(parsedJson, null, 2);
      return { isJson: true, formattedContent: formattedJson };
    } catch (e) {
      // If standard JSON parsing fails, try to handle JavaScript-like objects with NaN/undefined/Infinity
      try {
        // Track the positions of special values before replacement
        const specialValues: Array<{value: string, regex: RegExp}> = [
          {value: 'NaN', regex: /\bNaN\b/g},
          {value: 'undefined', regex: /\bundefined\b/g},
          {value: 'Infinity', regex: /\bInfinity\b/g},
          {value: '-Infinity', regex: /\b-Infinity\b/g}
        ];
        
        // Replace JavaScript-specific values with JSON-compatible ones for parsing
        let normalizedContent = content;
        specialValues.forEach(({regex}) => {
          normalizedContent = normalizedContent.replace(regex, 'null');
        });
        
        const parsedJson = JSON.parse(normalizedContent);
        let formattedJson = JSON.stringify(parsedJson, null, 2);
        
        // Now restore the special values by parsing the original content structure
        // This is a more precise approach than the previous heuristic
        const originalMatches: Array<{value: string, positions: number[]}> = [];
        
        specialValues.forEach(({value, regex}) => {
          const matches = [...content.matchAll(regex)];
          if (matches.length > 0) {
            originalMatches.push({
              value,
              positions: matches.map(m => m.index!).sort((a, b) => b - a) // reverse order for replacement
            });
          }
        });
        
        // Replace nulls back to original special values in reverse order to maintain positions
        originalMatches.forEach(({value, positions}) => {
          positions.forEach(() => {
            // Find the next occurrence of null in the formatted JSON and replace it
            const nullIndex = formattedJson.indexOf('null');
            if (nullIndex !== -1) {
              formattedJson = formattedJson.substring(0, nullIndex) + value + formattedJson.substring(nullIndex + 4);
            }
          });
        });
        
        return { isJson: true, formattedContent: formattedJson };
      } catch (e2) {
        // If both attempts fail, fall back to text formatting
        return { isJson: false, formattedContent: formatTextIntoParagraphs(content) };
      }
    }
  }
  
  // Format as regular text
  return { isJson: false, formattedContent: formatTextIntoParagraphs(content) };
}

/**
 * Creates a simple syntax-highlighted version of JSON
 * @param jsonString The JSON string to format
 * @returns HTML string with basic syntax highlighting classes
 */
export function createHighlightedJson(jsonString: string): string {
  if (!jsonString) return '';
  
  try {
    // Ensure the JSON is properly formatted
    const obj = JSON.parse(jsonString);
    const formattedJson = JSON.stringify(obj, null, 2);
    
    // Replace JSON elements with styled spans
    let highlightedJson = formattedJson
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, 
        (match) => {
          // Colors matching the screenshot
          if (/^"/.test(match)) {
            if (/:$/.test(match)) {
              return `<span class="text-primary">${match}</span>`;
            } else {
              // String values are orange
              return `<span style="color: #d18f52">${match}</span>`;
            }
          } else if (/true|false/.test(match)) {
            // Boolean values are purple
            return `<span style="color: #c586c0">${match}</span>`;
          } else if (/null/.test(match)) {
            // Null values are purple
            return `<span style="color: #c586c0">${match}</span>`;
          } else {
            // Numbers are light blue/teal
            return `<span class="text-blue-500">${match}</span>`;
          }
        }
      );
    
    // Style brackets and commas
    highlightedJson = highlightedJson
      // Brackets and braces - light gray
      .replace(/(\{|\}|\[|\])/g, '<span style="color: #d4d4d4">$1</span>')
      // Commas
      .replace(/,/g, '<span style="color: #d4d4d4">,</span>');
    
    return highlightedJson;
  } catch (e) {
    // If there's an error parsing/formatting, return the original string
    return jsonString
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
} 