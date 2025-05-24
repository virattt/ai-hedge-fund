/**
 * Formats an ISO timestamp to local browser time (HH:MM:SS.ms)
 * @param timestamp ISO timestamp string
 * @returns Formatted time string in local timezone
 */
export function formatTimeFromTimestamp(timestamp: string): string {
  // Parse ISO timestamp string into Date object
  const date = new Date(timestamp);
  
  // Get minutes, seconds separately
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const seconds = date.getSeconds().toString().padStart(2, '0');
  
  // Get milliseconds and format to 2 digits
  const ms = Math.floor((date.getMilliseconds() / 10));
  const twoDigitMs = ms.toString().padStart(2, '0');
  
  // Format time with milliseconds
  const hours12 = date.getHours() % 12 || 12;
  const ampm = date.getHours() >= 12 ? 'PM' : 'AM';
  const hours12Str = hours12.toString().padStart(2, '0');
  
  return `${hours12Str}:${minutes}:${seconds}.${twoDigitMs} ${ampm}`;
} 