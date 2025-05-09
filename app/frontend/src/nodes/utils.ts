export type NodeStatus = 'IDLE' | 'IN_PROGRESS' | 'COMPLETE' | 'ERROR';

/**
 * Returns the appropriate background color class based on node status
 */
export function getStatusColor(status: NodeStatus): string {
  switch (status) {
    case 'IN_PROGRESS':
      return 'bg-amber-500  dark:bg-amber-80';
    case 'COMPLETE':
      return 'bg-blue-500 dark:bg-blue-800';
    case 'ERROR':
      return 'bg-red-500 dark:bg-red-800';
    default:
      return 'bg-secondary';
  }
}
